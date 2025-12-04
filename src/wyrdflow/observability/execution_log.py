"""Execution logging and history tracking for workflow nodes."""

from collections import defaultdict
from datetime import datetime
from enum import Enum
import json
import logging
import threading
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution status for a node."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRY = "retry"


class NodeExecutionRecord(BaseModel):
    """Record of a single node execution attempt.

    This captures all relevant information about a node's execution including
    timing, inputs, outputs, errors, and retry attempts.
    """

    # Identification
    node_id: str = Field(description="Unique identifier for the node")
    execution_id: str = Field(
        description="Unique ID for this specific execution attempt"
    )
    workflow_id: UUID = Field(description="Workflow identifier")
    workflow_run_id: UUID = Field(description="Workflow run identifier")

    # Status
    status: ExecutionStatus = Field(
        default=ExecutionStatus.PENDING, description="Current execution status"
    )

    # Timing
    start_time: datetime = Field(
        default_factory=datetime.now, description="Execution start time"
    )
    end_time: Optional[datetime] = Field(default=None, description="Execution end time")
    duration_ms: Optional[float] = Field(
        default=None, description="Execution duration in milliseconds"
    )

    # Data (with size limits)
    input_data: Optional[dict[str, Any]] = Field(
        default=None, description="Node input data (may be truncated)"
    )
    output_data: Optional[dict[str, Any]] = Field(
        default=None, description="Node output data (may be truncated)"
    )
    input_size: int = Field(default=0, description="Original input size in bytes")
    output_size: int = Field(default=0, description="Original output size in bytes")

    # Error tracking
    error_message: Optional[str] = Field(
        default=None, description="Error message if execution failed"
    )
    error_type: Optional[str] = Field(
        default=None, description="Type of exception that occurred"
    )
    error_traceback: Optional[str] = Field(
        default=None, description="Full error traceback"
    )

    # Retry tracking
    retry_attempt: int = Field(default=0, description="Current retry attempt number")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")

    # Metadata
    node_name: Optional[str] = Field(default=None, description="Human-readable name")
    node_type: Optional[str] = Field(default=None, description="Type of node")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def mark_running(self) -> None:
        """Mark the execution as running."""
        self.status = ExecutionStatus.RUNNING
        self.start_time = datetime.now()

    def mark_success(self, output: dict[str, Any], output_size: int = 0) -> None:
        """Mark the execution as successful."""
        self.status = ExecutionStatus.SUCCESS
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.output_data = output
        self.output_size = output_size

    def mark_failed(
        self,
        error: Exception,
        error_traceback: Optional[str] = None,
    ) -> None:
        """Mark the execution as failed."""
        self.status = ExecutionStatus.FAILED
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.error_message = str(error)
        self.error_type = type(error).__name__
        self.error_traceback = error_traceback

    def mark_timeout(self) -> None:
        """Mark the execution as timed out."""
        self.status = ExecutionStatus.TIMEOUT
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def mark_retry(self, attempt: int) -> None:
        """Mark the execution as being retried."""
        self.status = ExecutionStatus.RETRY
        self.retry_attempt = attempt


