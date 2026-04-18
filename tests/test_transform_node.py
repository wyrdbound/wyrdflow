"""Tests for TransformNode."""

import pytest

from wyrdflow.core.base import NodeExecutionError
from wyrdflow.core.config import NodeConfig
from wyrdflow.nodes.transform_node import TransformNode, TransformNodeInput


class TestTransformNode:
    """Test suite for TransformNode."""

    @pytest.mark.asyncio
    async def test_filter_transformation(self):
        """Test filter transformation."""
        # Create filter node
        node = TransformNode(
            node_id="filter_test",
            transform_type="filter",
            filter_func=lambda x: x > 5,
        )

        # Test data
        input_data = TransformNodeInput(data=[1, 3, 5, 7, 9, 10])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == [7, 9, 10]
        assert result["transform_applied"] == "filter"

    @pytest.mark.asyncio
    async def test_map_transformation(self):
        """Test map transformation."""
        # Create map node
        node = TransformNode(
            node_id="map_test",
            transform_type="map",
            map_func=lambda x: x * 2,
        )

        # Test data
        input_data = TransformNodeInput(data=[1, 2, 3, 4, 5])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == [2, 4, 6, 8, 10]
        assert result["transform_applied"] == "map"

    @pytest.mark.asyncio
    async def test_reduce_transformation(self):
        """Test reduce transformation."""
        # Create reduce node
        node = TransformNode(
            node_id="reduce_test",
            transform_type="reduce",
            reduce_func=lambda acc, x: acc + x,
            reduce_initial=0,
        )

        # Test data
        input_data = TransformNodeInput(data=[1, 2, 3, 4, 5])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == 15
        assert result["transform_applied"] == "reduce"

    @pytest.mark.asyncio
    async def test_reduce_without_initial(self):
        """Test reduce transformation without initial value."""
        # Create reduce node
        node = TransformNode(
            node_id="reduce_test",
            transform_type="reduce",
            reduce_func=lambda acc, x: acc * x,
        )

        # Test data
        input_data = TransformNodeInput(data=[2, 3, 4])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == 24
        assert result["transform_applied"] == "reduce"

    @pytest.mark.asyncio
    async def test_sort_transformation_simple(self):
        """Test simple sort transformation."""
        # Create sort node
        node = TransformNode(
            node_id="sort_test",
            transform_type="sort",
            sort_key=None,
        )

        # Test data
        input_data = TransformNodeInput(data=[5, 2, 8, 1, 9])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == [1, 2, 5, 8, 9]
        assert result["transform_applied"] == "sort"

    @pytest.mark.asyncio
    async def test_sort_transformation_with_key(self):
        """Test sort transformation with key."""
        # Create sort node
        node = TransformNode(
            node_id="sort_test",
            transform_type="sort",
            sort_key="age",
            reverse=True,
        )

        # Test data
        input_data = TransformNodeInput(
            data=[
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25},
                {"name": "Charlie", "age": 35},
            ]
        )

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"][0]["name"] == "Charlie"
        assert result["result"][1]["name"] == "Alice"
        assert result["result"][2]["name"] == "Bob"
        assert result["transform_applied"] == "sort"

    @pytest.mark.asyncio
    async def test_sort_transformation_with_function(self):
        """Test sort transformation with function key."""
        # Create sort node
        node = TransformNode(
            node_id="sort_test",
            transform_type="sort",
            sort_key=lambda x: len(x),
        )

        # Test data
        input_data = TransformNodeInput(data=["apple", "hi", "banana", "x"])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == ["x", "hi", "apple", "banana"]
        assert result["transform_applied"] == "sort"

    @pytest.mark.asyncio
    async def test_flatten_transformation(self):
        """Test flatten transformation."""
        # Create flatten node
        node = TransformNode(
            node_id="flatten_test",
            transform_type="flatten",
            flatten_depth=1,
        )

        # Test data
        input_data = TransformNodeInput(data=[[1, 2], [3, 4], [5, 6]])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == [1, 2, 3, 4, 5, 6]
        assert result["transform_applied"] == "flatten"

    @pytest.mark.asyncio
    async def test_flatten_transformation_deep(self):
        """Test deep flatten transformation."""
        # Create flatten node
        node = TransformNode(
            node_id="flatten_test",
            transform_type="flatten",
            flatten_depth=2,
        )

        # Test data
        input_data = TransformNodeInput(data=[[[1, 2], [3]], [[4, 5]]])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == [1, 2, 3, 4, 5]
        assert result["transform_applied"] == "flatten"

    @pytest.mark.asyncio
    async def test_group_by_transformation(self):
        """Test group_by transformation."""
        # Create group_by node
        node = TransformNode(
            node_id="group_test",
            transform_type="group_by",
            group_by_key="category",
        )

        # Test data
        input_data = TransformNodeInput(
            data=[
                {"name": "apple", "category": "fruit"},
                {"name": "carrot", "category": "vegetable"},
                {"name": "banana", "category": "fruit"},
                {"name": "broccoli", "category": "vegetable"},
            ]
        )

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert "fruit" in result["result"]
        assert "vegetable" in result["result"]
        assert len(result["result"]["fruit"]) == 2
        assert len(result["result"]["vegetable"]) == 2
        assert result["transform_applied"] == "group_by"

    @pytest.mark.asyncio
    async def test_group_by_with_function(self):
        """Test group_by transformation with function."""
        # Create group_by node
        node = TransformNode(
            node_id="group_test",
            transform_type="group_by",
            group_by_key=lambda x: x % 2,
        )

        # Test data
        input_data = TransformNodeInput(data=[1, 2, 3, 4, 5, 6])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert 0 in result["result"]  # Even numbers
        assert 1 in result["result"]  # Odd numbers
        assert result["result"][1] == [1, 3, 5]
        assert result["result"][0] == [2, 4, 6]
        assert result["transform_applied"] == "group_by"

    @pytest.mark.asyncio
    async def test_custom_transformation(self):
        """Test custom transformation function."""

        def custom_transform(data):
            return [x.upper() for x in data if len(x) > 3]

        # Create custom transform node
        node = TransformNode(
            node_id="custom_test",
            custom_func=custom_transform,
        )

        # Test data
        input_data = TransformNodeInput(data=["hi", "hello", "hey", "world"])

        # Execute
        result = await node.run({"data": input_data.data})

        # Verify
        assert result["result"] == ["HELLO", "WORLD"]
        assert result["transform_applied"] == "custom"

    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test validation errors."""
        # Test missing both custom_func and transform_type
        with pytest.raises(ValueError, match="Must specify either"):
            TransformNode(node_id="invalid")

        # Test both custom_func and transform_type
        with pytest.raises(ValueError, match="Cannot specify both"):
            TransformNode(
                node_id="invalid",
                custom_func=lambda x: x,
                transform_type="filter",
            )

        # Test filter without filter_func
        with pytest.raises(ValueError, match="filter_func is required"):
            TransformNode(node_id="invalid", transform_type="filter")

        # Test map without map_func
        with pytest.raises(ValueError, match="map_func is required"):
            TransformNode(node_id="invalid", transform_type="map")

    @pytest.mark.asyncio
    async def test_invalid_input_type(self):
        """Test error when input is not a list."""
        node = TransformNode(
            node_id="filter_test",
            transform_type="filter",
            filter_func=lambda x: x > 5,
            config=NodeConfig(retry_attempts=1),
        )

        # Test with non-list data
        input_data = TransformNodeInput(data="not a list")

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"data": input_data.data})
