"""Tests for LangSmith tracing integration."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from wyrdflow.observability.tracing import (
    TracingConfig,
    WorkflowTracer,
    configure_tracing,
    get_tracer,
    set_tracer,
)


class TestTracingConfig:
    """Tests for TracingConfig class."""

    def test_create_config_default(self):
        """Test creating default tracing config."""
        config = TracingConfig()

        assert config.enabled is True
        assert config.project_name == "wyrdflow"
        assert config.tags == []
        assert config.metadata == {}

    def test_create_config_custom(self):
        """Test creating custom tracing config."""
        config = TracingConfig(
            enabled=False,
            project_name="custom-project",
            tags=["test", "dev"],
            metadata={"team": "ml"},
        )

        assert config.enabled is False
        assert config.project_name == "custom-project"
        assert config.tags == ["test", "dev"]
        assert config.metadata == {"team": "ml"}


class TestWorkflowTracer:
    """Tests for WorkflowTracer class."""

    @pytest.fixture
    def mock_langsmith_client(self):
        """Mock LangSmith client."""
        with patch("wyrdflow.observability.tracing.Client") as mock_client:
            yield mock_client

    def test_create_tracer_enabled(self, mock_langsmith_client):
        """Test creating a tracer with tracing enabled."""
        config = TracingConfig(enabled=True)
        tracer = WorkflowTracer(config)

        assert tracer.config.enabled is True
        assert tracer.client is not None

    def test_create_tracer_disabled(self):
        """Test creating a tracer with tracing disabled."""
        config = TracingConfig(enabled=False)
        tracer = WorkflowTracer(config)

        assert tracer.config.enabled is False
        assert tracer.client is None

    def test_create_tracer_client_fails(self, mock_langsmith_client):
        """Test graceful handling when LangSmith client fails."""
        mock_langsmith_client.side_effect = Exception("Connection failed")

        config = TracingConfig(enabled=True)
        tracer = WorkflowTracer(config)

        # Should disable tracing gracefully
        assert tracer.config.enabled is False
        assert tracer.client is None

    @patch("wyrdflow.observability.tracing.langsmith_trace")
    def test_trace_workflow_enabled(self, mock_trace, mock_langsmith_client):
        """Test tracing a workflow with tracing enabled."""
        config = TracingConfig(enabled=True, project_name="test-project")
        tracer = WorkflowTracer(config)

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Mock the context manager
        mock_trace.return_value.__enter__ = MagicMock(
            return_value={"run_id": "test-run"}
        )
        mock_trace.return_value.__exit__ = MagicMock(return_value=None)

        with tracer.trace_workflow(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            workflow_name="Test Workflow",
        ) as trace_context:
            assert trace_context is not None

        # Verify trace was called
        mock_trace.assert_called_once()
        call_kwargs = mock_trace.call_args[1]
        assert call_kwargs["project_name"] == "test-project"
        assert call_kwargs["run_type"] == "chain"

    def test_trace_workflow_disabled(self):
        """Test tracing a workflow with tracing disabled."""
        config = TracingConfig(enabled=False)
        tracer = WorkflowTracer(config)

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        with tracer.trace_workflow(
            workflow_id=workflow_id, workflow_run_id=workflow_run_id
        ) as trace_context:
            # Should return empty dict
            assert trace_context == {}

    @patch("wyrdflow.observability.tracing.langsmith_trace")
    def test_trace_workflow_with_tags_and_metadata(
        self, mock_trace, mock_langsmith_client
    ):
        """Test tracing with custom tags and metadata."""
        config = TracingConfig(
            enabled=True, tags=["base-tag"], metadata={"base": "value"}
        )
        tracer = WorkflowTracer(config)

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        mock_trace.return_value.__enter__ = MagicMock(return_value={})
        mock_trace.return_value.__exit__ = MagicMock(return_value=None)

        with tracer.trace_workflow(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            tags=["custom-tag"],
            metadata={"custom": "data"},
        ):
            pass

        call_kwargs = mock_trace.call_args[1]
        # Should combine base and custom tags/metadata
        assert "base-tag" in call_kwargs["tags"]
        assert "custom-tag" in call_kwargs["tags"]
        assert call_kwargs["metadata"]["base"] == "value"
        assert call_kwargs["metadata"]["custom"] == "data"

    @patch("wyrdflow.observability.tracing.langsmith_trace")
    def test_trace_node_enabled(self, mock_trace, mock_langsmith_client):
        """Test tracing a node with tracing enabled."""
        config = TracingConfig(enabled=True)
        tracer = WorkflowTracer(config)

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        mock_trace.return_value.__enter__ = MagicMock(return_value={})
        mock_trace.return_value.__exit__ = MagicMock(return_value=None)

        with tracer.trace_node(
            node_id="test_node",
            node_name="Test Node",
            node_type="TestNode",
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            input_data={"value": 10},
        ) as trace_context:
            assert trace_context is not None

        call_kwargs = mock_trace.call_args[1]
        assert call_kwargs["run_type"] == "tool"
        assert call_kwargs["inputs"] == {"value": 10}
        assert call_kwargs["metadata"]["node_id"] == "test_node"

    def test_trace_node_disabled(self):
        """Test tracing a node with tracing disabled."""
        config = TracingConfig(enabled=False)
        tracer = WorkflowTracer(config)

        with tracer.trace_node(
            node_id="test_node", node_name="Test Node"
        ) as trace_context:
            # Should return empty dict
            assert trace_context == {}

    @patch("wyrdflow.observability.tracing.langsmith_trace")
    def test_trace_node_with_tags(self, mock_trace, mock_langsmith_client):
        """Test tracing a node with custom tags."""
        config = TracingConfig(enabled=True)
        tracer = WorkflowTracer(config)

        mock_trace.return_value.__enter__ = MagicMock(return_value={})
        mock_trace.return_value.__exit__ = MagicMock(return_value=None)

        with tracer.trace_node(
            node_id="test_node",
            node_type="TestNode",
            tags=["custom-tag"],
        ):
            pass

        call_kwargs = mock_trace.call_args[1]
        # Should include both custom tag and node_type tag
        assert "custom-tag" in call_kwargs["tags"]
        assert "node_type:TestNode" in call_kwargs["tags"]

    @patch("wyrdflow.observability.tracing.langsmith_trace")
    def test_trace_workflow_error_handling(self, mock_trace, mock_langsmith_client):
        """Test error handling in workflow tracing."""
        config = TracingConfig(enabled=True)
        tracer = WorkflowTracer(config)

        # Make trace raise an exception
        mock_trace.side_effect = Exception("Trace failed")

        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Should handle error gracefully
        with tracer.trace_workflow(
            workflow_id=workflow_id, workflow_run_id=workflow_run_id
        ) as trace_context:
            # Should return empty dict on error
            assert trace_context == {}

    def test_add_trace_metadata_disabled(self):
        """Test adding metadata when tracing is disabled."""
        config = TracingConfig(enabled=False)
        tracer = WorkflowTracer(config)

        # Should not raise error
        tracer.add_trace_metadata({}, {"key": "value"})

    def test_record_error_disabled(self):
        """Test recording error when tracing is disabled."""
        config = TracingConfig(enabled=False)
        tracer = WorkflowTracer(config)

        error = ValueError("Test error")

        # Should not raise error
        tracer.record_error({}, error, "traceback...")


class TestGlobalTracer:
    """Tests for global tracer singleton."""

    def test_get_tracer(self):
        """Test getting the global tracer."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()

        # Should return the same instance
        assert tracer1 is tracer2

    def test_set_tracer(self):
        """Test setting a custom tracer."""
        config = TracingConfig(project_name="custom")
        custom_tracer = WorkflowTracer(config)

        set_tracer(custom_tracer)

        retrieved_tracer = get_tracer()
        assert retrieved_tracer is custom_tracer
        assert retrieved_tracer.config.project_name == "custom"

        # Reset for other tests
        set_tracer(WorkflowTracer())

    def test_configure_tracing(self):
        """Test configuring global tracing."""
        configure_tracing(
            enabled=True,
            project_name="configured-project",
            tags=["config-tag"],
            metadata={"configured": True},
        )

        tracer = get_tracer()
        assert tracer.config.enabled is True
        assert tracer.config.project_name == "configured-project"
        assert tracer.config.tags == ["config-tag"]
        assert tracer.config.metadata == {"configured": True}

        # Reset for other tests
        configure_tracing()
