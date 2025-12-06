"""Tests for MergeNode."""

import pytest

from wyrdflow.core.base import NodeExecutionError
from wyrdflow.core.config import NodeConfig
from wyrdflow.nodes.merge_node import MergeNode, MergeNodeInput


class TestMergeNode:
    """Test suite for MergeNode."""

    @pytest.mark.asyncio
    async def test_merge_last_write_wins(self):
        """Test merge with last_write_wins strategy."""
        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="last_write_wins",
        )

        # Test data
        input_data = MergeNodeInput(
            sources=[
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                {"a": 5, "d": 6},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - last values should win
        assert result["result"]["a"] == 5
        assert result["result"]["b"] == 3
        assert result["result"]["c"] == 4
        assert result["result"]["d"] == 6
        assert result["conflicts_resolved"] == 2  # a and b had conflicts
        assert result["merge_strategy_used"] == "last_write_wins"

    @pytest.mark.asyncio
    async def test_merge_first_write_wins(self):
        """Test merge with first_write_wins strategy."""
        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="first_write_wins",
        )

        # Test data
        input_data = MergeNodeInput(
            sources=[
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                {"a": 5, "d": 6},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - first values should win
        assert result["result"]["a"] == 1
        assert result["result"]["b"] == 2
        assert result["result"]["c"] == 4
        assert result["result"]["d"] == 6
        assert result["conflicts_resolved"] == 2  # a and b had conflicts

    @pytest.mark.asyncio
    async def test_merge_error_on_conflict(self):
        """Test merge with error strategy on conflict."""
        # Create merge node with no retries to speed up test
        node = MergeNode(
            node_id="merge_test",
            strategy="error",
            config=NodeConfig(retry_attempts=1),
        )

        # Test data with conflict
        input_data = MergeNodeInput(
            sources=[
                {"a": 1, "b": 2},
                {"a": 5, "c": 3},
            ]
        )

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"sources": input_data.sources})

    @pytest.mark.asyncio
    async def test_merge_custom_function(self):
        """Test merge with custom merge function."""

        def custom_merge(key, values):
            # Average numeric values
            if all(isinstance(v, (int, float)) for v in values):
                return sum(values) / len(values)
            return values[-1]

        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="custom",
            custom_merge_func=custom_merge,
        )

        # Test data
        input_data = MergeNodeInput(
            sources=[
                {"score": 10, "name": "Alice"},
                {"score": 20, "name": "Bob"},
                {"score": 30, "name": "Charlie"},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - score should be averaged, name should be last
        assert result["result"]["score"] == 20.0  # Average of 10, 20, 30
        assert result["result"]["name"] == "Charlie"  # Last value
        assert result["conflicts_resolved"] == 2

    @pytest.mark.asyncio
    async def test_deep_merge(self):
        """Test deep merge of nested objects."""
        # Create merge node with deep merge
        node = MergeNode(
            node_id="merge_test",
            strategy="last_write_wins",
            deep_merge=True,
        )

        # Test data with nested objects
        input_data = MergeNodeInput(
            sources=[
                {"user": {"name": "Alice", "age": 30}, "count": 1},
                {"user": {"age": 31, "city": "NYC"}, "count": 2},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - nested objects should be merged
        assert result["result"]["user"]["name"] == "Alice"
        assert result["result"]["user"]["age"] == 31
        assert result["result"]["user"]["city"] == "NYC"
        assert result["result"]["count"] == 2

    @pytest.mark.asyncio
    async def test_array_merge_concat(self):
        """Test array merge with concat strategy."""
        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="last_write_wins",
            deep_merge=True,
            array_merge_strategy="concat",
        )

        # Test data with arrays
        input_data = MergeNodeInput(
            sources=[
                {"items": [1, 2, 3]},
                {"items": [4, 5, 6]},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - arrays should be concatenated
        assert result["result"]["items"] == [1, 2, 3, 4, 5, 6]

    @pytest.mark.asyncio
    async def test_array_merge_replace(self):
        """Test array merge with replace strategy."""
        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="last_write_wins",
            deep_merge=True,
            array_merge_strategy="replace",
        )

        # Test data with arrays
        input_data = MergeNodeInput(
            sources=[
                {"items": [1, 2, 3]},
                {"items": [4, 5, 6]},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - last array should win
        assert result["result"]["items"] == [4, 5, 6]

    @pytest.mark.asyncio
    async def test_array_merge_unique(self):
        """Test array merge with unique strategy."""
        # Create merge node
        node = MergeNode(
            node_id="merge_test",
            strategy="last_write_wins",
            deep_merge=True,
            array_merge_strategy="unique",
        )

        # Test data with arrays having duplicates
        input_data = MergeNodeInput(
            sources=[
                {"items": [1, 2, 3]},
                {"items": [2, 3, 4]},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify - should have unique values
        assert len(result["result"]["items"]) == 4
        assert set(result["result"]["items"]) == {1, 2, 3, 4}

    @pytest.mark.asyncio
    async def test_merge_empty_sources(self):
        """Test merge with empty sources."""
        # Create merge node
        node = MergeNode(node_id="merge_test")

        # Test data
        input_data = MergeNodeInput(sources=[])

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify
        assert result["result"] == {}
        assert result["conflicts_resolved"] == 0

    @pytest.mark.asyncio
    async def test_merge_single_source(self):
        """Test merge with single source."""
        # Create merge node
        node = MergeNode(node_id="merge_test")

        # Test data
        input_data = MergeNodeInput(sources=[{"a": 1, "b": 2}])

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify
        assert result["result"] == {"a": 1, "b": 2}
        assert result["conflicts_resolved"] == 0

    @pytest.mark.asyncio
    async def test_merge_no_conflicts(self):
        """Test merge with no conflicts."""
        # Create merge node
        node = MergeNode(node_id="merge_test")

        # Test data with no overlapping keys
        input_data = MergeNodeInput(
            sources=[
                {"a": 1, "b": 2},
                {"c": 3, "d": 4},
                {"e": 5, "f": 6},
            ]
        )

        # Execute
        result = await node.run({"sources": input_data.sources})

        # Verify
        assert result["conflicts_resolved"] == 0
        assert len(result["result"]) == 6

    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test validation errors."""
        # Test custom strategy without custom_merge_func
        with pytest.raises(ValueError, match="custom_merge_func is required"):
            MergeNode(node_id="invalid", strategy="custom")
