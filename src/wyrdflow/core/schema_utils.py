"""Advanced input/output validation and schema inference utilities.

This module provides utilities for automatic schema alignment between nodes,
runtime validation of data flow, and enhanced schema compatibility checking.
"""

import logging
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field, ValidationError, create_model

from .base import BaseNode
from .langraph_utils import SchemaInference
from .schemas import NodeInput, NodeOutput
from .state import WorkflowState

logger = logging.getLogger(__name__)

# Type variables
InputSchemaType = TypeVar("InputSchemaType", bound=NodeInput)
OutputSchemaType = TypeVar("OutputSchemaType", bound=NodeOutput)


class SchemaMapper:
    """Utilities for mapping between node schemas and state data.

    This class provides methods to automatically create compatible input schemas
    from output schemas, validate data flow between nodes, and handle access
    to additional WorkflowState data.
    """

    @staticmethod
    def create_input_from_output(
        output_schema: type[NodeOutput],
        class_name: Optional[str] = None,
        additional_fields: Optional[dict[str, Any]] = None,
    ) -> type[NodeInput]:
        """Create a NodeInput schema from a NodeOutput schema.

        This automatically creates a compatible input schema that includes all
        fields from the output schema, allowing seamless data flow between nodes.

        Args:
            output_schema: The output schema to base the input schema on
            class_name: Optional name for the new input schema class
            additional_fields: Optional additional fields to include

        Returns:
            New NodeInput class compatible with the output schema

        Example:
            ```python
            # Automatically create input schema from output
            ProcessorInput = SchemaMapper.create_input_from_output(
                ValidatedDataOutput,
                "ProcessorInput"
            )

            # With additional fields from WorkflowState
            ProcessorInput = SchemaMapper.create_input_from_output(
                ValidatedDataOutput,
                "ProcessorInput",
                additional_fields={
                    "iteration_count": (int, Field(default=0, description="Current iteration")),
                    "previous_validation": (bool, Field(default=True, description="Previous validation result"))
                }
            )
            ```
        """
        if not issubclass(output_schema, NodeOutput):
            raise ValueError("output_schema must be a subclass of NodeOutput")

        # Get all fields from the output schema
        output_fields = output_schema.model_fields

        # Create field definitions for the new input schema
        field_definitions = {}

        # Copy fields from output schema
        for field_name, field_info in output_fields.items():
            # Get the field's annotation and info
            annotation = field_info.annotation

            # Create new field info, preserving the original configuration
            new_field_info = Field(
                default=field_info.default,
                description=field_info.description,
                validation_alias=field_info.validation_alias,
                serialization_alias=field_info.serialization_alias,
            )

            field_definitions[field_name] = (annotation, new_field_info)

        # Add additional fields if provided
        if additional_fields:
            for field_name, field_def in additional_fields.items():
                if isinstance(field_def, tuple) and len(field_def) == 2:
                    annotation, field_info = field_def
                    field_definitions[field_name] = (annotation, field_info)
                else:
                    # Assume it's just the type annotation
                    field_definitions[field_name] = (field_def, Field())

        # Generate class name if not provided
        if not class_name:
            output_name = output_schema.__name__
            if output_name.endswith("Output"):
                class_name = output_name.replace("Output", "Input")
            else:
                class_name = f"{output_name}Input"

        # Create the new input schema class
        input_schema = create_model(class_name, __base__=NodeInput, **field_definitions)  # type: ignore[call-overload]

        # Add metadata
        input_schema.__doc__ = (
            f"Auto-generated input schema from {output_schema.__name__}"
        )

        logger.info(f"Created input schema {class_name} from {output_schema.__name__}")
        return input_schema  # type: ignore[no-any-return]

    @staticmethod
    def create_enhanced_input(
        base_schema: type[NodeInput],
        workflow_fields: Optional[dict[str, Any]] = None,
        class_name: Optional[str] = None,
    ) -> type[NodeInput]:
        """Create an enhanced input schema with additional WorkflowState fields.

        This allows nodes to access additional data from the WorkflowState
        beyond just the output of the previous node.

        Args:
            base_schema: Base input schema to enhance
            workflow_fields: Additional fields to access from WorkflowState
            class_name: Optional name for the enhanced schema

        Returns:
            Enhanced input schema with additional fields

        Example:
            ```python
            # Add workflow context fields
            EnhancedInput = SchemaMapper.create_enhanced_input(
                ProcessorInput,
                workflow_fields={
                    "iteration_count": (int, Field(description="Current iteration number")),
                    "validation_errors": (int, Field(description="Total validation errors")),
                    "source_system": (str, Field(description="Original data source")),
                },
                class_name="EnhancedProcessorInput"
            )
            ```
        """
        if not issubclass(base_schema, NodeInput):
            raise ValueError("base_schema must be a subclass of NodeInput")

        # Get existing fields
        base_fields = base_schema.model_fields
        field_definitions = {}

        # Copy fields from base schema
        for field_name, field_info in base_fields.items():
            annotation = field_info.annotation
            new_field_info = Field(
                default=field_info.default,
                description=field_info.description,
                validation_alias=field_info.validation_alias,
                serialization_alias=field_info.serialization_alias,
            )
            field_definitions[field_name] = (annotation, new_field_info)

        # Add workflow fields
        if workflow_fields:
            for field_name, field_def in workflow_fields.items():
                if isinstance(field_def, tuple) and len(field_def) == 2:
                    annotation, field_info = field_def
                    field_definitions[field_name] = (annotation, field_info)
                else:
                    field_definitions[field_name] = (field_def, Field())

        # Generate class name if not provided
        if not class_name:
            class_name = f"Enhanced{base_schema.__name__}"

        # Create enhanced schema
        enhanced_schema = create_model(
            class_name, __base__=NodeInput, **field_definitions
        )  # type: ignore[call-overload]

        enhanced_schema.__doc__ = (
            f"Enhanced version of {base_schema.__name__} with WorkflowState access"
        )

        logger.info(f"Created enhanced input schema {class_name}")
        return enhanced_schema  # type: ignore[no-any-return]

    @staticmethod
    def extract_node_input(
        node: "BaseNode[Any, Any]",
        langraph_state: dict[str, Any],
        workflow_state: WorkflowState,
    ) -> dict[str, Any]:
        """Extract and prepare input data for a node from LangGraph state and WorkflowState.

        This method handles the complex logic of extracting the right data for a node's
        input schema, including data from previous nodes and additional WorkflowState data.

        Args:
            node: The node to prepare input for
            langraph_state: Current LangGraph state dictionary
            workflow_state: Current WorkflowState object

        Returns:
            Dictionary of input data ready for the node
        """
        if not hasattr(node, "input_schema"):
            return {}

        input_schema = node.input_schema
        input_fields = input_schema.model_fields
        extracted_data = {}

        # First, try to get data from direct node output in LangGraph state
        # This mirrors the logic in as_langraph_node()
        if "input" in langraph_state and "last_node" not in langraph_state:
            # First node - use explicit input
            direct_data = langraph_state["input"]
        else:
            # Subsequent nodes - use the entire state as input
            direct_data = langraph_state.copy()
            # Remove internal LangGraph metadata
            internal_keys = {"workflow_state", "context", "last_node", "input"}
            for key in internal_keys:
                direct_data.pop(key, None)

        # Extract fields that are available in the direct data
        for field_name in input_fields:
            if field_name in direct_data:
                extracted_data[field_name] = direct_data[field_name]

        # For any missing fields, try to get them from WorkflowState
        missing_fields = set(input_fields.keys()) - set(extracted_data.keys())
        for field_name in missing_fields:
            if field_name in workflow_state.data:
                extracted_data[field_name] = workflow_state.get(field_name)

        return extracted_data


