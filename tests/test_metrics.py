"""Tests for metrics collection functionality."""

from uuid import uuid4

import pytest

from wyrdflow.observability.metrics import (
    MetricsCollector,
    NodeMetrics,
    WorkflowMetrics,
    get_metrics_collector,
    set_metrics_collector,
)


class TestNodeMetrics:
    """Tests for NodeMetrics dataclass."""

    def test_create_node_metrics(self):
        """Test creating node metrics."""
        metrics = NodeMetrics(node_type="TestNode")

        assert metrics.node_type == "TestNode"
        assert metrics.execution_count == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.total_duration_ms == 0.0

    def test_record_successful_execution(self):
        """Test recording a successful execution."""
        metrics = NodeMetrics(node_type="TestNode")

        metrics.record_execution(success=True, duration_ms=100.0)

        assert metrics.execution_count == 1
        assert metrics.success_count == 1
        assert metrics.failure_count == 0
        assert metrics.total_duration_ms == 100.0
        assert metrics.min_duration_ms == 100.0
        assert metrics.max_duration_ms == 100.0
        assert metrics.avg_duration_ms == 100.0

    def test_record_failed_execution(self):
        """Test recording a failed execution."""
        metrics = NodeMetrics(node_type="TestNode")

        metrics.record_execution(success=False, duration_ms=50.0)

        assert metrics.execution_count == 1
        assert metrics.success_count == 0
        assert metrics.failure_count == 1

    def test_record_timeout(self):
        """Test recording a timeout."""
        metrics = NodeMetrics(node_type="TestNode")

        metrics.record_execution(success=False, duration_ms=200.0, timeout=True)

        assert metrics.timeout_count == 1
        assert metrics.failure_count == 1

    def test_record_retry(self):
        """Test recording a retry."""
        metrics = NodeMetrics(node_type="TestNode")

        metrics.record_execution(success=True, duration_ms=150.0, retry=True)

        assert metrics.retry_count == 1

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = NodeMetrics(node_type="TestNode")

        # Record mixed results
        metrics.record_execution(success=True, duration_ms=100.0)
        metrics.record_execution(success=True, duration_ms=100.0)
        metrics.record_execution(success=False, duration_ms=100.0)

        assert metrics.success_rate == pytest.approx(66.67, rel=0.01)
        assert metrics.failure_rate == pytest.approx(33.33, rel=0.01)

    def test_duration_statistics(self):
        """Test duration statistics calculation."""
        metrics = NodeMetrics(node_type="TestNode")

        # Record multiple executions
        metrics.record_execution(success=True, duration_ms=50.0)
        metrics.record_execution(success=True, duration_ms=100.0)
        metrics.record_execution(success=True, duration_ms=150.0)
        metrics.record_execution(success=True, duration_ms=200.0)

        assert metrics.min_duration_ms == 50.0
        assert metrics.max_duration_ms == 200.0
        assert metrics.avg_duration_ms == 125.0
        # P50 is calculated as 50th percentile (index 2 of 4 items = 150.0)
        assert metrics.p50_duration_ms == 150.0

    def test_record_tokens(self):
        """Test recording token usage."""
        metrics = NodeMetrics(node_type="LLMNode")

        metrics.record_tokens(prompt_tokens=100, completion_tokens=50)
        metrics.record_tokens(prompt_tokens=200, completion_tokens=75)

        assert metrics.prompt_tokens == 300
        assert metrics.completion_tokens == 125
        assert metrics.total_tokens == 425

    def test_record_cost(self):
        """Test recording execution cost."""
        metrics = NodeMetrics(node_type="LLMNode")

        metrics.record_cost(0.01)
        metrics.record_cost(0.02)

        assert metrics.total_cost == pytest.approx(0.03)

    def test_record_custom_metric(self):
        """Test recording custom metrics."""
        metrics = NodeMetrics(node_type="TestNode")

        metrics.record_custom_metric("api_calls", 5)
        metrics.record_custom_metric("api_calls", 10)
        metrics.record_custom_metric("cache_hits", 3)

        assert "api_calls" in metrics.custom_metrics
        assert metrics.custom_metrics["api_calls"] == [5, 10]
        assert metrics.custom_metrics["cache_hits"] == [3]

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = NodeMetrics(node_type="TestNode")
        metrics.record_execution(success=True, duration_ms=100.0)

        metrics_dict = metrics.to_dict()

        assert metrics_dict["node_type"] == "TestNode"
        assert metrics_dict["execution_count"] == 1
        assert "timing" in metrics_dict
        assert "tokens" in metrics_dict
        assert "cost" in metrics_dict


