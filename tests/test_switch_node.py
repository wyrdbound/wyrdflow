"""Tests for SwitchNode."""

from uuid import uuid4

import pytest

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.switch_node import (
    CaseCondition,
    SwitchNode,
    SwitchNodeInput,
)


@pytest.fixture
def context():
    """Create a node context for testing."""
    return NodeContext(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
        node_id="test_switch_node",
    )


@pytest.fixture
def state():
    """Create a workflow state for testing."""
    return WorkflowState(
        workflow_id=uuid4(),
        workflow_run_id=uuid4(),
    )


class TestSwitchNodeBasic:
    """Test basic Switch node functionality."""

    @pytest.mark.asyncio
    async def test_exact_value_match(self, context, state):
        """Test exact value matching."""
        cases = [
            CaseCondition(route="new", value="new"),
            CaseCondition(route="pending", value="pending"),
            CaseCondition(route="completed", value="completed"),
        ]
        node = SwitchNode(node_id="test", cases=cases)

        # Test each case
        for status in ["new", "pending", "completed"]:
            input_data = SwitchNodeInput(switch_value=status)
            result = await node.execute(input_data, context, state)
            assert result.route == status
            assert result.matched_case == status
            assert result.switch_value == status

    @pytest.mark.asyncio
    async def test_default_route(self, context, state):
        """Test default route when no cases match."""
        cases = [
            CaseCondition(route="new", value="new"),
            CaseCondition(route="pending", value="pending"),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="unknown")

        input_data = SwitchNodeInput(switch_value="archived")
        result = await node.execute(input_data, context, state)
        assert result.route == "unknown"
        assert result.matched_case is None

    @pytest.mark.asyncio
    async def test_numeric_values(self, context, state):
        """Test switching on numeric values."""
        cases = [
            CaseCondition(route="zero", value=0),
            CaseCondition(route="one", value=1),
            CaseCondition(route="ten", value=10),
        ]
        node = SwitchNode(node_id="test", cases=cases)

        for num, route in [(0, "zero"), (1, "one"), (10, "ten")]:
            input_data = SwitchNodeInput(switch_value=num)
            result = await node.execute(input_data, context, state)
            assert result.route == route


