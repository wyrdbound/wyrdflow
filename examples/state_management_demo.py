#!/usr/bin/env python3
"""Demonstration of Wyrdflow state management capabilities.

This example shows how to use the state inspection utilities and
snapshot/restore mechanisms for debugging and analysis.
"""

import asyncio

from wyrdflow.core import StateInspector, StateSnapshot, WorkflowState


def demonstrate_state_inspection():
    """Demonstrate state inspection utilities."""
    print("🔍 State Inspection Demo")
    print("=" * 50)

    # Create a workflow state with some complex data
    state = WorkflowState.create_new()
    state.set(
        "user_profile",
        {
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "preferences": {"theme": "dark", "notifications": True, "language": "en"},
            "activity": [
                {"action": "login", "timestamp": "2024-10-28T10:00:00Z"},
                {"action": "view_dashboard", "timestamp": "2024-10-28T10:01:00Z"},
                {"action": "create_workflow", "timestamp": "2024-10-28T10:05:00Z"},
            ],
        },
    )
    state.set(
        "processing_stats",
        {"total_records": 1500, "processed": 1200, "errors": 50, "success_rate": 0.94},
    )
    state.set_metadata("pipeline_version", "2.1.3")
    state.set_metadata("environment", "production")

    # Format and display the state
    print("📋 Formatted State:")
    print(StateInspector.format_state(state, max_depth=2))
    print()

    # Search for specific terms
    print("🔎 Search Results for 'alice':")
    search_results = StateInspector.search_state(state, "alice")
    for result in search_results:
        print(f"  Found in {result['match_in']}: {result['path']} = {result['value']}")
    print()

    # Search for terms in keys
    print("🔑 Search Results for 'user' in keys:")
    key_results = StateInspector.search_state(
        state, "user", search_keys=True, search_values=False
    )
    for result in key_results:
        print(f"  Key match: {result['path']}")
    print()


def demonstrate_state_comparison():
    """Demonstrate state comparison capabilities."""
    print("⚖️  State Comparison Demo")
    print("=" * 50)

    # Create first state
    state1 = WorkflowState.create_new()
    state1.set("counter", 10)
    state1.set("status", "processing")
    state1.set("data", ["item1", "item2", "item3"])

    # Create second state with changes
    state2 = WorkflowState(**state1.model_dump())
    state2.set("counter", 15)  # Modified
    state2.set("status", "completed")  # Modified
    state2.set("new_field", "added_value")  # Added
    state2.data.pop("data")  # Removed

    # Compare the states
    diff = StateInspector.compare_states(state1, state2)

    print("📊 State Comparison Results:")
    print(f"  Time difference: {diff['time_diff_seconds']:.3f} seconds")
    print(f"  Added fields: {list(diff['data_changes']['added'].keys())}")
    print(f"  Removed fields: {list(diff['data_changes']['removed'].keys())}")
    print(f"  Modified fields: {list(diff['data_changes']['modified'].keys())}")

    for field, change in diff["data_changes"]["modified"].items():
        print(f"    {field}: {change['old']} → {change['new']}")
    print()


def demonstrate_snapshots():
    """Demonstrate snapshot and restore functionality."""
    print("📸 Snapshot & Restore Demo")
    print("=" * 50)

    # Create a state with some data
    original_state = WorkflowState.create_new()
    original_state.set("process_id", "proc_123")
    original_state.set("stage", "validation")
    original_state.set("progress", 0.3)
    original_state.set_metadata("checkpoint", "stage_1_complete")

    print("📋 Original State:")
    print(f"  Process ID: {original_state.get('process_id')}")
    print(f"  Stage: {original_state.get('stage')}")
    print(f"  Progress: {original_state.get('progress')}")
    print(f"  Checkpoint: {original_state.get_metadata('checkpoint')}")
    print()

    # Create a snapshot
    snapshot = StateSnapshot.from_state(
        original_state, source_node_id="validation_node"
    )
    print(f"📸 Created snapshot: {snapshot.snapshot_id}")
    print(f"  Source node: {snapshot.source_node_id}")
    print(f"  Snapshot time: {snapshot.created_at.isoformat()}")
    print()

    # Modify the original state
    original_state.set("stage", "processing")
    original_state.set("progress", 0.7)
    original_state.set_metadata("checkpoint", "stage_2_complete")

    print("📋 Modified State:")
    print(f"  Process ID: {original_state.get('process_id')}")
    print(f"  Stage: {original_state.get('stage')}")
    print(f"  Progress: {original_state.get('progress')}")
    print(f"  Checkpoint: {original_state.get_metadata('checkpoint')}")
    print()

    # Restore from snapshot
    restored_state = snapshot.restore()
    print("🔄 Restored State from Snapshot:")
    print(f"  Process ID: {restored_state.get('process_id')}")
    print(f"  Stage: {restored_state.get('stage')}")
    print(f"  Progress: {restored_state.get('progress')}")
    print(f"  Checkpoint: {restored_state.get_metadata('checkpoint')}")
    print()

    # Verify they are separate objects
    restored_state.set("test_field", "restored_only")
    print("✅ Verification - Restored state is independent:")
    print(f"  Original has test_field: {original_state.get('test_field') is not None}")
    print(f"  Restored has test_field: {restored_state.get('test_field') is not None}")
    print()


async def main():
    """Run all state management demonstrations."""
    print("🌟 Wyrdflow State Management Demo")
    print("=" * 60)
    print()

    demonstrate_state_inspection()
    demonstrate_state_comparison()
    demonstrate_snapshots()

    print("✨ Demo completed! These utilities help with:")
    print("  • Debugging workflow state issues")
    print("  • Comparing states between workflow steps")
    print("  • Creating checkpoints for error recovery")
    print("  • Searching for specific data in complex states")
    print("  • Visualizing state structure for analysis")


if __name__ == "__main__":
    asyncio.run(main())
