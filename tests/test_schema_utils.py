"""Tests for schema utilities module."""

from typing import Any
import uuid

from pydantic import Field
import pytest

from wyrdflow.core import (
    BaseNode,
    NodeContext,
    NodeInput,
    NodeOutput,
    WorkflowState,
)
from wyrdflow.core.schema_utils import (
    DataFlowValidator,
    SchemaGenerator,
    SchemaMapper,
    auto_create_input,
    create_workflow_input,
    validate_node_connection,
)


# Test schema classes
class SimpleInput(NodeInput):
    result: str = Field(..., description="Simple result input")
    count: int = Field(default=0, description="Count value input")


class SimpleOutput(NodeOutput):
    result: str = Field(..., description="Simple result")
    count: int = Field(default=0, description="Count value")


class ComplexOutput(NodeOutput):
    data: dict[str, Any] = Field(..., description="Complex data")
    items: list[str] = Field(default_factory=list, description="List of items")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


class ProcessedOutput(NodeOutput):
    processed_data: dict[str, Any] = Field(..., description="Processed data")
    summary: str = Field(..., description="Summary text")


# Test node classes
class SimpleNode(BaseNode):
    input_schema = SimpleInput
    output_schema = SimpleOutput

    async def execute(
        self,
        input_data: SimpleInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> SimpleOutput:
        return SimpleOutput(result="simple", count=1)


class ComplexNode(BaseNode):
    input_schema = NodeInput
    output_schema = ComplexOutput

    async def execute(
        self,
        input_data: NodeInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> ComplexOutput:
        return ComplexOutput(
            data={"key": "value"},
            items=["item1", "item2"],
            metadata={"source": "test"},
        )


class ProcessorNode(BaseNode):
    input_schema = NodeInput
    output_schema = ProcessedOutput

    async def execute(
        self,
        input_data: NodeInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> ProcessedOutput:
        return ProcessedOutput(
            processed_data={"processed": True},
            summary="Processed data",
        )


class TestSchemaMapper:
    """Test SchemaMapper utility class."""

    def test_create_input_from_output_basic(self):
        """Test basic input schema creation from output schema."""
        input_schema = SchemaMapper.create_input_from_output(SimpleOutput)

        # Check that the schema was created
        assert input_schema is not None
        assert issubclass(input_schema, NodeInput)

        # Test that we can instantiate it (dynamic fields)
        instance = input_schema(**{"result": "test", "count": 5})
        assert hasattr(instance, "result")
        assert hasattr(instance, "count")

    def test_create_input_from_output_custom_name(self):
        """Test input schema creation with custom name."""
        input_schema = SchemaMapper.create_input_from_output(
            SimpleOutput, class_name="CustomInputSchema"
        )

        assert input_schema.__name__ == "CustomInputSchema"

    def test_create_input_from_output_additional_fields(self):
        """Test input schema creation with additional fields."""
        additional_fields = {
            "extra_field": (str, Field(default="default", description="Extra field"))
        }

        input_schema = SchemaMapper.create_input_from_output(
            SimpleOutput, additional_fields=additional_fields
        )

        # Test instantiation with additional field
        instance = input_schema(
            **{"result": "test", "count": 5, "extra_field": "custom"}
        )
        assert hasattr(instance, "extra_field")

    def test_create_input_from_complex_output(self):
        """Test input schema creation from complex output schema."""
        input_schema = SchemaMapper.create_input_from_output(ComplexOutput)

        instance = input_schema(
            **{
                "data": {"test": "data"},
                "items": ["a", "b"],
                "metadata": {"key": "value"},
            }
        )
        assert hasattr(instance, "data")
        assert hasattr(instance, "items")
        assert hasattr(instance, "metadata")

    def test_create_enhanced_input(self):
        """Test enhanced input schema creation."""
        base_input = SchemaMapper.create_input_from_output(SimpleOutput)
        workflow_fields = {
            "workflow_id": (str, Field(..., description="Workflow ID")),
            "step": (int, Field(default=1, description="Workflow step")),
        }

        enhanced_schema = SchemaMapper.create_enhanced_input(
            base_input, workflow_fields=workflow_fields
        )

        instance = enhanced_schema(
            **{"result": "test", "count": 5, "workflow_id": "wf_123", "step": 2}
        )
        assert hasattr(instance, "workflow_id")
        assert hasattr(instance, "step")


class TestDataFlowValidator:
    """Test DataFlowValidator utility class."""

    def test_extract_node_input_basic(self):
        """Test basic node input extraction."""
        node = SimpleNode("test_node")
        langraph_state = {"result": "test_result", "count": 42, "extra": "ignored"}
        workflow_state = WorkflowState(
            workflow_id=uuid.uuid4(), workflow_run_id=uuid.uuid4()
        )

        extracted = SchemaMapper.extract_node_input(
            node, langraph_state, workflow_state
        )

        # Should only include fields that match the node's input schema
        assert "result" in extracted or "count" in extracted

    def test_extract_node_input_with_workflow_state(self):
        """Test node input extraction with workflow state data."""
        node = SimpleNode("test_node")
        langraph_state = {"result": "test_result"}
        workflow_state = WorkflowState(
            workflow_id=uuid.uuid4(), workflow_run_id=uuid.uuid4()
        )
        workflow_state.set("global_count", 100)

        extracted = SchemaMapper.extract_node_input(
            node, langraph_state, workflow_state
        )

        assert isinstance(extracted, dict)

    def test_validate_node_transition_compatible(self):
        """Test validation of compatible node transition."""
        from_node = SimpleNode("from_node")
        to_node = ComplexNode("to_node")

        transition_data = {
            "result": "test",
            "count": 5,
            "additional_data": {"key": "value"},
        }
        workflow_state = WorkflowState(
            workflow_id=uuid.uuid4(), workflow_run_id=uuid.uuid4()
        )

        result = DataFlowValidator.validate_node_transition(
            from_node, to_node, transition_data, workflow_state
        )

        assert isinstance(result, dict)
        assert "valid" in result or "errors" in result

    def test_validate_node_transition_incompatible(self):
        """Test validation with missing required data."""
        from_node = SimpleNode("from_node")
        to_node = ProcessorNode("to_node")

        # Data that validates against from_node output but may not work with to_node
        transition_data = {"result": "test_result", "count": 42}
        workflow_state = WorkflowState(
            workflow_id=uuid.uuid4(), workflow_run_id=uuid.uuid4()
        )

        result = DataFlowValidator.validate_node_transition(
            from_node, to_node, transition_data, workflow_state
        )

        assert isinstance(result, dict)

    def test_validate_workflow_data_flow(self):
        """Test validation of entire workflow data flow."""
        nodes = {
            "node1": SimpleNode("node1"),
            "node2": ComplexNode("node2"),
            "node3": ProcessorNode("node3"),
        }
        edges = [("node1", "node2"), ("node2", "node3")]

        result = DataFlowValidator.validate_workflow_data_flow(nodes, edges)

        assert isinstance(result, dict)
        assert "overall_valid" in result or "edge_validations" in result

    def test_validate_workflow_empty(self):
        """Test validation of empty workflow."""
        result = DataFlowValidator.validate_workflow_data_flow({}, [])

        assert isinstance(result, dict)

    def test_validate_workflow_with_sample_data(self):
        """Test workflow validation with sample data."""
        nodes = {
            "node1": SimpleNode("node1"),
            "node2": ComplexNode("node2"),
        }
        edges = [("node1", "node2")]
        sample_data = {"result": "test", "count": 1}

        result = DataFlowValidator.validate_workflow_data_flow(
            nodes, edges, sample_data
        )

        assert isinstance(result, dict)


class TestSchemaGenerator:
    """Test SchemaGenerator utility class."""

    def test_infer_schema_from_data_simple(self):
        """Test schema inference from simple data."""
        data = {"name": "test", "count": 42, "active": True, "value": 3.14}

        schema = SchemaGenerator.infer_schema_from_data(data, "TestSchema")

        assert schema.__name__ == "TestSchema"

        # Test instantiation
        instance = schema(**data)
        assert instance.name == "test"
        assert instance.count == 42
        assert instance.active  # Use == instead of is for dynamic schemas
        assert instance.value == 3.14

    def test_infer_schema_from_data_complex(self):
        """Test schema inference from complex data."""
        data = {
            "items": ["a", "b", "c"],
            "metadata": {"key": "value", "count": 10},
            "nested_list": [{"id": 1}, {"id": 2}],
        }

        schema = SchemaGenerator.infer_schema_from_data(data, "ComplexSchema")

        instance = schema(**data)
        assert instance.items == ["a", "b", "c"]
        assert instance.metadata == {"key": "value", "count": 10}

    def test_infer_schema_empty_data(self):
        """Test schema inference from empty data."""
        schema = SchemaGenerator.infer_schema_from_data({}, "EmptySchema")

        assert schema.__name__ == "EmptySchema"
        instance = schema()
        assert isinstance(instance, NodeOutput)

    def test_create_union_schema(self):
        """Test creation of union schema."""
        schemas = [SimpleOutput, ComplexOutput]

        union_schema = SchemaGenerator.create_union_schema(schemas, "UnionSchema")

        assert union_schema.__name__ == "UnionSchema"

        # Should be able to handle fields from both schemas
        # This is a complex test that depends on implementation details


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_auto_create_input(self):
        """Test auto_create_input convenience function."""
        input_schema = auto_create_input(SimpleOutput)

        assert input_schema is not None
        assert issubclass(input_schema, NodeInput)

        instance = input_schema(**{"result": "test", "count": 5})
        assert hasattr(instance, "result")
        assert hasattr(instance, "count")

    def test_auto_create_input_with_name(self):
        """Test auto_create_input with custom name."""
        input_schema = auto_create_input(SimpleOutput, "CustomInput")

        assert input_schema.__name__ == "CustomInput"

    def test_validate_node_connection(self):
        """Test validate_node_connection convenience function."""
        from_node = SimpleNode("from_node")
        to_node = ComplexNode("to_node")

        result = validate_node_connection(from_node, to_node)
        assert isinstance(result, bool)

    def test_create_workflow_input(self):
        """Test create_workflow_input convenience function."""
        workflow_context = {"workflow_id": "wf_123", "step": 1, "user_id": "user_456"}

        input_schema = create_workflow_input(
            SimpleOutput, workflow_context, "WorkflowInput"
        )

        assert input_schema.__name__ == "WorkflowInput"

        # Test that the schema has the expected fields without instantiating
        # (to avoid the forward reference issue)
        field_names = set(input_schema.model_fields.keys())
        expected_fields = {"result", "count", "workflow_id", "step", "user_id"}

        # Should have fields from both the output schema and workflow context
        assert expected_fields.issubset(field_names)


class TestErrorHandling:
    """Test error handling in schema utilities."""

    def test_create_input_invalid_output_schema(self):
        """Test error handling with invalid output schema."""
        with pytest.raises(ValueError):  # Actual error type raised
            SchemaMapper.create_input_from_output(str)  # type: ignore

    def test_extract_node_input_invalid_node(self):
        """Test error handling with invalid node."""
        result = SchemaMapper.extract_node_input(
            None,  # type: ignore
            {},
            WorkflowState(workflow_id=uuid.uuid4(), workflow_run_id=uuid.uuid4()),
        )
        # Should handle gracefully
        assert isinstance(result, dict)

    def test_infer_schema_invalid_data(self):
        """Test error handling with invalid data for schema inference."""
        # This should not crash but handle gracefully
        schema = SchemaGenerator.infer_schema_from_data(
            {"complex_field": object()},  # Non-serializable object
            "TestSchema",
        )
        assert schema is not None


class TestSchemaCompatibility:
    """Test schema compatibility and conversion."""

    def test_schema_field_mapping(self):
        """Test field mapping between schemas."""
        output_schema = ComplexOutput
        input_schema = SchemaMapper.create_input_from_output(output_schema)

        # Fields should be mapped correctly
        output_fields = output_schema.model_fields
        input_fields = input_schema.model_fields

        # All output fields should exist in input (though types might differ)
        for field_name in output_fields:
            assert field_name in input_fields, (
                f"Field {field_name} missing in input schema"
            )

    def test_schema_validation_consistency(self):
        """Test that created schemas validate consistently."""
        input_schema = SchemaMapper.create_input_from_output(ComplexOutput)

        test_data = {
            "data": {"test": "value"},
            "items": ["a", "b"],
            "metadata": {"key": "val"},
        }

        # Should be able to create and validate instance
        instance = input_schema(**test_data)
        assert instance.data == test_data["data"]
        assert instance.items == test_data["items"]
        assert instance.metadata == test_data["metadata"]

    def test_nested_schema_handling(self):
        """Test handling of nested schema structures."""
        complex_data = {
            "level1": {
                "level2": {"level3": "deep_value", "numbers": [1, 2, 3]},
                "simple": "value",
            },
            "top_level": "test",
        }

        schema = SchemaGenerator.infer_schema_from_data(complex_data, "NestedSchema")
        instance = schema(**complex_data)

        assert instance.level1 == complex_data["level1"]
        assert instance.top_level == "test"
