"""Human input node for collecting user input during workflow execution."""

from abc import ABC, abstractmethod
from datetime import datetime
from types import GenericAlias
from typing import Any, Callable, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rich.console import Console
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors."""

    pass


class UserCancelledError(WorkflowExecutionError):
    """Raised when user cancels input collection."""

    pass


class InputValidationError(WorkflowExecutionError):
    """Raised when input validation fails after max attempts."""

    pass


class FieldValidationResult(BaseModel):
    """Result of field validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)


class FieldConfig(BaseModel):
    """Configuration for a single input field."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(description="Field name for display and state key")
    field_type: Union[type, GenericAlias] = Field(
        description="Python type (str, int, list, etc.)"
    )
    prompt: str = Field(description="User-facing prompt text")
    required: bool = Field(default=True)
    validation_fn: Optional[Callable[[Any], FieldValidationResult]] = Field(
        default=None
    )
    default_value: Optional[Any] = Field(default=None)
    help_text: Optional[str] = Field(default=None)


class InputInterface(ABC):
    """Abstract base for input collection interfaces."""

    @abstractmethod
    def collect_field(self, field_config: FieldConfig) -> Any:
        """Collect a single field value."""
        pass

    @abstractmethod
    def show_error(self, message: str) -> None:
        """Display error message to user."""
        pass

    @abstractmethod
    def show_help(self, message: str) -> None:
        """Display help text to user."""
        pass


class RichCLIInterface(InputInterface):
    """Rich terminal-based input collection."""

    def __init__(self) -> None:
        self.console = Console()

    def collect_field(self, field_config: FieldConfig) -> Any:
        """Collect input for a single field using Rich prompts."""
        # Display prompt and help text
        self.console.print(f"\n[bold cyan]{field_config.prompt}[/bold cyan]")

        if field_config.help_text:
            self.console.print(f"[dim]{field_config.help_text}[/dim]")

        # Handle different field types
        if field_config.field_type is bool:
            return self._collect_bool_input(field_config)
        if field_config.field_type is int:
            return self._collect_int_input(field_config)
        if field_config.field_type is float:
            return self._collect_float_input(field_config)
        if field_config.field_type == list[str]:
            return self._collect_list_input(field_config)
        # Default to string
        return self._collect_string_input(field_config)

    def _collect_string_input(self, field_config: FieldConfig) -> str:
        """Collect string input with default value support."""
        prompt_text = "Enter value"
        default_val = field_config.default_value or None

        value = Prompt.ask(prompt_text, default=default_val)
        return str(value) if value is not None else ""

    def _collect_int_input(self, field_config: FieldConfig) -> int:
        """Collect integer input."""
        prompt_text = "Enter integer"
        default_val = (
            int(field_config.default_value)
            if field_config.default_value is not None
            else None
        )

        result = IntPrompt.ask(prompt_text, default=default_val)
        return int(result) if result is not None else 0

    def _collect_float_input(self, field_config: FieldConfig) -> float:
        """Collect float input."""
        prompt_text = "Enter number"
        default_val = (
            float(field_config.default_value)
            if field_config.default_value is not None
            else None
        )

        result = FloatPrompt.ask(prompt_text, default=default_val)
        return float(result) if result is not None else 0.0

    def _collect_bool_input(self, field_config: FieldConfig) -> bool:
        """Collect boolean input."""
        default_val = (
            bool(field_config.default_value)
            if field_config.default_value is not None
            else False
        )
        result = Confirm.ask("Confirm", default=default_val)
        return bool(result) if result is not None else False

    def _collect_list_input(self, _field_config: FieldConfig) -> list[str]:
        """Collect list of strings (multi-line input)."""
        self.console.print("[dim]Enter one item per line. Empty line to finish:[/dim]")
        items: list[str] = []

        while True:
            line = Prompt.ask(f"Item {len(items) + 1}")
            if not line.strip():
                break
            items.append(line.strip())

        return items

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[red]Error: {message}[/red]")

    def show_help(self, message: str) -> None:
        """Display help text."""
        self.console.print(f"[blue]Help: {message}[/blue]")


class HumanInputNodeInput(NodeInput):
    """Input configuration for HumanInputNode."""

    fields: list[FieldConfig] = Field(description="List of fields to collect")
    output_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description=("Map field names to state paths (e.g., {'genre': 'plot.genre'})"),
    )
    max_retry_attempts: int = Field(
        default=3, description="Max retry attempts per field"
    )

    @field_validator("output_mapping")
    @classmethod
    def validate_state_paths(
        cls, v: Optional[dict[str, str]]
    ) -> Optional[dict[str, str]]:
        """Validate that state paths don't conflict."""
        if not v:
            return v

        paths = list(v.values())
        for i, path1 in enumerate(paths):
            for path2 in paths[i + 1 :]:
                if cls._paths_conflict(path1, path2):
                    raise ValueError(f"State paths conflict: {path1} and {path2}")
        return v

    @staticmethod
    def _paths_conflict(path1: str, path2: str) -> bool:
        """Check if two paths conflict (one is prefix of another)."""
        parts1 = path1.split(".")
        parts2 = path2.split(".")

        min_len = min(len(parts1), len(parts2))
        return parts1[:min_len] == parts2[:min_len]


