"""Tests for HumanApprovalNode."""

from datetime import datetime
from typing import Any, Optional
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.human_approval import (
    ApprovalDecision,
    ApprovalInterface,
    ApprovalRecord,
    ApprovalValidationError,
    HumanApprovalNode,
    HumanApprovalNodeInput,
    HumanApprovalNodeOutput,
    RichApprovalInterface,
    UserCancelledError,
)


class MockApprovalInterface(ApprovalInterface):
    """Mock approval interface for testing."""

    def __init__(
        self,
        decision: ApprovalDecision = ApprovalDecision.APPROVED,
        feedback: Optional[str] = None,
    ):
        self.decision = decision
        self.feedback = feedback
        self.displayed_data: Optional[dict[str, Any]] = None
        self.displayed_title: Optional[str] = None
        self.displayed_description: Optional[str] = None
        self.approval_prompt: Optional[str] = None
        self.allow_feedback_called: Optional[bool] = None
        self.errors_shown: list[str] = []

    def display_data_for_approval(
        self, title: str, data: dict[str, Any], description: Optional[str] = None
    ) -> None:
        """Mock display method that records what was shown."""
        self.displayed_title = title
        self.displayed_data = data
        self.displayed_description = description

    def collect_approval_decision(
        self, prompt: str, allow_feedback: bool = False
    ) -> tuple[ApprovalDecision, Optional[str]]:
        """Mock decision collection that returns preset values."""
        self.approval_prompt = prompt
        self.allow_feedback_called = allow_feedback
        return self.decision, self.feedback

    def show_error(self, message: str) -> None:
        """Mock error display."""
        self.errors_shown.append(message)


@pytest.mark.asyncio
async def test_basic_approval_flow() -> None:
    """Test basic approval functionality."""
    # Test data to review
    test_data = {
        "document_id": "DOC-123",
        "title": "Test Document",
        "content": "This is a test document for approval.",
        "author": "Test Author",
        "word_count": 150,
    }

    input_config = HumanApprovalNodeInput(
        data_to_review=test_data,
        approval_prompt="Please review this document",
        title="Document Review",
        description="Review the document for publication",
    )

    # Mock interface that approves with feedback
    mock_interface = MockApprovalInterface(
        decision=ApprovalDecision.APPROVED, feedback="Looks good to publish!"
    )

    # Create and execute node
    node = HumanApprovalNode(node_id="doc_approval", interface=mock_interface)

    # Create context and state
    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="doc_approval",
    )

    result = await node.execute(input_config, context, state)

    # Verify result
    assert isinstance(result, HumanApprovalNodeOutput)
    assert result.decision == ApprovalDecision.APPROVED
    assert result.feedback == "Looks good to publish!"
    assert result.approved is True
    assert isinstance(result.timestamp, datetime)
    assert result.execution_id is not None

    # Verify approval record
    assert result.approval_record.decision == ApprovalDecision.APPROVED
    assert result.approval_record.feedback == "Looks good to publish!"

    # Verify interface was called correctly
    assert mock_interface.displayed_data == test_data
    assert mock_interface.displayed_title == "Document Review"
    assert mock_interface.displayed_description == "Review the document for publication"
    assert mock_interface.approval_prompt == "Please review this document"
    assert mock_interface.allow_feedback_called is True

    # Verify state was updated
    approval_record = state.get("doc_approval_approval")
    assert approval_record is not None
    assert approval_record["decision"] == "approved"
    assert approval_record["feedback"] == "Looks good to publish!"

    # Verify approval history
    history = state.get("doc_approval_approval_history")
    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["decision"] == "approved"


@pytest.mark.asyncio
async def test_rejection_flow() -> None:
    """Test document rejection functionality."""
    test_data = {"document": "Poor quality content"}

    input_config = HumanApprovalNodeInput(
        data_to_review=test_data,
        allow_feedback=True,
    )

    # Mock interface that rejects with reason
    mock_interface = MockApprovalInterface(
        decision=ApprovalDecision.REJECTED,
        feedback="Content quality is not sufficient for publication",
    )

    node = HumanApprovalNode(node_id="quality_check", interface=mock_interface)
    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="quality_check",
    )

    result = await node.execute(input_config, context, state)

    # Verify rejection result
    assert result.decision == ApprovalDecision.REJECTED
    assert result.approved is False
    assert result.feedback == "Content quality is not sufficient for publication"

    # Verify state contains rejection
    approval_record = state.get("quality_check_approval")
    assert approval_record["decision"] == "rejected"


