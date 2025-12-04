"""State inspection utilities for workflow debugging."""

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from wyrdflow.core.state import WorkflowState


class StateDiff(BaseModel):
    """Represents differences between two states."""

    before: dict[str, Any] = Field(
        default_factory=dict, description="State before changes"
    )
    after: dict[str, Any] = Field(
        default_factory=dict, description="State after changes"
    )
    added: dict[str, Any] = Field(default_factory=dict, description="Keys added")
    removed: dict[str, Any] = Field(default_factory=dict, description="Keys removed")
    modified: dict[str, tuple[Any, Any]] = Field(
        default_factory=dict, description="Keys modified (old, new)"
    )
    unchanged: set[str] = Field(default_factory=set, description="Keys unchanged")
    label_before: str = Field(default="Before", description="Label for before state")
    label_after: str = Field(default="After", description="Label for after state")

    @property
    def added_paths(self) -> set[str]:
        """Get set of added paths."""
        return set(self.added.keys())

    @property
    def removed_paths(self) -> set[str]:
        """Get set of removed paths."""
        return set(self.removed.keys())

    @property
    def changed_paths(self) -> set[str]:
        """Get set of changed paths."""
        return set(self.modified.keys())

    def format(self) -> str:
        """Format the diff as a human-readable string.

        Returns:
            Formatted diff string
        """
        lines = [f"State Diff: {self.label_before} → {self.label_after}\n"]

        if self.added:
            lines.append("Added Paths:")
            for key, value in sorted(self.added.items()):
                value_str = repr(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                lines.append(f"  + {key} = {value_str}")
            lines.append("")

        if self.modified:
            lines.append("Changed Paths:")
            for key, (old, new) in sorted(self.modified.items()):
                old_str = repr(old)
                new_str = repr(new)
                if len(old_str) > 40:
                    old_str = old_str[:37] + "..."
                if len(new_str) > 40:
                    new_str = new_str[:37] + "..."
                lines.append(f"  ~ {key}: {old_str} → {new_str}")
            lines.append("")

        if self.removed:
            lines.append("Removed Paths:")
            for key in sorted(self.removed.keys()):
                lines.append(f"  - {key}")
            lines.append("")

        if not self.added and not self.modified and not self.removed:
            lines.append("No changes detected")
            lines.append("")

        return "\n".join(lines)


class StateInspector:
    """Utility for inspecting and analyzing workflow state.

    Provides methods for visualizing state, comparing states,
    searching within state, and exporting state in various formats.
    """

    def visualize(
        self,
        state: WorkflowState,
        title: str = "Workflow State",
        show_metadata: bool = False,
        max_depth: int = 10,
    ) -> None:
        """Visualize state as an interactive tree using Rich.

        Args:
            state: WorkflowState to visualize
            title: Title for the visualization
            show_metadata: Whether to show metadata
            max_depth: Maximum depth to traverse
        """
        console = Console()

        tree = Tree(f"[bold cyan]{title}[/bold cyan]")

        def _add_to_tree(
            parent: Tree, obj: Any, depth: int = 0, prefix: str = ""
        ) -> None:
            """Recursively add items to tree."""
            if depth >= max_depth:
                parent.add("[dim]... (max depth)[/dim]")
                return

            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{prefix}.{key}" if prefix else key

                    if isinstance(value, dict):
                        branch = parent.add(f"[green]{key}[/green]")
                        _add_to_tree(branch, value, depth + 1, current_path)
                    elif isinstance(value, list):
                        branch = parent.add(f"[green]{key}[/green] [dim](list)[/dim]")
                        _add_to_tree(branch, value, depth + 1, current_path)
                    else:
                        value_str = _format_value(value)
                        parent.add(f"[green]{key}[/green]: {value_str}")

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        branch = parent.add(f"[yellow][{i}][/yellow]")
                        _add_to_tree(branch, item, depth + 1, f"{prefix}[{i}]")
                    else:
                        value_str = _format_value(item)
                        parent.add(f"[yellow][{i}][/yellow]: {value_str}")

        def _format_value(value: Any) -> str:
            """Format a value for display."""
            if value is None:
                return "[dim]None[/dim]"

            if isinstance(value, bool):
                return f"[cyan]{value}[/cyan]"

            if isinstance(value, str):
                if len(value) > 50:
                    return f'[blue]"{value[:47]}..."[/blue]'
                return f'[blue]"{value}"[/blue]'

            if isinstance(value, (int, float)):
                return f"[magenta]{value}[/magenta]"

            # For other types, show type and truncated repr
            repr_str = repr(value)
            return (
                f"[dim]{type(value).__name__}(...)[/dim]"
                if len(repr_str) > 50
                else f"[dim]{repr_str}[/dim]"
            )

        # Add data tree
        data_branch = tree.add("[bold]data[/bold]")
        _add_to_tree(data_branch, state.data, 0)

        # Optionally add metadata
        if show_metadata and state.metadata:
            meta_branch = tree.add("[bold]metadata[/bold]")
            _add_to_tree(meta_branch, state.metadata, 0)

        # Print in a panel
        panel = Panel(
            tree,
            title=f"[bold]{title}[/bold]",
            border_style="blue",
        )
        console.print(panel)

    def search(
        self,
        state: WorkflowState,
        path_pattern: Optional[str] = None,
        value: Optional[Any] = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for values in state by path pattern or value.

        Args:
            state: WorkflowState to search
            path_pattern: Pattern to match paths (supports * wildcard and regex)
            value: Value to search for (supports regex for strings)
            max_results: Maximum number of results to return

        Returns:
            List of dicts with 'path' and 'value' keys
        """
        results: list[dict[str, Any]] = []

        def _matches_pattern(path: str, pattern: str) -> bool:
            """Check if path matches pattern."""
            # Convert wildcard to regex
            if "*" in pattern and not pattern.startswith(".*"):
                # Simple wildcard
                regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
                return bool(re.match(f"^{regex_pattern}$", path))
            else:
                # Assume it's a regex or exact match
                try:
                    return bool(re.match(pattern, path))
                except re.error:
                    # If regex is invalid, do exact match
                    return path == pattern

        def _matches_value(val: Any, search_val: Any) -> bool:
            """Check if value matches search value."""
            if isinstance(search_val, str) and isinstance(val, str):
                # Try regex match for strings
                try:
                    return bool(re.search(search_val, val))
                except re.error:
                    # If regex is invalid, do exact match
                    return bool(val == search_val)
            return bool(val == search_val)

        def _search_recursive(obj: Any, path: str = "") -> None:
            """Recursively search through nested structures."""
            if len(results) >= max_results:
                return

            if isinstance(obj, dict):
                for key, val in obj.items():
                    current_path = f"{path}.{key}" if path else key

                    # Check path pattern
                    path_match = path_pattern is None or _matches_pattern(
                        current_path, path_pattern
                    )

                    # Check value
                    value_match = value is None or _matches_value(val, value)

                    if path_match and value_match:
                        results.append({"path": current_path, "value": val})

                    # Recurse into nested structures
                    if isinstance(val, (dict, list)):
                        _search_recursive(val, current_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"

                    # Check value match for list items
                    if value is not None and _matches_value(item, value):
                        results.append({"path": current_path, "value": item})

                    # Recurse into nested structures
                    if isinstance(item, (dict, list)):
                        _search_recursive(item, current_path)

        _search_recursive(state.data)
        return results[:max_results]

    def diff(
        self,
        before: WorkflowState,
        after: WorkflowState,
        label_before: str = "Before",
        label_after: str = "After",
    ) -> StateDiff:
        """Compare two states and return detailed differences.

        Args:
            before: State before changes
            after: State after changes
            label_before: Label for before state
            label_after: Label for after state

        Returns:
            StateDiff object with comprehensive change information
        """
        before_data = before.data
        after_data = after.data

        # Find differences at all levels
        def _deep_diff(
            obj1: Any, obj2: Any, path: str = ""
        ) -> tuple[dict[str, Any], dict[str, Any], dict[str, tuple[Any, Any]]]:
            """Recursively compare two objects."""
            added: dict[str, Any] = {}
            removed: dict[str, Any] = {}
            modified: dict[str, tuple[Any, Any]] = {}

            if isinstance(obj1, dict) and isinstance(obj2, dict):
                # Keys only in obj2 (added)
                for key in obj2.keys() - obj1.keys():
                    current_path = f"{path}.{key}" if path else key
                    added[current_path] = obj2[key]

                # Keys only in obj1 (removed)
                for key in obj1.keys() - obj2.keys():
                    current_path = f"{path}.{key}" if path else key
                    removed[current_path] = obj1[key]

                # Keys in both (check for modifications)
                for key in obj1.keys() & obj2.keys():
                    current_path = f"{path}.{key}" if path else key
                    val1, val2 = obj1[key], obj2[key]

                    if isinstance(val1, dict) and isinstance(val2, dict):
                        # Recurse into nested dicts
                        sub_added, sub_removed, sub_modified = _deep_diff(
                            val1, val2, current_path
                        )
                        added.update(sub_added)
                        removed.update(sub_removed)
                        modified.update(sub_modified)
                    elif val1 != val2:
                        modified[current_path] = (val1, val2)

            elif obj1 != obj2:
                # Non-dict values that differ
                if path:
                    modified[path] = (obj1, obj2)

            return added, removed, modified

        added, removed, modified = _deep_diff(before_data, after_data)

        # Find unchanged keys (top-level only for simplicity)
        unchanged = set()
        if isinstance(before_data, dict) and isinstance(after_data, dict):
            modified_keys = {k.split(".")[0] for k in modified}
            for key in before_data.keys() & after_data.keys():
                if key not in modified_keys:
                    unchanged.add(key)

        return StateDiff(
            before=before_data,
            after=after_data,
            added=added,
            removed=removed,
            modified=modified,
            unchanged=unchanged,
            label_before=label_before,
            label_after=label_after,
        )

    @staticmethod
    def visualize_tree(state: WorkflowState, max_depth: int = 10) -> str:
        """Visualize state as a tree structure.

        Args:
            state: WorkflowState to visualize
            max_depth: Maximum depth to traverse (prevents infinite recursion)

        Returns:
            Tree representation as a string
        """
        lines = ["WorkflowState:"]
        lines.append(f"  workflow_id: {state.workflow_id}")
        lines.append(f"  workflow_run_id: {state.workflow_run_id}")
        lines.append("  data:")

        def _add_tree_lines(obj: Any, prefix: str = "    ", depth: int = 0) -> None:
            """Recursively add tree lines for nested structures."""
            if depth >= max_depth:
                lines.append(f"{prefix}... (max depth reached)")
                return

            if isinstance(obj, dict):
                items = list(obj.items())
                for i, (key, value) in enumerate(items):
                    is_last_item = i == len(items) - 1
                    connector = "└─" if is_last_item else "├─"
                    lines.append(f"{prefix}{connector} {key}")

                    # Prepare prefix for children
                    child_prefix = prefix + ("    " if is_last_item else "│   ")

                    if isinstance(value, (dict, list)):
                        _add_tree_lines(value, child_prefix, depth + 1)
                    else:
                        # Leaf node - show value
                        value_str = _format_value(value)
                        lines.append(f"{child_prefix}  → {value_str}")

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    is_last_item = i == len(obj) - 1
                    connector = "└─" if is_last_item else "├─"
                    lines.append(f"{prefix}{connector} [{i}]")

                    child_prefix = prefix + ("    " if is_last_item else "│   ")

                    if isinstance(item, (dict, list)):
                        _add_tree_lines(item, child_prefix, depth + 1)
                    else:
                        value_str = _format_value(item)
                        lines.append(f"{child_prefix}  → {value_str}")

        def _format_value(value: Any) -> str:
            """Format a value for display."""
            if value is None:
                return "None"
            if isinstance(value, str):
                # Truncate long strings
                if len(value) > 50:
                    return f'"{value[:47]}..."'
                return f'"{value}"'
            if isinstance(value, (int, float, bool)):
                return str(value)
            # For other types, show type and truncated repr
            repr_str = repr(value)
            if len(repr_str) > 50:
                return f"{type(value).__name__}(...)"
            return repr_str

        _add_tree_lines(state.data)
        return "\n".join(lines)

    @staticmethod
    def get_value(state: WorkflowState, path: str) -> Any:
        """Get value at a specific path in the state.

        Args:
            state: WorkflowState to query
            path: Dot-notation path (e.g., "user.profile.name")

        Returns:
            Value at path, or None if not found

        Examples:
            >>> inspector = StateInspector()
            >>> value = inspector.get_value(state, "user.profile.name")
        """
        return state.get(path)

    @staticmethod
    def format_diff(diff: StateDiff, show_unchanged: bool = False) -> str:
        """Format a StateDiff as a human-readable string.

        Args:
            diff: StateDiff to format
            show_unchanged: Whether to show unchanged keys

        Returns:
            Formatted diff string
        """
        lines = ["State Diff:"]

        if diff.added:
            lines.append("\n✅ Added:")
            for key, value in diff.added.items():
                value_str = repr(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                lines.append(f"  + {key}: {value_str}")

        if diff.removed:
            lines.append("\n❌ Removed:")
            for key, value in diff.removed.items():
                value_str = repr(value)
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                lines.append(f"  - {key}: {value_str}")

        if diff.modified:
            lines.append("\n📝 Modified:")
            for key, (old, new) in diff.modified.items():
                old_str = repr(old)
                new_str = repr(new)
                if len(old_str) > 30:
                    old_str = old_str[:27] + "..."
                if len(new_str) > 30:
                    new_str = new_str[:27] + "..."
                lines.append(f"  ~ {key}:")
                lines.append(f"      Before: {old_str}")
                lines.append(f"      After:  {new_str}")

        if show_unchanged and diff.unchanged:
            lines.append("\n⚪ Unchanged:")
            for key in sorted(diff.unchanged):
                lines.append(f"  = {key}")

        if not diff.added and not diff.removed and not diff.modified:
            lines.append("\n✨ No changes detected")

        return "\n".join(lines)

    @staticmethod
    def export_json(state: WorkflowState, pretty: bool = True) -> str:
        """Export state as JSON string.

        Args:
            state: WorkflowState to export
            pretty: Whether to format JSON with indentation

        Returns:
            JSON string representation of state
        """
        state_dict = {
            "workflow_id": str(state.workflow_id),
            "workflow_run_id": str(state.workflow_run_id),
            "data": state.data,
            "metadata": state.metadata,
        }

        if pretty:
            return json.dumps(state_dict, indent=2, default=str)
        return json.dumps(state_dict, default=str)

    @staticmethod
    def summary(state: WorkflowState) -> str:
        """Get a summary of the state.

        Args:
            state: WorkflowState to summarize

        Returns:
            Summary string with key statistics
        """

        def _count_items(obj: Any) -> tuple[int, int]:
            """Count total keys and nested depth."""
            if not isinstance(obj, dict):
                return 0, 0

            count = len(obj)
            max_depth = 0

            for value in obj.values():
                if isinstance(value, dict):
                    nested_count, nested_depth = _count_items(value)
                    count += nested_count
                    max_depth = max(max_depth, nested_depth + 1)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            nested_count, nested_depth = _count_items(item)
                            count += nested_count
                            max_depth = max(max_depth, nested_depth + 1)

            return count, max_depth

        total_keys, max_depth = _count_items(state.data)

        lines = [
            "State Summary:",
            f"  Workflow ID: {state.workflow_id}",
            f"  Run ID: {state.workflow_run_id}",
            f"  Total Keys: {total_keys}",
            f"  Top-Level Keys: {len(state.data)}",
            f"  Max Nesting Depth: {max_depth}",
            f"  Metadata Keys: {len(state.metadata)}",
        ]

        return "\n".join(lines)


# Singleton instance
_state_inspector: Optional[StateInspector] = None


def get_state_inspector() -> StateInspector:
    """Get the global StateInspector instance.

    Returns:
        StateInspector singleton instance
    """
    global _state_inspector  # noqa: PLW0603
    if _state_inspector is None:
        _state_inspector = StateInspector()
    return _state_inspector
