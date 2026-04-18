"""Metrics collection and aggregation for workflow executions."""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
import threading
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """Metrics for a specific node type.

    Tracks execution statistics including timing, success/failure rates,
    and retry attempts.
    """

    node_type: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    retry_count: int = 0

    # Timing statistics (in milliseconds)
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    durations: list[float] = field(default_factory=list)

    # Token usage (for LLM nodes)
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Cost tracking
    total_cost: float = 0.0

    # Custom metrics
    custom_metrics: dict[str, Any] = field(default_factory=dict)

    def record_execution(
        self,
        success: bool,
        duration_ms: float,
        timeout: bool = False,
        retry: bool = False,
    ) -> None:
        """Record an execution result.

        Args:
            success: Whether the execution succeeded
            duration_ms: Execution duration in milliseconds
            timeout: Whether the execution timed out
            retry: Whether this was a retry attempt
        """
        self.execution_count += 1

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        if timeout:
            self.timeout_count += 1

        if retry:
            self.retry_count += 1

        # Update timing statistics
        self.total_duration_ms += duration_ms
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.durations.append(duration_ms)

    def record_tokens(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """Record token usage (for LLM nodes).

        Args:
            prompt_tokens: Number of prompt tokens used
            completion_tokens: Number of completion tokens generated
        """
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens

    def record_cost(self, cost: float) -> None:
        """Record execution cost.

        Args:
            cost: Cost in dollars
        """
        self.total_cost += cost

    def record_custom_metric(self, name: str, value: Any) -> None:
        """Record a custom metric.

        Args:
            name: Metric name
            value: Metric value
        """
        if name not in self.custom_metrics:
            self.custom_metrics[name] = []
        self.custom_metrics[name].append(value)

    @property
    def avg_duration_ms(self) -> float:
        """Average execution duration in milliseconds."""
        return (
            self.total_duration_ms / self.execution_count
            if self.execution_count > 0
            else 0.0
        )

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage (0-100)."""
        return (
            (self.success_count / self.execution_count) * 100
            if self.execution_count > 0
            else 0.0
        )

    @property
    def failure_rate(self) -> float:
        """Failure rate as a percentage (0-100)."""
        return (
            (self.failure_count / self.execution_count) * 100
            if self.execution_count > 0
            else 0.0
        )

    @property
    def p50_duration_ms(self) -> float:
        """Median (50th percentile) execution duration."""
        return self._percentile(50)

    @property
    def p95_duration_ms(self) -> float:
        """95th percentile execution duration."""
        return self._percentile(95)

    @property
    def p99_duration_ms(self) -> float:
        """99th percentile execution duration."""
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        """Calculate percentile of durations.

        Args:
            p: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not self.durations:
            return 0.0

        sorted_durations = sorted(self.durations)
        index = int((p / 100.0) * len(sorted_durations))
        index = min(index, len(sorted_durations) - 1)
        return sorted_durations[index]

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary representation of metrics
        """
        return {
            "node_type": self.node_type,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "retry_count": self.retry_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "timing": {
                "total_ms": self.total_duration_ms,
                "avg_ms": self.avg_duration_ms,
                "min_ms": (
                    self.min_duration_ms
                    if self.min_duration_ms != float("inf")
                    else 0.0
                ),
                "max_ms": self.max_duration_ms,
                "p50_ms": self.p50_duration_ms,
                "p95_ms": self.p95_duration_ms,
                "p99_ms": self.p99_duration_ms,
            },
            "tokens": {
                "total": self.total_tokens,
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
            },
            "cost": self.total_cost,
            "custom_metrics": self.custom_metrics,
        }


@dataclass
class WorkflowMetrics:
    """Aggregated metrics for an entire workflow."""

    workflow_id: UUID
    workflow_run_id: Optional[UUID] = None
    node_metrics: dict[str, NodeMetrics] = field(default_factory=dict)
    total_executions: int = 0
    total_successes: int = 0
    total_failures: int = 0

    def get_or_create_node_metrics(self, node_type: str) -> NodeMetrics:
        """Get or create metrics for a node type.

        Args:
            node_type: Type of node

        Returns:
            NodeMetrics instance
        """
        if node_type not in self.node_metrics:
            self.node_metrics[node_type] = NodeMetrics(node_type=node_type)
        return self.node_metrics[node_type]

    def to_dict(self) -> dict[str, Any]:
        """Convert workflow metrics to dictionary.

        Returns:
            Dictionary representation of metrics
        """
        return {
            "workflow_id": str(self.workflow_id),
            "workflow_run_id": (
                str(self.workflow_run_id) if self.workflow_run_id else None
            ),
            "total_executions": self.total_executions,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "node_metrics": {
                node_type: metrics.to_dict()
                for node_type, metrics in self.node_metrics.items()
            },
        }


class MetricsCollector:
    """Thread-safe metrics collector for workflow executions.

    Collects and aggregates metrics across all workflow executions.
    Provides methods for querying metrics by workflow, node type, etc.
    """

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._lock = threading.RLock()
        self._workflow_metrics: dict[UUID, WorkflowMetrics] = {}
        self._node_type_metrics: dict[str, NodeMetrics] = defaultdict(
            lambda: NodeMetrics(node_type="unknown")
        )

        logger.info("Initialized MetricsCollector")

    def record_node_execution(
        self,
        workflow_id: UUID,
        workflow_run_id: UUID,
        node_id: str,  # noqa: ARG002
        node_type: str,
        success: bool,
        duration_ms: float,
        timeout: bool = False,
        retry: bool = False,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """Record a node execution.

        Args:
            workflow_id: Workflow identifier
            workflow_run_id: Workflow run identifier
            node_id: Node identifier
            node_type: Type of node
            success: Whether execution succeeded
            duration_ms: Execution duration in milliseconds
            timeout: Whether execution timed out
            retry: Whether this was a retry attempt
            prompt_tokens: Prompt tokens used (LLM nodes)
            completion_tokens: Completion tokens used (LLM nodes)
            cost: Execution cost
        """
        with self._lock:
            # Get or create workflow metrics
            if workflow_id not in self._workflow_metrics:
                self._workflow_metrics[workflow_id] = WorkflowMetrics(
                    workflow_id=workflow_id
                )

            workflow_metrics = self._workflow_metrics[workflow_id]

            # Update workflow-level counts
            workflow_metrics.total_executions += 1
            if success:
                workflow_metrics.total_successes += 1
            else:
                workflow_metrics.total_failures += 1

            # Update node-level metrics within workflow
            node_metrics = workflow_metrics.get_or_create_node_metrics(node_type)
            node_metrics.record_execution(success, duration_ms, timeout, retry)

            if prompt_tokens > 0 or completion_tokens > 0:
                node_metrics.record_tokens(prompt_tokens, completion_tokens)

            if cost > 0:
                node_metrics.record_cost(cost)

            # Update global node type metrics
            global_node_metrics = self._node_type_metrics[node_type]
            global_node_metrics.node_type = node_type
            global_node_metrics.record_execution(success, duration_ms, timeout, retry)

            if prompt_tokens > 0 or completion_tokens > 0:
                global_node_metrics.record_tokens(prompt_tokens, completion_tokens)

            if cost > 0:
                global_node_metrics.record_cost(cost)

            logger.debug(
                f"Recorded metrics for {node_type} node "
                f"(workflow={workflow_id}, run={workflow_run_id})"
            )

    def record_custom_metric(
        self,
        workflow_id: UUID,
        node_type: str,
        metric_name: str,
        value: Any,
    ) -> None:
        """Record a custom metric.

        Args:
            workflow_id: Workflow identifier
            node_type: Type of node
            metric_name: Name of the metric
            value: Metric value
        """
        with self._lock:
            if workflow_id in self._workflow_metrics:
                workflow_metrics = self._workflow_metrics[workflow_id]
                node_metrics = workflow_metrics.get_or_create_node_metrics(node_type)
                node_metrics.record_custom_metric(metric_name, value)

            # Also record globally
            global_metrics = self._node_type_metrics[node_type]
            global_metrics.node_type = node_type
            global_metrics.record_custom_metric(metric_name, value)

    def get_workflow_metrics(self, workflow_id: UUID) -> Optional[WorkflowMetrics]:
        """Get metrics for a specific workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowMetrics if found, None otherwise
        """
        with self._lock:
            return self._workflow_metrics.get(workflow_id)

    def get_node_type_metrics(self, node_type: str) -> Optional[NodeMetrics]:
        """Get aggregated metrics for a node type.

        Args:
            node_type: Type of node

        Returns:
            NodeMetrics if found, None otherwise
        """
        with self._lock:
            return self._node_type_metrics.get(node_type)

    def get_all_node_type_metrics(self) -> dict[str, NodeMetrics]:
        """Get metrics for all node types.

        Returns:
            Dictionary mapping node types to their metrics
        """
        with self._lock:
            return dict(self._node_type_metrics)

    def get_all_workflow_metrics(self) -> dict[UUID, WorkflowMetrics]:
        """Get metrics for all workflows.

        Returns:
            Dictionary mapping workflow IDs to their metrics
        """
        with self._lock:
            return dict(self._workflow_metrics)

    def clear(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self._workflow_metrics.clear()
            self._node_type_metrics.clear()
            logger.info("Cleared all metrics")

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics.

        Returns:
            Summary dictionary
        """
        with self._lock:
            return {
                "total_workflows": len(self._workflow_metrics),
                "total_node_types": len(self._node_type_metrics),
                "node_type_metrics": {
                    node_type: metrics.to_dict()
                    for node_type, metrics in self._node_type_metrics.items()
                },
            }


# Global metrics collector instance
_global_metrics_collector: Optional[MetricsCollector] = None
_global_metrics_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        Global MetricsCollector instance
    """
    global _global_metrics_collector  # noqa: PLW0603

    if _global_metrics_collector is None:
        with _global_metrics_lock:
            if _global_metrics_collector is None:
                _global_metrics_collector = MetricsCollector()

    return _global_metrics_collector


def set_metrics_collector(collector: MetricsCollector) -> None:
    """Set the global metrics collector instance.

    Args:
        collector: MetricsCollector instance to use globally
    """
    global _global_metrics_collector  # noqa: PLW0603

    with _global_metrics_lock:
        _global_metrics_collector = collector
