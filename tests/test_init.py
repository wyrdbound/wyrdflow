"""Tests for main package functionality."""

import importlib.metadata

import wyrdflow
from wyrdflow.core import StateInspector, StateSnapshot, WorkflowState


def test_package_import():
    """Test that the main package can be imported."""
    assert wyrdflow is not None
    # Version is defined in pyproject.toml, available via importlib.metadata
    version = importlib.metadata.version("wyrdflow")
    assert version is not None


def test_core_imports():
    """Test that core classes can be imported from wyrdflow.core."""
    # Test WorkflowState
    state = WorkflowState.create_new()
    assert state is not None
    assert hasattr(state, "workflow_id")

    # Test StateInspector
    formatted = StateInspector.format_state(state)
    assert isinstance(formatted, str)
    assert "WorkflowState Overview" in formatted

    # Test StateSnapshot
    snapshot = StateSnapshot.from_state(state)
    assert snapshot is not None
    assert hasattr(snapshot, "snapshot_id")
