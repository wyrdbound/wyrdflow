"""Human approval node for workflow approval workflows."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors."""

    pass


class UserCancelledError(WorkflowExecutionError):
    """Raised when user cancels approval process."""

    pass


class ApprovalValidationError(WorkflowExecutionError):
    """Raised when approval validation fails."""

    pass


class ApprovalDecision(str, Enum):
    """Approval decision options."""

    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRecord(BaseModel):
    """Record of an approval decision."""

    model_config = ConfigDict(use_enum_values=False)

    decision: ApprovalDecision = Field(description="Approval decision")
    feedback: Optional[str] = Field(default=None, description="Optional feedback")
    timestamp: datetime = Field(description="When the decision was made")
    execution_id: str = Field(description="Unique execution identifier")


class ApprovalInterface(ABC):
    """Abstract interface for approval collection."""

    @abstractmethod
    def display_data_for_approval(
        self, title: str, data: dict[str, Any], description: Optional[str] = None
    ) -> None:
        """Display data in a formatted way for approval review."""
        pass

    @abstractmethod
    def collect_approval_decision(
        self, prompt: str, allow_feedback: bool = False
    ) -> tuple[ApprovalDecision, Optional[str]]:
        """Collect approval decision and optional feedback."""
        pass

    @abstractmethod
    def show_error(self, message: str) -> None:
        """Display error message to user."""
        pass


