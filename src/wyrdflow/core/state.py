"""Workflow state management classes."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class WorkflowState(BaseModel):
    """Base class for workflow state management.

    This Pydantic model provides full validation and serialization for workflow
    state, ensuring type safety and consistency across workflow execution.

    Required Attributes:
        workflow_id: UUID v4 identifier for the workflow definition
        workflow_run_id: UUID v4 identifier for this specific execution run

    Optional Attributes:
        created_at: Timestamp when the workflow run was created
        updated_at: Timestamp when the state was last updated
        data: Arbitrary state data as key-value pairs
        metadata: Workflow execution metadata
    """

    # Required workflow identifiers
    workflow_id: UUID = Field(
        description="UUID v4 identifier for the workflow definition"
    )
    workflow_run_id: UUID = Field(
        description="UUID v4 identifier for this specific execution run"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the workflow run was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the state was last updated",
    )

    # State data - arbitrary nested objects supported
    data: dict[str, Any] = Field(
        default_factory=dict, description="Workflow state data as key-value pairs"
    )

    # Execution metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Workflow execution metadata"
    )

    model_config = ConfigDict(
        # Allow extra fields for flexibility
        extra="allow",
        # Validate assignments to catch errors early
        validate_assignment=True,
        # Use enum values in serialization
        use_enum_values=True,
        # Enable arbitrary types for complex nested objects
        arbitrary_types_allowed=True,
    )

    @classmethod
    def create_new(
        cls,
        workflow_id: Optional[UUID] = None,
        initial_data: Optional[dict[str, Any]] = None,
        initial_metadata: Optional[dict[str, Any]] = None,
    ) -> "WorkflowState":
        """Create a new workflow state with auto-generated IDs.

        Args:
            workflow_id: Optional workflow ID (generates new UUID if not provided)
            initial_data: Initial state data
            initial_metadata: Initial metadata

        Returns:
            New WorkflowState instance with generated IDs
        """
        return cls(
            workflow_id=workflow_id or uuid4(),
            workflow_run_id=uuid4(),
            data=initial_data or {},
            metadata=initial_metadata or {},
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the state data.

        Args:
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value from state data or default
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the state data.

        Args:
            key: Key to set
            value: Value to set
        """
        self.data[key] = value
        self.updated_at = datetime.utcnow()

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple values in the state data.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        self.data.update(updates)
        self.updated_at = datetime.utcnow()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a value from the metadata.

        Args:
            key: Metadata key to retrieve
            default: Default value if key not found

        Returns:
            Value from metadata or default
        """
        return self.metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a value in the metadata.

        Args:
            key: Metadata key to set
            value: Value to set
        """
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()

    def copy_for_node(self, node_id: str) -> "WorkflowState":
        """Create a copy of the state for node execution.

        This creates a deep copy of the state with updated metadata
        to track which node is currently executing.

        Args:
            node_id: ID of the node that will execute

        Returns:
            New WorkflowState instance for the node
        """
        new_state = self.model_copy(deep=True)
        new_state.set_metadata("current_node_id", node_id)
        new_state.set_metadata(
            "execution_history", [*self.get_metadata("execution_history", []), node_id]
        )
        return new_state


class StateSnapshot(BaseModel):
    """Immutable snapshot of workflow state for restore operations.

    This class provides in-memory snapshot and restore capabilities for
    WorkflowState objects, enabling debugging, testing, and error recovery.
    """

    # Snapshot metadata
    snapshot_id: UUID = Field(default_factory=uuid4, description="Unique snapshot ID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When snapshot was created"
    )
    source_node_id: Optional[str] = Field(
        default=None, description="Node ID where snapshot was taken"
    )

    # Captured state data
    workflow_id: UUID = Field(description="Original workflow ID")
    workflow_run_id: UUID = Field(description="Original workflow run ID")
    state_created_at: datetime = Field(description="Original state creation time")
    state_updated_at: datetime = Field(description="Original state update time")
    data: dict[str, Any] = Field(description="Snapshot of state data")
    metadata: dict[str, Any] = Field(description="Snapshot of state metadata")
    extra_fields: dict[str, Any] = Field(
        default_factory=dict, description="Any extra fields from original state"
    )

    model_config = ConfigDict(
        frozen=True,  # Make snapshots immutable
        arbitrary_types_allowed=True,
    )

    @classmethod
    def from_state(
        cls, state: WorkflowState, source_node_id: Optional[str] = None
    ) -> "StateSnapshot":
        """Create a snapshot from a WorkflowState.

        Args:
            state: The WorkflowState to snapshot
            source_node_id: Optional node ID where snapshot was taken

        Returns:
            Immutable StateSnapshot instance
        """
        # Get all model fields and extra fields
        state_dict = state.model_dump()
        core_fields = {
            "workflow_id",
            "workflow_run_id",
            "created_at",
            "updated_at",
            "data",
            "metadata",
        }
        extra_fields = {k: v for k, v in state_dict.items() if k not in core_fields}

        return cls(
            source_node_id=source_node_id,
            workflow_id=state.workflow_id,
            workflow_run_id=state.workflow_run_id,
            state_created_at=state.created_at,
            state_updated_at=state.updated_at,
            data=state.data.copy(),
            metadata=state.metadata.copy(),
            extra_fields=extra_fields,
        )

    def restore(self) -> WorkflowState:
        """Restore a WorkflowState from this snapshot.

        Returns:
            New WorkflowState instance with data from snapshot
        """
        # Create base state data
        restored_data = {
            "workflow_id": self.workflow_id,
            "workflow_run_id": self.workflow_run_id,
            "created_at": self.state_created_at,
            "updated_at": self.state_updated_at,
            "data": self.data.copy(),
            "metadata": self.metadata.copy(),
        }

        # Add any extra fields
        restored_data.update(self.extra_fields)

        return WorkflowState(**restored_data)  # type: ignore[arg-type]


