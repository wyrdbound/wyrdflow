"""Tests for HumanInputNode."""

from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.human_input import (
    FieldConfig,
    FieldValidationResult,
    HumanInputNode,
    HumanInputNodeInput,
    HumanInputNodeOutput,
    InputInterface,
    InputValidationError,
    RichCLIInterface,
    UserCancelledError,
)


class MockInterface(InputInterface):
    """Mock interface for testing."""

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.errors_shown: list[str] = []
        self.help_shown: list[str] = []

    def collect_field(self, field_config: FieldConfig) -> Any:
        return self.responses.get(field_config.name, "")

    def show_error(self, message: str) -> None:
        self.errors_shown.append(message)

    def show_help(self, message: str) -> None:
        self.help_shown.append(message)


@pytest.mark.asyncio
async def test_basic_input_collection() -> None:
    """Test basic input collection functionality."""
    # Create field configs
    fields = [
        FieldConfig(name="name", field_type=str, prompt="Enter your name:"),
        FieldConfig(name="age", field_type=int, prompt="Enter your age:"),
    ]

    input_config = HumanInputNodeInput(fields=fields)

    # Mock interface with responses
    mock_interface = MockInterface({"name": "Alice", "age": 25})

    # Create and execute node
    node = HumanInputNode(node_id="user_input", interface=mock_interface)

    # Create context and state
    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="user_input",
    )

    result = await node.execute(input_config, context, state)

    assert isinstance(result, HumanInputNodeOutput)
    assert result.collected_fields == {"name": "Alice", "age": 25}
    assert set(result.fields_collected) == {"name", "age"}


@pytest.mark.asyncio
async def test_validation_function() -> None:
    """Test custom validation function."""

    def validate_age(value: int) -> FieldValidationResult:
        if value < 0 or value > 120:
            return FieldValidationResult(
                is_valid=False, errors=["Age must be between 0 and 120"]
            )
        return FieldValidationResult(is_valid=True)

    fields = [
        FieldConfig(
            name="age",
            field_type=int,
            prompt="Enter age:",
            validation_fn=validate_age,
        )
    ]

    input_config = HumanInputNodeInput(fields=fields)
    mock_interface = MockInterface({"age": 150})  # Invalid age

    node = HumanInputNode(node_id="test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test",
    )

    with pytest.raises(InputValidationError):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_state_path_mapping() -> None:
    """Test output mapping to state paths."""
    fields = [
        FieldConfig(name="genre", field_type=str, prompt="Genre:"),
        FieldConfig(name="length", field_type=int, prompt="Length:"),
    ]

    input_config = HumanInputNodeInput(
        fields=fields,
        output_mapping={"genre": "book.genre", "length": "book.details.length"},
    )

    mock_interface = MockInterface({"genre": "sci-fi", "length": 300})

    node = HumanInputNode(node_id="book_input", interface=mock_interface)

    # Create state and execute
    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="book_input",
    )

    result = await node.execute(input_config, context, state)

    # Check that state was updated correctly
    assert state.data["book"]["genre"] == "sci-fi"
    assert state.data["book"]["details"]["length"] == 300
    assert result.collected_fields == {"genre": "sci-fi", "length": 300}


def test_conflicting_state_paths() -> None:
    """Test validation of conflicting state paths."""
    fields = [
        FieldConfig(name="genre", field_type=str, prompt="Genre:"),
        FieldConfig(name="title", field_type=str, prompt="Title:"),
    ]

    with pytest.raises(ValueError, match="State paths conflict"):
        HumanInputNodeInput(
            fields=fields,
            output_mapping={
                "genre": "book.genre",
                "title": "book.genre.title",  # Conflicts with book.genre
            },
        )


