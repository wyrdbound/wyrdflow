"""Test configuration and fixtures for wyrdflow tests."""

from typing import Any

import pytest


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