@pytest.mark.asyncio
async def test_custom_state_path() -> None:
    """Test using custom state path for approval record."""
    test_data = {"task": "Complete project review"}

    input_config = HumanApprovalNodeInput(
        data_to_review=test_data,
        state_path="project.reviews.final_approval",
    )

    mock_interface = MockApprovalInterface(decision=ApprovalDecision.APPROVED)
    node = HumanApprovalNode(node_id="project_approval", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="project_approval",
    )

    result = await node.execute(input_config, context, state)

    # Verify custom state path was used
    approval_record = state.get("project.reviews.final_approval")
    assert approval_record is not None
    assert approval_record["decision"] == "approved"

    # Verify history uses custom path
    history = state.get("project.reviews.final_approval_history")
    assert isinstance(history, list)
    assert len(history) == 1

    # Verify result is still valid
    assert result.decision == ApprovalDecision.APPROVED


@pytest.mark.asyncio
async def test_no_feedback_allowed() -> None:
    """Test approval process with feedback collection disabled."""
    test_data = {"simple": "approval"}

    input_config = HumanApprovalNodeInput(
        data_to_review=test_data,
        allow_feedback=False,
    )

    mock_interface = MockApprovalInterface(
        decision=ApprovalDecision.APPROVED, feedback=None
    )
    node = HumanApprovalNode(node_id="simple_approval", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="simple_approval",
    )

    result = await node.execute(input_config, context, state)

    # Verify feedback collection was disabled
    assert mock_interface.allow_feedback_called is False
    assert result.feedback is None


@pytest.mark.asyncio
async def test_user_cancellation() -> None:
    """Test user cancellation (CTRL+C) during approval."""
    test_data = {"test": "data"}
    input_config = HumanApprovalNodeInput(data_to_review=test_data)

    # Mock interface that raises KeyboardInterrupt
    mock_interface = Mock()
    mock_interface.display_data_for_approval = Mock()
    mock_interface.collect_approval_decision.side_effect = KeyboardInterrupt()

    node = HumanApprovalNode(node_id="cancel_test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="cancel_test",
    )

    with pytest.raises(UserCancelledError):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_approval_history_accumulation() -> None:
    """Test that multiple approvals accumulate in history."""
    test_data = {"version": 1}
    input_config = HumanApprovalNodeInput(
        data_to_review=test_data, state_path="document.approval"
    )

    # Execute first approval
    mock_interface1 = MockApprovalInterface(
        decision=ApprovalDecision.REJECTED, feedback="Needs revision"
    )
    node = HumanApprovalNode(node_id="doc_review", interface=mock_interface1)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="doc_review",
    )

    await node.execute(input_config, context, state)

    # Execute second approval
    test_data2 = {"version": 2}
    input_config2 = HumanApprovalNodeInput(
        data_to_review=test_data2, state_path="document.approval"
    )
    mock_interface2 = MockApprovalInterface(
        decision=ApprovalDecision.APPROVED, feedback="Much better!"
    )
    node2 = HumanApprovalNode(node_id="doc_review", interface=mock_interface2)

    await node2.execute(input_config2, context, state)

    # Verify history contains both approvals
    history = state.get("document.approval_history")
    assert len(history) == 2
    assert history[0]["decision"] == "rejected"
    assert history[0]["feedback"] == "Needs revision"
    assert history[1]["decision"] == "approved"
    assert history[1]["feedback"] == "Much better!"

    # Verify current approval is the latest
    current = state.get("document.approval")
    assert current["decision"] == "approved"


@pytest.mark.asyncio
async def test_metadata_update() -> None:
    """Test that execution metadata is properly updated."""
    test_data = {"metadata_test": "value"}
    input_config = HumanApprovalNodeInput(data_to_review=test_data)

    mock_interface = MockApprovalInterface(decision=ApprovalDecision.APPROVED)
    node = HumanApprovalNode(node_id="meta_test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="meta_test",
    )

    result = await node.execute(input_config, context, state)

    # Check metadata was set
    metadata = state.get_metadata("meta_test_execution")
    assert metadata is not None
    assert "timestamp" in metadata
    assert metadata["decision"] == "approved"
    assert metadata["approved"] is True
    assert metadata["execution_id"] == result.execution_id


