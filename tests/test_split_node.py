"""Tests for SplitNode."""

import pytest

from wyrdflow.core.base import NodeExecutionError
from wyrdflow.core.config import NodeConfig
from wyrdflow.nodes.split_node import SplitNode, SplitNodeInput


class TestSplitNode:
    """Test suite for SplitNode."""

    @pytest.mark.asyncio
    async def test_split_by_count(self):
        """Test split by count strategy."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_count",
            chunk_count=3,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6, 7, 8, 9])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 3
        assert len(result["chunks"]) == 3
        # Each chunk should have 3 items
        assert len(result["chunks"][0]) == 3
        assert len(result["chunks"][1]) == 3
        assert len(result["chunks"][2]) == 3
        assert result["split_strategy_used"] == "by_count"

    @pytest.mark.asyncio
    async def test_split_by_count_uneven(self):
        """Test split by count with uneven distribution."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_count",
            chunk_count=3,
        )

        # Test data with 10 items (not evenly divisible by 3)
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 3
        # First chunk gets the extra item
        assert len(result["chunks"][0]) == 4
        assert len(result["chunks"][1]) == 3
        assert len(result["chunks"][2]) == 3

    @pytest.mark.asyncio
    async def test_split_by_size(self):
        """Test split by size strategy."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_size",
            chunk_size=3,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 4  # 3 + 3 + 3 + 1
        assert len(result["chunks"][0]) == 3
        assert len(result["chunks"][1]) == 3
        assert len(result["chunks"][2]) == 3
        assert len(result["chunks"][3]) == 1  # Remainder

    @pytest.mark.asyncio
    async def test_split_by_condition(self):
        """Test split by condition strategy."""

        def categorize(item):
            return item["category"]

        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_condition",
            condition_func=categorize,
        )

        # Test data
        input_data = SplitNodeInput(
            data=[
                {"name": "apple", "category": "fruit"},
                {"name": "carrot", "category": "vegetable"},
                {"name": "banana", "category": "fruit"},
                {"name": "broccoli", "category": "vegetable"},
                {"name": "orange", "category": "fruit"},
            ]
        )

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 2  # fruit and vegetable
        # Find fruit and vegetable chunks
        fruit_chunk = None
        veg_chunk = None
        for chunk in result["chunks"]:
            if chunk[0]["category"] == "fruit":
                fruit_chunk = chunk
            else:
                veg_chunk = chunk

        assert fruit_chunk is not None
        assert veg_chunk is not None
        assert len(fruit_chunk) == 3
        assert len(veg_chunk) == 2

    @pytest.mark.asyncio
    async def test_split_by_condition_numeric(self):
        """Test split by condition with numeric categorization."""

        def even_odd(item):
            return "even" if item % 2 == 0 else "odd"

        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_condition",
            condition_func=even_odd,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 2  # even and odd
        # Each chunk should have 3 items
        assert all(len(chunk) == 3 for chunk in result["chunks"])

    @pytest.mark.asyncio
    async def test_split_round_robin(self):
        """Test split with round-robin strategy."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="round_robin",
            chunk_count=3,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6, 7, 8, 9])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 3
        # Each chunk should get items in round-robin fashion
        assert result["chunks"][0] == [1, 4, 7]
        assert result["chunks"][1] == [2, 5, 8]
        assert result["chunks"][2] == [3, 6, 9]

    @pytest.mark.asyncio
    async def test_split_round_robin_uneven(self):
        """Test round-robin with uneven distribution."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="round_robin",
            chunk_count=4,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["chunk_count"] == 4
        assert result["chunks"][0] == [1, 5]
        assert result["chunks"][1] == [2]
        assert result["chunks"][2] == [3]
        assert result["chunks"][3] == [4]

    @pytest.mark.asyncio
    async def test_split_empty_data(self):
        """Test split with empty data."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_count",
            chunk_count=3,
        )

        # Test data
        input_data = SplitNodeInput(data=[])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify - should create empty chunks
        assert result["chunk_count"] == 3
        assert all(len(chunk) == 0 for chunk in result["chunks"])

    @pytest.mark.asyncio
    async def test_split_preserves_order(self):
        """Test that split preserves item order."""
        # Create split node
        node = SplitNode(
            node_id="split_test",
            strategy="by_size",
            chunk_size=2,
            preserve_order=True,
        )

        # Test data
        input_data = SplitNodeInput(data=[1, 2, 3, 4, 5, 6])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify order is preserved
        assert result["chunks"][0] == [1, 2]
        assert result["chunks"][1] == [3, 4]
        assert result["chunks"][2] == [5, 6]

    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test validation errors."""
        # Test by_count without chunk_count
        with pytest.raises(ValueError, match="chunk_count is required"):
            SplitNode(node_id="invalid", strategy="by_count")

        # Test by_size without chunk_size
        with pytest.raises(ValueError, match="chunk_size is required"):
            SplitNode(node_id="invalid", strategy="by_size")

        # Test by_condition without condition_func
        with pytest.raises(ValueError, match="condition_func is required"):
            SplitNode(node_id="invalid", strategy="by_condition")

        # Test round_robin without chunk_count
        with pytest.raises(ValueError, match="chunk_count is required"):
            SplitNode(node_id="invalid", strategy="round_robin")

        # Test invalid chunk_count
        with pytest.raises(ValueError, match="must be positive"):
            SplitNode(
                node_id="invalid",
                strategy="by_count",
                chunk_count=0,
            )

        # Test invalid chunk_size
        with pytest.raises(ValueError, match="must be positive"):
            SplitNode(
                node_id="invalid",
                strategy="by_size",
                chunk_size=-1,
            )

    @pytest.mark.asyncio
    async def test_invalid_input_type(self):
        """Test error when input is not a list."""
        node = SplitNode(
            node_id="split_test",
            strategy="by_count",
            chunk_count=3,
            config=NodeConfig(retry_attempts=1),
        )

        # Test with non-list data
        input_data = SplitNodeInput(data="not a list")

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"data": input_data.data})
