"""Tests for execution logging functionality."""

from datetime import datetime
import json
from uuid import uuid4

import pytest

from wyrdflow.observability.execution_log import (
    ExecutionStatus,
    NodeExecutionRecord,
    WorkflowExecutionLog,
    get_execution_log,
    set_execution_log,
)


class TestNodeExecutionRecord:
    """Tests for NodeExecutionRecord model."""

    def test_create_record(self):
        """Test creating an execution record."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        record = NodeExecutionRecord(
            node_id="test_node",
            execution_id="test_exec_123",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_name="Test Node",
            node_type="TestNode",
        )

        assert record.node_id == "test_node"
        assert record.execution_id == "test_exec_123"
        assert record.workflow_id == workflow_id
        assert record.workflow_run_id == workflow_run_id
        assert record.status == ExecutionStatus.PENDING
        assert record.node_name == "Test Node"
        assert record.node_type == "TestNode"

    def test_mark_running(self):
        """Test marking record as running."""
        record = NodeExecutionRecord(
            node_id="test",
            execution_id="exec",
            workflow_id=uuid4(),
            workflow_run_id=uuid4(),
        )

        start_time = datetime.now()
        record.mark_running()

        assert record.status == ExecutionStatus.RUNNING
        assert record.start_time >= start_time

    def test_mark_success(self):
        """Test marking record as successful."""
        record = NodeExecutionRecord(
            node_id="test",
            execution_id="exec",
            workflow_id=uuid4(),
            workflow_run_id=uuid4(),
        )
        record.mark_running()

        output = {"result": 42}
        record.mark_success(output, output_size=100)

        assert record.status == ExecutionStatus.SUCCESS
        assert record.end_time is not None
        assert record.duration_ms is not None
        assert record.duration_ms > 0
        assert record.output_data == output
        assert record.output_size == 100

    def test_mark_failed(self):
        """Test marking record as failed."""
        record = NodeExecutionRecord(
            node_id="test",
            execution_id="exec",
            workflow_id=uuid4(),
            workflow_run_id=uuid4(),
        )
        record.mark_running()

        error = ValueError("Test error")
        traceback_str = "Traceback..."
        record.mark_failed(error, traceback_str)

        assert record.status == ExecutionStatus.FAILED
        assert record.end_time is not None
        assert record.duration_ms is not None
        assert record.error_message == "Test error"
        assert record.error_type == "ValueError"
        assert record.error_traceback == traceback_str

    def test_mark_timeout(self):
        """Test marking record as timed out."""
        record = NodeExecutionRecord(
            node_id="test",
            execution_id="exec",
            workflow_id=uuid4(),
            workflow_run_id=uuid4(),
        )
        record.mark_running()

        record.mark_timeout()

        assert record.status == ExecutionStatus.TIMEOUT
        assert record.end_time is not None
        assert record.duration_ms is not None

    def test_mark_retry(self):
        """Test marking record as retrying."""
        record = NodeExecutionRecord(
            node_id="test",
            execution_id="exec",
            workflow_id=uuid4(),
            workflow_run_id=uuid4(),
        )

        record.mark_retry(2)

        assert record.status == ExecutionStatus.RETRY
        assert record.retry_attempt == 2


class TestWorkflowExecutionLog:
    """Tests for WorkflowExecutionLog class."""

    @pytest.fixture
    def exec_log(self):
        """Create a fresh execution log for each test."""
        return WorkflowExecutionLog(max_records=100, max_data_size=1000, trace_dir=None)

    def test_create_log(self, exec_log):
        """Test creating an execution log."""
        assert exec_log.max_records == 100
        assert exec_log.max_data_size == 1000
        assert len(exec_log.get_all_records()) == 0

    def test_record_execution_start(self, exec_log):
        """Test recording execution start."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        execution_id = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_data={"value": 10},
            node_name="Test Node",
            node_type="TestNode",
        )

        assert execution_id is not None
        assert str(workflow_run_id) in execution_id
        assert "test_node" in execution_id

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        assert records[0].node_id == "test_node"
        assert records[0].status == ExecutionStatus.RUNNING

    def test_record_execution_success(self, exec_log):
        """Test recording execution success."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        execution_id = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        output = {"result": 42}
        exec_log.record_execution_success(execution_id, output)

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        assert records[0].status == ExecutionStatus.SUCCESS
        assert records[0].output_data == output

    def test_record_execution_failure(self, exec_log):
        """Test recording execution failure."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        execution_id = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        error = RuntimeError("Test failure")
        exec_log.record_execution_failure(execution_id, error, "traceback...")

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        assert records[0].status == ExecutionStatus.FAILED
        assert records[0].error_message == "Test failure"
        assert records[0].error_type == "RuntimeError"

    def test_record_execution_timeout(self, exec_log):
        """Test recording execution timeout."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        execution_id = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        exec_log.record_execution_timeout(execution_id)

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        assert records[0].status == ExecutionStatus.TIMEOUT

    def test_record_retry_attempt(self, exec_log):
        """Test recording retry attempt."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        execution_id = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        exec_log.record_retry_attempt(execution_id, 2)

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        assert records[0].status == ExecutionStatus.RETRY
        assert records[0].retry_attempt == 2

    def test_data_truncation(self, exec_log):
        """Test that large data is truncated."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Create large input data
        large_data = {"key": "x" * 2000}  # Exceeds max_data_size

        exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_data=large_data,
        )

        records = exec_log.get_records_by_run(workflow_run_id)
        assert len(records) == 1
        # Data should be truncated
        assert records[0].input_size > exec_log.max_data_size

    def test_get_records_by_node(self, exec_log):
        """Test getting records by node ID."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Create records for different nodes
        exec_log.record_execution_start(
            node_id="node1",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )
        exec_log.record_execution_start(
            node_id="node2",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )
        exec_log.record_execution_start(
            node_id="node1",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        node1_records = exec_log.get_records_by_node("node1")
        assert len(node1_records) == 2

        node2_records = exec_log.get_records_by_node("node2")
        assert len(node2_records) == 1

    def test_get_latest_record(self, exec_log):
        """Test getting the latest record for a node."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Create multiple records
        exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )
        exec_id2 = exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        latest = exec_log.get_latest_record("test_node", workflow_run_id)
        assert latest is not None
        assert latest.execution_id == exec_id2

    def test_clear_records(self, exec_log):
        """Test clearing all records."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        assert len(exec_log.get_all_records()) == 1

        exec_log.clear()

        assert len(exec_log.get_all_records()) == 0

    def test_export_to_json(self, exec_log):
        """Test exporting records to JSON."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        exec_log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_data={"value": 10},
        )

        json_str = exec_log.export_to_json(workflow_run_id)

        # Should be valid JSON
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["node_id"] == "test_node"

    def test_cleanup_old_records(self):
        """Test that old records are cleaned up."""
        # Create log with small max_records
        exec_log = WorkflowExecutionLog(max_records=5, trace_dir=None)

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Add more records than max_records
        for i in range(10):
            exec_log.record_execution_start(
                node_id=f"node_{i}",
                workflow_id=workflow_id,
                workflow_run_id=workflow_run_id,
            )

        # Should have cleaned up to stay under max
        assert len(exec_log.get_all_records()) <= exec_log.max_records


class TestGlobalExecutionLog:
    """Tests for global execution log singleton."""

    def test_get_execution_log(self):
        """Test getting the global execution log."""
        log1 = get_execution_log()
        log2 = get_execution_log()

        # Should return the same instance
        assert log1 is log2

    def test_set_execution_log(self):
        """Test setting a custom execution log."""
        custom_log = WorkflowExecutionLog(max_records=50)
        set_execution_log(custom_log)

        retrieved_log = get_execution_log()
        assert retrieved_log is custom_log
        assert retrieved_log.max_records == 50

        # Reset to default for other tests
        set_execution_log(WorkflowExecutionLog())
