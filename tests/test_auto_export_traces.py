"""Tests for automatic trace export functionality."""

import json
from pathlib import Path
from uuid import uuid4

from wyrdflow.observability.execution_log import WorkflowExecutionLog


class TestAutoExportTraces:
    """Test suite for automatic trace export."""

    def test_auto_export_enabled_by_default(self, tmp_path: Path):
        """Test that auto-export is enabled with default trace directory."""
        # Create execution log with custom trace dir
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        # Create workflow run
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_data={"test": "input"},
        )

        log.record_execution_success(
            execution_id=exec_id,
            output_data={"test": "output"},
        )

        # Verify trace file was created
        trace_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert trace_file.exists(), "Trace file should be auto-exported"

        # Verify content
        with trace_file.open() as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["node_id"] == "test_node"
        assert data[0]["status"] == "success"

    def test_auto_export_disabled_when_none(self, tmp_path: Path):
        """Test that auto-export can be disabled by setting trace_dir=None."""
        # Create execution log with no trace dir
        log = WorkflowExecutionLog(trace_dir=None)

        # Create workflow run
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id)

        # Verify no trace file was created (check default traces dir doesn't exist)
        default_traces = Path("traces")
        if default_traces.exists():
            trace_file = default_traces / f"execution_{workflow_run_id}.json"
            assert not trace_file.exists(), "Should not auto-export when disabled"

    def test_auto_export_on_failure(self, tmp_path: Path):
        """Test that traces are auto-exported even on failure."""
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record failed execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_failure(
            execution_id=exec_id,
            error=ValueError("Test error"),
        )

        # Verify trace file was created
        trace_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert trace_file.exists()

        # Verify error details are included
        with trace_file.open() as f:
            data = json.load(f)

        assert data[0]["status"] == "failed"
        assert data[0]["error_message"] == "Test error"
        assert data[0]["error_type"] == "ValueError"

    def test_auto_export_on_timeout(self, tmp_path: Path):
        """Test that traces are auto-exported on timeout."""
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record timed out execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_timeout(execution_id=exec_id)

        # Verify trace file was created
        trace_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert trace_file.exists()

        # Verify timeout status
        with trace_file.open() as f:
            data = json.load(f)

        assert data[0]["status"] == "timeout"

    def test_auto_export_updates_on_new_executions(self, tmp_path: Path):
        """Test that trace file is updated as new nodes execute in workflow."""
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record first node execution
        exec_id_1 = log.record_execution_start(
            node_id="node_1",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id_1)

        trace_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert trace_file.exists()

        # Verify trace has 1 execution
        with trace_file.open() as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["node_id"] == "node_1"

        # Record second node execution in same workflow run
        exec_id_2 = log.record_execution_start(
            node_id="node_2",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id_2)

        # Verify trace was updated with both executions
        with trace_file.open() as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["node_id"] == "node_1"
        assert data[1]["node_id"] == "node_2"

    def test_auto_export_creates_directory(self, tmp_path: Path):
        """Test that trace directory is created if it doesn't exist."""
        trace_dir = tmp_path / "custom" / "nested" / "traces"

        # Verify directory doesn't exist yet
        assert not trace_dir.exists()

        # Create execution log (directory should be created)
        _ = WorkflowExecutionLog(trace_dir=trace_dir)

        # Verify directory was created
        assert trace_dir.exists()
        assert trace_dir.is_dir()

    def test_manual_export_still_works(self, tmp_path: Path):
        """Test that manual export_to_json still works alongside auto-export."""
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id)

        # Manually export to different location
        manual_output = log.export_to_json(workflow_run_id)
        manual_file = tmp_path / "manual_export.json"

        with manual_file.open("w") as f:
            f.write(manual_output)

        # Verify both files exist
        auto_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert auto_file.exists()
        assert manual_file.exists()

        # Verify content is the same
        with auto_file.open() as f:
            auto_data = json.load(f)
        with manual_file.open() as f:
            manual_data = json.load(f)

        assert auto_data == manual_data

    def test_clear_resets_exported_runs(self, tmp_path: Path):
        """Test that clear() resets the exported runs tracking."""
        log = WorkflowExecutionLog(trace_dir=tmp_path / "traces")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record execution
        exec_id = log.record_execution_start(
            node_id="test_node",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id)

        # Verify exported
        trace_file = tmp_path / "traces" / f"execution_{workflow_run_id}.json"
        assert trace_file.exists()

        # Clear the log
        log.clear()

        # Verify _exported_runs was cleared (by checking it allows re-export)
        exec_id_2 = log.record_execution_start(
            node_id="test_node_2",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
        )

        log.record_execution_success(execution_id=exec_id_2)

        # Should create new export (would not if _exported_runs wasn't cleared)
        assert trace_file.exists()