class HumanInputNodeOutput(NodeOutput):
    """Output from HumanInputNode containing collected field values."""

    collected_fields: dict[str, Any] = Field(
        description="Dictionary of collected field values"
    )
    fields_collected: list[str] = Field(
        description="List of field names that were collected"
    )
    execution_id: str = Field(description="Unique execution identifier")


class HumanInputNode(BaseNode[HumanInputNodeInput, HumanInputNodeOutput]):
    """Node that collects human input via configurable interface."""

    input_schema = HumanInputNodeInput
    output_schema = HumanInputNodeOutput

    def __init__(
        self,
        node_id: str,
        interface: Optional[InputInterface] = None,
        **kwargs: Any,
    ):
        super().__init__(node_id=node_id, **kwargs)
        self.interface = interface or RichCLIInterface()

    async def execute(
        self,
        input_data: HumanInputNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> HumanInputNodeOutput:
        """Execute human input collection."""
        results: dict[str, Any] = {}

        try:
            for field_config in input_data.fields:
                results[field_config.name] = self._collect_field_with_validation(
                    field_config, input_data.max_retry_attempts
                )

            # Apply output mapping to state if provided
            if input_data.output_mapping:
                for field_name, state_path in input_data.output_mapping.items():
                    if field_name in results:
                        self._set_nested_value(state, state_path, results[field_name])
            else:
                # Default: put all fields under node_id key
                state.set(f"{self.node_id}_input", results)

            # Update metadata
            execution_id = str(uuid4())
            state.set_metadata(
                f"{self.node_id}_execution",
                {
                    "timestamp": datetime.utcnow(),
                    "fields_collected": list(results.keys()),
                    "execution_id": execution_id,
                },
            )

            return HumanInputNodeOutput(
                collected_fields=results,
                fields_collected=list(results.keys()),
                execution_id=execution_id,
            )

        except KeyboardInterrupt:
            raise UserCancelledError("User cancelled workflow execution") from None
        except Exception as e:
            if isinstance(e, (UserCancelledError, InputValidationError)):
                raise
            raise InputValidationError(f"Failed to collect valid input: {e}") from e

    def _collect_field_with_validation(
        self, field_config: FieldConfig, max_attempts: int
    ) -> Any:
        """Collect a single field with validation and retry logic."""
        for attempt in range(max_attempts):
            try:
                # Collect input
                value = self.interface.collect_field(field_config)

                # Validate if validation function provided
                if field_config.validation_fn:
                    validation_result = field_config.validation_fn(value)
                    if not validation_result.is_valid:
                        for error in validation_result.errors:
                            self.interface.show_error(error)

                        if attempt < max_attempts - 1:
                            self.interface.show_error(
                                f"Please try again ({attempt + 1}/{max_attempts})"
                            )
                            continue
                        else:
                            raise InputValidationError(
                                f"Field '{field_config.name}' validation "
                                f"failed: {validation_result.errors}"
                            )

                # Check required field - be careful about falsy values
                if field_config.required and self._is_empty_value(
                    value, field_config.field_type
                ):
                    self.interface.show_error(
                        f"Field '{field_config.name}' is required"
                    )
                    if attempt < max_attempts - 1:
                        continue
                    else:
                        raise InputValidationError(
                            f"Required field '{field_config.name}' cannot be empty"
                        )

                return value

            except KeyboardInterrupt:
                raise  # Re-raise to be handled at higher level
            except (InputValidationError, UserCancelledError):
                raise  # Re-raise our own exceptions
            except Exception as e:
                if attempt < max_attempts - 1:
                    self.interface.show_error(f"Error: {e}. Please try again.")
                    continue
                raise InputValidationError(
                    f"Failed to collect field '{field_config.name}': {e}"
                ) from e

        # This should never be reached but satisfies type checker
        raise InputValidationError(f"Failed to collect field '{field_config.name}'")

    def _is_empty_value(
        self, value: Any, field_type: Union[type, GenericAlias]
    ) -> bool:
        """Check if a value is considered empty for a required field."""
        # None is always empty
        if value is None:
            return True

        # For strings, empty string is empty
        if field_type is str:
            return bool(value == "")

        # For booleans, False is a valid value, not empty
        if field_type is bool:
            return False

        # For numbers, 0 is a valid value, not empty
        if field_type in (int, float):
            return False

        # For lists, empty list is empty
        if field_type == list[str] or (
            isinstance(field_type, GenericAlias)
            and getattr(field_type, "__origin__", None) is list
        ):
            return bool(len(value) == 0)

        # For other types, use truthiness but be conservative
        return bool(not value)

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
