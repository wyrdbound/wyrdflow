"""LangSmith tracing integration for workflow observability."""

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from typing import Any, Optional
from uuid import UUID

from langsmith import Client
from langsmith.run_helpers import trace as langsmith_trace

logger = logging.getLogger(__name__)


class TracingConfig:
    """Configuration for LangSmith tracing.

    Attributes:
        enabled: Whether tracing is enabled
        project_name: LangSmith project name
        tags: Default tags to apply to all traces
        metadata: Default metadata to apply to all traces
    """

    def __init__(
        self,
        enabled: bool = True,
        project_name: str = "wyrdflow",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Initialize tracing configuration.

        Args:
            enabled: Whether to enable tracing
            project_name: LangSmith project name
            tags: Default tags for traces
            metadata: Default metadata for traces
        """
        self.enabled = enabled
        self.project_name = project_name
        self.tags = tags or []
        self.metadata = metadata or {}


class WorkflowTracer:
    """LangSmith tracer for workflow executions.

    Provides automatic tracing of workflow and node executions with
    integration to LangSmith for visualization and debugging.
    """

    def __init__(self, config: Optional[TracingConfig] = None):
        """Initialize the workflow tracer.

        Args:
            config: Tracing configuration
        """
        self.config = config or TracingConfig()

        # Initialize LangSmith client if tracing is enabled
        self.client: Optional[Client] = None
        if self.config.enabled:
            try:
                self.client = Client()
                logger.info(
                    f"Initialized LangSmith tracer for project: "
                    f"{self.config.project_name}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize LangSmith client: {e}. "
                    "Tracing will be disabled."
                )
                self.config.enabled = False

    @contextmanager
    def trace_workflow(
        self,
        workflow_id: UUID,
        workflow_run_id: UUID,
        workflow_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """Context manager for tracing an entire workflow execution.

        Args:
            workflow_id: Workflow identifier
            workflow_run_id: Workflow run identifier
            workflow_name: Human-readable workflow name
            tags: Additional tags for this trace
            metadata: Additional metadata for this trace

        Yields:
            Trace context dictionary
        """
        if not self.config.enabled:
            yield {}
            return

        # Combine default and provided tags/metadata
        all_tags = list(self.config.tags)
        if tags:
            all_tags.extend(tags)

        all_metadata = dict(self.config.metadata)
        if metadata:
            all_metadata.update(metadata)

        # Add workflow identifiers to metadata
        all_metadata.update(
            {
                "workflow_id": str(workflow_id),
                "workflow_run_id": str(workflow_run_id),
                "workflow_name": workflow_name or str(workflow_id),
            }
        )

        try:
            with langsmith_trace(
                name=workflow_name or f"Workflow-{workflow_id}",
                run_type="chain",
                project_name=self.config.project_name,
                tags=all_tags,
                metadata=all_metadata,
            ) as trace_context:
                yield trace_context
        except Exception as e:
            logger.warning(f"Failed to create workflow trace: {e}")
            yield {}

    @contextmanager
    def trace_node(
        self,
        node_id: str,
        node_name: Optional[str] = None,
        node_type: Optional[str] = None,
        workflow_id: Optional[UUID] = None,
        workflow_run_id: Optional[UUID] = None,
        input_data: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """Context manager for tracing a node execution.

        Args:
            node_id: Node identifier
            node_name: Human-readable node name
            node_type: Type of node
            workflow_id: Workflow identifier
            workflow_run_id: Workflow run identifier
            input_data: Node input data
            tags: Additional tags for this trace
            metadata: Additional metadata for this trace

        Yields:
            Trace context dictionary
        """
        if not self.config.enabled:
            yield {}
            return

        # Combine default and provided tags/metadata
        all_tags = list(self.config.tags)
        if tags:
            all_tags.extend(tags)
        if node_type:
            all_tags.append(f"node_type:{node_type}")

        all_metadata = dict(self.config.metadata)
        if metadata:
            all_metadata.update(metadata)

        # Add node information to metadata
        all_metadata.update(
            {
                "node_id": node_id,
                "node_name": node_name or node_id,
                "node_type": node_type or "unknown",
            }
        )

        if workflow_id:
            all_metadata["workflow_id"] = str(workflow_id)
        if workflow_run_id:
            all_metadata["workflow_run_id"] = str(workflow_run_id)

        try:
            with langsmith_trace(
                name=node_name or node_id,
                run_type="tool",
                project_name=self.config.project_name,
                inputs=input_data or {},
                tags=all_tags,
                metadata=all_metadata,
            ) as trace_context:
                yield trace_context
        except Exception as e:
            logger.warning(f"Failed to create node trace for {node_id}: {e}")
            yield {}

    def add_trace_metadata(
        self, trace_context: dict[str, Any], metadata: dict[str, Any]
    ) -> None:
        """Add metadata to an active trace.

        Args:
            trace_context: Trace context from trace_workflow or trace_node
            metadata: Metadata to add
        """
        if not self.config.enabled or not trace_context:
            return

        try:
            # LangSmith trace context allows updating metadata
            if "run_id" in trace_context and self.client:
                run_id = trace_context["run_id"]
                self.client.update_run(run_id, extra=metadata)
        except Exception as e:
            logger.warning(f"Failed to add trace metadata: {e}")

    def record_error(
        self,
        trace_context: dict[str, Any],
        error: Exception,
        error_traceback: Optional[str] = None,
    ) -> None:
        """Record an error in an active trace.

        Args:
            trace_context: Trace context from trace_workflow or trace_node
            error: Exception that occurred
            error_traceback: Full error traceback
        """
        if not self.config.enabled or not trace_context:
            return

        try:
            error_metadata = {
                "error": str(error),
                "error_type": type(error).__name__,
            }
            if error_traceback:
                error_metadata["error_traceback"] = error_traceback

            self.add_trace_metadata(trace_context, error_metadata)
        except Exception as e:
            logger.warning(f"Failed to record error in trace: {e}")


# Global tracer instance
_global_tracer: Optional[WorkflowTracer] = None


def get_tracer() -> WorkflowTracer:
    """Get the global workflow tracer instance.

    Returns:
        Global WorkflowTracer instance
    """
    global _global_tracer  # noqa: PLW0603

    if _global_tracer is None:
        _global_tracer = WorkflowTracer()

    return _global_tracer


def set_tracer(tracer: WorkflowTracer) -> None:
    """Set the global workflow tracer instance.

    Args:
        tracer: WorkflowTracer instance to use globally
    """
    global _global_tracer  # noqa: PLW0603
    _global_tracer = tracer


def configure_tracing(
    enabled: bool = True,
    project_name: str = "wyrdflow",
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Configure global tracing settings.

    Args:
        enabled: Whether to enable tracing
        project_name: LangSmith project name
        tags: Default tags for traces
        metadata: Default metadata for traces
    """
    config = TracingConfig(
        enabled=enabled,
        project_name=project_name,
        tags=tags,
        metadata=metadata,
    )
    set_tracer(WorkflowTracer(config))
