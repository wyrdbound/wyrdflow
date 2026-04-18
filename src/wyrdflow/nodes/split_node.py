"""Split node for dividing data into parallel branches."""

from typing import Any, Callable, Literal, Optional

from pydantic import ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class SplitNodeInput(NodeInput):
    """Input for SplitNode."""

    model_config = ConfigDict(extra="allow")

    data: Any = Field(description="Data to split")


class SplitNodeOutput(NodeOutput):
    """Output from SplitNode."""

    model_config = ConfigDict(extra="allow")

    chunks: list[Any] = Field(description="List of data chunks after splitting")
    chunk_count: int = Field(description="Number of chunks created")
    split_strategy_used: str = Field(description="Strategy used for splitting")


class SplitNode(BaseNode[SplitNodeInput, SplitNodeOutput]):
    """Node for splitting data into parallel processing branches.

    Supports various split strategies:
    - by_count: Split into N equal chunks
    - by_size: Create chunks of size N
    - by_condition: Split based on a predicate function
    - round_robin: Distribute items across N chunks in round-robin fashion

    Examples:
        # Split into 3 equal chunks
        split = SplitNode(
            node_id="split_data",
            strategy="by_count",
            chunk_count=3,
            input_map={"data": "documents"}
        )

        # Split into chunks of size 10
        split = SplitNode(
            node_id="split_batches",
            strategy="by_size",
            chunk_size=10,
            input_map={"data": "items"}
        )

        # Split by condition (e.g., separate by category)
        def categorize(item):
            return item["category"]

        split = SplitNode(
            node_id="split_by_category",
            strategy="by_condition",
            condition_func=categorize,
            input_map={"data": "products"}
        )

        # Round-robin distribution
        split = SplitNode(
            node_id="split_round_robin",
            strategy="round_robin",
            chunk_count=4,
            input_map={"data": "tasks"}
        )
    """

    input_schema = SplitNodeInput
    output_schema = SplitNodeOutput

    def __init__(
        self,
        node_id: str,
        strategy: Literal[
            "by_count", "by_size", "by_condition", "round_robin"
        ] = "by_count",
        chunk_count: Optional[int] = None,
        chunk_size: Optional[int] = None,
        condition_func: Optional[Callable[[Any], Any]] = None,
        preserve_order: bool = True,
        **kwargs: Any,
    ):
        """Initialize the Split node.

        Args:
            node_id: Unique identifier for the node
            strategy: Strategy for splitting data
            chunk_count: Number of chunks (for by_count and round_robin)
            chunk_size: Size of each chunk (for by_size)
            condition_func: Function to determine how to split (for by_condition).
                Should return a key that determines which chunk the item goes into.
            preserve_order: Whether to preserve order of items within chunks
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.strategy = strategy
        self.chunk_count = chunk_count
        self.chunk_size = chunk_size
        self.condition_func = condition_func
        self.preserve_order = preserve_order

        # Validate configuration
        if strategy == "by_count" and chunk_count is None:
            raise ValueError("chunk_count is required when strategy='by_count'")

        if strategy == "by_size" and chunk_size is None:
            raise ValueError("chunk_size is required when strategy='by_size'")

        if strategy == "by_condition" and condition_func is None:
            raise ValueError("condition_func is required when strategy='by_condition'")

        if strategy == "round_robin" and chunk_count is None:
            raise ValueError("chunk_count is required when strategy='round_robin'")

        if chunk_count is not None and chunk_count <= 0:
            raise ValueError("chunk_count must be positive")

        if chunk_size is not None and chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

    async def execute(
        self,
        input_data: SplitNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> SplitNodeOutput:
        """Execute the split operation.

        Args:
            input_data: Input containing data to split
            context: Execution context
            state: Current workflow state

        Returns:
            Output with split chunks
        """
        data = input_data.data

        # Convert data to list if needed
        if not isinstance(data, (list, tuple)):
            raise ValueError("Split operation requires list or tuple input")

        data_list = list(data)

        # Apply split strategy
        if self.strategy == "by_count":
            chunks = self._split_by_count(data_list)
        elif self.strategy == "by_size":
            chunks = self._split_by_size(data_list)
        elif self.strategy == "by_condition":
            chunks = self._split_by_condition(data_list)
        elif self.strategy == "round_robin":
            chunks = self._split_round_robin(data_list)
        else:
            raise ValueError(f"Unknown split strategy: {self.strategy}")

        self._logger.info(
            f"Split node {self.node_id} split {len(data_list)} items into "
            f"{len(chunks)} chunks using '{self.strategy}' strategy"
        )

        return SplitNodeOutput(
            chunks=chunks,
            chunk_count=len(chunks),
            split_strategy_used=self.strategy,
        )

    def _split_by_count(self, data: list[Any]) -> list[list[Any]]:
        """Split data into N equal chunks."""
        if self.chunk_count is None or self.chunk_count <= 0:
            raise ValueError("chunk_count must be a positive integer")

        if not data:
            return [[] for _ in range(self.chunk_count)]

        chunk_count = min(self.chunk_count, len(data))
        chunk_size = len(data) // chunk_count
        remainder = len(data) % chunk_count

        chunks = []
        start = 0

        for i in range(chunk_count):
            # Distribute remainder across first chunks
            extra = 1 if i < remainder else 0
            end = start + chunk_size + extra
            chunks.append(data[start:end])
            start = end

        return chunks

    def _split_by_size(self, data: list[Any]) -> list[list[Any]]:
        """Split data into chunks of specified size."""
        if self.chunk_size is None or self.chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")

        if not data:
            return []

        chunks = []
        for i in range(0, len(data), self.chunk_size):
            chunks.append(data[i : i + self.chunk_size])

        return chunks

    def _split_by_condition(self, data: list[Any]) -> list[list[Any]]:
        """Split data based on a condition function."""
        if self.condition_func is None:
            raise ValueError("condition_func is required for by_condition strategy")

        if not data:
            return []

        # Group items by condition result
        groups: dict[Any, list[Any]] = {}
        group_order: list[Any] = []  # Track order of first appearance

        for item in data:
            key = self.condition_func(item)

            if key not in groups:
                groups[key] = []
                group_order.append(key)

            groups[key].append(item)

        # Convert groups to list of chunks
        # Maintain order based on first appearance if preserve_order is True
        if self.preserve_order:
            chunks = [groups[key] for key in group_order]
        else:
            chunks = list(groups.values())

        return chunks

    def _split_round_robin(self, data: list[Any]) -> list[list[Any]]:
        """Split data using round-robin distribution."""
        if self.chunk_count is None or self.chunk_count <= 0:
            raise ValueError("chunk_count must be a positive integer")

        if not data:
            return [[] for _ in range(self.chunk_count)]

        chunks: list[list[Any]] = [[] for _ in range(self.chunk_count)]

        for i, item in enumerate(data):
            chunk_idx = i % self.chunk_count
            chunks[chunk_idx].append(item)

        return chunks
