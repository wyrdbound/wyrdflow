"""Tests for AggregateNode."""

from collections import Counter

import pytest

from wyrdflow.core.base import NodeExecutionError
from wyrdflow.core.config import NodeConfig
from wyrdflow.nodes.aggregate_node import AggregateNode, AggregateNodeInput


class TestAggregateNode:
    """Test suite for AggregateNode."""

    @pytest.mark.asyncio
    async def test_aggregate_concat(self):
        """Test concat aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="concat",
        )

        # Test data
        input_data = AggregateNodeInput(results=[[1, 2, 3], [4, 5, 6], [7, 8, 9]])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert result["items_aggregated"] == 3
        assert result["aggregation_strategy_used"] == "concat"

    @pytest.mark.asyncio
    async def test_aggregate_sum(self):
        """Test sum aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="sum",
        )

        # Test data
        input_data = AggregateNodeInput(results=[10, 20, 30, 40])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 100
        assert result["items_aggregated"] == 4

    @pytest.mark.asyncio
    async def test_aggregate_avg(self):
        """Test average aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="avg",
        )

        # Test data
        input_data = AggregateNodeInput(results=[10, 20, 30, 40])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 25.0
        assert result["items_aggregated"] == 4

    @pytest.mark.asyncio
    async def test_aggregate_min(self):
        """Test min aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="min",
        )

        # Test data
        input_data = AggregateNodeInput(results=[10, 5, 30, 2, 15])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 2
        assert result["items_aggregated"] == 5

    @pytest.mark.asyncio
    async def test_aggregate_max(self):
        """Test max aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="max",
        )

        # Test data
        input_data = AggregateNodeInput(results=[10, 5, 30, 2, 15])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 30
        assert result["items_aggregated"] == 5

    @pytest.mark.asyncio
    async def test_aggregate_count(self):
        """Test count aggregation strategy."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="count",
        )

        # Test data
        input_data = AggregateNodeInput(results=[1, 2, 3, 4, 5, 6, 7])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 7
        assert result["items_aggregated"] == 7

    @pytest.mark.asyncio
    async def test_aggregate_merge_last_write_wins(self):
        """Test merge aggregation with last_write_wins."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="merge",
            merge_strategy="last_write_wins",
        )

        # Test data
        input_data = AggregateNodeInput(
            results=[
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                {"a": 5, "d": 6},
            ]
        )

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"]["a"] == 5
        assert result["result"]["b"] == 3
        assert result["result"]["c"] == 4
        assert result["result"]["d"] == 6

    @pytest.mark.asyncio
    async def test_aggregate_merge_first_write_wins(self):
        """Test merge aggregation with first_write_wins."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="merge",
            merge_strategy="first_write_wins",
        )

        # Test data
        input_data = AggregateNodeInput(
            results=[
                {"a": 1, "b": 2},
                {"b": 3, "c": 4},
                {"a": 5, "d": 6},
            ]
        )

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"]["a"] == 1
        assert result["result"]["b"] == 2
        assert result["result"]["c"] == 4
        assert result["result"]["d"] == 6

    @pytest.mark.asyncio
    async def test_aggregate_custom(self):
        """Test custom aggregation function."""

        def find_mode(results):
            return Counter(results).most_common(1)[0][0]

        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="custom",
            custom_func=find_mode,
        )

        # Test data
        input_data = AggregateNodeInput(results=[1, 2, 2, 3, 3, 3, 4])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify - 3 appears most frequently
        assert result["result"] == 3

    @pytest.mark.asyncio
    async def test_filter_none_values(self):
        """Test filtering of None values."""
        # Create aggregate node with filter_none=True
        node = AggregateNode(
            node_id="agg_test",
            strategy="sum",
            filter_none=True,
        )

        # Test data with None values
        input_data = AggregateNodeInput(results=[10, None, 20, None, 30])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify - None values should be filtered out
        assert result["result"] == 60
        assert result["items_aggregated"] == 3  # Only non-None values

    @pytest.mark.asyncio
    async def test_no_filter_none_values(self):
        """Test not filtering None values."""
        # Create aggregate node with filter_none=False
        node = AggregateNode(
            node_id="agg_test",
            strategy="concat",
            filter_none=False,
        )

        # Test data with None values
        input_data = AggregateNodeInput(results=[[1, 2], None, [3, 4]])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify - None should be included
        assert result["items_aggregated"] == 3

    @pytest.mark.asyncio
    async def test_flatten_results(self):
        """Test flattening of nested results."""
        # Create aggregate node with flatten_results=True
        node = AggregateNode(
            node_id="agg_test",
            strategy="sum",
            flatten_results=True,
        )

        # Test data with nested lists
        input_data = AggregateNodeInput(results=[[10, 20], [30, 40], 50])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify - should flatten and sum all values
        assert result["result"] == 150
        assert result["items_aggregated"] == 5

    @pytest.mark.asyncio
    async def test_aggregate_empty_results(self):
        """Test aggregation with empty results."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="concat",
        )

        # Test data
        input_data = AggregateNodeInput(results=[])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == []
        assert result["items_aggregated"] == 0

    @pytest.mark.asyncio
    async def test_aggregate_sum_empty(self):
        """Test sum aggregation with empty results."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="sum",
        )

        # Test data
        input_data = AggregateNodeInput(results=[])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 0.0

    @pytest.mark.asyncio
    async def test_aggregate_avg_empty(self):
        """Test avg aggregation with empty results."""
        # Create aggregate node
        node = AggregateNode(
            node_id="agg_test",
            strategy="avg",
        )

        # Test data
        input_data = AggregateNodeInput(results=[])

        # Execute
        result = await node.run({"results": input_data.results})

        # Verify
        assert result["result"] == 0.0

    @pytest.mark.asyncio
    async def test_validation_errors(self):
        """Test validation errors."""
        # Test custom strategy without custom_func
        with pytest.raises(ValueError, match="custom_func is required"):
            AggregateNode(node_id="invalid", strategy="custom")

    @pytest.mark.asyncio
    async def test_aggregate_min_empty_error(self):
        """Test min aggregation with empty results raises error."""
        # Create aggregate node with no retries to speed up test
        node = AggregateNode(
            node_id="agg_test",
            strategy="min",
            config=NodeConfig(retry_attempts=1),
        )

        # Test data
        input_data = AggregateNodeInput(results=[])

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"results": input_data.results})

    @pytest.mark.asyncio
    async def test_aggregate_max_empty_error(self):
        """Test max aggregation with empty results raises error."""
        # Create aggregate node with no retries to speed up test
        node = AggregateNode(
            node_id="agg_test",
            strategy="max",
            config=NodeConfig(retry_attempts=1),
        )

        # Test data
        input_data = AggregateNodeInput(results=[])

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"results": input_data.results})

    @pytest.mark.asyncio
    async def test_aggregate_merge_non_dict_error(self):
        """Test merge aggregation with non-dict values raises error."""
        # Create aggregate node with no retries to speed up test
        node = AggregateNode(
            node_id="agg_test",
            strategy="merge",
            config=NodeConfig(retry_attempts=1),
        )

        # Test data with non-dict values
        input_data = AggregateNodeInput(results=[1, 2, 3])

        # Execute and expect error
        with pytest.raises(NodeExecutionError):
            await node.run({"results": input_data.results})