class DataFlowValidator:
    """Runtime validation utilities for data flowing between nodes.

    This class provides methods to validate data compatibility at runtime,
    ensuring that data flowing through the workflow matches expected schemas.
    """

    @staticmethod
    def validate_node_transition(
        from_node: "BaseNode[Any, Any]",
        to_node: "BaseNode[Any, Any]",
        transition_data: dict[str, Any],
        workflow_state: WorkflowState,
    ) -> dict[str, Any]:
        """Validate data transition between two nodes.

        Args:
            from_node: Source node
            to_node: Target node
            transition_data: Data being passed between nodes
            workflow_state: Current WorkflowState for additional context

        Returns:
            Validation results with success status and any issues
        """
        results: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "data_mapping": {},
        }

        # Validate output from source node
        if hasattr(from_node, "output_schema"):
            try:
                from_node.validate_output(transition_data)
                results["data_mapping"]["source_validation"] = "passed"
            except ValidationError as e:
                results["valid"] = False
                results["errors"].append(f"Source node output validation failed: {e}")
                results["data_mapping"]["source_validation"] = "failed"

        # Prepare input data for target node
        target_input_data = SchemaMapper.extract_node_input(
            to_node, transition_data, workflow_state
        )

        # Validate input for target node
        if hasattr(to_node, "input_schema"):
            try:
                to_node.validate_input(target_input_data)
                results["data_mapping"]["target_validation"] = "passed"
            except ValidationError as e:
                results["valid"] = False
                results["errors"].append(f"Target node input validation failed: {e}")
                results["data_mapping"]["target_validation"] = "failed"

        # Check for data loss (fields in output that won't be used by input)
        if hasattr(from_node, "output_schema") and hasattr(to_node, "input_schema"):
            output_fields = set(from_node.output_schema.model_fields.keys())
            input_fields = set(to_node.input_schema.model_fields.keys())

            unused_fields = output_fields - input_fields
            if unused_fields:
                results["warnings"].append(f"Unused output fields: {unused_fields}")
                results["data_mapping"]["unused_fields"] = list(unused_fields)

        return results

    @staticmethod
    def validate_workflow_data_flow(
        nodes: "dict[str, BaseNode[Any, Any]]",
        edges: list[tuple[str, str]],
        sample_data: Optional[dict[str, Any]] = None,  # noqa: ARG004
    ) -> dict[str, Any]:
        """Validate data flow across an entire workflow.

        Args:
            nodes: Dictionary mapping node IDs to BaseNode instances
            edges: List of (from_node_id, to_node_id) tuples
            sample_data: Optional sample data to validate against

        Returns:
            Comprehensive validation results for the entire workflow
        """
        results: dict[str, Any] = {
            "valid": True,
            "edge_validations": {},
            "global_issues": [],
            "recommendations": [],
        }

        # Validate each edge
        for from_id, to_id in edges:
            if from_id not in nodes or to_id not in nodes:
                results["valid"] = False
                results["global_issues"].append(
                    f"Unknown nodes in edge: {from_id} -> {to_id}"
                )
                continue

            from_node = nodes[from_id]
            to_node = nodes[to_id]

            # For now, validate schema compatibility (no sample data needed)
            edge_key = f"{from_id} -> {to_id}"

            # Check basic schema compatibility
            if hasattr(from_node, "output_schema") and hasattr(to_node, "input_schema"):
                from_schema = from_node.output_schema
                to_schema = to_node.input_schema

                # Check field overlap
                from_fields = set(from_schema.model_fields.keys())
                to_required_fields = {
                    name
                    for name, field in to_schema.model_fields.items()
                    if field.is_required()
                }

                missing_required = to_required_fields - from_fields
                if missing_required:
                    results["valid"] = False
                    results["edge_validations"][edge_key] = {
                        "valid": False,
                        "missing_required_fields": list(missing_required),
                    }
                else:
                    results["edge_validations"][edge_key] = {
                        "valid": True,
                        "available_fields": list(
                            from_fields & set(to_schema.model_fields.keys())
                        ),
                    }
            else:
                results["edge_validations"][edge_key] = {
                    "valid": True,
                    "note": "One or both nodes missing schema - cannot validate",
                }

        # Generate recommendations
        if not results["valid"]:
            results["recommendations"].append(
                "Fix schema compatibility issues before deployment"
            )

        # Check for potential workflow state dependencies
        for node_id, node in nodes.items():
            if hasattr(node, "input_schema"):
                # This is a simplified check - in practice, you'd analyze actual field usage
                field_count = len(node.input_schema.model_fields)
                if field_count > 10:
                    results["recommendations"].append(
                        f"Node {node_id} has many input fields ({field_count}) - consider using WorkflowState for some data"
                    )

        return results


