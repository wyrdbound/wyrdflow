"""Tests for state inspection and debugging utilities."""

from wyrdflow import WorkflowState, get_state_inspector
from wyrdflow.observability.state_inspector import StateDiff, StateInspector


class TestStateInspector:
    """Test suite for StateInspector class."""

    def test_singleton_pattern(self) -> None:
        """Test that get_state_inspector returns the same instance."""
        inspector1 = get_state_inspector()
        inspector2 = get_state_inspector()
        assert inspector1 is inspector2

    def test_visualize_simple_state(self) -> None:
        """Test visualization of simple state."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")
        state.set("user.age", 30)

        inspector = get_state_inspector()

        # Should not raise any exceptions
        inspector.visualize(state, title="Test State")

    def test_visualize_nested_state(self) -> None:
        """Test visualization of deeply nested state."""
        state = WorkflowState.create_new()
        state.set("config.db.host", "localhost")
        state.set("config.db.port", 5432)
        state.set("config.api.key", "secret")
        state.set("config.api.timeout", 30)

        inspector = get_state_inspector()

        # Should not raise any exceptions
        inspector.visualize(state, title="Nested State")

    def test_visualize_empty_state(self) -> None:
        """Test visualization of empty state."""
        state = WorkflowState.create_new()

        inspector = get_state_inspector()

        # Should not raise any exceptions
        inspector.visualize(state, title="Empty State")

    def test_search_by_path_exact(self) -> None:
        """Test searching by exact path."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")
        state.set("user.age", 30)
        state.set("admin.name", "Bob")

        inspector = get_state_inspector()

        # Search for exact path
        results = inspector.search(state, path_pattern="user.name")
        assert len(results) == 1
        assert results[0]["path"] == "user.name"
        assert results[0]["value"] == "Alice"

    def test_search_by_path_wildcard(self) -> None:
        """Test searching by path with wildcard."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")
        state.set("user.age", 30)
        state.set("admin.name", "Bob")

        inspector = get_state_inspector()

        # Search for all user paths
        results = inspector.search(state, path_pattern="user.*")
        assert len(results) == 2

        paths = {r["path"] for r in results}
        assert "user.name" in paths
        assert "user.age" in paths

    def test_search_by_path_regex(self) -> None:
        """Test searching by path with regex."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")
        state.set("admin.name", "Bob")
        state.set("guest.age", 25)

        inspector = get_state_inspector()

        # Search for all name fields using regex
        results = inspector.search(state, path_pattern=r".*\.name$")
        assert len(results) == 2

        paths = {r["path"] for r in results}
        assert "user.name" in paths
        assert "admin.name" in paths

    def test_search_by_value(self) -> None:
        """Test searching by value."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")
        state.set("user.city", "NYC")
        state.set("admin.name", "Bob")
        state.set("admin.city", "NYC")

        inspector = get_state_inspector()

        # Search for value "NYC"
        results = inspector.search(state, value="NYC")
        assert len(results) == 2

        paths = {r["path"] for r in results}
        assert "user.city" in paths
        assert "admin.city" in paths

    def test_search_by_value_regex(self) -> None:
        """Test searching by value with regex."""
        state = WorkflowState.create_new()
        state.set("user.email", "alice@example.com")
        state.set("admin.email", "bob@example.com")
        state.set("guest.name", "Charlie")

        inspector = get_state_inspector()

        # Search for email addresses using regex
        results = inspector.search(state, value=r".*@example\.com")
        assert len(results) == 2

        values = {r["value"] for r in results}
        assert "alice@example.com" in values
        assert "bob@example.com" in values

    def test_search_with_max_results(self) -> None:
        """Test search with max_results limit."""
        state = WorkflowState.create_new()
        for i in range(10):
            state.set(f"item{i}", i)

        inspector = get_state_inspector()

        # Search for all items but limit results
        results = inspector.search(state, path_pattern="item*", max_results=5)
        assert len(results) == 5

    def test_search_no_matches(self) -> None:
        """Test search with no matches."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")

        inspector = get_state_inspector()

        # Search for non-existent path
        results = inspector.search(state, path_pattern="admin.*")
        assert len(results) == 0

    def test_diff_no_changes(self) -> None:
        """Test diff with no changes."""
        state = WorkflowState.create_new()
        state.set("user.name", "Alice")

        inspector = get_state_inspector()
        diff = inspector.diff(state, state)

        assert len(diff.added_paths) == 0
        assert len(diff.removed_paths) == 0
        assert len(diff.changed_paths) == 0

    def test_diff_added_paths(self) -> None:
        """Test diff with added paths."""
        state1 = WorkflowState.create_new()
        state1.set("user.name", "Alice")

        state2 = WorkflowState.create_new()
        state2.set("user.name", "Alice")
        state2.set("user.age", 30)
        state2.set("user.city", "NYC")

        inspector = get_state_inspector()
        diff = inspector.diff(state1, state2)

        assert len(diff.added_paths) == 2
        assert "user.age" in diff.added_paths
        assert "user.city" in diff.added_paths
        assert len(diff.removed_paths) == 0
        assert len(diff.changed_paths) == 0

    def test_diff_removed_paths(self) -> None:
        """Test diff with removed paths."""
        state1 = WorkflowState.create_new()
        state1.set("user.name", "Alice")
        state1.set("user.age", 30)

        state2 = WorkflowState.create_new()
        state2.set("user.name", "Alice")

        inspector = get_state_inspector()
        diff = inspector.diff(state1, state2)

        assert len(diff.added_paths) == 0
        assert len(diff.removed_paths) == 1
        assert "user.age" in diff.removed_paths
        assert len(diff.changed_paths) == 0

    def test_diff_changed_paths(self) -> None:
        """Test diff with changed values."""
        state1 = WorkflowState.create_new()
        state1.set("user.name", "Alice")
        state1.set("user.age", 30)

        state2 = WorkflowState.create_new()
        state2.set("user.name", "Alice")
        state2.set("user.age", 31)

        inspector = get_state_inspector()
        diff = inspector.diff(state1, state2)

        assert len(diff.added_paths) == 0
        assert len(diff.removed_paths) == 0
        assert len(diff.changed_paths) == 1
        assert "user.age" in diff.changed_paths

    def test_diff_multiple_changes(self) -> None:
        """Test diff with multiple types of changes."""
        state1 = WorkflowState.create_new()
        state1.set("user.name", "Alice")
        state1.set("user.age", 30)
        state1.set("user.city", "NYC")

        state2 = WorkflowState.create_new()
        state2.set("user.name", "Alice")
        state2.set("user.age", 31)  # Changed
        state2.set("user.email", "alice@example.com")  # Added
        # city removed

        inspector = get_state_inspector()
        diff = inspector.diff(state1, state2)

        assert len(diff.added_paths) == 1
        assert "user.email" in diff.added_paths

        assert len(diff.removed_paths) == 1
        assert "user.city" in diff.removed_paths

        assert len(diff.changed_paths) == 1
        assert "user.age" in diff.changed_paths

    def test_diff_format_empty(self) -> None:
        """Test formatting of empty diff."""
        state = WorkflowState.create_new()

        inspector = get_state_inspector()
        diff = inspector.diff(state, state)

        formatted = diff.format()
        assert "No changes" in formatted

    def test_diff_format_with_changes(self) -> None:
        """Test formatting of diff with changes."""
        state1 = WorkflowState.create_new()
        state1.set("user.name", "Alice")

        state2 = WorkflowState.create_new()
        state2.set("user.name", "Alice")
        state2.set("user.age", 30)

        inspector = get_state_inspector()
        diff = inspector.diff(
            state1, state2, label_before="Before", label_after="After"
        )

        formatted = diff.format()
        assert "Before" in formatted
        assert "After" in formatted
        assert "user.age" in formatted

    def test_diff_with_custom_labels(self) -> None:
        """Test diff with custom labels."""
        state1 = WorkflowState.create_new()
        state1.set("value", 1)

        state2 = WorkflowState.create_new()
        state2.set("value", 2)

        inspector = get_state_inspector()
        diff = inspector.diff(
            state1, state2, label_before="Initial", label_after="Final"
        )

        assert diff.label_before == "Initial"
        assert diff.label_after == "Final"

    def test_search_nested_values(self) -> None:
        """Test searching in nested structures."""
        state = WorkflowState.create_new()
        state.set("config.api.endpoints.users", "/api/users")
        state.set("config.api.endpoints.posts", "/api/posts")
        state.set("config.db.host", "localhost")

        inspector = get_state_inspector()

        # Search for all endpoints
        results = inspector.search(state, path_pattern="config.api.endpoints.*")
        assert len(results) == 2

    def test_diff_nested_changes(self) -> None:
        """Test diff with nested value changes."""
        state1 = WorkflowState.create_new()
        state1.set("config.db.host", "localhost")
        state1.set("config.db.port", 5432)

        state2 = WorkflowState.create_new()
        state2.set("config.db.host", "db.example.com")
        state2.set("config.db.port", 5432)

        inspector = get_state_inspector()
        diff = inspector.diff(state1, state2)

        assert len(diff.changed_paths) == 1
        assert "config.db.host" in diff.changed_paths