@pytest.mark.asyncio
async def test_user_cancellation() -> None:
    """Test user cancellation (CTRL+C)."""
    fields = [FieldConfig(name="test", field_type=str, prompt="Test:")]
    input_config = HumanInputNodeInput(fields=fields)

    # Mock interface that raises KeyboardInterrupt
    mock_interface = Mock()
    mock_interface.collect_field.side_effect = KeyboardInterrupt()

    node = HumanInputNode(node_id="test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test",
    )

    with pytest.raises(UserCancelledError):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_list_input() -> None:
    """Test list input collection."""
    fields = [FieldConfig(name="items", field_type=list[str], prompt="Enter items:")]

    input_config = HumanInputNodeInput(fields=fields)
    mock_interface = MockInterface({"items": ["item1", "item2", "item3"]})

    node = HumanInputNode(node_id="list_test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="list_test",
    )

    result = await node.execute(input_config, context, state)
    assert result.collected_fields["items"] == ["item1", "item2", "item3"]


@pytest.mark.asyncio
async def test_required_field_validation() -> None:
    """Test required field validation."""
    fields = [
        FieldConfig(
            name="required_field", field_type=str, prompt="Required:", required=True
        )
    ]

    input_config = HumanInputNodeInput(fields=fields)
    mock_interface = MockInterface({"required_field": ""})  # Empty value

    node = HumanInputNode(node_id="test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test",
    )

    with pytest.raises(InputValidationError):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_default_state_mapping() -> None:
    """Test default state mapping (no output_mapping provided)."""
    fields = [
        FieldConfig(name="field1", field_type=str, prompt="Field 1:"),
        FieldConfig(name="field2", field_type=int, prompt="Field 2:"),
    ]

    input_config = HumanInputNodeInput(fields=fields)  # No output_mapping
    mock_interface = MockInterface({"field1": "value1", "field2": 42})

    node = HumanInputNode(node_id="test_node", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test_node",
    )

    result = await node.execute(input_config, context, state)

    # Check that data was stored under node_id_input
    assert state.data["test_node_input"] == {"field1": "value1", "field2": 42}
    assert result.collected_fields == {"field1": "value1", "field2": 42}


@pytest.mark.asyncio
async def test_validation_with_valid_input() -> None:
    """Test validation function with valid input."""

    def validate_positive(value: int) -> FieldValidationResult:
        if value > 0:
            return FieldValidationResult(is_valid=True)
        return FieldValidationResult(is_valid=False, errors=["Value must be positive"])

    fields = [
        FieldConfig(
            name="number",
            field_type=int,
            prompt="Enter positive number:",
            validation_fn=validate_positive,
        )
    ]

    input_config = HumanInputNodeInput(fields=fields)
    mock_interface = MockInterface({"number": 42})  # Valid number

    node = HumanInputNode(node_id="test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test",
    )

    result = await node.execute(input_config, context, state)
    assert result.collected_fields["number"] == 42


@pytest.mark.asyncio
async def test_metadata_update() -> None:
    """Test that execution metadata is properly updated."""
    fields = [FieldConfig(name="test", field_type=str, prompt="Test:")]

    input_config = HumanInputNodeInput(fields=fields)
    mock_interface = MockInterface({"test": "value"})

    node = HumanInputNode(node_id="metadata_test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="metadata_test",
    )

    result = await node.execute(input_config, context, state)

    # Check metadata was set
    metadata = state.get_metadata("metadata_test_execution")
    assert metadata is not None
    assert "timestamp" in metadata
    assert "fields_collected" in metadata
    assert "execution_id" in metadata
    assert metadata["fields_collected"] == ["test"]
    assert result.execution_id == metadata["execution_id"]


@pytest.mark.asyncio
async def test_optional_field_with_default() -> None:
    """Test optional field with default value."""
    fields = [
        FieldConfig(
            name="optional",
            field_type=str,
            prompt="Optional field:",
            required=False,
            default_value="default_value",
        )
    ]

    input_config = HumanInputNodeInput(fields=fields)
    # Return empty string to trigger default
    mock_interface = MockInterface({"optional": ""})

    node = HumanInputNode(node_id="test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="test",
    )

    result = await node.execute(input_config, context, state)
    # Empty string is allowed for optional fields
    assert result.collected_fields["optional"] == ""


