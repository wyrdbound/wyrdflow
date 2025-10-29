"""Base schema classes for node input and output validation."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NodeInput(BaseModel):
    """Base class for all node input schemas.

    Users should inherit from this class to define typed inputs for their nodes.
    This provides automatic validation and serialization via Pydantic.

    Example:
        class MyNodeInput(NodeInput):
            text: str
            max_length: int = 100
            options: List[str] = []
    """

    model_config = ConfigDict(
        # Allow extra fields for flexibility but validate known fields
        extra="allow",
        # Validate assignments to catch errors early
        validate_assignment=True,
        # Use enum values in serialization
        use_enum_values=True,
        # Enable arbitrary types (for complex objects)
        arbitrary_types_allowed=True,
    )


class NodeOutput(BaseModel):
    """Base class for all node output schemas.

    Users should inherit from this class to define typed outputs for their nodes.
    This ensures consistent output structure and validation.

    Example:
        class MyNodeOutput(NodeOutput):
            result: str
            confidence: float
            metadata: Dict[str, Any] = {}
    """

    model_config = ConfigDict(
        # Allow extra fields for flexibility but validate known fields
        extra="allow",
        # Validate assignments to catch errors early
        validate_assignment=True,
        # Use enum values in serialization
        use_enum_values=True,
        # Enable arbitrary types (for complex objects)
        arbitrary_types_allowed=True,
    )


class NodeContext(BaseModel):
    """Context information passed to nodes during execution.

    This contains metadata about the workflow execution that nodes may need
    to access, such as the workflow ID, run ID, and current execution state.
    """

    workflow_id: UUID
    workflow_run_id: UUID
    node_id: str
    execution_metadata: dict[str, Any] = {}

    model_config = ConfigDict(
        # Don't allow extra fields to keep context clean
        extra="forbid",
        # Validate assignments
        validate_assignment=True,
        # Use enum values
        use_enum_values=True,
    )
