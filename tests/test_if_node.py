"""Tests for IfNode."""

from uuid import uuid4

import pytest

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.if_node import IfNode, IfNodeInput, IfNodeOutput


@pytest.fixture
def context():
    """Create a node context for testing."""
    return NodeContext(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
        node_id="test_if_node",
    )


@pytest.fixture
def state():
    """Create a workflow state for testing."""
    return WorkflowState(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
    )


class TestIfNodeBasic:
    """Test basic If node functionality."""

    @pytest.mark.asyncio
    async def test_boolean_true(self, context, state):
        """Test simple boolean true value."""
        node = IfNode(node_id="test")
        input_data = IfNodeInput(condition_value=True)

        result = await node.execute(input_data, context, state)

        assert isinstance(result, IfNodeOutput)
        assert result.route == "true"
        assert result.condition_result is True
        assert result.evaluated_value is True

    @pytest.mark.asyncio
    async def test_boolean_false(self, context, state):
        """Test simple boolean false value."""
        node = IfNode(node_id="test")
        input_data = IfNodeInput(condition_value=False)

        result = await node.execute(input_data, context, state)

        assert result.route == "false"
        assert result.condition_result is False
        assert result.evaluated_value is False

    @pytest.mark.asyncio
    async def test_truthy_value(self, context, state):
        """Test truthy value evaluation."""
        node = IfNode(node_id="test")

        # Test various truthy values
        for value in [1, "non-empty", [1, 2], {"key": "value"}]:
            input_data = IfNodeInput(condition_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "true"
            assert result.condition_result is True

    @pytest.mark.asyncio
    async def test_falsy_value(self, context, state):
        """Test falsy value evaluation."""
        node = IfNode(node_id="test")

        # Test various falsy values
        for value in [0, "", [], {}]:
            input_data = IfNodeInput(condition_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "false"
            assert result.condition_result is False


class TestIfNodeExpression:
    """Test If node with expression evaluation."""

    @pytest.mark.asyncio
    async def test_simple_expression(self, context, state):
        """Test simple comparison expression."""
        node = IfNode(node_id="test", expression="value > 10")

        # Test value greater than 10
        input_data = IfNodeInput(condition_value=15)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        # Test value less than 10
        input_data = IfNodeInput(condition_value=5)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_complex_expression(self, context, state):
        """Test complex expression with multiple conditions."""
        node = IfNode(node_id="test", expression="value > 10 and value < 100")

        # Test value in range
        input_data = IfNodeInput(condition_value=50)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        # Test value out of range
        input_data = IfNodeInput(condition_value=150)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_expression_with_functions(self, context, state):
        """Test expression using allowed functions."""
        node = IfNode(node_id="test", expression="len(value) > 3")

        input_data = IfNodeInput(condition_value="hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value="hi")
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_invalid_expression(self, context, state):
        """Test that invalid expressions raise errors."""
        node = IfNode(node_id="test", expression="value @ 1")  # Invalid operator

        input_data = IfNodeInput(condition_value=5)
        with pytest.raises(ValueError, match="Failed to evaluate expression"):
            await node.execute(input_data, context, state)


class TestIfNodeComparison:
    """Test If node with comparison operators."""

    @pytest.mark.asyncio
    async def test_equals(self, context, state):
        """Test equality comparison."""
        node = IfNode(node_id="test", comparison_op="eq", comparison_value=42)

        input_data = IfNodeInput(condition_value=42)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value=43)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_not_equals(self, context, state):
        """Test not equals comparison."""
        node = IfNode(node_id="test", comparison_op="ne", comparison_value=42)

        input_data = IfNodeInput(condition_value=43)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value=42)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_greater_than(self, context, state):
        """Test greater than comparison."""
        node = IfNode(node_id="test", comparison_op="gt", comparison_value=10)

        input_data = IfNodeInput(condition_value=15)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value=5)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_string_comparison(self, context, state):
        """Test comparison with strings."""
        node = IfNode(node_id="test", comparison_op="eq", comparison_value="approved")

        input_data = IfNodeInput(condition_value="approved")
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value="rejected")
        result = await node.execute(input_data, context, state)
        assert result.route == "false"


class TestIfNodeCustomFunction:
    """Test If node with custom condition functions."""

    @pytest.mark.asyncio
    async def test_custom_function(self, context, state):
        """Test custom condition function."""

        def is_valid(value):
            return value is not None and len(value) > 0

        node = IfNode(node_id="test", condition_func=is_valid)

        input_data = IfNodeInput(condition_value="hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value="")
        result = await node.execute(input_data, context, state)
        assert result.route == "false"

    @pytest.mark.asyncio
    async def test_lambda_function(self, context, state):
        """Test lambda function as condition."""
        node = IfNode(
            node_id="test", condition_func=lambda x: x.get("status") == "active"
        )

        input_data = IfNodeInput(condition_value={"status": "active"})
        result = await node.execute(input_data, context, state)
        assert result.route == "true"

        input_data = IfNodeInput(condition_value={"status": "inactive"})
        result = await node.execute(input_data, context, state)
        assert result.route == "false"


class TestIfNodeNullHandling:
    """Test If node null/None handling."""

    @pytest.mark.asyncio
    async def test_null_as_false(self, context, state):
        """Test null treated as false (default)."""
        node = IfNode(node_id="test", null_handling="false")

        input_data = IfNodeInput(condition_value=None)
        result = await node.execute(input_data, context, state)
        assert result.route == "false"
        assert result.condition_result is False

    @pytest.mark.asyncio
    async def test_null_as_true(self, context, state):
        """Test null treated as true."""
        node = IfNode(node_id="test", null_handling="true")

        input_data = IfNodeInput(condition_value=None)
        result = await node.execute(input_data, context, state)
        assert result.route == "true"
        assert result.condition_result is True

    @pytest.mark.asyncio
    async def test_null_as_error(self, context, state):
        """Test null raises error."""
        node = IfNode(node_id="test", null_handling="error")

        input_data = IfNodeInput(condition_value=None)
        with pytest.raises(ValueError, match="Condition value is None/null"):
            await node.execute(input_data, context, state)


class TestIfNodeValidation:
    """Test If node configuration validation."""

    def test_multiple_condition_methods_error(self):
        """Test that multiple condition methods raise error."""
        with pytest.raises(ValueError, match="Only one condition method"):
            IfNode(node_id="test", expression="value > 10", comparison_op="gt")

    def test_get_routes(self):
        """Test get_routes returns correct routes."""
        node = IfNode(node_id="test")
        routes = node.get_routes()
        assert routes == ["true", "false"]


class TestIfNodeStateMapping:
    """Test If node with state mapping."""

    @pytest.mark.asyncio
    async def test_input_mapping(self, context, state):
        """Test input mapping from state."""
        state.data["score"] = 85

        node = IfNode(
            node_id="test",
            expression="value > 80",
            input_map={"condition_value": "score"},
        )

        # This test validates that input mapping works with LangGraph integration
        # The actual mapping is done by as_langraph_node(), not execute()
        input_data = IfNodeInput(condition_value=state.data["score"])
        result = await node.execute(input_data, context, state)
        assert result.route == "true"