@pytest.mark.asyncio
async def test_complex_data_structure() -> None:
    """Test approval with complex nested data structures."""
    complex_data = {
        "user": {
            "name": "John Doe",
            "email": "john@example.com",
            "preferences": {"theme": "dark", "notifications": True},
        },
        "permissions": ["read", "write", "admin"],
        "metadata": {"created": "2023-01-01", "last_login": None},
        "scores": [85, 92, 78, 95],
    }

    input_config = HumanApprovalNodeInput(
        data_to_review=complex_data,
        title="User Permission Review",
        description="Review user permissions and data before granting access",
    )

    mock_interface = MockApprovalInterface(decision=ApprovalDecision.APPROVED)
    node = HumanApprovalNode(node_id="permission_review", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="permission_review",
    )

    result = await node.execute(input_config, context, state)

    # Verify complex data was passed correctly
    assert mock_interface.displayed_data == complex_data
    assert result.decision == ApprovalDecision.APPROVED

    # Verify state contains the approval
    approval_record = state.get("permission_review_approval")
    assert approval_record is not None


def test_state_path_validation() -> None:
    """Test validation of state path configuration."""
    test_data = {"test": "data"}

    # Empty string should be invalid
    with pytest.raises(ValueError, match="State path cannot be empty"):
        HumanApprovalNodeInput(data_to_review=test_data, state_path="")

    # Whitespace only should be invalid
    with pytest.raises(ValueError, match="State path cannot be empty"):
        HumanApprovalNodeInput(data_to_review=test_data, state_path="   ")

    # Valid path should work
    valid_input = HumanApprovalNodeInput(
        data_to_review=test_data, state_path="valid.path"
    )
    assert valid_input.state_path == "valid.path"

    # None should work (uses default)
    none_input = HumanApprovalNodeInput(data_to_review=test_data, state_path=None)
    assert none_input.state_path is None


@pytest.mark.asyncio
async def test_generic_exception_handling() -> None:
    """Test handling of unexpected exceptions during approval."""

    class ErrorInterface(ApprovalInterface):
        def display_data_for_approval(
            self, title: str, data: dict[str, Any], description: Optional[str] = None
        ) -> None:
            raise RuntimeError("Unexpected display error")

        def collect_approval_decision(
            self, prompt: str, allow_feedback: bool = False
        ) -> tuple[ApprovalDecision, Optional[str]]:
            return ApprovalDecision.APPROVED, None

        def show_error(self, message: str) -> None:
            pass

    test_data = {"error_test": "data"}
    input_config = HumanApprovalNodeInput(data_to_review=test_data)

    node = HumanApprovalNode(node_id="error_test", interface=ErrorInterface())

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="error_test",
    )

    with pytest.raises(
        ApprovalValidationError,
        match=r"Failed to collect approval.*Unexpected display error",
    ):
        await node.execute(input_config, context, state)


@pytest.mark.asyncio
async def test_nested_state_path_conflict() -> None:
    """Test error when nested path encounters non-dict value."""

    class ConflictInterface(ApprovalInterface):
        def display_data_for_approval(
            self, title: str, data: dict[str, Any], description: Optional[str] = None
        ) -> None:
            pass

        def collect_approval_decision(
            self, prompt: str, allow_feedback: bool = False
        ) -> tuple[ApprovalDecision, Optional[str]]:
            return ApprovalDecision.APPROVED, None

        def show_error(self, message: str) -> None:
            pass

    test_data = {"test": "data"}
    input_config = HumanApprovalNodeInput(
        data_to_review=test_data, state_path="user.name.approval"
    )

    node = HumanApprovalNode(node_id="conflict_test", interface=ConflictInterface())

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    # Pre-populate with conflicting value
    state.data["user"] = {"name": "John"}  # name is a string, not dict

    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="conflict_test",
    )

    with pytest.raises(
        ApprovalValidationError, match=r"Failed to collect approval.*is not a dict"
    ):
        await node.execute(input_config, context, state)


@pytest.mark.integration
def test_rich_approval_interface() -> None:
    """Integration test for RichApprovalInterface (requires manual verification)."""
    interface = RichApprovalInterface()
    assert interface is not None
    assert hasattr(interface, "console")


