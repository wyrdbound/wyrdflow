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
