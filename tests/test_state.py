"""Tests for WorkflowState class."""

from datetime import datetime
import time
from uuid import UUID, uuid4

import pytest

from wyrdflow.core import WorkflowState


class TestWorkflowState:
    """Test suite for WorkflowState class."""

    def test_create_new_generates_uuids(self):
        """Test that create_new generates proper UUIDs."""
        state = WorkflowState.create_new()

        assert isinstance(state.workflow_id, UUID)
        assert isinstance(state.workflow_run_id, UUID)
        assert state.workflow_id != state.workflow_run_id

    def test_create_new_with_custom_workflow_id(self):
        """Test create_new with custom workflow ID."""
        custom_id = uuid4()
        state = WorkflowState.create_new(workflow_id=custom_id)

        assert state.workflow_id == custom_id
        assert isinstance(state.workflow_run_id, UUID)
        assert state.workflow_id != state.workflow_run_id

    def test_create_new_with_initial_data(self):
        """Test create_new with initial data and metadata."""
        initial_data = {"key1": "value1", "key2": 42}
        initial_metadata = {"source": "test", "version": "1.0"}

        state = WorkflowState.create_new(
            initial_data=initial_data, initial_metadata=initial_metadata
        )

        assert state.data == initial_data
        assert state.metadata == initial_metadata

    def test_timestamps_auto_populated(self):
        """Test that timestamps are automatically populated."""
        before = datetime.utcnow()
        state = WorkflowState.create_new()
        after = datetime.utcnow()

        assert before <= state.created_at <= after
        assert before <= state.updated_at <= after

    def test_get_set_data(self):
        """Test get and set methods for data."""
        state = WorkflowState.create_new()

        # Test default value
        assert state.get("nonexistent") is None
        assert state.get("nonexistent", "default") == "default"

        # Test set and get
        state.set("test_key", "test_value")
        assert state.get("test_key") == "test_value"

    def test_update_data(self):
        """Test update method for multiple data changes."""
        state = WorkflowState.create_new()
        original_updated_at = state.updated_at

        # Small delay to ensure timestamp changes
        time.sleep(0.001)

        updates = {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}
        state.update(updates)

        assert state.get("key1") == "value1"
        assert state.get("key2") == 42
        assert state.get("key3") == [1, 2, 3]
        assert state.updated_at > original_updated_at

    def test_metadata_operations(self):
        """Test metadata get and set operations."""
        state = WorkflowState.create_new()

        # Test default value
        assert state.get_metadata("nonexistent") is None
        assert state.get_metadata("nonexistent", "default") == "default"

        # Test set and get metadata
        state.set_metadata("test_meta", "meta_value")
        assert state.get_metadata("test_meta") == "meta_value"

    def test_copy_for_node(self):
        """Test copy_for_node creates proper copy with node tracking."""
        original_state = WorkflowState.create_new()
        original_state.set("shared_data", "test_value")
        original_state.set_metadata("original_meta", "original")

        # Create copy for node
        node_state = original_state.copy_for_node("test_node_123")

        # Check that IDs are preserved
        assert node_state.workflow_id == original_state.workflow_id
        assert node_state.workflow_run_id == original_state.workflow_run_id

        # Check that data is deep copied
        assert node_state.get("shared_data") == "test_value"

        # Check that node-specific metadata is added
        assert node_state.get_metadata("current_node_id") == "test_node_123"
        assert node_state.get_metadata("execution_history") == ["test_node_123"]

        # Check that original metadata is preserved
        assert node_state.get_metadata("original_meta") == "original"

        # Verify they are separate objects
        node_state.set("new_data", "node_only")
        assert original_state.get("new_data") is None

    def test_copy_for_node_with_existing_history(self):
        """Test copy_for_node appends to existing execution history."""
        state = WorkflowState.create_new()
        state.set_metadata("execution_history", ["node1", "node2"])

        node_state = state.copy_for_node("node3")

        expected_history = ["node1", "node2", "node3"]
        assert node_state.get_metadata("execution_history") == expected_history

    def test_pydantic_validation(self):
        """Test Pydantic validation and serialization."""
        workflow_id = uuid4()
        workflow_run_id = uuid4()

        # Test direct instantiation
        state = WorkflowState(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            data={"test": "data"},
            metadata={"test": "meta"},
        )

        assert state.workflow_id == workflow_id
        assert state.workflow_run_id == workflow_run_id
        assert state.data["test"] == "data"
        assert state.metadata["test"] == "meta"

    def test_model_dump_serialization(self):
        """Test that the model can be serialized to dict."""
        state = WorkflowState.create_new()
        state.set("test_data", "value")
        state.set_metadata("test_meta", "meta_value")

        serialized = state.model_dump()

        assert "workflow_id" in serialized
        assert "workflow_run_id" in serialized
        assert "created_at" in serialized
        assert "updated_at" in serialized
        assert serialized["data"]["test_data"] == "value"
        assert serialized["metadata"]["test_meta"] == "meta_value"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed in the model."""
        state_dict = {
            "workflow_id": uuid4(),
            "workflow_run_id": uuid4(),
            "custom_field": "custom_value",
            "another_field": {"nested": "data"},
        }

        state = WorkflowState(**state_dict)

        # Extra fields should be accessible
        assert hasattr(state, "custom_field")
        assert state.custom_field == "custom_value"  # type: ignore[attr-defined]
        assert hasattr(state, "another_field")

    def test_validate_assignment(self):
        """Test that assignment validation works."""
        state = WorkflowState.create_new()

        # This should work - valid UUID
        new_uuid = uuid4()
        state.workflow_id = new_uuid
        assert state.workflow_id == new_uuid

        # This should raise validation error - invalid type
        with pytest.raises(ValueError):
            state.workflow_id = "not-a-uuid"  # type: ignore[assignment]
