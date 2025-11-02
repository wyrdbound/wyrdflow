"""Tests for WorkflowState class."""

from datetime import datetime
import time
from uuid import UUID, uuid4

import pytest

from wyrdflow.core import StateInspector, StateSnapshot, WorkflowState


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

    def test_get_nested_dot_notation(self):
        """Test get with nested dot notation (default behavior)."""
        state = WorkflowState.create_new()

        # Set up nested structure
        state.data = {
            "user": {"name": "Alice", "age": 30, "address": {"city": "NYC"}},
            "config": {"debug": True},
        }

        # Test nested access (default nested=True)
        assert state.get("user.name") == "Alice"
        assert state.get("user.age") == 30
        assert state.get("user.address.city") == "NYC"
        assert state.get("config.debug") is True

        # Test missing nested paths
        assert state.get("user.missing") is None
        assert state.get("user.missing", "default") == "default"
        assert state.get("missing.nested.path") is None
        assert state.get("user.name.invalid") is None  # name is not a dict

    def test_get_literal_key_with_dots(self):
        """Test get with literal keys containing dots."""
        state = WorkflowState.create_new()

        # Set up data with literal dot keys
        state.data = {"file.txt": "contents", "api.response": {"status": 200}}

        # Test literal access with nested=False
        assert state.get("file.txt", nested=False) == "contents"
        assert state.get("api.response", nested=False) == {"status": 200}

        # With nested=True (default), these would look for nested paths
        assert state.get("file.txt") is None  # Looks for data["file"]["txt"]
        assert state.get("api.response") is None  # Looks for data["api"]["response"]

    def test_get_nested_invalid_key_format(self):
        """Test get raises ValueError for invalid nested keys."""
        state = WorkflowState.create_new()

        # Empty parts in path should raise ValueError
        with pytest.raises(ValueError, match="contains empty parts"):
            state.get("a..b")

        with pytest.raises(ValueError, match="contains empty parts"):
            state.get(".key")

        with pytest.raises(ValueError, match="contains empty parts"):
            state.get("key.")

        # These should work fine with nested=False
        state.data = {"a..b": "value1", ".key": "value2", "key.": "value3"}
        assert state.get("a..b", nested=False) == "value1"
        assert state.get(".key", nested=False) == "value2"
        assert state.get("key.", nested=False) == "value3"

    def test_get_nested_non_dict_in_path(self):
        """Test get handles non-dict values in nested path gracefully."""
        state = WorkflowState.create_new()

        # Set up structure where intermediate value is not a dict
        state.data = {
            "user": {"name": "Alice", "age": 30},  # age is int, not dict
            "settings": "simple_string",  # string, not dict
        }

        # Trying to traverse through non-dict should return default
        assert state.get("user.age.invalid") is None
        assert state.get("user.age.invalid", "default") == "default"
        assert state.get("settings.nested") is None
        assert state.get("settings.nested.deep") is None

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


class TestStateSnapshot:
    """Test suite for StateSnapshot class."""

    def test_create_snapshot_from_state(self):
        """Test creating a snapshot from WorkflowState."""
        # Create a state with some data
        state = WorkflowState.create_new()
        state.set("test_data", "test_value")
        state.set_metadata("test_meta", "meta_value")

        # Create snapshot
        snapshot = StateSnapshot.from_state(state, source_node_id="test_node")

        assert snapshot.workflow_id == state.workflow_id
        assert snapshot.workflow_run_id == state.workflow_run_id
        assert snapshot.source_node_id == "test_node"
        assert snapshot.data["test_data"] == "test_value"
        assert snapshot.metadata["test_meta"] == "meta_value"
        assert isinstance(snapshot.snapshot_id, UUID)

    def test_snapshot_is_immutable(self):
        """Test that snapshots are immutable."""
        state = WorkflowState.create_new()
        snapshot = StateSnapshot.from_state(state)

        # Should not be able to modify snapshot fields
        with pytest.raises(ValueError):
            snapshot.workflow_id = uuid4()  # type: ignore[misc]

    def test_restore_state_from_snapshot(self):
        """Test restoring a WorkflowState from snapshot."""
        # Create original state
        original_state = WorkflowState.create_new()
        original_state.set("test_data", "test_value")
        original_state.set_metadata("test_meta", "meta_value")

        # Create snapshot
        snapshot = StateSnapshot.from_state(original_state)

        # Restore state
        restored_state = snapshot.restore()

        assert restored_state.workflow_id == original_state.workflow_id
        assert restored_state.workflow_run_id == original_state.workflow_run_id
        assert restored_state.get("test_data") == "test_value"
        assert restored_state.get_metadata("test_meta") == "meta_value"

        # Verify they are separate objects
        restored_state.set("new_data", "new_value")
        assert original_state.get("new_data") is None

    def test_snapshot_with_extra_fields(self):
        """Test snapshot handles extra fields correctly."""
        # Create state with extra fields
        state_dict = {
            "workflow_id": uuid4(),
            "workflow_run_id": uuid4(),
            "data": {"test": "data"},
            "metadata": {"test": "meta"},
            "custom_field": "custom_value",
        }
        state = WorkflowState(**state_dict)

        # Create snapshot
        snapshot = StateSnapshot.from_state(state)

        # Restore and check extra fields
        restored_state = snapshot.restore()
        assert hasattr(restored_state, "custom_field")
        assert restored_state.custom_field == "custom_value"  # type: ignore[attr-defined]