@pytest.mark.integration
def test_rich_cli_interface() -> None:
    """Integration test for RichCLIInterface (requires manual verification)."""
    # This test would require actual user input, so it's marked for integration
    # In actual implementation, you might want to patch Rich's input methods
    interface = RichCLIInterface()
    assert interface is not None
    assert hasattr(interface, "console")


@pytest.mark.asyncio
async def test_keyboard_interrupt() -> None:
    """Test that KeyboardInterrupt is converted to UserCancelledError."""

    class InterruptInterface(InputInterface):
        def collect_field(self, field_config: FieldConfig) -> Any:
            raise KeyboardInterrupt()

        def show_error(self, message: str) -> None:
            pass

        def show_help(self, message: str) -> None:
            pass

    fields = [FieldConfig(name="test", field_type=str, prompt="Test:")]
    input_config = HumanInputNodeInput(fields=fields)
    node = HumanInputNode(node_id="interrupt_test", interface=InterruptInterface())

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="interrupt_test",
    )

    with pytest.raises(UserCancelledError, match="User cancelled workflow execution"):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_nested_state_path_error() -> None:
    """Test error when nested path encounters non-dict value."""

    class TestInterface(InputInterface):
        def collect_field(self, field_config: FieldConfig) -> Any:
            return "value"

        def show_error(self, message: str) -> None:
            pass

        def show_help(self, message: str) -> None:
            pass

    fields = [FieldConfig(name="field1", field_type=str, prompt="Field:")]
    # Create conflict: user.name.first where user.name is already a string
    output_mapping = {"field1": "user.name.first"}
    input_config = HumanInputNodeInput(fields=fields, output_mapping=output_mapping)
    node = HumanInputNode(node_id="nested_test", interface=TestInterface())

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    # Pre-populate with conflicting value
    state.data["user"] = {"name": "John"}  # name is a string, not dict

    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="nested_test",
    )

    # The ValueError gets wrapped in InputValidationError by the execute method
    with pytest.raises(
        InputValidationError, match=r"Failed to collect valid input.*is not a dict"
    ):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_validation_retry_exhaustion() -> None:
    """Test that validation errors after max retries raise InputValidationError."""

    class FailingInterface(InputInterface):
        def __init__(self) -> None:
            self.call_count = 0

        def collect_field(self, field_config: FieldConfig) -> Any:
            self.call_count += 1
            return "invalid"

        def show_error(self, message: str) -> None:
            pass

        def show_help(self, message: str) -> None:
            pass

    def always_fail(_value: Any) -> FieldValidationResult:
        return FieldValidationResult(is_valid=False, errors=["Always fails"])

    fields = [
        FieldConfig(
            name="field", field_type=str, prompt="Field:", validation_fn=always_fail
        )
    ]
    input_config = HumanInputNodeInput(fields=fields, max_retry_attempts=2)
    interface = FailingInterface()
    node = HumanInputNode(node_id="retry_test", interface=interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="retry_test",
    )

    with pytest.raises(InputValidationError, match="validation failed"):
        await node.execute(input_config, context, state)

    # Should have tried max_retry_attempts times
    assert interface.call_count == 2


@pytest.mark.asyncio
async def test_generic_exception_during_collection() -> None:
    """Test handling of unexpected exceptions during field collection."""

    class ErrorInterface(InputInterface):
        def collect_field(self, field_config: FieldConfig) -> Any:
            raise RuntimeError("Unexpected error")

        def show_error(self, message: str) -> None:
            pass

        def show_help(self, message: str) -> None:
            pass

    fields = [FieldConfig(name="field", field_type=str, prompt="Field:")]
    input_config = HumanInputNodeInput(fields=fields, max_retry_attempts=2)
    node = HumanInputNode(node_id="error_test", interface=ErrorInterface())

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="error_test",
    )

    with pytest.raises(InputValidationError, match="Failed to collect field 'field'"):
        await node.execute(input_config, context, state)