class TestWorkflowMetrics:
    """Tests for WorkflowMetrics dataclass."""

    def test_create_workflow_metrics(self):
        """Test creating workflow metrics."""
        workflow_id = uuid4()
        metrics = WorkflowMetrics(workflow_id=workflow_id)

        assert metrics.workflow_id == workflow_id
        assert metrics.workflow_run_id is None
        assert len(metrics.node_metrics) == 0

    def test_get_or_create_node_metrics(self):
        """Test getting or creating node metrics."""
        workflow_id = uuid4()
        metrics = WorkflowMetrics(workflow_id=workflow_id)

        node_metrics = metrics.get_or_create_node_metrics("TestNode")

        assert node_metrics.node_type == "TestNode"
        assert "TestNode" in metrics.node_metrics

        # Should return same instance on second call
        node_metrics2 = metrics.get_or_create_node_metrics("TestNode")
        assert node_metrics is node_metrics2

    def test_to_dict(self):
        """Test converting workflow metrics to dictionary."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()
        metrics = WorkflowMetrics(
            workflow_id=workflow_id, workflow_run_id=workflow_run_id
        )

        node_metrics = metrics.get_or_create_node_metrics("TestNode")
        node_metrics.record_execution(success=True, duration_ms=100.0)

        metrics_dict = metrics.to_dict()

        assert metrics_dict["workflow_id"] == str(workflow_id)
        assert metrics_dict["workflow_run_id"] == str(workflow_run_id)
        assert "node_metrics" in metrics_dict
        assert "TestNode" in metrics_dict["node_metrics"]


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @pytest.fixture
    def collector(self):
        """Create a fresh metrics collector for each test."""
        return MetricsCollector()

    def test_create_collector(self, collector):
        """Test creating a metrics collector."""
        assert collector is not None
        assert len(collector.get_all_node_type_metrics()) == 0

    def test_record_node_execution(self, collector):
        """Test recording a node execution."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="test_node",
            node_type="TestNode",
            success=True,
            duration_ms=100.0,
        )

        # Check workflow metrics
        workflow_metrics = collector.get_workflow_metrics(workflow_id)
        assert workflow_metrics is not None
        assert workflow_metrics.total_executions == 1
        assert workflow_metrics.total_successes == 1

        # Check node type metrics
        node_metrics = collector.get_node_type_metrics("TestNode")
        assert node_metrics is not None
        assert node_metrics.execution_count == 1

    def test_record_multiple_executions(self, collector):
        """Test recording multiple executions."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record multiple executions
        for i in range(5):
            collector.record_node_execution(
                workflow_id=workflow_id,
                workflow_run_id=workflow_run_id,
                node_id=f"node_{i}",
                node_type="TestNode",
                success=i % 2 == 0,  # Alternate success/failure
                duration_ms=100.0 + i * 10,
            )

        workflow_metrics = collector.get_workflow_metrics(workflow_id)
        assert workflow_metrics.total_executions == 5
        assert workflow_metrics.total_successes == 3
        assert workflow_metrics.total_failures == 2

        node_metrics = collector.get_node_type_metrics("TestNode")
        assert node_metrics.execution_count == 5

    def test_record_with_tokens(self, collector):
        """Test recording execution with token usage."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="llm_node",
            node_type="LLMNode",
            success=True,
            duration_ms=200.0,
            prompt_tokens=100,
            completion_tokens=50,
        )

        node_metrics = collector.get_node_type_metrics("LLMNode")
        assert node_metrics.total_tokens == 150

    def test_record_with_cost(self, collector):
        """Test recording execution with cost."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="llm_node",
            node_type="LLMNode",
            success=True,
            duration_ms=200.0,
            cost=0.05,
        )

        node_metrics = collector.get_node_type_metrics("LLMNode")
        assert node_metrics.total_cost == pytest.approx(0.05)

    def test_record_custom_metric(self, collector):
        """Test recording custom metrics."""
        workflow_id = uuid4()

        collector.record_custom_metric(
            workflow_id=workflow_id,
            node_type="TestNode",
            metric_name="custom_value",
            value=42,
        )

        # First create the workflow by recording an execution
        workflow_run_id = uuid4()
        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="test",
            node_type="TestNode",
            success=True,
            duration_ms=100.0,
        )

        collector.record_custom_metric(
            workflow_id=workflow_id,
            node_type="TestNode",
            metric_name="custom_value",
            value=42,
        )

        workflow_metrics = collector.get_workflow_metrics(workflow_id)
        node_metrics = workflow_metrics.get_or_create_node_metrics("TestNode")
        assert "custom_value" in node_metrics.custom_metrics

    def test_get_all_node_type_metrics(self, collector):
        """Test getting all node type metrics."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Record executions for different node types
        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="node1",
            node_type="TypeA",
            success=True,
            duration_ms=100.0,
        )
        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="node2",
            node_type="TypeB",
            success=True,
            duration_ms=100.0,
        )

        all_metrics = collector.get_all_node_type_metrics()
        assert len(all_metrics) == 2
        assert "TypeA" in all_metrics
        assert "TypeB" in all_metrics

    def test_get_all_workflow_metrics(self, collector):
        """Test getting all workflow metrics."""
        workflow_id1 = uuid4()
        workflow_id2 = uuid4()
        workflow_run_id = uuid4()

        # Record executions for different workflows
        collector.record_node_execution(
            workflow_id=workflow_id1,
            workflow_run_id=workflow_run_id,
            node_id="node1",
            node_type="TestNode",
            success=True,
            duration_ms=100.0,
        )
        collector.record_node_execution(
            workflow_id=workflow_id2,
            workflow_run_id=workflow_run_id,
            node_id="node2",
            node_type="TestNode",
            success=True,
            duration_ms=100.0,
        )

        all_workflow_metrics = collector.get_all_workflow_metrics()
        assert len(all_workflow_metrics) == 2
        assert workflow_id1 in all_workflow_metrics
        assert workflow_id2 in all_workflow_metrics

    def test_clear_metrics(self, collector):
        """Test clearing all metrics."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="test",
            node_type="TestNode",
            success=True,
            duration_ms=100.0,
        )

        assert len(collector.get_all_node_type_metrics()) > 0

        collector.clear()

        assert len(collector.get_all_node_type_metrics()) == 0
        assert len(collector.get_all_workflow_metrics()) == 0

    def test_get_summary(self, collector):
        """Test getting metrics summary."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="node1",
            node_type="TypeA",
            success=True,
            duration_ms=100.0,
        )
        collector.record_node_execution(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="node2",
            node_type="TypeB",
            success=True,
            duration_ms=100.0,
        )

        summary = collector.get_summary()

        assert summary["total_workflows"] == 1
        assert summary["total_node_types"] == 2
        assert "node_type_metrics" in summary


class TestGlobalMetricsCollector:
    """Tests for global metrics collector singleton."""

    def test_get_metrics_collector(self):
        """Test getting the global metrics collector."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        # Should return the same instance
        assert collector1 is collector2

    def test_set_metrics_collector(self):
        """Test setting a custom metrics collector."""
        custom_collector = MetricsCollector()
        set_metrics_collector(custom_collector)

        retrieved_collector = get_metrics_collector()
        assert retrieved_collector is custom_collector

        # Reset to default for other tests
        set_metrics_collector(MetricsCollector())