class SchemaGenerator:
    """Generator utilities for creating schema classes dynamically.

    This class provides utilities for generating schema classes based on
    actual data structures, runtime analysis, and workflow patterns.
    """

    @staticmethod
    def infer_schema_from_data(
        data: dict[str, Any],
        schema_name: str,
        base_class: type[BaseModel] = NodeOutput,
    ) -> type[BaseModel]:
        """Infer a Pydantic schema from actual data.

        Args:
            data: Sample data to infer schema from
            schema_name: Name for the generated schema class
            base_class: Base class to inherit from (NodeInput or NodeOutput)

        Returns:
            Generated Pydantic schema class
        """
        field_definitions = {}

        for key, value in data.items():
            # Infer type from value
            field_type: type[Any]
            if isinstance(value, str):
                field_type = str
            elif isinstance(value, int):
                field_type = int
            elif isinstance(value, float):
                field_type = float
            elif isinstance(value, bool):
                field_type = bool
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    field_type = list[dict[str, Any]]
                else:
                    field_type = list[Any]
            elif isinstance(value, dict):
                field_type = dict[str, Any]
            else:
                field_type = type(value)  # fallback to runtime type

            # Create field with inferred type
            field_definitions[key] = (
                field_type,
                Field(description=f"Inferred field: {key}"),
            )

        # Create the schema class
        schema_class = create_model(
            schema_name, __base__=base_class, **field_definitions
        )  # type: ignore[call-overload]

        schema_class.__doc__ = "Auto-inferred schema from sample data"

        logger.info(
            f"Generated schema {schema_name} with {len(field_definitions)} fields"
        )
        return schema_class  # type: ignore[no-any-return]

    @staticmethod
    def create_union_schema(
        schemas: list[type[BaseModel]],
        schema_name: str,
        base_class: type[BaseModel] = NodeInput,
    ) -> type[BaseModel]:
        """Create a union schema that can handle multiple input types.

        Args:
            schemas: List of schema classes to combine
            schema_name: Name for the union schema
            base_class: Base class to inherit from

        Returns:
            Union schema that accepts fields from any of the input schemas
        """
        all_fields = {}

        # Collect all fields from all schemas
        for schema in schemas:
            for field_name, field_info in schema.model_fields.items():
                if field_name not in all_fields:
                    # Make all fields optional in the union (since they come from different sources)
                    annotation = field_info.annotation
                    # Make it optional by wrapping in Optional
                    optional_annotation = (
                        Optional[annotation] if annotation else Optional[Any]
                    )

                    new_field_info = Field(
                        default=None,
                        description=f"From {schema.__name__}: {field_info.description or field_name}",
                    )

                    all_fields[field_name] = (optional_annotation, new_field_info)

        # Create union schema
        union_schema = create_model(schema_name, __base__=base_class, **all_fields)  # type: ignore[call-overload]

        union_schema.__doc__ = (
            f"Union schema combining: {[s.__name__ for s in schemas]}"
        )

        logger.info(f"Created union schema {schema_name} from {len(schemas)} schemas")
        return union_schema  # type: ignore[no-any-return]


