"""Tests for RouterNode."""

from uuid import uuid4

import pytest

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.router_node import (
    RouteCondition,
    RouterNode,
    RouterNodeInput,
)


@pytest.fixture
def context():
    """Create a node context for testing."""
    return NodeContext(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
        node_id="test_router_node",
    )


@pytest.fixture
def state():
    """Create a workflow state for testing."""
    return WorkflowState(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
    )


class TestRouterNodeBasic:
    """Test basic Router node functionality."""

    @pytest.mark.asyncio
    async def test_simple_routing(self, context, state):
        """Test simple routing with expressions."""
        routes = [
            RouteCondition(name="high", expression="value > 80"),
            RouteCondition(name="medium", expression="value > 50"),
            RouteCondition(name="low", expression="value <= 50"),
        ]
        node = RouterNode(node_id="test", routes=routes)

        # Test high route
        input_data = RouterNodeInput(routing_value=90)
        result = await node.execute(input_data, context, state)
        assert result.route == "high"
        assert "high" in result.matched_conditions

        # Test medium route
        input_data = RouterNodeInput(routing_value=60)
        result = await node.execute(input_data, context, state)
        assert result.route == "medium"

        # Test low route
        input_data = RouterNodeInput(routing_value=30)
        result = await node.execute(input_data, context, state)
        assert result.route == "low"

    @pytest.mark.asyncio
    async def test_default_route(self, context, state):
        """Test default route when no conditions match."""
        routes = [
            RouteCondition(name="positive", expression="value > 0"),
        ]
        node = RouterNode(node_id="test", routes=routes, default_route="negative")

        input_data = RouterNodeInput(routing_value=-5)
        result = await node.execute(input_data, context, state)
        assert result.route == "negative"
        assert len(result.matched_conditions) == 0

    @pytest.mark.asyncio
    async def test_list_order_evaluation(self, context, state):
        """Test that routes are evaluated in list order."""
        routes = [
            RouteCondition(name="first_matching", expression="value > 0"),
            RouteCondition(name="second_matching", expression="value > 0"),
        ]
        node = RouterNode(node_id="test", routes=routes)

        input_data = RouterNodeInput(routing_value=10)
        result = await node.execute(input_data, context, state)
        # Should match first_matching due to list order
        assert result.route == "first_matching"


class TestRouterNodeCustomFunctions:
    """Test Router node with custom functions."""

    @pytest.mark.asyncio
    async def test_custom_condition_func(self, context, state):
        """Test routing with custom condition functions."""

        def is_urgent(value):
            return value.get("priority") == "high"

        def is_important(value):
            return value.get("importance", 0) > 8

        routes = [
            RouteCondition(name="urgent", condition_func=is_urgent),
            RouteCondition(name="important", condition_func=is_important),
        ]
        node = RouterNode(node_id="test", routes=routes, default_route="normal")

        # Test urgent route
        input_data = RouterNodeInput(
            routing_value={"priority": "high", "importance": 3}
        )
        result = await node.execute(input_data, context, state)
        assert result.route == "urgent"

        # Test important route
        input_data = RouterNodeInput(routing_value={"priority": "low", "importance": 9})
        result = await node.execute(input_data, context, state)
        assert result.route == "important"

        # Test default route
        input_data = RouterNodeInput(routing_value={"priority": "low", "importance": 3})
        result = await node.execute(input_data, context, state)
        assert result.route == "normal"

    @pytest.mark.asyncio
    async def test_lambda_functions(self, context, state):
        """Test routing with lambda functions."""
        routes = [
            RouteCondition(name="even", condition_func=lambda x: x % 2 == 0),
            RouteCondition(name="odd", condition_func=lambda x: x % 2 == 1),
        ]
        node = RouterNode(node_id="test", routes=routes)

        input_data = RouterNodeInput(routing_value=4)
        result = await node.execute(input_data, context, state)
        assert result.route == "even"

        input_data = RouterNodeInput(routing_value=7)
        result = await node.execute(input_data, context, state)
        assert result.route == "odd"


class TestRouterNodeMatchMode:
    """Test Router node match modes."""

    @pytest.mark.asyncio
    async def test_first_match_mode(self, context, state):
        """Test first match mode (default)."""
        routes = [
            RouteCondition(name="route1", expression="value > 50"),
            RouteCondition(name="route2", expression="value > 30"),
        ]
        node = RouterNode(node_id="test", routes=routes, match_mode="first")

        # Value matches both, should return first by list order
        input_data = RouterNodeInput(routing_value=60)
        result = await node.execute(input_data, context, state)
        assert result.route == "route1"
        assert len(result.matched_conditions) == 1

    @pytest.mark.asyncio
    async def test_all_match_mode(self, context, state):
        """Test all match mode."""
        routes = [
            RouteCondition(name="route1", expression="value > 50"),
            RouteCondition(name="route2", expression="value > 30"),
            RouteCondition(name="route3", expression="value < 100"),
        ]
        node = RouterNode(node_id="test", routes=routes, match_mode="all")

        input_data = RouterNodeInput(routing_value=60)
        result = await node.execute(input_data, context, state)
        # First route is still returned
        assert result.route == "route1"
        # But all matches are recorded
        assert len(result.matched_conditions) == 3
        assert "route1" in result.matched_conditions
        assert "route2" in result.matched_conditions
        assert "route3" in result.matched_conditions


