"""Test configuration and fixtures for wyrdflow tests."""

from typing import Any

import pytest

from wyrdflow.observability.execution_log import (
    WorkflowExecutionLog,
    set_execution_log,
)


@pytest.fixture  # type: ignore[misc]
def sample_workflow_state() -> dict[str, Any]:
    """Sample workflow state for testing."""
    return {
        "input_data": "test input",
        "processed": False,
        "results": [],
        "metadata": {
            "run_id": "test-123",
            "timestamp": "2025-10-26T00:00:00Z",
        },
    }


@pytest.fixture  # type: ignore[misc]
def mock_node_config() -> dict[str, Any]:
    """Mock node configuration for testing."""
    return {
        "retry_attempts": 3,
        "retry_delay": 1.0,
        "timeout": 30.0,
        "enable_logging": True,
    }


@pytest.fixture(autouse=True)  # type: ignore[misc]
def disable_trace_auto_export():
    """Disable automatic trace export for all tests to avoid filesystem noise.

    This fixture runs automatically before each test and ensures that
    the global execution log is configured to not auto-export traces.
    Tests that specifically test auto-export functionality can override
    this by creating their own WorkflowExecutionLog instances.
    """
    # Create execution log with trace_dir=None to disable auto-export
    test_log = WorkflowExecutionLog(trace_dir=None)
    set_execution_log(test_log)

    yield

    # Clean up after test
    test_log.clear()