# Convenience functions for common operations
def auto_create_input(
    output_schema: type[NodeOutput], name: Optional[str] = None
) -> type[NodeInput]:
    """Convenience function to automatically create input schema from output schema.

    Args:
        output_schema: Output schema to base input on
        name: Optional name for the input schema

    Returns:
        Compatible input schema
    """
    return SchemaMapper.create_input_from_output(output_schema, name)


def validate_node_connection(
    from_node: "BaseNode[Any, Any]", to_node: "BaseNode[Any, Any]"
) -> bool:
    """Convenience function to check if two nodes can be connected.

    Args:
        from_node: Source node
        to_node: Target node

    Returns:
        True if nodes are compatible, False otherwise
    """
    can_connect, _ = SchemaInference.can_connect(from_node, to_node)
    return can_connect


def create_workflow_input(
    base_output: type[NodeOutput],
    workflow_context: dict[str, Any],
    name: Optional[str] = None,
) -> type[NodeInput]:
    """Create an input schema that combines node output with workflow context.

    Args:
        base_output: Base output schema from previous node
        workflow_context: Additional context fields from WorkflowState
        name: Optional name for the combined schema

    Returns:
        Combined input schema
    """
    input_schema = SchemaMapper.create_input_from_output(base_output, name)
    return SchemaMapper.create_enhanced_input(input_schema, workflow_context, name)
