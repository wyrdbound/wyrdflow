"""Simple 3-node sequential data transformation pipeline example.

This example demonstrates the basic usage of Wyrdflow's BaseNode with:
1. InputNode: Receives raw data and validates it
2. ProcessorNode: Transforms the data by applying operations
3. OutputNode: Formats and outputs the final result

The pipeline flows: raw data → validation → processing → output formatting

This example automatically runs both approaches for comparison:
1. Manual orchestration with direct node execution
2. LangGraph integration using as_langraph_node()

Simply run: python simple_pipeline.py
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from wyrdflow.core import (
    BaseNode,
    NodeConfig,
    NodeContext,
    NodeInput,
    NodeOutput,
    WorkflowState,
)


# Define LangGraph state schema
class GraphState(TypedDict, total=False):
    """State schema for LangGraph workflow."""

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


# Define custom input/output schemas for each node
class RawDataInput(NodeInput):
    """Input schema for receiving raw data."""

    raw_data: list[dict[str, Any]] = Field(
        description="Raw data as list of dictionaries"
    )
    source: str = Field(description="Source of the data")


class ValidatedDataOutput(NodeOutput):
    """Output schema for validated data."""

    validated_data: list[dict[str, Any]] = Field(description="Validated data records")
    validation_summary: dict[str, int] = Field(
        description="Summary of validation results"
    )


# Input schema for the processor node (same data as ValidatedDataOutput but inherits from NodeInput)
class ValidatedDataInput(NodeInput):
    """Input schema for processor node - receives validated data."""

    validated_data: list[dict[str, Any]] = Field(description="Validated data records")
    validation_summary: dict[str, int] = Field(
        description="Summary of validation results"
    )


class ProcessedDataOutput(NodeOutput):
    """Output schema for processed data."""

    processed_data: list[dict[str, Any]] = Field(description="Processed data records")
    processing_stats: dict[str, Any] = Field(description="Statistics about processing")


# Input schema for the output node
class ProcessedDataInput(NodeInput):
    """Input schema for output node - receives processed data."""

    processed_data: list[dict[str, Any]] = Field(description="Processed data records")
    processing_stats: dict[str, Any] = Field(description="Statistics about processing")


class FinalOutput(NodeOutput):
    """Output schema for final formatted result."""

    formatted_result: str = Field(description="Final formatted output")
    record_count: int = Field(description="Total number of records processed")
    success: bool = Field(description="Whether processing was successful")


# Node implementations
class InputNode(BaseNode[RawDataInput, ValidatedDataOutput]):
    """Node that validates and cleans raw input data."""

    input_schema = RawDataInput
    output_schema = ValidatedDataOutput

    async def execute(
        self,
        input_data: RawDataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> ValidatedDataOutput:
        """Validate and clean the raw data."""
        self._logger.info(f"Processing {len(input_data.raw_data)} raw records")

        # Simple validation: ensure each record has required fields
        validated_records = []
        errors = 0

        for record in input_data.raw_data:
            if "id" in record and "value" in record:
                # Clean the record
                cleaned_record = {
                    "id": str(record["id"]),
                    "value": float(record["value"]) if record["value"] else 0.0,
                    "source": input_data.source,
                }
                validated_records.append(cleaned_record)
            else:
                errors += 1
                self._logger.warning(f"Skipping invalid record: {record}")

        # Store validation results in workflow state
        state.set("input_source", input_data.source)
        state.set("validation_errors", errors)

        validation_summary = {
            "total_input": len(input_data.raw_data),
            "valid_records": len(validated_records),
            "errors": errors,
        }

        return ValidatedDataOutput(
            validated_data=validated_records,
            validation_summary=validation_summary,
        )


class ProcessorNode(BaseNode[ValidatedDataInput, ProcessedDataOutput]):
    """Node that transforms validated data."""

    input_schema = ValidatedDataInput
    output_schema = ProcessedDataOutput

    async def execute(
        self,
        input_data: ValidatedDataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> ProcessedDataOutput:
        """Apply transformations to the validated data."""
        self._logger.info(f"Processing {len(input_data.validated_data)} records")

        processed_records = []
        total_value = 0.0

        # Apply some transformations
        for record in input_data.validated_data:
            # Calculate some derived values
            value = record["value"]
            processed_record = {
                "id": record["id"],
                "original_value": value,
                "doubled_value": value * 2,
                "squared_value": value**2,
                "source": record["source"],
                "processing_timestamp": "2024-01-01T00:00:00Z",  # Placeholder
            }
            processed_records.append(processed_record)
            total_value += value

        # Calculate processing statistics
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

        # Update workflow state
        state.set("processing_stats", processing_stats)

        return ProcessedDataOutput(
            processed_data=processed_records,
            processing_stats=processing_stats,
        )


class OutputNode(BaseNode[ProcessedDataInput, FinalOutput]):
    """Node that formats the final output."""

    input_schema = ProcessedDataInput
    output_schema = FinalOutput

    async def execute(
        self,
        input_data: ProcessedDataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,
    ) -> FinalOutput:
        """Format the processed data into final output."""
        self._logger.info("Formatting final output")

        # Get data from previous processing steps
        source = state.get("input_source", "unknown")
        validation_errors = state.get("validation_errors", 0)

        # Create formatted summary
        stats = input_data.processing_stats
        formatted_lines = [
            "Data Processing Summary",
            "=" * 25,
            f"Source: {source}",
            f"Records processed: {stats['total_records']}",
            f"Validation errors: {validation_errors}",
            f"Total value: {stats['total_value']:.2f}",
            f"Average value: {stats['average_value']:.2f}",
            f"Value range: {stats['min_value']:.2f} - {stats['max_value']:.2f}",
            "",
            "Sample processed records:",
        ]

        # Add sample records
        for i, record in enumerate(input_data.processed_data[:3]):  # First 3 records
            formatted_lines.append(
                f"  {i + 1}. ID: {record['id']}, "
                f"Original: {record['original_value']}, "
                f"Doubled: {record['doubled_value']}"
            )

        if len(input_data.processed_data) > 3:
            formatted_lines.append(
                f"  ... and {len(input_data.processed_data) - 3} more"
            )

        formatted_result = "\n".join(formatted_lines)

        return FinalOutput(
            formatted_result=formatted_result,
            record_count=len(input_data.processed_data),
            success=True,
        )


# Create shared node instances used by both approaches
def create_pipeline_nodes():
    """Create the pipeline nodes that will be shared between manual and LangGraph execution."""
    input_node = InputNode(
        node_id="input_validator",
        config=NodeConfig(retry_attempts=2, timeout=30.0),
        name="Data Input Validator",
        description="Validates and cleans raw input data",
    )

    processor_node = ProcessorNode(
        node_id="data_processor",
        config=NodeConfig(retry_attempts=3, timeout=60.0),
        name="Data Transformer",
        description="Applies transformations to validated data",
    )

    output_node = OutputNode(
        node_id="output_formatter",
        config=NodeConfig(retry_attempts=1, timeout=15.0),
        name="Output Formatter",
        description="Formats processed data for final output",
    )

    return input_node, processor_node, output_node


# Create sample data used by both approaches
def create_sample_data():
    """Create the sample data used by both pipeline approaches."""
    return [
        {"id": "A001", "value": 10.5},
        {"id": "A002", "value": 25.0},
        {"id": "A003", "value": 7.8},
        {"id": "A004", "value": None},  # This will cause validation to clean it
        {"id": "A005", "value": 42.3},
        {"missing_id": "bad_record"},  # This will be filtered out
    ]


# Example usage function
async def run_data_pipeline(input_node, processor_node, output_node, raw_data):
    """Run the complete 3-node data transformation pipeline."""
    print("🚀 Starting Wyrdflow Data Transformation Pipeline\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()
    print(f"Created workflow run: {workflow_state.workflow_run_id}")

    # Step 1: Input Node - Validate raw data
    print("\n📥 Step 1: Input Node - Validating data...")

    input_result = await input_node.run(
        {"raw_data": raw_data, "source": "example_dataset"},
        state=workflow_state,
    )
    print(f"✅ Validated {input_result['validation_summary']['valid_records']} records")
    print(f"   Errors: {input_result['validation_summary']['errors']}")

    # Step 2: Processor Node - Transform data
    print("\n⚙️  Step 2: Processor Node - Transforming data...")

    # Convert ValidatedDataOutput to ValidatedDataInput format
    processor_input = {
        "validated_data": input_result["validated_data"],
        "validation_summary": input_result["validation_summary"],
    }

    processed_result = await processor_node.run(processor_input, state=workflow_state)
    print(
        f"✅ Processed {processed_result['processing_stats']['total_records']} records"
    )
    print(
        f"   Average value: {processed_result['processing_stats']['average_value']:.2f}"
    )

    # Step 3: Output Node - Format results
    print("\n📤 Step 3: Output Node - Formatting results...")

    # Convert ProcessedDataOutput to ProcessedDataInput format
    output_input = {
        "processed_data": processed_result["processed_data"],
        "processing_stats": processed_result["processing_stats"],
    }

    final_result = await output_node.run(output_input, state=workflow_state)
    print(f"✅ Generated final output with {final_result['record_count']} records")

    # Display final results
    print("\n" + "=" * 50)
    print("📋 FINAL PIPELINE RESULTS")
    print("=" * 50)
    print(final_result["formatted_result"])
    print("\n🎉 Pipeline completed successfully!")

    return final_result


# LangGraph version of the pipeline
async def run_langgraph_pipeline(input_node, processor_node, output_node, raw_data):
    """Run the same pipeline using LangGraph integration."""
    print("🚀 Starting Wyrdflow + LangGraph Data Transformation Pipeline\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()
    print(f"Created workflow run: {workflow_state.workflow_run_id}")

    # Create LangGraph workflow
    print("🔧 Building LangGraph workflow...")
    graph = StateGraph(GraphState)

    # Add nodes using as_langraph_node()
    graph.add_node("input", input_node.as_langraph_node())
    graph.add_node("processor", processor_node.as_langraph_node())
    graph.add_node("output", output_node.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "input")
    graph.add_edge("input", "processor")
    graph.add_edge("processor", "output")
    graph.add_edge("output", END)

    # Compile the graph
    workflow = graph.compile()
    print("✅ LangGraph workflow compiled successfully")

    # Prepare initial state for LangGraph
    initial_state: GraphState = {
        "input": {"raw_data": raw_data, "source": "example_dataset"},
        "workflow_state": workflow_state.model_dump(),
    }

    print("\n🎯 Executing LangGraph workflow...")

    # Execute the workflow
    result = await workflow.ainvoke(initial_state)

    # Extract final results - LangGraph state contains all data
    print("✅ LangGraph pipeline completed!")
    print(f"   Records processed: {result.get('record_count', 0)}")

    # Display final results
    print("\n" + "=" * 50)
    print("📋 LANGGRAPH PIPELINE RESULTS")
    print("=" * 50)
    if "formatted_result" in result:
        print(result["formatted_result"])
    else:
        print("No formatted result found in final state")
        print("Available keys:", list(result.keys()))
    print("\n🎉 LangGraph pipeline completed successfully!")

    return result


# Example comparison function
async def run_both_examples():
    """Run both manual and LangGraph versions for comparison."""
    print("=" * 60)
    print("🔄 RUNNING BOTH PIPELINE VERSIONS FOR COMPARISON")
    print("=" * 60)

    # Create shared nodes and data once
    print("🔧 Creating shared pipeline nodes...")
    input_node, processor_node, output_node = create_pipeline_nodes()
    raw_data = create_sample_data()
    print("✅ Pipeline nodes created and ready for both approaches\n")

    print("1️⃣ MANUAL ORCHESTRATION VERSION:")
    print("-" * 40)
    await run_data_pipeline(input_node, processor_node, output_node, raw_data)

    print("\n\n2️⃣ LANGGRAPH INTEGRATION VERSION:")
    print("-" * 40)
    await run_langgraph_pipeline(input_node, processor_node, output_node, raw_data)

    print("\n" + "=" * 60)
    print("📊 COMPARISON SUMMARY")
    print("=" * 60)
    print("Both approaches produce equivalent results!")
    print("• Manual: Direct control, explicit state management")
    print("• LangGraph: Workflow orchestration, visual graph structure")
    print("• Same BaseNode instances power both approaches seamlessly!")


# Entry point for the example
if __name__ == "__main__":
    # Always run both approaches for comparison
    asyncio.run(run_both_examples())