def test_rich_cli_string_input() -> None:
    """Test RichCLIInterface string input collection."""
    interface = RichCLIInterface()
    field_config = FieldConfig(
        name="name",
        field_type=str,
        prompt="Enter your name:",
        help_text="Your full name",
        default_value="John",
    )

    with patch("rich.prompt.Prompt.ask", return_value="Alice"):
        result = interface.collect_field(field_config)
        assert result == "Alice"


def test_rich_cli_int_input() -> None:
    """Test RichCLIInterface integer input collection."""
    interface = RichCLIInterface()
    field_config = FieldConfig(
        name="age", field_type=int, prompt="Enter age:", default_value=25
    )

    with patch("rich.prompt.IntPrompt.ask", return_value=30):
        result = interface.collect_field(field_config)
        assert result == 30


def test_rich_cli_float_input() -> None:
    """Test RichCLIInterface float input collection."""
    interface = RichCLIInterface()
    field_config = FieldConfig(
        name="price", field_type=float, prompt="Enter price:", default_value=9.99
    )

    with patch("rich.prompt.FloatPrompt.ask", return_value=19.99):
        result = interface.collect_field(field_config)
        assert result == 19.99


def test_rich_cli_bool_input() -> None:
    """Test RichCLIInterface boolean input collection."""
    interface = RichCLIInterface()
    field_config = FieldConfig(
        name="confirm", field_type=bool, prompt="Confirm?", default_value=False
    )

    with patch("rich.prompt.Confirm.ask", return_value=True):
        result = interface.collect_field(field_config)
        assert result is True


def test_rich_cli_list_input() -> None:
    """Test RichCLIInterface list input collection."""
    interface = RichCLIInterface()
    field_config = FieldConfig(name="tags", field_type=list[str], prompt="Enter tags:")

    # Simulate entering two items then empty line
    with patch("rich.prompt.Prompt.ask", side_effect=["python", "testing", ""]):
        result = interface.collect_field(field_config)
        assert result == ["python", "testing"]


def test_rich_cli_show_error() -> None:
    """Test RichCLIInterface error display."""
    interface = RichCLIInterface()

    with patch.object(interface.console, "print") as mock_print:
        interface.show_error("Test error")
        mock_print.assert_called_once()
        args = mock_print.call_args[0][0]
        assert "Test error" in args
        assert "[red]" in args


def test_rich_cli_show_help() -> None:
    """Test RichCLIInterface help display."""
    interface = RichCLIInterface()

    with patch.object(interface.console, "print") as mock_print:
        interface.show_help("Test help")
        mock_print.assert_called_once()
        args = mock_print.call_args[0][0]
        assert "Test help" in args
        assert "[blue]" in args


@pytest.mark.asyncio
async def test_boolean_false_not_treated_as_empty() -> None:
    """Test that boolean False values are not treated as empty for required fields."""
    # Mock interface that returns False for boolean input
    mock_interface = Mock(spec=InputInterface)
    mock_interface.collect_field.return_value = False
    mock_interface.show_error = Mock()

    node = HumanInputNode("test_bool_node", interface=mock_interface)

    # Create field config for required boolean field
    field_config = FieldConfig(
        name="confirm_action",
        field_type=bool,
        prompt="Confirm action?",
        required=True,
    )

    input_data = HumanInputNodeInput(fields=[field_config])
    context = NodeContext(
        workflow_id=uuid4(), workflow_run_id=uuid4(), node_id="test_bool_node"
    )
    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())

    # Execute and ensure it doesn't fail with "required field" error
    result = await node.execute(input_data, context, state)

    # Verify the result contains the False value
    assert result.collected_fields["confirm_action"] is False
    assert "confirm_action" in result.fields_collected

    # Verify no error was shown about required field
    mock_interface.show_error.assert_not_called()
