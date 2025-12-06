"""Aggregate node for collecting results from parallel branches."""

from typing import Any, Callable, Literal, Optional

from pydantic import ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class AggregateNodeInput(NodeInput):
    """Input for AggregateNode."""

    model_config = ConfigDict(extra="allow")

    results: list[Any] = Field(
        description="List of results to aggregate from parallel branches"
    )


class AggregateNodeOutput(NodeOutput):
    """Output from AggregateNode."""

    model_config = ConfigDict(extra="allow")

    result: Any = Field(description="Aggregated result")
    items_aggregated: int = Field(description="Number of items that were aggregated")
    aggregation_strategy_used: str = Field(description="Strategy used for aggregation")


class AggregateNode(BaseNode[AggregateNodeInput, AggregateNodeOutput]):
    """Node for aggregating results from parallel processing branches.

    Supports various aggregation strategies:
    - concat: Concatenate all results into a single list
    - sum: Sum numeric values
    - avg: Calculate average of numeric values
    - min: Find minimum value
    - max: Find maximum value
    - count: Count items
    - merge: Merge dictionaries (using merge strategies)
    - custom: Use a custom aggregation function

    Examples:
        # Concatenate results
        aggregate = AggregateNode(
            node_id="combine_results",
            strategy="concat",
            input_map={"results": "parallel_outputs"}
        )

        # Calculate average
        aggregate = AggregateNode(
            node_id="avg_scores",
            strategy="avg",
            input_map={"results": "score_results"}
        )

        # Custom aggregation
        def custom_agg(results):
            # Find most common value
            from collections import Counter
            return Counter(results).most_common(1)[0][0]

        aggregate = AggregateNode(
            node_id="find_consensus",
            strategy="custom",
            custom_func=custom_agg,
            input_map={"results": "votes"}
        )

        # Merge dictionaries
        aggregate = AggregateNode(
            node_id="merge_configs",
            strategy="merge",
            merge_strategy="last_write_wins",
            input_map={"results": "config_chunks"}
        )
    """

    input_schema = AggregateNodeInput
    output_schema = AggregateNodeOutput

    def __init__(
        self,
        node_id: str,
        strategy: Literal[
            "concat", "sum", "avg", "min", "max", "count", "merge", "custom"
        ] = "concat",
        custom_func: Optional[Callable[[list[Any]], Any]] = None,
        merge_strategy: Literal[
            "last_write_wins", "first_write_wins"
        ] = "last_write_wins",
        flatten_results: bool = False,
        filter_none: bool = True,
        **kwargs: Any,
    ):
        """Initialize the Aggregate node.

        Args:
            node_id: Unique identifier for the node
            strategy: Aggregation strategy to use
            custom_func: Custom aggregation function (for strategy='custom')
            merge_strategy: Strategy for merging dicts (for strategy='merge')
            flatten_results: Whether to flatten nested lists before aggregation
            filter_none: Whether to filter out None values before aggregation
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.strategy = strategy
        self.custom_func = custom_func
        self.merge_strategy = merge_strategy
        self.flatten_results = flatten_results
        self.filter_none = filter_none

        # Validate configuration
        if strategy == "custom" and custom_func is None:
            raise ValueError("custom_func is required when strategy='custom'")

    async def execute(
        self,
        input_data: AggregateNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> AggregateNodeOutput:
        """Execute the aggregation operation.

        Args:
            input_data: Input containing results to aggregate
            context: Execution context
            state: Current workflow state

        Returns:
            Output with aggregated result
        """
        results = input_data.results

        # Preprocess results
        processed_results = self._preprocess_results(results)

        # Apply aggregation strategy
        result: Any
        if self.strategy == "concat":
            result = self._aggregate_concat(processed_results)
        elif self.strategy == "sum":
            result = self._aggregate_sum(processed_results)
        elif self.strategy == "avg":
            result = self._aggregate_avg(processed_results)
        elif self.strategy == "min":
            result = self._aggregate_min(processed_results)
        elif self.strategy == "max":
            result = self._aggregate_max(processed_results)
        elif self.strategy == "count":
            result = self._aggregate_count(processed_results)
        elif self.strategy == "merge":
            result = self._aggregate_merge(processed_results)
        elif self.strategy == "custom":
            result = self._aggregate_custom(processed_results)
        else:
            raise ValueError(f"Unknown aggregation strategy: {self.strategy}")

        self._logger.info(
            f"Aggregate node {self.node_id} aggregated {len(processed_results)} "
            f"items using '{self.strategy}' strategy"
        )

        return AggregateNodeOutput(
            result=result,
            items_aggregated=len(processed_results),
            aggregation_strategy_used=self.strategy,
        )

    def _preprocess_results(self, results: list[Any]) -> list[Any]:
        """Preprocess results based on configuration."""
        processed = results

        # Filter None values if configured
        if self.filter_none:
            processed = [r for r in processed if r is not None]

        # Flatten if configured
        if self.flatten_results:
            processed = self._flatten_list(processed)

        return processed

    def _flatten_list(self, data: list[Any]) -> list[Any]:
        """Flatten a list of lists into a single list."""
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result

    def _aggregate_concat(self, results: list[Any]) -> list[Any]:
        """Concatenate all results into a single list."""
        if not results:
            return []

        # If all results are lists, concatenate them
        if all(isinstance(r, list) for r in results):
            concatenated = []
            for r in results:
                concatenated.extend(r)
            return concatenated

        # Otherwise, return results as-is
        return results

    def _aggregate_sum(self, results: list[Any]) -> float:
        """Sum all numeric results."""
        if not results:
            return 0.0

        try:
            return float(sum(results))
        except TypeError as e:
            raise ValueError(
                f"Sum aggregation requires numeric values, got: {type(results[0])}"
            ) from e

    def _aggregate_avg(self, results: list[Any]) -> float:
        """Calculate average of all numeric results."""
        if not results:
            return 0.0

        try:
            return float(sum(results)) / len(results)
        except TypeError as e:
            raise ValueError(
                f"Average aggregation requires numeric values, got: {type(results[0])}"
            ) from e

    def _aggregate_min(self, results: list[Any]) -> Any:
        """Find minimum value in results."""
        if not results:
            raise ValueError("Cannot find minimum of empty results")

        try:
            return min(results)
        except TypeError as e:
            raise ValueError(
                f"Min aggregation requires comparable values, got: {type(results[0])}"
            ) from e

    def _aggregate_max(self, results: list[Any]) -> Any:
        """Find maximum value in results."""
        if not results:
            raise ValueError("Cannot find maximum of empty results")

        try:
            return max(results)
        except TypeError as e:
            raise ValueError(
                f"Max aggregation requires comparable values, got: {type(results[0])}"
            ) from e

    def _aggregate_count(self, results: list[Any]) -> int:
        """Count number of results."""
        return len(results)

    def _aggregate_merge(self, results: list[Any]) -> dict[str, Any]:
        """Merge dictionary results."""
        if not results:
            return {}

        # Ensure all results are dictionaries
        if not all(isinstance(r, dict) for r in results):
            raise ValueError(
                "Merge aggregation requires all results to be dictionaries"
            )

        merged: dict[str, Any] = {}

        for result_dict in results:
            if self.merge_strategy == "last_write_wins":
                merged.update(result_dict)
            elif self.merge_strategy == "first_write_wins":
                # Only add keys that don't exist
                for key, value in result_dict.items():
                    if key not in merged:
                        merged[key] = value

        return merged

    def _aggregate_custom(self, results: list[Any]) -> Any:
        """Apply custom aggregation function."""
        if self.custom_func is None:
            raise ValueError("custom_func is required for custom aggregation")

        return self.custom_func(results)