class TestRouterNodeNullHandling:
    """Test Router node null/None handling."""

    @pytest.mark.asyncio
    async def test_null_uses_default(self, context, state):
        """Test null value uses default route."""
        routes = [
            RouteCondition(name="route1", expression="value > 0"),
        ]
        node = RouterNode(
            node_id="test",
            routes=routes,
            default_route="null_route",
            null_handling="default",
        )

        input_data = RouterNodeInput(routing_value=None)
        result = await node.execute(input_data, context, state)
        assert result.route == "null_route"

    @pytest.mark.asyncio
    async def test_null_raises_error(self, context, state):
        """Test null value raises error."""
        routes = [
            RouteCondition(name="route1", expression="value > 0"),
        ]
        node = RouterNode(node_id="test", routes=routes, null_handling="error")

        input_data = RouterNodeInput(routing_value=None)
        with pytest.raises(ValueError, match="Routing value is None/null"):
            await node.execute(input_data, context, state)


class TestRouterNodeComplexExpressions:
    """Test Router node with complex expressions."""

    @pytest.mark.asyncio
    async def test_complex_boolean_logic(self, context, state):
        """Test complex boolean expressions."""
        routes = [
            RouteCondition(name="valid_range", expression="value > 10 and value < 100"),
            RouteCondition(name="too_low", expression="value <= 10"),
            RouteCondition(name="too_high", expression="value >= 100"),
        ]
        node = RouterNode(node_id="test", routes=routes)

        # Test valid range
        input_data = RouterNodeInput(routing_value=50)
        result = await node.execute(input_data, context, state)
        assert result.route == "valid_range"

        # Test too low
        input_data = RouterNodeInput(routing_value=5)
        result = await node.execute(input_data, context, state)
        assert result.route == "too_low"

        # Test too high
        input_data = RouterNodeInput(routing_value=150)
        result = await node.execute(input_data, context, state)
        assert result.route == "too_high"

    @pytest.mark.asyncio
    async def test_list_operations(self, context, state):
        """Test expressions with list operations."""
        routes = [
            RouteCondition(name="long_list", expression="len(value) > 5"),
            RouteCondition(name="has_items", expression="len(value) > 0"),
        ]
        node = RouterNode(node_id="test", routes=routes, default_route="empty")

        # Test long list
        input_data = RouterNodeInput(routing_value=[1, 2, 3, 4, 5, 6])
        result = await node.execute(input_data, context, state)
        assert result.route == "long_list"

        # Test short list
        input_data = RouterNodeInput(routing_value=[1, 2])
        result = await node.execute(input_data, context, state)
        assert result.route == "has_items"

        # Test empty list
        input_data = RouterNodeInput(routing_value=[])
        result = await node.execute(input_data, context, state)
        assert result.route == "empty"


class TestRouterNodeValidation:
    """Test Router node validation."""

    def test_duplicate_route_names(self):
        """Test that duplicate route names raise error."""
        routes = [
            RouteCondition(name="route1", expression="value > 0"),
            RouteCondition(name="route1", expression="value < 0"),
        ]
        with pytest.raises(ValueError, match="Route names must be unique"):
            RouterNode(node_id="test", routes=routes)

    def test_no_condition_method(self):
        """Test that routes without condition method raise error."""
        routes = [
            RouteCondition(name="route1"),
        ]
        with pytest.raises(ValueError, match="must have exactly one condition"):
            RouterNode(node_id="test", routes=routes)

    def test_multiple_condition_methods(self):
        """Test that routes with multiple condition methods raise error."""
        routes = [
            RouteCondition(
                name="route1",
                expression="value > 0",
                condition_func=lambda x: x > 0,
            ),
        ]
        with pytest.raises(ValueError, match="must have exactly one condition"):
            RouterNode(node_id="test", routes=routes)

    def test_get_routes(self):
        """Test get_routes returns all possible routes."""
        routes = [
            RouteCondition(name="route1", expression="value > 0"),
            RouteCondition(name="route2", expression="value < 0"),
        ]
        node = RouterNode(node_id="test", routes=routes, default_route="default")

        route_names = node.get_routes()
        assert "route1" in route_names
        assert "route2" in route_names
        assert "default" in route_names


class TestRouterNodeErrorHandling:
    """Test Router node error handling."""

    @pytest.mark.asyncio
    async def test_expression_error_skips_route(self, context, state):
        """Test that expression errors skip the route."""
        routes = [
            RouteCondition(name="error_route", expression="value.nonexistent_method()"),
            RouteCondition(name="valid_route", expression="value > 0"),
        ]
        node = RouterNode(node_id="test", routes=routes)

        input_data = RouterNodeInput(routing_value=10)
        result = await node.execute(input_data, context, state)
        # Should skip error_route and match valid_route
        assert result.route == "valid_route"

    @pytest.mark.asyncio
    async def test_all_errors_use_default(self, context, state):
        """Test that when all routes error, default is used."""
        routes = [
            RouteCondition(name="error_route1", expression="value.bad_method()"),
            RouteCondition(name="error_route2", expression="invalid syntax here"),
        ]
        node = RouterNode(node_id="test", routes=routes, default_route="fallback")

        input_data = RouterNodeInput(routing_value=10)
        result = await node.execute(input_data, context, state)
        assert result.route == "fallback"