class WorkflowExecutionLog:
    """Thread-safe execution log for workflow runs.

    This class maintains an in-memory log of all node executions with
    configurable retention and size limits. It provides methods for
    querying execution history and generating reports.

    Features:
    - Thread-safe operations
    - Configurable data size limits
    - Automatic cleanup of old records
    - Query by workflow, run, or node
    - Export to JSON
    """

    def __init__(
        self,
        max_records: int = 10000,
        max_data_size: int = 10240,  # 10KB default
        retention_seconds: Optional[int] = None,  # No automatic cleanup by default
    ):
        """Initialize the execution log.

        Args:
            max_records: Maximum number of records to keep in memory
            max_data_size: Maximum size of input/output data to store (bytes)
            retention_seconds: How long to keep records (None = indefinite)
        """
        self.max_records = max_records
        self.max_data_size = max_data_size
        self.retention_seconds = retention_seconds

        # Thread-safe storage
        self._lock = threading.RLock()
        self._records: list[NodeExecutionRecord] = []
        self._records_by_run: dict[UUID, list[NodeExecutionRecord]] = defaultdict(list)
        self._records_by_node: dict[str, list[NodeExecutionRecord]] = defaultdict(list)

        logger.info(
            f"Initialized WorkflowExecutionLog with max_records={max_records}, "
            f"max_data_size={max_data_size}"
        )

    def _truncate_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Truncate data if it exceeds size limit.

        Args:
            data: Data to potentially truncate

        Returns:
            Truncated data dictionary
        """
        data_str = json.dumps(data)
        data_size = len(data_str.encode("utf-8"))

        if data_size <= self.max_data_size:
            return data

        # Truncate to max size
        truncated_str = data_str[: self.max_data_size]
        try:
            # Try to parse truncated JSON
            result: dict[str, Any] = json.loads(truncated_str)
            return result
        except json.JSONDecodeError:
            # If we can't parse, return a marker
            return {
                "_truncated": True,
                "_original_size": data_size,
                "_max_size": self.max_data_size,
            }

    def record_execution_start(
        self,
        node_id: str,
        workflow_id: UUID,
        workflow_run_id: UUID,
        input_data: Optional[dict[str, Any]] = None,
        node_name: Optional[str] = None,
        node_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Record the start of a node execution.

        Args:
            node_id: Node identifier
            workflow_id: Workflow identifier
            workflow_run_id: Workflow run identifier
            input_data: Node input data
            node_name: Human-readable node name
            node_type: Type of node
            metadata: Additional metadata

        Returns:
            Execution ID for this execution attempt
        """
        with self._lock:
            # Generate unique execution ID
            execution_id = f"{workflow_run_id}_{node_id}_{datetime.now().timestamp()}"

            # Prepare input data (truncate if needed)
            input_size = 0
            truncated_input = None
            if input_data:
                input_str = json.dumps(input_data)
                input_size = len(input_str.encode("utf-8"))
                truncated_input = self._truncate_data(input_data)

            # Create record
            record = NodeExecutionRecord(
                node_id=node_id,
                execution_id=execution_id,
                workflow_id=workflow_id,
                workflow_run_id=workflow_run_id,
                status=ExecutionStatus.RUNNING,
                input_data=truncated_input,
                input_size=input_size,
                node_name=node_name,
                node_type=node_type,
                metadata=metadata or {},
            )

            # Mark as running
            record.mark_running()

            # Store record
            self._add_record(record)

            logger.debug(f"Started execution: {execution_id}")
            return execution_id

    def record_execution_success(
        self,
        execution_id: str,
        output_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record successful completion of a node execution.

        Args:
            execution_id: Execution ID from record_execution_start
            output_data: Node output data
        """
        with self._lock:
            record = self._find_record(execution_id)
            if not record:
                logger.warning(f"No record found for execution: {execution_id}")
                return

            # Prepare output data (truncate if needed)
            output_size = 0
            truncated_output = None
            if output_data:
                output_str = json.dumps(output_data)
                output_size = len(output_str.encode("utf-8"))
                truncated_output = self._truncate_data(output_data)

            record.mark_success(truncated_output or {}, output_size)
            logger.debug(f"Completed execution: {execution_id}")

    def record_execution_failure(
        self,
        execution_id: str,
        error: Exception,
        error_traceback: Optional[str] = None,
    ) -> None:
        """Record failure of a node execution.

        Args:
            execution_id: Execution ID from record_execution_start
            error: Exception that occurred
            error_traceback: Full error traceback
        """
        with self._lock:
            record = self._find_record(execution_id)
            if not record:
                logger.warning(f"No record found for execution: {execution_id}")
                return

            record.mark_failed(error, error_traceback)
            logger.debug(f"Failed execution: {execution_id} - {error}")

    def record_execution_timeout(self, execution_id: str) -> None:
        """Record timeout of a node execution.

        Args:
            execution_id: Execution ID from record_execution_start
        """
        with self._lock:
            record = self._find_record(execution_id)
            if not record:
                logger.warning(f"No record found for execution: {execution_id}")
                return

            record.mark_timeout()
            logger.debug(f"Timed out execution: {execution_id}")

    def record_retry_attempt(self, execution_id: str, attempt: int) -> None:
        """Record a retry attempt for a node execution.

        Args:
            execution_id: Execution ID from record_execution_start
            attempt: Retry attempt number
        """
        with self._lock:
            record = self._find_record(execution_id)
            if not record:
                logger.warning(f"No record found for execution: {execution_id}")
                return

            record.mark_retry(attempt)
            logger.debug(f"Retry attempt {attempt} for execution: {execution_id}")

    def _add_record(self, record: NodeExecutionRecord) -> None:
        """Add a record to the log (internal, assumes lock is held).

        Args:
            record: Record to add
        """
        # Check if we need to clean up old records
        if len(self._records) >= self.max_records:
            self._cleanup_old_records()

        # Add to primary list
        self._records.append(record)

        # Add to indexes
        self._records_by_run[record.workflow_run_id].append(record)
        self._records_by_node[record.node_id].append(record)

    def _find_record(self, execution_id: str) -> Optional[NodeExecutionRecord]:
        """Find a record by execution ID (internal, assumes lock is held).

        Args:
            execution_id: Execution ID to find

        Returns:
            Record if found, None otherwise
        """
        for record in reversed(self._records):
            if record.execution_id == execution_id:
                return record
        return None

    def _cleanup_old_records(self) -> None:
        """Clean up old records to stay within limits (internal).

        This removes the oldest records when we exceed max_records.
        """
        if len(self._records) < self.max_records:
            return

        # Remove oldest 10% of records
        num_to_remove = max(1, len(self._records) // 10)
        removed_records = self._records[:num_to_remove]
        self._records = self._records[num_to_remove:]

        # Update indexes
        for record in removed_records:
            # Remove from run index
            run_list = self._records_by_run.get(record.workflow_run_id, [])
            if record in run_list:
                run_list.remove(record)

            # Remove from node index
            node_list = self._records_by_node.get(record.node_id, [])
            if record in node_list:
                node_list.remove(record)

        logger.info(f"Cleaned up {num_to_remove} old execution records")

    def get_records_by_run(self, workflow_run_id: UUID) -> list[NodeExecutionRecord]:
        """Get all records for a specific workflow run.

        Args:
            workflow_run_id: Workflow run identifier

        Returns:
            List of execution records
        """
        with self._lock:
            return list(self._records_by_run.get(workflow_run_id, []))

    def get_records_by_node(self, node_id: str) -> list[NodeExecutionRecord]:
        """Get all records for a specific node.

        Args:
            node_id: Node identifier

        Returns:
            List of execution records
        """
        with self._lock:
            return list(self._records_by_node.get(node_id, []))

    def get_latest_record(
        self, node_id: str, workflow_run_id: Optional[UUID] = None
    ) -> Optional[NodeExecutionRecord]:
        """Get the most recent execution record for a node.

        Args:
            node_id: Node identifier
            workflow_run_id: Optional workflow run to filter by

        Returns:
            Most recent record or None
        """
        with self._lock:
            records = self._records_by_node.get(node_id, [])
            if workflow_run_id:
                records = [r for r in records if r.workflow_run_id == workflow_run_id]

            return records[-1] if records else None

    def get_all_records(self) -> list[NodeExecutionRecord]:
        """Get all execution records.

        Returns:
            List of all execution records
        """
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        """Clear all execution records."""
        with self._lock:
            self._records.clear()
            self._records_by_run.clear()
            self._records_by_node.clear()
            logger.info("Cleared all execution records")

    def export_to_json(self, workflow_run_id: Optional[UUID] = None) -> str:
        """Export execution records to JSON.

        Args:
            workflow_run_id: Optional workflow run to filter by

        Returns:
            JSON string of execution records
        """
        with self._lock:
            if workflow_run_id:
                records = self.get_records_by_run(workflow_run_id)
            else:
                records = self._records

            # Convert to dictionaries
            records_dict = [record.model_dump() for record in records]

            return json.dumps(records_dict, indent=2, default=str)


# Global execution log instance
_global_execution_log: Optional[WorkflowExecutionLog] = None
_global_log_lock = threading.Lock()


def get_execution_log() -> WorkflowExecutionLog:
    """Get the global execution log instance.

    Returns:
        Global WorkflowExecutionLog instance
    """
    global _global_execution_log  # noqa: PLW0603

    if _global_execution_log is None:
        with _global_log_lock:
            if _global_execution_log is None:
                _global_execution_log = WorkflowExecutionLog()

    return _global_execution_log


def set_execution_log(log: WorkflowExecutionLog) -> None:
    """Set the global execution log instance.

    Args:
        log: WorkflowExecutionLog instance to use globally
    """
    global _global_execution_log  # noqa: PLW0603

    with _global_log_lock:
        _global_execution_log = log