def test_rich_interface_display_data() -> None:
    """Test RichApprovalInterface data display formatting."""
    interface = RichApprovalInterface()

    test_data = {
        "simple": "value",
        "nested": {"key": "value", "num": 42},
        "list": ["item1", "item2", "item3"],
        "long_list": list(range(10)),
    }

    with patch.object(interface.console, "print") as mock_print:
        interface.display_data_for_approval(
            title="Test Data", data=test_data, description="Test description"
        )
        # Verify print was called (display happened)
        assert mock_print.call_count >= 2  # At least title and data


def test_rich_interface_collect_approval() -> None:
    """Test RichApprovalInterface approval collection."""
    interface = RichApprovalInterface()

    # Test approval with feedback
    with (
        patch("rich.prompt.Confirm.ask", return_value=True),
        patch("rich.prompt.Prompt.ask", return_value="Great work!"),
        patch.object(interface.console, "print"),
    ):
        decision, feedback = interface.collect_approval_decision(
            "Approve?", allow_feedback=True
        )
        assert decision == ApprovalDecision.APPROVED
        assert feedback == "Great work!"

    # Test rejection without feedback
    with (
        patch("rich.prompt.Confirm.ask", return_value=False),
        patch.object(interface.console, "print"),
    ):
        decision, feedback = interface.collect_approval_decision(
            "Approve?", allow_feedback=False
        )
        assert decision == ApprovalDecision.REJECTED
        assert feedback is None


def test_rich_interface_error_display() -> None:
    """Test RichApprovalInterface error display."""
    interface = RichApprovalInterface()

    with patch.object(interface.console, "print") as mock_print:
        interface.show_error("Test error message")
        mock_print.assert_called_once()
        args = mock_print.call_args[0][0]
        assert "Test error message" in args
        assert "[red]" in args


def test_rich_interface_format_methods() -> None:
    """Test RichApprovalInterface formatting helper methods."""
    interface = RichApprovalInterface()

    # Test dict formatting
    test_dict = {"key1": "value1", "nested": {"key2": "value2"}}
    formatted = interface._format_dict_value(test_dict)
    assert "key1: value1" in formatted
    assert "nested:" in formatted
    assert "key2: value2" in formatted

    # Test list formatting
    short_list = ["a", "b", "c"]
    formatted_short = interface._format_list_value(short_list)
    assert formatted_short == "[a, b, c]"

    long_list = list(range(10))
    formatted_long = interface._format_list_value(long_list)
    assert "..." in formatted_long
    assert "10 items" in formatted_long


def test_approval_record_model() -> None:
    """Test ApprovalRecord Pydantic model."""
    timestamp = datetime.utcnow()
    record = ApprovalRecord(
        decision=ApprovalDecision.APPROVED,
        feedback="Excellent work",
        timestamp=timestamp,
        execution_id="test-123",
    )

    assert record.decision == ApprovalDecision.APPROVED
    assert record.feedback == "Excellent work"
    assert record.timestamp == timestamp
    assert record.execution_id == "test-123"

    # Test serialization
    data = record.model_dump()
    assert data["decision"] == "approved"
    assert data["feedback"] == "Excellent work"


@pytest.mark.asyncio
async def test_approval_without_feedback_when_rejected() -> None:
    """Test that rejection without feedback works correctly."""
    test_data = {"simple": "test"}
    input_config = HumanApprovalNodeInput(data_to_review=test_data, allow_feedback=True)

    # Mock rejection with empty feedback
    mock_interface = MockApprovalInterface(
        decision=ApprovalDecision.REJECTED,
        feedback="",  # Empty string
    )

    node = HumanApprovalNode(node_id="no_feedback_test", interface=mock_interface)

    state = WorkflowState(workflow_id=uuid4(), workflow_run_id=uuid4())
    context = NodeContext(
        workflow_id=state.workflow_id,
        workflow_run_id=state.workflow_run_id,
        node_id="no_feedback_test",
    )

    # Override the interface behavior to return None for empty feedback
    def mock_collect_decision(
        prompt: str, allow_feedback: bool = False
    ) -> tuple[ApprovalDecision, Optional[str]]:
        mock_interface.approval_prompt = prompt
        mock_interface.allow_feedback_called = allow_feedback
        return ApprovalDecision.REJECTED, None  # Return None for empty feedback

    mock_interface.collect_approval_decision = mock_collect_decision

    result = await node.execute(input_config, context, state)

    assert result.decision == ApprovalDecision.REJECTED
    assert result.feedback is None  # Should be None, not empty string
    assert result.approved is False