class TestSwitchNodeValueList:
    """Test Switch node with value lists."""

    @pytest.mark.asyncio
    async def test_value_list_match(self, context, state):
        """Test matching against a list of values."""
        cases = [
            CaseCondition(
                route="success", value_list=["completed", "done", "finished"]
            ),
            CaseCondition(route="error", value_list=["failed", "error", "rejected"]),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="other")

        # Test success matches
        for value in ["completed", "done", "finished"]:
            input_data = SwitchNodeInput(switch_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "success"

        # Test error matches
        for value in ["failed", "error", "rejected"]:
            input_data = SwitchNodeInput(switch_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "error"

        # Test no match
        input_data = SwitchNodeInput(switch_value="pending")
        result = await node.execute(input_data, context, state)
        assert result.route == "other"


class TestSwitchNodePattern:
    """Test Switch node with pattern matching."""

    @pytest.mark.asyncio
    async def test_simple_pattern(self, context, state):
        """Test simple regex pattern matching."""
        cases = [
            CaseCondition(route="company", pattern=r".*@company\.com$"),
            CaseCondition(route="gmail", pattern=r".*@gmail\.com$"),
            CaseCondition(route="yahoo", pattern=r".*@yahoo\.com$"),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="other")

        # Test company email
        input_data = SwitchNodeInput(switch_value="user@company.com")
        result = await node.execute(input_data, context, state)
        assert result.route == "company"

        # Test gmail
        input_data = SwitchNodeInput(switch_value="someone@gmail.com")
        result = await node.execute(input_data, context, state)
        assert result.route == "gmail"

        # Test other
        input_data = SwitchNodeInput(switch_value="user@outlook.com")
        result = await node.execute(input_data, context, state)
        assert result.route == "other"

    @pytest.mark.asyncio
    async def test_case_sensitive_pattern(self, context, state):
        """Test case-sensitive pattern matching."""
        cases = [
            CaseCondition(route="uppercase", pattern=r"^[A-Z]+$"),
            CaseCondition(route="lowercase", pattern=r"^[a-z]+$"),
        ]
        node = SwitchNode(
            node_id="test", cases=cases, case_sensitive=True, default_route="mixed"
        )

        input_data = SwitchNodeInput(switch_value="HELLO")
        result = await node.execute(input_data, context, state)
        assert result.route == "uppercase"

        input_data = SwitchNodeInput(switch_value="hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "lowercase"

        input_data = SwitchNodeInput(switch_value="Hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "mixed"

    @pytest.mark.asyncio
    async def test_case_insensitive_pattern(self, context, state):
        """Test case-insensitive pattern matching."""
        cases = [
            CaseCondition(route="match", pattern=r"^hello"),
        ]
        node = SwitchNode(
            node_id="test", cases=cases, case_sensitive=False, default_route="no_match"
        )

        # All should match due to case-insensitive flag
        for value in ["hello", "HELLO", "Hello", "HeLLo"]:
            input_data = SwitchNodeInput(switch_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "match"

    @pytest.mark.asyncio
    async def test_pattern_with_non_string(self, context, state):
        """Test that patterns don't match non-string values."""
        cases = [
            CaseCondition(route="string_match", pattern=r"^\d+$"),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="not_string")

        # Numeric value should not match pattern (only strings)
        input_data = SwitchNodeInput(switch_value=123)
        result = await node.execute(input_data, context, state)
        assert result.route == "not_string"


class TestSwitchNodePredicate:
    """Test Switch node with predicate functions."""

    @pytest.mark.asyncio
    async def test_simple_predicate(self, context, state):
        """Test simple predicate function."""

        def is_positive(value):
            return value > 0

        def is_negative(value):
            return value < 0

        cases = [
            CaseCondition(route="positive", predicate=is_positive),
            CaseCondition(route="negative", predicate=is_negative),
            CaseCondition(route="zero", predicate=lambda x: x == 0),
        ]
        node = SwitchNode(node_id="test", cases=cases)

        input_data = SwitchNodeInput(switch_value=10)
        result = await node.execute(input_data, context, state)
        assert result.route == "positive"

        input_data = SwitchNodeInput(switch_value=-5)
        result = await node.execute(input_data, context, state)
        assert result.route == "negative"

        input_data = SwitchNodeInput(switch_value=0)
        result = await node.execute(input_data, context, state)
        assert result.route == "zero"

    @pytest.mark.asyncio
    async def test_complex_predicate(self, context, state):
        """Test complex predicate with object inspection."""

        def is_vip(customer):
            return customer.get("tier") == "platinum"

        def is_premium(customer):
            return customer.get("tier") in ["gold", "silver"]

        cases = [
            CaseCondition(route="vip", predicate=is_vip),
            CaseCondition(route="premium", predicate=is_premium),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="standard")

        # VIP customer
        input_data = SwitchNodeInput(switch_value={"name": "John", "tier": "platinum"})
        result = await node.execute(input_data, context, state)
        assert result.route == "vip"

        # Premium customer
        input_data = SwitchNodeInput(switch_value={"name": "Jane", "tier": "gold"})
        result = await node.execute(input_data, context, state)
        assert result.route == "premium"

        # Standard customer
        input_data = SwitchNodeInput(switch_value={"name": "Bob", "tier": "bronze"})
        result = await node.execute(input_data, context, state)
        assert result.route == "standard"


class TestSwitchNodeCaseSensitivity:
    """Test Switch node case sensitivity."""

    @pytest.mark.asyncio
    async def test_case_sensitive_value_match(self, context, state):
        """Test case-sensitive value matching."""
        cases = [
            CaseCondition(route="lower", value="hello"),
            CaseCondition(route="upper", value="HELLO"),
        ]
        node = SwitchNode(
            node_id="test", cases=cases, case_sensitive=True, default_route="no_match"
        )

        input_data = SwitchNodeInput(switch_value="hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "lower"

        input_data = SwitchNodeInput(switch_value="HELLO")
        result = await node.execute(input_data, context, state)
        assert result.route == "upper"

        input_data = SwitchNodeInput(switch_value="Hello")
        result = await node.execute(input_data, context, state)
        assert result.route == "no_match"

    @pytest.mark.asyncio
    async def test_case_insensitive_value_match(self, context, state):
        """Test case-insensitive value matching."""
        cases = [
            CaseCondition(route="match", value="hello"),
        ]
        node = SwitchNode(
            node_id="test", cases=cases, case_sensitive=False, default_route="no_match"
        )

        # All should match
        for value in ["hello", "HELLO", "Hello", "HeLLo"]:
            input_data = SwitchNodeInput(switch_value=value)
            result = await node.execute(input_data, context, state)
            assert result.route == "match"

    @pytest.mark.asyncio
    async def test_case_sensitivity_only_strings(self, context, state):
        """Test that case sensitivity only applies to strings."""
        cases = [
            CaseCondition(route="match", value=42),
        ]
        node = SwitchNode(node_id="test", cases=cases, case_sensitive=False)

        # Numeric values should match normally
        input_data = SwitchNodeInput(switch_value=42)
        result = await node.execute(input_data, context, state)
        assert result.route == "match"


class TestSwitchNodeNullHandling:
    """Test Switch node null/None handling."""

    @pytest.mark.asyncio
    async def test_null_uses_default(self, context, state):
        """Test null value uses default route."""
        cases = [
            CaseCondition(route="case1", value="value1"),
        ]
        node = SwitchNode(
            node_id="test",
            cases=cases,
            default_route="null_route",
            null_handling="default",
        )

        input_data = SwitchNodeInput(switch_value=None)
        result = await node.execute(input_data, context, state)
        assert result.route == "null_route"

    @pytest.mark.asyncio
    async def test_null_raises_error(self, context, state):
        """Test null value raises error."""
        cases = [
            CaseCondition(route="case1", value="value1"),
        ]
        node = SwitchNode(node_id="test", cases=cases, null_handling="error")

        input_data = SwitchNodeInput(switch_value=None)
        with pytest.raises(ValueError, match="Switch value is None/null"):
            await node.execute(input_data, context, state)


class TestSwitchNodeValidation:
    """Test Switch node validation."""

    def test_invalid_pattern(self):
        """Test that invalid regex pattern raises error."""
        cases = [
            CaseCondition(route="bad", pattern="[invalid(regex"),
        ]
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            SwitchNode(node_id="test", cases=cases)

    def test_no_matching_method(self):
        """Test that cases without matching method raise error."""
        cases = [
            CaseCondition(route="invalid"),
        ]
        with pytest.raises(ValueError, match="must have exactly one"):
            SwitchNode(node_id="test", cases=cases)

    def test_multiple_matching_methods(self):
        """Test that cases with multiple methods raise error."""
        cases = [
            CaseCondition(route="invalid", value="test", pattern=r"test"),
        ]
        with pytest.raises(ValueError, match="must have exactly one"):
            SwitchNode(node_id="test", cases=cases)

    def test_get_routes(self):
        """Test get_routes returns all possible routes."""
        cases = [
            CaseCondition(route="case1", value="value1"),
            CaseCondition(route="case2", value="value2"),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="default")

        route_names = node.get_routes()
        assert "case1" in route_names
        assert "case2" in route_names
        assert "default" in route_names


class TestSwitchNodeErrorHandling:
    """Test Switch node error handling."""

    @pytest.mark.asyncio
    async def test_predicate_error_skips_case(self, context, state):
        """Test that predicate errors skip the case."""

        def bad_predicate(value):
            raise ValueError("Intentional error")

        def good_predicate(value):
            return True

        cases = [
            CaseCondition(route="error_case", predicate=bad_predicate),
            CaseCondition(route="good_case", predicate=good_predicate),
        ]
        node = SwitchNode(node_id="test", cases=cases)

        input_data = SwitchNodeInput(switch_value="test")
        result = await node.execute(input_data, context, state)
        # Should skip error_case and match good_case
        assert result.route == "good_case"

    @pytest.mark.asyncio
    async def test_all_errors_use_default(self, context, state):
        """Test that when all cases error, default is used."""

        def error_predicate(value):
            raise ValueError("Error")

        cases = [
            CaseCondition(route="error1", predicate=error_predicate),
            CaseCondition(route="error2", predicate=error_predicate),
        ]
        node = SwitchNode(node_id="test", cases=cases, default_route="fallback")

        input_data = SwitchNodeInput(switch_value="test")
        result = await node.execute(input_data, context, state)
        assert result.route == "fallback"


class TestSwitchNodeFirstMatch:
    """Test that Switch returns first matching case."""

    @pytest.mark.asyncio
    async def test_first_match_order(self, context, state):
        """Test that first matching case is returned."""
        cases = [
            CaseCondition(route="case1", value_list=["a", "b", "c"]),
            CaseCondition(route="case2", value_list=["b", "c", "d"]),
            CaseCondition(route="case3", value_list=["c", "d", "e"]),
        ]
        node = SwitchNode(node_id="test", cases=cases)

        # Value "c" matches all three cases, should return first
        input_data = SwitchNodeInput(switch_value="c")
        result = await node.execute(input_data, context, state)
        assert result.route == "case1"
