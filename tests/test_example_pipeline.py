"""Tests for the simple pipeline example."""

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from wyrdflow.core import NodeConfig, WorkflowState

# Add examples directory to Python path
examples_dir = Path(__file__).parent.parent / "examples"
sys.path.insert(0, str(examples_dir))

from simple_pipeline import (  # noqa: E402
    FinalOutput,
    InputNode,
    OutputNode,
    ProcessedDataInput,
    ProcessedDataOutput,
    ProcessorNode,
    RawDataInput,
    ValidatedDataInput,
    ValidatedDataOutput,
    run_data_pipeline,
)


class TestPipelineSchemas:
    """Test the pipeline schema classes."""

    def test_raw_data_input_validation(self):
        """Test RawDataInput schema validation."""
        data = {"raw_data": [{"id": "A001", "value": 10.5}], "source": "test_source"}

        input_obj = RawDataInput(**data)

        assert input_obj.raw_data == [{"id": "A001", "value": 10.5}]
        assert input_obj.source == "test_source"

    def test_validated_data_output_validation(self):
        """Test ValidatedDataOutput schema validation."""
        data = {
            "validated_data": [{"id": "A001", "value": 10.5, "source": "test"}],
            "validation_summary": {"total_input": 1, "valid_records": 1, "errors": 0},
        }

        output_obj = ValidatedDataOutput(**data)

        assert len(output_obj.validated_data) == 1
        assert output_obj.validation_summary["errors"] == 0

    def test_processed_data_output_validation(self):
        """Test ProcessedDataOutput schema validation."""
        data = {
            "processed_data": [{"id": "A001", "original_value": 10.5}],
            "processing_stats": {"total_records": 1, "total_value": 10.5},
        }

        output_obj = ProcessedDataOutput(**data)

        assert len(output_obj.processed_data) == 1
        assert output_obj.processing_stats["total_value"] == 10.5

    def test_final_output_validation(self):
        """Test FinalOutput schema validation."""
        data = {"formatted_result": "Test result", "record_count": 5, "success": True}

        output_obj = FinalOutput(**data)

        assert output_obj.formatted_result == "Test result"
        assert output_obj.record_count == 5
        assert output_obj.success is True


class TestInputNode:
    """Test the InputNode implementation."""

    @pytest.mark.asyncio
    async def test_input_node_valid_data(self):
        """Test InputNode with valid data."""
        node = InputNode(
            node_id="test_input",
            config=NodeConfig(retry_attempts=1),
        )

        raw_input = {
            "raw_data": [
                {"id": "A001", "value": 10.5},
                {"id": "A002", "value": 25.0},
                {"id": "A003", "value": 7.8},
            ],
            "source": "test_dataset",
        }

        state = WorkflowState.create_new()
        result = await node.run(raw_input, state=state)

        assert len(result["validated_data"]) == 3
        assert result["validation_summary"]["total_input"] == 3
        assert result["validation_summary"]["valid_records"] == 3
        assert result["validation_summary"]["errors"] == 0

        # Check state was updated
        assert state.get("input_source") == "test_dataset"
        assert state.get("validation_errors") == 0

    @pytest.mark.asyncio
    async def test_input_node_with_invalid_records(self):
        """Test InputNode with some invalid records."""
        node = InputNode(node_id="test_input")

        raw_input = {
            "raw_data": [
                {"id": "A001", "value": 10.5},  # Valid
                {"missing_id": "bad_record"},  # Invalid - no id
                {"id": "A002", "value": None},  # Valid - None value converted to 0.0
                {"id": "A003"},  # Invalid - no value
            ],
            "source": "mixed_dataset",
        }

        state = WorkflowState.create_new()
        result = await node.run(raw_input, state=state)

        assert len(result["validated_data"]) == 2  # Only 2 valid records
        assert result["validation_summary"]["total_input"] == 4
        assert result["validation_summary"]["valid_records"] == 2
        assert result["validation_summary"]["errors"] == 2

        # Check that None value was converted to 0.0
        valid_records = result["validated_data"]
        a002_record = next(r for r in valid_records if r["id"] == "A002")
        assert a002_record["value"] == 0.0

    @pytest.mark.asyncio
    async def test_input_node_empty_data(self):
        """Test InputNode with empty data."""
        node = InputNode(node_id="test_input")

        raw_input = {"raw_data": [], "source": "empty_dataset"}

        result = await node.run(raw_input)

        assert len(result["validated_data"]) == 0
        assert result["validation_summary"]["total_input"] == 0
        assert result["validation_summary"]["valid_records"] == 0
        assert result["validation_summary"]["errors"] == 0