class StateInspector:
    """Utility class for inspecting and analyzing WorkflowState objects.

    Provides methods for visualizing state, comparing states, and searching
    through state data for debugging and analysis purposes.
    """

    @staticmethod
    def format_state(
        state: WorkflowState, include_metadata: bool = True, max_depth: int = 3
    ) -> str:
        """Format a WorkflowState for human-readable display.

        Args:
            state: The WorkflowState to format
            include_metadata: Whether to include metadata in output
            max_depth: Maximum nesting depth to display

        Returns:
            Formatted string representation of the state
        """
        lines = []
        lines.append("WorkflowState Overview:")
        lines.append(f"  Workflow ID: {state.workflow_id}")
        lines.append(f"  Run ID: {state.workflow_run_id}")
        lines.append(f"  Created: {state.created_at.isoformat()}")
        lines.append(f"  Updated: {state.updated_at.isoformat()}")

        # Format data section
        lines.append(f"\nData ({len(state.data)} keys):")
        if state.data:
            for key, value in state.data.items():
                formatted_value = StateInspector._format_value(value, max_depth)
                lines.append(f"  {key}: {formatted_value}")
        else:
            lines.append("  (empty)")

        # Format metadata section if requested
        if include_metadata:
            lines.append(f"\nMetadata ({len(state.metadata)} keys):")
            if state.metadata:
                for key, value in state.metadata.items():
                    formatted_value = StateInspector._format_value(value, max_depth)
                    lines.append(f"  {key}: {formatted_value}")
            else:
                lines.append("  (empty)")

        return "\n".join(lines)

    @staticmethod
    def _format_value(value: Any, max_depth: int, current_depth: int = 0) -> str:
        """Format a value with depth limiting for readability."""
        if current_depth >= max_depth:
            return "..."

        if isinstance(value, dict):
            return StateInspector._format_dict(value, max_depth, current_depth)
        elif isinstance(value, list):
            return StateInspector._format_list(value, max_depth, current_depth)
        elif isinstance(value, str):
            return StateInspector._format_string(value)
        else:
            return str(value)

    @staticmethod
    def _format_dict(value: dict[str, Any], max_depth: int, current_depth: int) -> str:
        """Format a dictionary value."""
        if not value:
            return "{}"
        if current_depth >= max_depth - 1:
            return f"{{{len(value)} keys}}"

        items = []
        for k, v in list(value.items())[:3]:  # Show max 3 items
            formatted_v = StateInspector._format_value(v, max_depth, current_depth + 1)
            items.append(f"{k}: {formatted_v}")

        result = f"{{{', '.join(items)}"
        if len(value) > 3:
            result += f", ...{len(value) - 3} more"
        result += "}"
        return result

    @staticmethod
    def _format_list(value: list[Any], max_depth: int, current_depth: int) -> str:
        """Format a list value."""
        if not value:
            return "[]"
        if current_depth >= max_depth - 1:
            return f"[{len(value)} items]"

        items = []
        for item in value[:3]:  # Show max 3 items
            formatted_item = StateInspector._format_value(
                item, max_depth, current_depth + 1
            )
            items.append(formatted_item)

        result = f"[{', '.join(items)}"
        if len(value) > 3:
            result += f", ...{len(value) - 3} more"
        result += "]"
        return result

    @staticmethod
    def _format_string(value: str) -> str:
        """Format a string value."""
        if len(value) > 50:
            return f'"{value[:47]}..."'
        return f'"{value}"'

    @staticmethod
    def compare_states(
        state1: WorkflowState, state2: WorkflowState, compare_metadata: bool = False
    ) -> dict[str, Any]:
        """Compare two WorkflowState objects and return differences.

        Args:
            state1: First state to compare
            state2: Second state to compare
            compare_metadata: Whether to include metadata comparison

        Returns:
            Dictionary containing the differences between states
        """
        diff = {
            "workflow_id_changed": state1.workflow_id != state2.workflow_id,
            "workflow_run_id_changed": state1.workflow_run_id != state2.workflow_run_id,
            "time_diff_seconds": (
                state2.updated_at - state1.updated_at
            ).total_seconds(),
            "data_changes": StateInspector._compare_dicts(state1.data, state2.data),
        }

        if compare_metadata:
            diff["metadata_changes"] = StateInspector._compare_dicts(
                state1.metadata, state2.metadata
            )

        return diff

    @staticmethod
    def _compare_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
        """Compare two dictionaries and return structured diff."""
        all_keys = set(dict1.keys()) | set(dict2.keys())

        changes: dict[str, dict[str, Any]] = {
            "added": {},
            "removed": {},
            "modified": {},
            "unchanged": {},
        }

        for key in all_keys:
            if key not in dict1:
                changes["added"][key] = dict2[key]
            elif key not in dict2:
                changes["removed"][key] = dict1[key]
            elif dict1[key] != dict2[key]:
                changes["modified"][key] = {"old": dict1[key], "new": dict2[key]}
            else:
                changes["unchanged"][key] = dict1[key]

        return changes

    @staticmethod
    def search_state(
        state: WorkflowState,
        search_term: str,
        search_keys: bool = True,
        search_values: bool = True,
        case_sensitive: bool = False,
    ) -> list[dict[str, Any]]:
        """Search for a term within the state data and metadata.

        Args:
            state: The WorkflowState to search
            search_term: Term to search for
            search_keys: Whether to search in dictionary keys
            search_values: Whether to search in values
            case_sensitive: Whether search should be case sensitive

        Returns:
            List of search results with path and context information
        """
        results = []

        if not case_sensitive:
            search_term = search_term.lower()

        # Search in data
        results.extend(
            StateInspector._search_dict(
                state.data,
                search_term,
                "data",
                search_keys,
                search_values,
                case_sensitive,
            )
        )

        # Search in metadata
        results.extend(
            StateInspector._search_dict(
                state.metadata,
                search_term,
                "metadata",
                search_keys,
                search_values,
                case_sensitive,
            )
        )

        return results

    @staticmethod
    def _search_dict(
        data: dict[str, Any],
        search_term: str,
        base_path: str,
        search_keys: bool,
        search_values: bool,
        case_sensitive: bool,
        current_path: str = "",
    ) -> list[dict[str, Any]]:
        """Recursively search through a dictionary."""
        results = []

        for key, value in data.items():
            full_path = (
                f"{base_path}.{current_path}.{key}"
                if current_path
                else f"{base_path}.{key}"
            )

            # Search in key names
            if search_keys:
                key_text = key if case_sensitive else str(key).lower()
                if search_term in key_text:
                    results.append(
                        {
                            "type": "key",
                            "path": full_path,
                            "key": key,
                            "value": value,
                            "match_in": "key",
                        }
                    )

            # Search in values
            if search_values:
                if isinstance(value, str):
                    value_text = value if case_sensitive else value.lower()
                    if search_term in value_text:
                        results.append(
                            {
                                "type": "value",
                                "path": full_path,
                                "key": key,
                                "value": value,
                                "match_in": "value",
                            }
                        )
                elif isinstance(value, dict):
                    # Recursively search nested dictionaries
                    nested_results = StateInspector._search_dict(
                        value,
                        search_term,
                        base_path,
                        search_keys,
                        search_values,
                        case_sensitive,
                        f"{current_path}.{key}" if current_path else key,
                    )
                    results.extend(nested_results)
                else:
                    # Convert other types to string and search
                    value_text = str(value)
                    if not case_sensitive:
                        value_text = value_text.lower()
                    if search_term in value_text:
                        results.append(
                            {
                                "type": "value",
                                "path": full_path,
                                "key": key,
                                "value": value,
                                "match_in": "value",
                            }
                        )

        return results
