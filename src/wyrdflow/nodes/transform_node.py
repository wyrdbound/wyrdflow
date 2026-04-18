"""Transform node for data manipulation and transformation."""

from functools import reduce
from typing import Any, Callable, Literal, Optional, Union

from pydantic import ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class TransformNodeInput(NodeInput):
    """Input for TransformNode."""

    model_config = ConfigDict(extra="allow")

    data: Any = Field(description="Data to transform")


class TransformNodeOutput(NodeOutput):
    """Output from TransformNode."""

    model_config = ConfigDict(extra="allow")

    result: Any = Field(description="Transformed data")
    transform_applied: str = Field(
        description="Name of the transformation that was applied"
    )


class TransformNode(BaseNode[TransformNodeInput, TransformNodeOutput]):
    """Node for transforming data with built-in or custom functions.

    Supports various built-in transformations:
    - filter: Filter items based on a condition
    - map: Apply a function to each item
    - reduce: Aggregate items into a single value
    - sort: Sort items by a key
    - flatten: Flatten nested structures
    - group_by: Group items by a key

    Examples:
        # Filter items
        transform = TransformNode(
            node_id="filter_high_scores",
            transform_type="filter",
            filter_func=lambda x: x["score"] > 80,
            input_map={"data": "scores"}
        )

        # Map transformation
        transform = TransformNode(
            node_id="extract_names",
            transform_type="map",
            map_func=lambda x: x["name"],
            input_map={"data": "users"}
        )

        # Sort by key
        transform = TransformNode(
            node_id="sort_by_date",
            transform_type="sort",
            sort_key="created_at",
            reverse=True,
            input_map={"data": "records"}
        )

        # Custom transformation
        def custom_transform(data):
            return [item.upper() for item in data if len(item) > 3]

        transform = TransformNode(
            node_id="custom",
            custom_func=custom_transform,
            input_map={"data": "text_list"}
        )
    """

    input_schema = TransformNodeInput
    output_schema = TransformNodeOutput

    def __init__(
        self,
        node_id: str,
        transform_type: Optional[
            Literal["filter", "map", "reduce", "sort", "flatten", "group_by"]
        ] = None,
        filter_func: Optional[Callable[[Any], bool]] = None,
        map_func: Optional[Callable[[Any], Any]] = None,
        reduce_func: Optional[Callable[[Any, Any], Any]] = None,
        reduce_initial: Optional[Any] = None,
        sort_key: Optional[Union[str, Callable[[Any], Any]]] = None,
        reverse: bool = False,
        group_by_key: Optional[Union[str, Callable[[Any], Any]]] = None,
        flatten_depth: int = 1,
        custom_func: Optional[Callable[[Any], Any]] = None,
        **kwargs: Any,
    ):
        """Initialize the Transform node.

        Args:
            node_id: Unique identifier for the node
            transform_type: Type of built-in transformation
            filter_func: Function for filter transformation
            map_func: Function for map transformation
            reduce_func: Function for reduce transformation
            reduce_initial: Initial value for reduce
            sort_key: Key or function to sort by
            reverse: Whether to reverse sort order
            group_by_key: Key or function to group by
            flatten_depth: Depth to flatten nested structures (default: 1)
            custom_func: Custom transformation function
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.transform_type = transform_type
        self.filter_func = filter_func
        self.map_func = map_func
        self.reduce_func = reduce_func
        self.reduce_initial = reduce_initial
        self.sort_key = sort_key
        self.reverse = reverse
        self.group_by_key = group_by_key
        self.flatten_depth = flatten_depth
        self.custom_func = custom_func

        # Validate configuration
        if custom_func is not None and transform_type is not None:
            raise ValueError(
                "Cannot specify both custom_func and transform_type. "
                "Use one or the other."
            )

        if custom_func is None and transform_type is None:
            raise ValueError("Must specify either custom_func or transform_type")

        # Validate transform-specific parameters
        if transform_type == "filter" and filter_func is None:
            raise ValueError("filter_func is required when transform_type='filter'")

        if transform_type == "map" and map_func is None:
            raise ValueError("map_func is required when transform_type='map'")

        if transform_type == "reduce" and reduce_func is None:
            raise ValueError("reduce_func is required when transform_type='reduce'")

        # Note: sort_key is optional - None means sort by value

        if transform_type == "group_by" and group_by_key is None:
            raise ValueError("group_by_key is required when transform_type='group_by'")

    async def execute(
        self,
        input_data: TransformNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> TransformNodeOutput:
        """Execute the transformation.

        Args:
            input_data: Input containing data to transform
            context: Execution context
            state: Current workflow state

        Returns:
            Output with transformed data
        """
        data = input_data.data

        # Apply transformation
        if self.custom_func:
            result = self.custom_func(data)
            transform_name = "custom"
        elif self.transform_type == "filter":
            result = self._apply_filter(data)
            transform_name = "filter"
        elif self.transform_type == "map":
            result = self._apply_map(data)
            transform_name = "map"
        elif self.transform_type == "reduce":
            result = self._apply_reduce(data)
            transform_name = "reduce"
        elif self.transform_type == "sort":
            result = self._apply_sort(data)
            transform_name = "sort"
        elif self.transform_type == "flatten":
            result = self._apply_flatten(data)
            transform_name = "flatten"
        elif self.transform_type == "group_by":
            result = self._apply_group_by(data)
            transform_name = "group_by"
        else:
            raise ValueError(f"Unknown transform type: {self.transform_type}")

        self._logger.info(
            f"Transform node {self.node_id} applied '{transform_name}' transformation"
        )

        return TransformNodeOutput(result=result, transform_applied=transform_name)

    def _apply_filter(self, data: Any) -> list[Any]:
        """Apply filter transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Filter transformation requires list or tuple input")

        if self.filter_func is None:
            raise ValueError("filter_func is required for filter transformation")

        return [item for item in data if self.filter_func(item)]

    def _apply_map(self, data: Any) -> list[Any]:
        """Apply map transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Map transformation requires list or tuple input")

        if self.map_func is None:
            raise ValueError("map_func is required for map transformation")

        return [self.map_func(item) for item in data]

    def _apply_reduce(self, data: Any) -> Any:
        """Apply reduce transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Reduce transformation requires list or tuple input")

        if self.reduce_func is None:
            raise ValueError("reduce_func is required for reduce transformation")

        if not data:
            return self.reduce_initial

        if self.reduce_initial is not None:
            return reduce(self.reduce_func, data, self.reduce_initial)
        else:
            return reduce(self.reduce_func, data)

    def _apply_sort(self, data: Any) -> list[Any]:
        """Apply sort transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Sort transformation requires list or tuple input")

        if self.sort_key is None:
            # Sort by value
            return sorted(data, reverse=self.reverse)

        if callable(self.sort_key):
            # Sort by function
            return sorted(data, key=self.sort_key, reverse=self.reverse)
        else:
            # Sort by key name (assume dict items)
            def get_sort_key(x: Any) -> Any:
                if isinstance(x, dict):
                    return x.get(self.sort_key)
                else:
                    return getattr(x, str(self.sort_key), None)

            return sorted(data, key=get_sort_key, reverse=self.reverse)

    def _apply_flatten(self, data: Any) -> list[Any]:
        """Apply flatten transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Flatten transformation requires list or tuple input")

        def flatten_recursive(items: Any, depth: int) -> list[Any]:
            if depth <= 0:
                return list(items) if isinstance(items, (list, tuple)) else [items]

            result = []
            for item in items:
                if isinstance(item, (list, tuple)):
                    result.extend(flatten_recursive(item, depth - 1))
                else:
                    result.append(item)
            return result

        return flatten_recursive(data, self.flatten_depth)

    def _apply_group_by(self, data: Any) -> dict[Any, list[Any]]:
        """Apply group_by transformation."""
        if not isinstance(data, (list, tuple)):
            raise ValueError("Group by transformation requires list or tuple input")

        if self.group_by_key is None:
            raise ValueError("group_by_key is required for group_by transformation")

        groups: dict[Any, list[Any]] = {}

        for item in data:
            if callable(self.group_by_key):
                key = self.group_by_key(item)
            elif isinstance(item, dict):
                key = item.get(self.group_by_key)
            else:
                key = getattr(item, str(self.group_by_key), None)

            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        return groups