class TestStateDiff:
    """Test suite for StateDiff model."""

    def test_state_diff_creation(self) -> None:
        """Test creating a StateDiff."""
        diff = StateDiff(
            before={"user": {"name": "Alice"}},
            after={"user": {"name": "Bob"}},
            added={},
            removed={},
            modified={"user.name": ("Alice", "Bob")},
            unchanged=set(),
        )

        assert diff.before == {"user": {"name": "Alice"}}
        assert diff.after == {"user": {"name": "Bob"}}
        assert "user.name" in diff.changed_paths

    def test_state_diff_format_added(self) -> None:
        """Test formatting diff with added paths."""
        diff = StateDiff(
            before={},
            after={"user": {"name": "Alice"}},
            added={"user.name": "Alice"},
            removed={},
            modified={},
            unchanged=set(),
        )

        formatted = diff.format()
        assert "Added Paths" in formatted
        assert "user.name" in formatted

    def test_state_diff_format_removed(self) -> None:
        """Test formatting diff with removed paths."""
        diff = StateDiff(
            before={"user": {"name": "Alice"}},
            after={},
            added={},
            removed={"user.name": "Alice"},
            modified={},
            unchanged=set(),
        )

        formatted = diff.format()
        assert "Removed Paths" in formatted
        assert "user.name" in formatted

    def test_state_diff_format_changed(self) -> None:
        """Test formatting diff with changed paths."""
        diff = StateDiff(
            before={"user": {"age": 30}},
            after={"user": {"age": 31}},
            added={},
            removed={},
            modified={"user.age": (30, 31)},
            unchanged=set(),
        )

        formatted = diff.format()
        assert "Changed Paths" in formatted
        assert "user.age" in formatted

    def test_state_diff_custom_labels(self) -> None:
        """Test StateDiff with custom labels."""
        diff = StateDiff(
            before={},
            after={"value": 1},
            added={"value": 1},
            removed={},
            modified={},
            unchanged=set(),
            label_before="Start",
            label_after="End",
        )

        formatted = diff.format()
        assert "Start" in formatted
        assert "End" in formatted


def test_state_inspector_instance() -> None:
    """Test StateInspector direct instantiation."""
    inspector = StateInspector()

    state = WorkflowState.create_new()
    state.set("test", "value")

    # Should work without any issues
    inspector.visualize(state)
    results = inspector.search(state, path_pattern="test")
    assert len(results) == 1


def test_visualize_tree_static_method() -> None:
    """Test the static visualize_tree method."""
    state = WorkflowState.create_new()
    state.set("user.name", "Alice")
    state.set("user.age", 30)

    # Test static method
    tree_output = StateInspector.visualize_tree(state)

    assert "WorkflowState:" in tree_output
    assert "user.name" in tree_output or "name" in tree_output
    assert "Alice" in tree_output