class TestProcessorNode:
    """Test the ProcessorNode implementation."""

    @pytest.mark.asyncio
    async def test_processor_node_basic_processing(self):
        """Test ProcessorNode with basic data processing."""
        node = ProcessorNode(node_id="test_processor")

        input_data = {
            "validated_data": [
                {"id": "A001", "value": 10.0, "source": "test"},
                {"id": "A002", "value": 20.0, "source": "test"},
            ],
            "validation_summary": {"total_input": 2, "valid_records": 2, "errors": 0},
        }

        state = WorkflowState.create_new()
        result = await node.run(input_data, state=state)

        processed_data = result["processed_data"]
        assert len(processed_data) == 2

        # Check transformations
        a001_record = next(r for r in processed_data if r["id"] == "A001")
        assert a001_record["original_value"] == 10.0
        assert a001_record["doubled_value"] == 20.0
        assert a001_record["squared_value"] == 100.0

        # Check processing stats
        stats = result["processing_stats"]
        assert stats["total_records"] == 2
        assert stats["total_value"] == 30.0  # 10 + 20
        assert stats["average_value"] == 15.0
        assert stats["max_value"] == 20.0
        assert stats["min_value"] == 10.0

        # Check state was updated
        assert state.get("processing_stats") == stats

    @pytest.mark.asyncio
    async def test_processor_node_empty_data(self):
        """Test ProcessorNode with empty data."""
        node = ProcessorNode(node_id="test_processor")

        input_data = {
            "validated_data": [],
            "validation_summary": {"total_input": 0, "valid_records": 0, "errors": 0},
        }

        result = await node.run(input_data)

        assert len(result["processed_data"]) == 0
        stats = result["processing_stats"]
        assert stats["total_records"] == 0
        assert stats["total_value"] == 0.0
        assert stats["average_value"] == 0  # No division by zero
        assert stats["max_value"] == 0
        assert stats["min_value"] == 0


class TestOutputNode:
    """Test the OutputNode implementation."""

    @pytest.mark.asyncio
    async def test_output_node_formatting(self):
        """Test OutputNode formatting functionality."""
        node = OutputNode(node_id="test_output")

        input_data = {
            "processed_data": [
                {"id": "A001", "original_value": 10.0, "doubled_value": 20.0},
                {"id": "A002", "original_value": 15.0, "doubled_value": 30.0},
                {"id": "A003", "original_value": 5.0, "doubled_value": 10.0},
            ],
            "processing_stats": {
                "total_records": 3,
                "total_value": 30.0,
                "average_value": 10.0,
                "max_value": 15.0,
                "min_value": 5.0,
            },
        }

        state = WorkflowState.create_new()
        state.set("input_source", "test_source")
        state.set("validation_errors", 1)

        result = await node.run(input_data, state=state)

        assert result["record_count"] == 3
        assert result["success"] is True

        formatted_result = result["formatted_result"]
        assert "Data Processing Summary" in formatted_result
        assert "Source: test_source" in formatted_result
        assert "Records processed: 3" in formatted_result
        assert "Validation errors: 1" in formatted_result
        assert "Total value: 30.00" in formatted_result
        assert "Average value: 10.00" in formatted_result
        assert "Value range: 5.00 - 15.00" in formatted_result

        # Check that sample records are included
        assert "ID: A001" in formatted_result
        assert "Original: 10.0" in formatted_result

    @pytest.mark.asyncio
    async def test_output_node_many_records(self):
        """Test OutputNode with more than 3 records."""
        node = OutputNode(node_id="test_output")

        # Create 5 records
        processed_data = []
        for i in range(5):
            processed_data.append(
                {
                    "id": f"A{i:03d}",
                    "original_value": float(i * 10),
                    "doubled_value": float(i * 20),
                }
            )

        input_data = {
            "processed_data": processed_data,
            "processing_stats": {
                "total_records": 5,
                "total_value": 100.0,
                "average_value": 20.0,
                "max_value": 40.0,
                "min_value": 0.0,
            },
        }

        state = WorkflowState.create_new()
        result = await node.run(input_data, state=state)

        formatted_result = result["formatted_result"]

        # Should show first 3 records plus "... and 2 more"
        assert "ID: A000" in formatted_result
        assert "ID: A001" in formatted_result
        assert "ID: A002" in formatted_result
        assert "... and 2 more" in formatted_result

    @pytest.mark.asyncio
    async def test_output_node_empty_state(self):
        """Test OutputNode with minimal state data."""
        node = OutputNode(node_id="test_output")

        input_data = {
            "processed_data": [
                {"id": "A001", "original_value": 10.0, "doubled_value": 20.0},
            ],
            "processing_stats": {
                "total_records": 1,
                "total_value": 10.0,
                "average_value": 10.0,
                "max_value": 10.0,
                "min_value": 10.0,
            },
        }

        state = WorkflowState.create_new()
        # Don't set any state values to test defaults

        result = await node.run(input_data, state=state)

        formatted_result = result["formatted_result"]
        assert "Source: unknown" in formatted_result  # Default value
        assert "Validation errors: 0" in formatted_result  # Default value


