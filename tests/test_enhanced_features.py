"""Tests for enhanced LangGraph integration features."""

from pydantic import Field
import pytest

from wyrdflow.core import (
    BaseNode,
    NodeContext,
    NodeInput,
    NodeOutput,
    SchemaInference,
    SchemaMapper,
    WorkflowState,
    auto_create_input,
    create_enhanced_node,
    get_registry,
    pin_node_output,
    register_node,
    unpin_node_output,
    validate_node_connection,
)


# Test schemas
class ExampleOutput(NodeOutput):
    """Test output schema."""

    result: str = Field(description="Test result")
    count: int = Field(description="Test count")


class ExampleInput(NodeInput):
    """Test input schema."""

    data: str = Field(description="Test data")


class SimpleTestNode(BaseNode[ExampleInput, ExampleOutput]):
    """Simple test node for enhanced features."""

    input_schema = ExampleInput
    output_schema = ExampleOutput

    async def execute(
        self, input_data: ExampleInput, context: NodeContext, state: WorkflowState
    ) -> ExampleOutput:
        return ExampleOutput(
            result=f"processed_{input_data.data}", count=len(input_data.data)
        )


class TestEnhancedFeatures:
    """Test suite for enhanced LangGraph integration features."""

    def test_auto_create_input_schema(self):
        """Test automatic input schema creation from output schema."""
        # Create input schema from output schema
        AutoInput = auto_create_input(ExampleOutput, "AutoTestInput")

        # Verify the schema was created correctly
        assert AutoInput.__name__ == "AutoTestInput"
        assert issubclass(AutoInput, NodeInput)

        # Check fields are copied
        fields = AutoInput.model_fields
        assert "result" in fields
        assert "count" in fields

        # Test instantiation (dynamic fields)
        instance = AutoInput(**{"result": "test", "count": 5})
        assert instance.result == "test"
        assert instance.count == 5

    def test_schema_inference_compatibility(self):
        """Test schema compatibility checking between nodes."""
        # Create nodes with compatible schemas
        node1 = SimpleTestNode("node1")

        # Create a node that accepts TestOutput as input
        CompatibleInput = auto_create_input(ExampleOutput, "CompatibleInput")

        class CompatibleNode(BaseNode):
            def __init__(self, node_id: str):
                super().__init__(node_id)
                self.input_schema = CompatibleInput
                self.output_schema = ExampleOutput

            async def execute(
                self,
                input_data: CompatibleInput,
                context: NodeContext,
                state: WorkflowState,
            ) -> ExampleOutput:
                return ExampleOutput(result="compatible", count=1)

        node2 = CompatibleNode("node2")

        # Test compatibility

        can_connect, issues = SchemaInference.can_connect(node1, node2)
        assert can_connect
        assert len(issues) == 0

        # Test convenience function
        assert validate_node_connection(node1, node2)

    def test_output_pinning(self):
        """Test output pinning functionality."""
        node = SimpleTestNode("test_node")

        # Initially not pinned
        assert not node.config.is_output_pinned()

        # Pin output
        pinned_data = {"result": "pinned_result", "count": 999}
        pin_node_output(node, pinned_data)

        # Verify pinned
        assert node.config.is_output_pinned()
        assert node.config.pinned_output == pinned_data

        # Unpin
        unpin_node_output(node)
        assert not node.config.is_output_pinned()
        assert node.config.pinned_output is None

    @pytest.mark.asyncio
    async def test_pinned_output_execution(self):
        """Test that pinned output is returned instead of executing."""
        node = SimpleTestNode("test_node")

        # Pin output with compatible data
        pinned_output = ExampleOutput(result="pinned", count=42)
        pin_node_output(node, pinned_output)

        # Execute with any input - should return pinned output
        workflow_state = WorkflowState.create_new()
        context = NodeContext(
            workflow_id=workflow_state.workflow_id,
            workflow_run_id=workflow_state.workflow_run_id,
            node_id=node.node_id,
        )

        result = await node.run(
            {"data": "any_input"}, context=context, state=workflow_state
        )

        # Should return pinned data, not processed input
        assert result["result"] == "pinned"
        assert result["count"] == 42

    def test_create_enhanced_node(self):
        """Test enhanced node creation with configuration overrides."""
        enhanced_node = create_enhanced_node(
            SimpleTestNode,
            "enhanced_test",
            config_overrides={
                "retry_attempts": 5,
                "timeout": 120.0,
                "enable_logging": False,
            },
            name="Enhanced Test Node",
            description="A test node with enhanced configuration",
        )

        # Verify configuration was applied
        assert enhanced_node.config.retry_attempts == 5
        assert enhanced_node.config.timeout == 120.0
        assert enhanced_node.config.enable_logging is False
        assert enhanced_node.name == "Enhanced Test Node"
        assert enhanced_node.description == "A test node with enhanced configuration"

    def test_node_registry_integration(self):
        """Test node registry functionality."""
        registry = get_registry()
        initial_count = len(registry.list_nodes())

        # Register a node type
        register_node(
            SimpleTestNode,
            name="Simple Test Node",
            description="A simple test node for unit testing",
            category="Testing",
            tags=["test", "simple"],
        )

        # Verify registration
        nodes = registry.list_nodes()
        assert len(nodes) == initial_count + 1

        # Find our registered node
        test_nodes = registry.find_nodes(category="Testing")
        assert len(test_nodes) > 0

        tagged_nodes = registry.find_nodes(tag="test")
        assert len(tagged_nodes) > 0

        # Get node info
        node_info = registry.get_node_info("Simple Test Node")
        assert node_info is not None
        assert node_info.description == "A simple test node for unit testing"
        assert "test" in node_info.tags

    def test_schema_mapper_extract_input(self):
        """Test schema mapper input extraction from state."""
        # Create a node with specific input requirements
        node = SimpleTestNode("mapper_test")

        # Create sample LangGraph state
        langraph_state = {
            "data": "test_data",
            "extra_field": "extra_value",
            "workflow_state": {},
            "context": {},
            "last_node": "previous",
        }

        # Create workflow state
        workflow_state = WorkflowState.create_new()
        workflow_state.set("additional_data", "from_workflow")

        # Extract input data
        extracted = SchemaMapper.extract_node_input(
            node, langraph_state, workflow_state
        )

        # Should contain the data field that the node needs
        assert "data" in extracted
        assert extracted["data"] == "test_data"

        # Should not contain internal fields
        assert "workflow_state" not in extracted
        assert "context" not in extracted

    def test_enhanced_input_schema_creation(self):
        """Test creation of enhanced input schemas with workflow fields."""
        # Create base input schema
        base_input = auto_create_input(ExampleOutput, "BaseInput")

        # Create enhanced version with additional workflow fields
        enhanced_input = SchemaMapper.create_enhanced_input(
            base_input,
            workflow_fields={
                "iteration": (int, Field(description="Iteration number")),
                "source": (str, Field(description="Data source")),
            },
            class_name="TestEnhancedInput",
        )

        # Verify enhanced schema
        assert enhanced_input.__name__ == "TestEnhancedInput"
        fields = enhanced_input.model_fields

        # Should have original fields
        assert "result" in fields
        assert "count" in fields

        # Should have additional workflow fields
        assert "iteration" in fields
        assert "source" in fields

        # Test instantiation (dynamic fields)
        instance = enhanced_input(
            **{"result": "test", "count": 5, "iteration": 1, "source": "test_source"}
        )
        assert instance.iteration == 1
        assert instance.source == "test_source"


if __name__ == "__main__":
    # Run a simple test
    test_suite = TestEnhancedFeatures()
    test_suite.test_auto_create_input_schema()
    test_suite.test_output_pinning()
    test_suite.test_create_enhanced_node()
    print("✅ All basic tests passed!")
