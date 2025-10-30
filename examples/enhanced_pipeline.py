"""Enhanced simple pipeline example demonstrating new Wyrdflow features.

This example demonstrates the enhanced LangGraph integration capabilities including:
1. Automatic schema creation from output schemas
2. Output pinning for testing
3. Node registry usage
4. Enhanced validation and workflow analysis
5. Schema inference and compatibility checking

Run this after the original simple_pipeline.py to see the enhanced features.
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from wyrdflow.core import (
    BaseNode,
    NodeContext,
    NodeInput,
    NodeOutput,
    SchemaInference,
    SchemaMapper,
    WorkflowAnalyzer,
    WorkflowState,
    # New enhanced features
    auto_create_input,
    create_enhanced_node,
    get_registry,
    pin_node_output,
    register_node,
    unpin_node_output,
    validate_node_connection,
)


# Base schemas using the new capabilities
class EnhancedRawDataInput(NodeInput):
    """Input schema for receiving raw data."""

    raw_data: list[dict[str, Any]] = Field(
        description="Raw data as list of dictionaries"
    )
    source: str = Field(description="Source of the data")


class EnhancedValidatedDataOutput(NodeOutput):
    """Output schema for validated data."""

    validated_data: list[dict[str, Any]] = Field(description="Validated data records")
    validation_summary: dict[str, int] = Field(
        description="Summary of validation results"
    )


class EnhancedProcessedDataOutput(NodeOutput):
    """Output schema for processed data."""

    processed_data: list[dict[str, Any]] = Field(description="Processed data records")
    processing_stats: dict[str, Any] = Field(description="Statistics about processing")


class EnhancedFinalOutput(NodeOutput):
    """Output schema for final formatted result."""

    formatted_result: str = Field(description="Final formatted output")
    record_count: int = Field(description="Total number of records processed")
    success: bool = Field(description="Whether processing was successful")


# Automatically create compatible input schemas
EnhancedValidatedDataInput = auto_create_input(
    EnhancedValidatedDataOutput, "EnhancedValidatedDataInput"
)

# Create enhanced input schema with additional WorkflowState fields
EnhancedProcessedDataInput = SchemaMapper.create_enhanced_input(
    auto_create_input(EnhancedProcessedDataOutput, "ProcessedDataInput"),
    workflow_fields={
        "iteration_count": (
            int,
            Field(default=0, description="Current iteration number"),
        ),
        "source_system": (
            str,
            Field(default="unknown", description="Original data source"),
        ),
    },
    class_name="EnhancedProcessedDataInput",
)


# Enhanced node implementations with new features
class EnhancedInputNode(BaseNode[EnhancedRawDataInput, EnhancedValidatedDataOutput]):
    """Enhanced input node with registry integration."""

    input_schema = EnhancedRawDataInput
    output_schema = EnhancedValidatedDataOutput

    async def execute(
        self,
        input_data: EnhancedRawDataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> EnhancedValidatedDataOutput:
        """Validate and clean the raw data with enhanced features."""
        self._logger.info(
            f"Enhanced processing of {len(input_data.raw_data)} raw records"
        )

        validated_records = []
        errors = 0

        for record in input_data.raw_data:
            if "id" in record and "value" in record:
                cleaned_record = {
                    "id": str(record["id"]),
                    "value": float(record["value"]) if record["value"] else 0.0,
                    "source": input_data.source,
                }
                validated_records.append(cleaned_record)
            else:
                errors += 1
                self._logger.warning(f"Skipping invalid record: {record}")

        # Store additional metadata in WorkflowState
        state.set("input_source", input_data.source)
        state.set("validation_errors", errors)
        state.set("source_system", input_data.source)
        state.set("iteration_count", 1)

        validation_summary = {
            "total_input": len(input_data.raw_data),
            "valid_records": len(validated_records),
            "errors": errors,
        }

        return EnhancedValidatedDataOutput(
            validated_data=validated_records,
            validation_summary=validation_summary,
        )


class EnhancedProcessorNode(BaseNode):
    """Enhanced processor node with automatic schema compatibility."""

    def __init__(self, *args, **kwargs):
        # Set schemas dynamically
        self.input_schema = EnhancedValidatedDataInput
        self.output_schema = EnhancedProcessedDataOutput
        super().__init__(*args, **kwargs)

    async def execute(
        self,
        input_data: Any,  # Use Any since schema is set dynamically
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> EnhancedProcessedDataOutput:
        """Process data with enhanced validation."""
        self._logger.info(
            f"Enhanced processing of {len(input_data.validated_data)} records"
        )

        processed_records = []
        total_value = 0.0

        for record in input_data.validated_data:
            value = record["value"]
            processed_record = {
                "id": record["id"],
                "original_value": value,
                "doubled_value": value * 2,
                "squared_value": value**2,
                "source": record["source"],
                "processing_timestamp": "2024-01-01T00:00:00Z",
            }
            processed_records.append(processed_record)
            total_value += value

        processing_stats = {
            "total_records": len(processed_records),
            "total_value": total_value,
            "average_value": total_value / len(processed_records)
            if processed_records
            else 0,
            "max_value": max(
                (r["original_value"] for r in processed_records), default=0
            ),
            "min_value": min(
                (r["original_value"] for r in processed_records), default=0
            ),
        }

        # Update iteration count
        current_iteration = state.get("iteration_count", 0)
        state.set("iteration_count", current_iteration + 1)
        state.set("processing_stats", processing_stats)

        return EnhancedProcessedDataOutput(
            processed_data=processed_records,
            processing_stats=processing_stats,
        )


class EnhancedOutputNode(BaseNode):
    """Enhanced output node with WorkflowState integration."""

    def __init__(self, *args, **kwargs):
        # Set schemas dynamically
        self.input_schema = EnhancedProcessedDataInput
        self.output_schema = EnhancedFinalOutput
        super().__init__(*args, **kwargs)

    async def execute(
        self,
        input_data: Any,  # Use Any since schema is set dynamically
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> EnhancedFinalOutput:
        """Format final output with enhanced context."""
        self._logger.info("Enhanced formatting of final output")

        # Access additional context from WorkflowState and input schema
        source = (
            input_data.source_system
            if hasattr(input_data, "source_system")
            else state.get("input_source", "unknown")
        )
        iteration_count = (
            input_data.iteration_count
            if hasattr(input_data, "iteration_count")
            else state.get("iteration_count", 0)
        )
        validation_errors = state.get("validation_errors", 0)

        stats = input_data.processing_stats
        formatted_lines = [
            "Enhanced Data Processing Summary",
            "=" * 35,
            f"Source System: {source}",
            f"Iteration Count: {iteration_count}",
            f"Records processed: {stats['total_records']}",
            f"Validation errors: {validation_errors}",
            f"Total value: {stats['total_value']:.2f}",
            f"Average value: {stats['average_value']:.2f}",
            f"Value range: {stats['min_value']:.2f} - {stats['max_value']:.2f}",
            "",
            "Enhanced sample processed records:",
        ]

        # Add sample records
        for i, record in enumerate(input_data.processed_data[:3]):
            formatted_lines.append(
                f"  {i + 1}. ID: {record['id']}, "
                f"Original: {record['original_value']}, "
                f"Enhanced: {record['doubled_value']}"
            )

        if len(input_data.processed_data) > 3:
            formatted_lines.append(
                f"  ... and {len(input_data.processed_data) - 3} more"
            )

        formatted_result = "\n".join(formatted_lines)

        return EnhancedFinalOutput(
            formatted_result=formatted_result,
            record_count=len(input_data.processed_data),
            success=True,
        )


def create_enhanced_pipeline_nodes():
    """Create enhanced pipeline nodes with new configuration options."""

    # Create nodes with enhanced configuration
    input_node = create_enhanced_node(
        EnhancedInputNode,
        "enhanced_input_validator",
        config_overrides={
            "retry_attempts": 2,
            "timeout": 30.0,
            "enable_logging": True,
        },
        name="Enhanced Data Input Validator",
        description="Validates and cleans raw input data with enhanced features",
    )

    processor_node = create_enhanced_node(
        EnhancedProcessorNode,
        "enhanced_data_processor",
        config_overrides={
            "retry_attempts": 3,
            "timeout": 60.0,
        },
        name="Enhanced Data Transformer",
        description="Applies transformations with automatic schema compatibility",
    )

    output_node = create_enhanced_node(
        EnhancedOutputNode,
        "enhanced_output_formatter",
        config_overrides={
            "retry_attempts": 1,
            "timeout": 15.0,
        },
        name="Enhanced Output Formatter",
        description="Formats processed data with WorkflowState integration",
    )

    return input_node, processor_node, output_node


def register_enhanced_nodes():
    """Register the enhanced nodes in the global registry."""
    registry = get_registry()

    register_node(
        EnhancedInputNode,
        name="Enhanced Input Validator",
        description="Validates raw data with enhanced error handling and metadata tracking",
        category="Data Input",
        tags=["validation", "input", "enhanced"],
    )

    register_node(
        EnhancedProcessorNode,
        name="Enhanced Data Processor",
        description="Processes validated data with automatic schema compatibility",
        category="Data Processing",
        tags=["processing", "transformation", "enhanced"],
    )

    register_node(
        EnhancedOutputNode,
        name="Enhanced Output Formatter",
        description="Formats final output with WorkflowState integration",
        category="Data Output",
        tags=["formatting", "output", "enhanced"],
    )

    print(f"✅ Registered {len(registry.list_nodes())} node types in registry")


async def demonstrate_output_pinning():
    """Demonstrate output pinning for testing scenarios."""
    print("\n🧪 DEMONSTRATING OUTPUT PINNING FOR TESTING")
    print("=" * 50)

    # Create nodes
    input_node, processor_node, _output_node = create_enhanced_pipeline_nodes()

    # Pin the processor node output to skip expensive processing
    pinned_processing_result = {
        "processed_data": [
            {
                "id": "TEST001",
                "original_value": 100.0,
                "doubled_value": 200.0,
                "squared_value": 10000.0,
                "source": "test",
                "processing_timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "id": "TEST002",
                "original_value": 50.0,
                "doubled_value": 100.0,
                "squared_value": 2500.0,
                "source": "test",
                "processing_timestamp": "2024-01-01T00:00:00Z",
            },
        ],
        "processing_stats": {
            "total_records": 2,
            "total_value": 150.0,
            "average_value": 75.0,
            "max_value": 100.0,
            "min_value": 50.0,
        },
    }

    pin_node_output(processor_node, pinned_processing_result)
    print(
        f"📌 Pinned output for {processor_node.node_id} - will skip expensive processing"
    )

    # Run a test with pinned output
    workflow_state = WorkflowState.create_new()

    # Run input node normally
    input_result = await input_node.run(
        {"raw_data": [{"id": "A001", "value": 10.5}], "source": "test_dataset"},
        state=workflow_state,
    )
    print(
        f"✅ Input node executed normally, validated {len(input_result['validated_data'])} records"
    )

    # Run processor node with pinned output (will skip execution)
    processor_input = {
        "validated_data": input_result["validated_data"],
        "validation_summary": input_result["validation_summary"],
    }

    processor_result = await processor_node.run(processor_input, state=workflow_state)
    print(
        f"📌 Processor node used pinned output, returned {len(processor_result['processed_data'])} records"
    )

    # Unpin for normal operation
    unpin_node_output(processor_node)
    print("🔓 Unpinned processor node output")

    # Run again normally
    processor_result_normal = await processor_node.run(
        processor_input, state=workflow_state
    )
    print(
        f"✅ Processor node executed normally, processed {len(processor_result_normal['processed_data'])} records"
    )


async def demonstrate_schema_validation():
    """Demonstrate schema validation and compatibility checking."""
    print("\n🔍 DEMONSTRATING SCHEMA VALIDATION")
    print("=" * 40)

    # Create nodes
    input_node, processor_node, output_node = create_enhanced_pipeline_nodes()

    # Check node compatibility
    can_connect_1_2 = validate_node_connection(input_node, processor_node)
    can_connect_2_3 = validate_node_connection(processor_node, output_node)

    print(f"✅ Input → Processor compatibility: {can_connect_1_2}")
    print(f"✅ Processor → Output compatibility: {can_connect_2_3}")

    # Detailed schema analysis
    compatibility_1_2 = SchemaInference.can_connect(input_node, processor_node)
    print(f"📋 Detailed analysis (Input → Processor): {compatibility_1_2}")

    compatibility_2_3 = SchemaInference.can_connect(processor_node, output_node)
    print(f"📋 Detailed analysis (Processor → Output): {compatibility_2_3}")

    # Workflow analysis
    analyzer = WorkflowAnalyzer()
    analyzer.add_node("input", input_node)
    analyzer.add_node("processor", processor_node)
    analyzer.add_node("output", output_node)
    analyzer.add_edge("input", "processor")
    analyzer.add_edge("processor", "output")

    analysis = analyzer.analyze()
    print("\n📊 Workflow Analysis:")
    print(f"   Nodes: {analysis['node_count']}")
    print(f"   Edges: {analysis['edge_count']}")
    print(f"   Schema Compatible: {analysis['schema_compatibility']['compatible']}")
    print(f"   Node Types: {analysis['node_types']['type_distribution']}")

    if analysis["recommendations"]:
        print(f"💡 Recommendations: {analysis['recommendations']}")


async def demonstrate_enhanced_langgraph_workflow():
    """Demonstrate the enhanced LangGraph workflow with all new features."""
    print("\n🚀 ENHANCED LANGGRAPH WORKFLOW")
    print("=" * 40)

    # Create nodes
    input_node, processor_node, output_node = create_enhanced_pipeline_nodes()

    # Create enhanced LangGraph state schema
    class EnhancedGraphState(TypedDict, total=False):
        """Enhanced state schema for LangGraph workflow."""

        input: dict[str, Any]
        validated_data: list[dict[str, Any]]
        validation_summary: dict[str, int]
        processed_data: list[dict[str, Any]]
        processing_stats: dict[str, Any]
        formatted_result: str
        record_count: int
        success: bool
        workflow_state: dict[str, Any]
        last_node: str
        # Enhanced fields
        iteration_count: int
        source_system: str
        enhanced_metadata: dict[str, Any]

    # Create and execute workflow
    graph = StateGraph(EnhancedGraphState)

    # Add nodes using as_langraph_node()
    graph.add_node("input", input_node.as_langraph_node())
    graph.add_node("processor", processor_node.as_langraph_node())
    graph.add_node("output", output_node.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "input")
    graph.add_edge("input", "processor")
    graph.add_edge("processor", "output")
    graph.add_edge("output", END)

    # Compile and execute
    workflow = graph.compile()

    # Prepare enhanced initial state
    workflow_state = WorkflowState.create_new()
    initial_state: EnhancedGraphState = {
        "input": {
            "raw_data": [
                {"id": "E001", "value": 15.5},
                {"id": "E002", "value": 30.0},
                {"id": "E003", "value": 12.8},
            ],
            "source": "enhanced_dataset",
        },
        "workflow_state": workflow_state.model_dump(),
        "enhanced_metadata": {
            "version": "2.0",
            "enhanced_features": True,
        },
    }

    print("🎯 Executing enhanced LangGraph workflow...")
    result = await workflow.ainvoke(initial_state)

    print("✅ Enhanced workflow completed!")
    print(f"   Records processed: {result.get('record_count', 0)}")
    print(f"   Iterations: {result.get('iteration_count', 0)}")
    print(f"   Source system: {result.get('source_system', 'unknown')}")

    # Display results
    print("\n" + "=" * 50)
    print("📋 ENHANCED WORKFLOW RESULTS")
    print("=" * 50)
    if "formatted_result" in result:
        print(result["formatted_result"])
    else:
        print("No formatted result found")


async def run_enhanced_demonstrations():
    """Run all enhanced feature demonstrations."""
    print("🌟 WYRDFLOW ENHANCED FEATURES DEMONSTRATION")
    print("=" * 60)

    # Register enhanced nodes
    register_enhanced_nodes()

    # Run all demonstrations
    await demonstrate_output_pinning()
    await demonstrate_schema_validation()
    await demonstrate_enhanced_langgraph_workflow()

    print("\n" + "=" * 60)
    print("🎉 ENHANCED FEATURES DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("Key enhancements demonstrated:")
    print("✅ Automatic schema creation and compatibility")
    print("✅ Output pinning for testing scenarios")
    print("✅ Node registry and metadata tracking")
    print("✅ Enhanced validation and workflow analysis")
    print("✅ WorkflowState integration with schema mapping")
    print("✅ Seamless LangGraph integration with enhanced features")


if __name__ == "__main__":
    asyncio.run(run_enhanced_demonstrations())