class TestStateInspector:
    """Test suite for StateInspector class."""

    def test_format_state_basic(self):
        """Test basic state formatting."""
        state = WorkflowState.create_new()
        state.set("simple_key", "simple_value")
        state.set_metadata("meta_key", "meta_value")

        formatted = StateInspector.format_state(state)

        assert "WorkflowState Overview" in formatted
        assert str(state.workflow_id) in formatted
        assert 'simple_key: "simple_value"' in formatted
        assert 'meta_key: "meta_value"' in formatted

    def test_format_state_without_metadata(self):
        """Test state formatting without metadata."""
        state = WorkflowState.create_new()
        state.set("test_key", "test_value")

        formatted = StateInspector.format_state(state, include_metadata=False)

        assert 'test_key: "test_value"' in formatted
        assert "Metadata" not in formatted

    def test_format_state_with_nested_data(self):
        """Test formatting state with nested data structures."""
        state = WorkflowState.create_new()
        state.set("nested", {"level1": {"level2": "deep_value"}})
        state.set("list_data", [1, 2, 3, 4, 5])

        formatted = StateInspector.format_state(state, max_depth=2)

        assert "nested:" in formatted
        assert "level1:" in formatted
        assert "list_data:" in formatted

    def test_compare_states_no_changes(self):
        """Test comparing identical states."""
        state1 = WorkflowState.create_new()
        state1.set("test_key", "test_value")

        # Create a copy
        state2 = WorkflowState(**state1.model_dump())

        diff = StateInspector.compare_states(state1, state2)

        assert not diff["workflow_id_changed"]
        assert not diff["workflow_run_id_changed"]
        assert len(diff["data_changes"]["added"]) == 0
        assert len(diff["data_changes"]["removed"]) == 0
        assert len(diff["data_changes"]["modified"]) == 0

    def test_compare_states_with_changes(self):
        """Test comparing states with differences."""
        state1 = WorkflowState.create_new()
        state1.set("existing_key", "old_value")
        state1.set("remove_key", "will_be_removed")

        state2 = WorkflowState(**state1.model_dump())
        state2.set("existing_key", "new_value")  # Modified
        state2.set("added_key", "new_value")  # Added
        state2.data.pop("remove_key")  # Removed

        diff = StateInspector.compare_states(state1, state2)

        # Check changes
        assert "existing_key" in diff["data_changes"]["modified"]
        assert diff["data_changes"]["modified"]["existing_key"]["old"] == "old_value"
        assert diff["data_changes"]["modified"]["existing_key"]["new"] == "new_value"
        assert "added_key" in diff["data_changes"]["added"]
        assert "remove_key" in diff["data_changes"]["removed"]

    def test_search_state_in_keys(self):
        """Test searching for terms in state keys."""
        state = WorkflowState.create_new()
        state.set("user_name", "john")
        state.set("user_email", "john@example.com")
        state.set("system_info", "data")

        results = StateInspector.search_state(
            state, "user", search_keys=True, search_values=False
        )

        assert len(results) == 2
        assert all(result["match_in"] == "key" for result in results)
        assert any("user_name" in result["path"] for result in results)
        assert any("user_email" in result["path"] for result in results)

    def test_search_state_in_values(self):
        """Test searching for terms in state values."""
        state = WorkflowState.create_new()
        state.set("name", "john doe")
        state.set("email", "john@example.com")
        state.set("city", "New York")

        results = StateInspector.search_state(
            state, "john", search_keys=False, search_values=True
        )

        assert len(results) == 2
        assert all(result["match_in"] == "value" for result in results)

    def test_search_state_case_insensitive(self):
        """Test case-insensitive search."""
        state = WorkflowState.create_new()
        state.set("USER_NAME", "John Doe")

        # Case insensitive search (default)
        results = StateInspector.search_state(state, "user")
        assert len(results) == 1

        results = StateInspector.search_state(state, "john")
        assert len(results) == 1

        # Case sensitive search
        results = StateInspector.search_state(state, "user", case_sensitive=True)
        assert len(results) == 0

        results = StateInspector.search_state(state, "USER", case_sensitive=True)
        assert len(results) == 1

    def test_search_state_nested_data(self):
        """Test searching in nested data structures."""
        state = WorkflowState.create_new()
        state.set("user", {"profile": {"name": "john", "settings": {"theme": "dark"}}})

        results = StateInspector.search_state(state, "john")

        assert len(results) == 1
        assert "user.profile.name" in results[0]["path"]

    def test_search_state_empty_results(self):
        """Test search with no matches."""
        state = WorkflowState.create_new()
        state.set("test_key", "test_value")

        results = StateInspector.search_state(state, "nonexistent")

        assert len(results) == 0