class TestFullPipeline:
    """Test the complete pipeline integration."""

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """Test the complete pipeline from start to finish."""
        # Mock the print statements to avoid output during testing
        with patch("builtins.print"):
            result = await run_data_pipeline()

        # Check final result structure
        assert "formatted_result" in result
        assert "record_count" in result
        assert "success" in result
        assert result["success"] is True
        assert result["record_count"] > 0  # Should have processed some records

        # Check that the formatted result contains expected content
        formatted_result = result["formatted_result"]
        assert "Data Processing Summary" in formatted_result
        assert "example_dataset" in formatted_result  # Source should be preserved

    @pytest.mark.asyncio
    async def test_pipeline_with_mock_nodes(self):
        """Test pipeline coordination with mocked nodes."""
        # Create test data
        raw_data = [
            {"id": "T001", "value": 100.0},
            {"id": "T002", "value": 200.0},
        ]

        workflow_state = WorkflowState.create_new()

        # Test Input Node
        input_node = InputNode(node_id="input_test")
        input_result = await input_node.run(
            {"raw_data": raw_data, "source": "integration_test"}, state=workflow_state
        )

        # Test Processor Node with input node output
        processor_input = {
            "validated_data": input_result["validated_data"],
            "validation_summary": input_result["validation_summary"],
        }
        processor_node = ProcessorNode(node_id="processor_test")
        processed_result = await processor_node.run(
            processor_input, state=workflow_state
        )

        # Test Output Node with processor output
        output_input = {
            "processed_data": processed_result["processed_data"],
            "processing_stats": processed_result["processing_stats"],
        }
        output_node = OutputNode(node_id="output_test")
        final_result = await output_node.run(output_input, state=workflow_state)

        # Verify the complete flow worked
        assert len(input_result["validated_data"]) == 2
        assert len(processed_result["processed_data"]) == 2
        assert final_result["record_count"] == 2
        assert final_result["success"] is True

        # Check that data flowed correctly through the pipeline
        assert workflow_state.get("input_source") == "integration_test"
        assert workflow_state.get("processing_stats")["total_records"] == 2

    def test_pipeline_node_type_safety(self):
        """Test that pipeline nodes have correct type annotations."""
        # Check that nodes have proper generic types
        input_node = InputNode(node_id="test")
        processor_node = ProcessorNode(node_id="test")
        output_node = OutputNode(node_id="test")

        # Verify input/output schemas are set correctly
        assert input_node.input_schema == RawDataInput
        assert input_node.output_schema == ValidatedDataOutput

        assert processor_node.input_schema == ValidatedDataInput
        assert processor_node.output_schema == ProcessedDataOutput

        assert output_node.input_schema == ProcessedDataInput
        assert output_node.output_schema == FinalOutput