class RichApprovalInterface(ApprovalInterface):
    """Rich terminal-based approval interface."""

    def __init__(self) -> None:
        self.console = Console()

    def display_data_for_approval(
        self, title: str, data: dict[str, Any], description: Optional[str] = None
    ) -> None:
        """Display data in a formatted table for approval review."""
        # Create a panel with the title
        panel_title = f"[bold cyan]{title}[/bold cyan]"
        if description:
            panel_title += f"\n[dim]{description}[/dim]"

        # Create a table for the data
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        # Add data rows
        for key, value in data.items():
            # Format complex values
            if isinstance(value, dict):
                formatted_value = self._format_dict_value(value)
            elif isinstance(value, list):
                formatted_value = self._format_list_value(value)
            else:
                formatted_value = str(value)

            table.add_row(str(key), formatted_value)

        # Display in a panel
        panel = Panel(
            table,
            title=panel_title,
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print("\n")
        self.console.print(panel)
        self.console.print("\n")

    def collect_approval_decision(
        self, prompt: str, allow_feedback: bool = False
    ) -> tuple[ApprovalDecision, Optional[str]]:
        """Collect approval decision and optional feedback."""
        self.console.print(f"[bold yellow]{prompt}[/bold yellow]")

        # Get approval decision
        approved = Confirm.ask("Do you approve?", default=False)
        decision = ApprovalDecision.APPROVED if approved else ApprovalDecision.REJECTED

        # Collect optional feedback
        feedback = None
        if allow_feedback:
            feedback_prompt = (
                "Comments (optional)"
                if decision == ApprovalDecision.APPROVED
                else "Reason for rejection (optional)"
            )
            feedback = Prompt.ask(feedback_prompt, default="")
            if not feedback.strip():
                feedback = None

        return decision, feedback

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[red]Error: {message}[/red]")

    def _format_dict_value(self, data: dict[str, Any], indent: int = 0) -> str:
        """Format dictionary value for display."""
        if not data:
            return "{}"

        lines = []
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict_value(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: {self._format_list_value(value)}")
            else:
                lines.append(f"{prefix}{key}: {value}")

        return "\n".join(lines)

    def _format_list_value(self, data: list[Any]) -> str:
        """Format list value for display."""
        if not data:
            return "[]"
        if len(data) <= 3:
            return f"[{', '.join(str(item) for item in data)}]"
        return f"[{', '.join(str(item) for item in data[:3])}, ... ({len(data)} items)]"


class HumanApprovalNodeInput(NodeInput):
    """Input configuration for HumanApprovalNode."""

    data_to_review: dict[str, Any] = Field(
        description="Data to display for approval review"
    )
    approval_prompt: str = Field(
        default="Please review the data above",
        description="Prompt text to display before approval decision",
    )
    title: str = Field(
        default="Data Review", description="Title for the approval display"
    )
    description: Optional[str] = Field(
        default=None, description="Optional description for the approval process"
    )
    allow_feedback: bool = Field(
        default=True, description="Whether to collect optional feedback/comments"
    )
    state_path: Optional[str] = Field(
        default=None,
        description=(
            "State path to store approval record "
            "(e.g., 'approval.document_review'). "
            "If None, stores under '{node_id}_approval'"
        ),
    )

    @field_validator("state_path")
    @classmethod
    def validate_state_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate state path format."""
        if v is not None and not v.strip():
            raise ValueError("State path cannot be empty")
        return v


class HumanApprovalNodeOutput(NodeOutput):
    """Output from HumanApprovalNode containing approval decision."""

    model_config = ConfigDict(use_enum_values=False)

    decision: ApprovalDecision = Field(description="Approval decision")
    feedback: Optional[str] = Field(
        default=None, description="Optional feedback provided"
    )
    approved: bool = Field(description="Whether the data was approved")
    timestamp: datetime = Field(description="When the decision was made")
    execution_id: str = Field(description="Unique execution identifier")
    approval_record: ApprovalRecord = Field(
        description="Complete approval record for history tracking"
    )


class HumanApprovalNode(BaseNode[HumanApprovalNodeInput, HumanApprovalNodeOutput]):
    """Node that presents data for human approval with binary approve/reject flow."""

    input_schema = HumanApprovalNodeInput
    output_schema = HumanApprovalNodeOutput

    def __init__(
        self,
        node_id: str,
        interface: Optional[ApprovalInterface] = None,
        **kwargs: Any,
    ):
        super().__init__(node_id=node_id, **kwargs)
        self.interface = interface or RichApprovalInterface()

    async def execute(
        self,
        input_data: HumanApprovalNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> HumanApprovalNodeOutput:
        """Execute human approval collection."""
        try:
            # Display data for review
            self.interface.display_data_for_approval(
                title=input_data.title,
                data=input_data.data_to_review,
                description=input_data.description,
            )

            # Collect approval decision
            decision, feedback = self.interface.collect_approval_decision(
                prompt=input_data.approval_prompt,
                allow_feedback=input_data.allow_feedback,
            )

            # Create approval record
            execution_id = str(uuid4())
            timestamp = datetime.utcnow()
            approved = decision == ApprovalDecision.APPROVED

            approval_record = ApprovalRecord(
                decision=decision,
                feedback=feedback,
                timestamp=timestamp,
                execution_id=execution_id,
            )

            # Store approval record in state
            state_key = input_data.state_path or f"{self.node_id}_approval"
            self._set_nested_value(state, state_key, approval_record.model_dump())

            # Store approval history (append to list)
            history_key = f"{state_key}_history"
            existing_history = state.get(history_key, [])
            if not isinstance(existing_history, list):
                existing_history = []
            existing_history.append(approval_record.model_dump())
            self._set_nested_value(state, history_key, existing_history)

            # Update metadata
            state.set_metadata(
                f"{self.node_id}_execution",
                {
                    "timestamp": timestamp,
                    "decision": decision.value,
                    "execution_id": execution_id,
                    "approved": approved,
                },
            )

            return HumanApprovalNodeOutput(
                decision=decision,
                feedback=feedback,
                approved=approved,
                timestamp=timestamp,
                execution_id=execution_id,
                approval_record=approval_record,
            )

        except KeyboardInterrupt:
            raise UserCancelledError("User cancelled approval process") from None
        except Exception as e:
            if isinstance(e, (UserCancelledError, ApprovalValidationError)):
                raise
            raise ApprovalValidationError(f"Failed to collect approval: {e}") from e

    def _set_nested_value(self, state: WorkflowState, path: str, value: Any) -> None:
        """Set nested value using dot notation."""
        parts = path.split(".")
        current = state.data

        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise ValueError(
                    f"Cannot set nested path '{path}': '{part}' is not a dict"
                )
            current = current[part]

        # Set final value
        current[parts[-1]] = value
        state.updated_at = datetime.utcnow()
