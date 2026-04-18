"""Merge node for combining multiple state branches."""

from typing import Any, Callable, Literal, Optional

from pydantic import ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class MergeNodeInput(NodeInput):
    """Input for MergeNode."""

    model_config = ConfigDict(extra="allow")

    sources: list[dict[str, Any]] = Field(description="List of data sources to merge")


class MergeNodeOutput(NodeOutput):
    """Output from MergeNode."""

    model_config = ConfigDict(extra="allow")

    result: dict[str, Any] = Field(description="Merged data")
    conflicts_resolved: int = Field(
        default=0, description="Number of conflicts that were resolved"
    )
    merge_strategy_used: str = Field(description="Strategy used for merging")


class MergeNode(BaseNode[MergeNodeInput, MergeNodeOutput]):
    """Node for merging multiple data sources with conflict resolution.

    Supports various conflict resolution strategies:
    - last_write_wins: Last value takes precedence
    - first_write_wins: First value takes precedence
    - error: Raise an error on conflicts
    - custom: Use a custom merge function

    Examples:
        # Last write wins (default)
        merge = MergeNode(
            node_id="merge_results",
            strategy="last_write_wins",
            input_map={"sources": "parallel_results"}
        )

        # First write wins
        merge = MergeNode(
            node_id="merge_configs",
            strategy="first_write_wins",
            input_map={"sources": "config_sources"}
        )

        # Custom merge function
        def custom_merge(key, values):
            # Average numeric values
            if all(isinstance(v, (int, float)) for v in values):
                return sum(values) / len(values)
            return values[-1]

        merge = MergeNode(
            node_id="merge_metrics",
            strategy="custom",
            custom_merge_func=custom_merge,
            input_map={"sources": "metric_sources"}
        )

        # Deep merge for nested objects
        merge = MergeNode(
            node_id="merge_nested",
            strategy="last_write_wins",
            deep_merge=True,
            input_map={"sources": "nested_data"}
        )
    """

    input_schema = MergeNodeInput
    output_schema = MergeNodeOutput

    def __init__(
        self,
        node_id: str,
        strategy: Literal[
            "last_write_wins", "first_write_wins", "error", "custom"
        ] = "last_write_wins",
        custom_merge_func: Optional[Callable[[str, list[Any]], Any]] = None,
        deep_merge: bool = False,
        array_merge_strategy: Literal["concat", "replace", "unique"] = "replace",
        **kwargs: Any,
    ):
        """Initialize the Merge node.

        Args:
            node_id: Unique identifier for the node
            strategy: Conflict resolution strategy
            custom_merge_func: Custom function for merging conflicts.
                Takes (key, values) and returns merged value
            deep_merge: Whether to perform deep merge for nested objects
            array_merge_strategy: How to merge arrays:
                - concat: Concatenate all arrays
                - replace: Replace with last array
                - unique: Concatenate and remove duplicates
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.strategy = strategy
        self.custom_merge_func = custom_merge_func
        self.deep_merge = deep_merge
        self.array_merge_strategy = array_merge_strategy

        # Validate configuration
        if strategy == "custom" and custom_merge_func is None:
            raise ValueError("custom_merge_func is required when strategy='custom'")

    async def execute(
        self,
        input_data: MergeNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> MergeNodeOutput:
        """Execute the merge operation.

        Args:
            input_data: Input containing sources to merge
            context: Execution context
            state: Current workflow state

        Returns:
            Output with merged data
        """
        sources = input_data.sources

        if not sources:
            return MergeNodeOutput(
                result={},
                conflicts_resolved=0,
                merge_strategy_used=self.strategy,
            )

        if len(sources) == 1:
            return MergeNodeOutput(
                result=sources[0],
                conflicts_resolved=0,
                merge_strategy_used=self.strategy,
            )

        # Perform merge
        conflicts = 0
        if self.deep_merge:
            result, conflicts = self._deep_merge(sources)
        else:
            result, conflicts = self._shallow_merge(sources)

        self._logger.info(
            f"Merge node {self.node_id} merged {len(sources)} sources "
            f"with {conflicts} conflicts using '{self.strategy}' strategy"
        )

        return MergeNodeOutput(
            result=result,
            conflicts_resolved=conflicts,
            merge_strategy_used=self.strategy,
        )

    def _shallow_merge(
        self, sources: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], int]:
        """Perform shallow merge of sources.

        Returns:
            Tuple of (merged_result, conflicts_count)
        """
        result: dict[str, Any] = {}
        conflicts = 0

        # Collect all keys and their values across sources
        key_values: dict[str, list[Any]] = {}
        for source in sources:
            for key, value in source.items():
                if key not in key_values:
                    key_values[key] = []
                key_values[key].append(value)

        # Resolve conflicts
        for key, values in key_values.items():
            if len(values) == 1:
                # No conflict
                result[key] = values[0]
            else:
                # Conflict - apply resolution strategy
                conflicts += 1
                result[key] = self._resolve_conflict(key, values)

        return result, conflicts

    def _deep_merge(self, sources: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Perform deep merge of sources.

        Returns:
            Tuple of (merged_result, conflicts_count)
        """
        conflicts = 0

        def merge_recursive(dicts: list[Any]) -> Any:
            nonlocal conflicts

            # If not all items are dicts, treat as conflict
            if not all(isinstance(d, dict) for d in dicts):
                conflicts += 1
                # Handle arrays
                if all(isinstance(d, list) for d in dicts):
                    return self._merge_arrays(dicts)
                # Otherwise resolve as normal conflict
                return self._resolve_conflict("", dicts)

            # Collect all keys
            all_keys = set()
            for d in dicts:
                all_keys.update(d.keys())

            result = {}
            for key in all_keys:
                # Get values for this key from all dicts that have it
                values = [d[key] for d in dicts if key in d]

                if len(values) == 1:
                    result[key] = values[0]
                elif all(isinstance(v, dict) for v in values):
                    # Recursively merge nested dicts
                    result[key] = merge_recursive(values)
                elif all(isinstance(v, list) for v in values):
                    # Merge arrays
                    result[key] = self._merge_arrays(values)
                else:
                    # Conflict at this level
                    conflicts += 1
                    result[key] = self._resolve_conflict(key, values)

            return result

        result = merge_recursive(sources)
        return result, conflicts

    def _resolve_conflict(self, key: str, values: list[Any]) -> Any:
        """Resolve a conflict using the configured strategy.

        Args:
            key: The key where conflict occurred
            values: List of conflicting values

        Returns:
            Resolved value
        """
        if self.strategy == "last_write_wins":
            return values[-1]
        elif self.strategy == "first_write_wins":
            return values[0]
        elif self.strategy == "custom":
            if self.custom_merge_func is None:
                raise ValueError("custom_merge_func is required for custom strategy")
            return self.custom_merge_func(key, values)
        elif self.strategy == "error":
            raise ValueError(
                f"Merge conflict at key '{key}': found {len(values)} different values"
            )
        else:
            raise ValueError(f"Unknown merge strategy: {self.strategy}")

    def _merge_arrays(self, arrays: list[list[Any]]) -> list[Any]:
        """Merge arrays according to array_merge_strategy."""
        if self.array_merge_strategy == "concat":
            result = []
            for arr in arrays:
                result.extend(arr)
            return result
        elif self.array_merge_strategy == "replace":
            return arrays[-1]
        elif self.array_merge_strategy == "unique":
            result = []
            seen = set()
            for arr in arrays:
                for item in arr:
                    # Use string representation for hashability
                    item_key = str(item)
                    if item_key not in seen:
                        seen.add(item_key)
                        result.append(item)
            return result
        else:
            raise ValueError(
                f"Unknown array merge strategy: {self.array_merge_strategy}"
            )
