"""Observability Example - Demonstrates execution logging, metrics, and tracing.

This example shows how to:
1. Automatically capture execution history for all nodes
2. Access and inspect execution logs programmatically
3. Collect and analyze performance metrics
4. Configure LangSmith tracing
5. Use state inspection to debug workflow state
6. Use the CLI to inspect workflow executions
"""

import asyncio
from pathlib import Path
from uuid import UUID

from pydantic import Field

from wyrdflow import (
    BaseNode,
    NodeConfig,
    NodeContext,
    NodeInput,
    NodeOutput,
    WorkflowState,
    get_execution_log,
    get_metrics_collector,
    get_state_inspector,
)


# Define input/output schemas
class DataInput(NodeInput):
    """Input for data processing nodes."""

    value: int = Field(description="Input value to process")


class DataOutput(NodeOutput):
    """Output for data processing nodes."""

    result: int = Field(description="Processed result")


# Example nodes
class MultiplyNode(BaseNode[DataInput, DataOutput]):
    """Multiply input by a factor."""

    input_schema = DataInput
    output_schema = DataOutput

    def __init__(
        self,
        node_id: str,
        factor: int = 2,
        config: NodeConfig | None = None,
    ):
        """Initialize with multiplication factor."""
        super().__init__(node_id, config)
        self.factor = factor

    async def execute(
        self,
        input_data: DataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> DataOutput:
        """Multiply the input value by the factor."""
        # Simulate some processing time
        await asyncio.sleep(0.1)

        result = input_data.value * self.factor
        return DataOutput(result=result)


class AddNode(BaseNode[DataInput, DataOutput]):
    """Add a constant to the input."""

    input_schema = DataInput
    output_schema = DataOutput

    def __init__(
        self,
        node_id: str,
        addend: int = 10,
        config: NodeConfig | None = None,
    ):
        """Initialize with addend."""
        super().__init__(node_id, config)
        self.addend = addend

    async def execute(
        self,
        input_data: DataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> DataOutput:
        """Add the constant to the input value."""
        # Simulate some processing time
        await asyncio.sleep(0.05)

        result = input_data.value + self.addend
        return DataOutput(result=result)


class FailingSometimesNode(BaseNode[DataInput, DataOutput]):
    """Node that fails on first attempt but succeeds on retry."""

    input_schema = DataInput
    output_schema = DataOutput

    def __init__(self, node_id: str, config: NodeConfig | None = None):
        """Initialize with retry configuration."""
        # Configure retries
        if config is None:
            config = NodeConfig(retry_attempts=3, retry_delay=0.1)
        super().__init__(node_id, config)
        self.attempt_count = 0

    async def execute(
        self,
        input_data: DataInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> DataOutput:
        """Fail on first attempt, succeed on retry."""
        self.attempt_count += 1

        # Fail on first attempt
        if self.attempt_count == 1:
            raise ValueError("Simulated failure - will retry")

        # Succeed on retry
        return DataOutput(result=input_data.value * 100)


async def run_workflow_with_observability() -> tuple[UUID, WorkflowState]:
    """Run a workflow and demonstrate observability features.

    Returns:
        Tuple of (workflow run ID, final state) for inspection
    """
    print("=" * 70)
    print("OBSERVABILITY EXAMPLE - Automatic Execution Tracking")
    print("=" * 70)

    # Create workflow state
    state = WorkflowState.create_new()
    print(f"\n📊 Created workflow run: {state.workflow_run_id}\n")

    # Add some initial data to state for state inspection demo
    state.set("config.multiplier", 3)
    state.set("config.addend", 5)
    state.set("user.name", "Alice")
    state.set("user.role", "engineer")

    # Create nodes
    multiply_node = MultiplyNode("multiply", factor=3)
    add_node = AddNode("add", addend=5)
    retry_node = FailingSometimesNode("retry_demo")

    # Run nodes in sequence
    print("▶️  Running workflow nodes...\n")

    # Step 1: Multiply
    print("  1. Multiplying 10 by 3...")
    result1 = await multiply_node.run({"value": 10}, state=state)
    state.set("step1.result", result1["result"])
    print(f"     ✓ Result: {result1['result']}\n")

    # Step 2: Add
    print("  2. Adding 5 to result...")
    result2 = await add_node.run({"value": result1["result"]}, state=state)
    state.set("step2.result", result2["result"])
    print(f"     ✓ Result: {result2['result']}\n")

    # Step 3: Retry demo (will fail once, then succeed)
    print("  3. Testing retry logic (will fail once)...")
    result3 = await retry_node.run({"value": 1}, state=state)
    state.set("step3.result", result3["result"])
    print(f"     ✓ Result: {result3['result']} (succeeded after retry)\n")

    print("=" * 70)
    print("✅ Workflow completed successfully!")
    print("=" * 70)

    return state.workflow_run_id, state


def inspect_execution_history(workflow_run_id: UUID) -> None:
    """Inspect execution history for a workflow run."""
    print("\n" + "=" * 70)
    print("📋 EXECUTION HISTORY INSPECTION")
    print("=" * 70)

    # Get execution log
    exec_log = get_execution_log()

    # Get all records for this run
    records = exec_log.get_records_by_run(workflow_run_id)

    print(f"\nFound {len(records)} execution records:\n")

    for i, record in enumerate(records, 1):
        print(f"{i}. Node: {record.node_id}")
        print(f"   Type: {record.node_type}")
        print(f"   Status: {record.status.value}")
        print(f"   Duration: {record.duration_ms:.2f}ms")
        print(f"   Retry Attempts: {record.retry_attempt}")

        if record.error_message:
            print(f"   Error: {record.error_message}")

        print()

    # Export to JSON
    print("💾 Exporting execution history to JSON...")
    json_output = exec_log.export_to_json(workflow_run_id)
    print(f"   JSON size: {len(json_output)} characters")
    print(f"   First 200 chars: {json_output[:200]}...\n")


def analyze_metrics(workflow_run_id: UUID) -> None:  # noqa: ARG001
    """Analyze performance metrics."""
    print("=" * 70)
    print("📈 PERFORMANCE METRICS ANALYSIS")
    print("=" * 70)

    # Get metrics collector
    metrics = get_metrics_collector()

    # Get all node type metrics
    node_metrics = metrics.get_all_node_type_metrics()

    print(f"\nCollected metrics for {len(node_metrics)} node types:\n")

    for node_type, node_metric in node_metrics.items():
        print(f"📊 {node_type}")
        print(f"   Executions: {node_metric.execution_count}")
        print(f"   Success Rate: {node_metric.success_rate:.1f}%")
        print(f"   Failure Rate: {node_metric.failure_rate:.1f}%")
        print(f"   Retry Count: {node_metric.retry_count}")
        print("   Duration Stats:")
        print(f"     - Average: {node_metric.avg_duration_ms:.2f}ms")
        print(f"     - Min: {node_metric.min_duration_ms:.2f}ms")
        print(f"     - Max: {node_metric.max_duration_ms:.2f}ms")
        print(f"     - P95: {node_metric.p95_duration_ms:.2f}ms")
        print()

    # Get metrics summary
    summary = metrics.get_summary()
    print("Overall Summary:")
    print(f"  Total Workflows: {summary['total_workflows']}")
    print(f"  Total Node Types: {summary['total_node_types']}")
    print()


def demonstrate_tracing_config() -> None:
    """Demonstrate LangSmith tracing configuration."""
    print("=" * 70)
    print("🔍 LANGSMITH TRACING CONFIGURATION")
    print("=" * 70)

    print("""
LangSmith tracing is automatically enabled when you set the environment
variables:

    export LANGSMITH_API_KEY="your-api-key"
    export LANGSMITH_TRACING=true

You can also configure tracing programmatically:

    from wyrdflow import configure_tracing

    # Enable tracing with custom project
    configure_tracing(
        enabled=True,
        project_name="my-workflow-project",
        tags=["production", "v1.0"],
        metadata={"team": "ml-engineering"}
    )

All node executions will automatically be traced to LangSmith with:
- Node-level spans with timing information
- Input/output data capture
- Error tracking with full stack traces
- Retry attempt tracking
- Custom tags and metadata

Example LangSmith trace structure:

Workflow: my-workflow
├─ Node: multiply (duration: 102ms)
│  ├─ Input: {"value": 10}
│  └─ Output: {"result": 30}
├─ Node: add (duration: 51ms)
│  ├─ Input: {"value": 30}
│  └─ Output: {"result": 35}
└─ Node: retry_demo (duration: 205ms, retries: 1)
   ├─ Attempt 1: Failed (error captured)
   ├─ Attempt 2: Success
   └─ Output: {"result": 100}
    """)


def demonstrate_state_inspection(state: WorkflowState) -> None:
    """Demonstrate state inspection features."""
    print("=" * 70)
    print("🔬 STATE INSPECTION & DEBUGGING")
    print("=" * 70)

    inspector = get_state_inspector()

    # 1. Visualize current state
    print("\n1. State Visualization (Tree View):\n")
    inspector.visualize(state, title="Final Workflow State")

    # 2. Search for specific values
    print("\n2. Searching State:\n")

    # Search for config values
    print("   Searching for 'config' in keys:")
    config_results = inspector.search(state, path_pattern="config.*")
    for result in config_results:
        print(f"     - {result['path']}: {result['value']}")

    # Search for results
    print("\n   Searching for 'result' in keys:")
    result_paths = inspector.search(state, path_pattern=r".*\.result$")
    for result in result_paths:
        print(f"     - {result['path']}: {result['value']}")

    # Search by value
    print("\n   Searching for value 'Alice':")
    alice_results = inspector.search(state, value="Alice")
    for result in alice_results:
        print(f"     - {result['path']}: {result['value']}")

    # 3. State Diff - compare initial vs final state
    print("\n3. State Diff (Initial vs Final):\n")

    # Create a copy of initial state for comparison
    initial_state = WorkflowState.create_new()
    initial_state.set("config.multiplier", 3)
    initial_state.set("config.addend", 5)
    initial_state.set("user.name", "Alice")
    initial_state.set("user.role", "engineer")

    # Create diff between initial and final states
    diff = inspector.diff(
        before=initial_state,
        after=state,
        label_before="Initial State",
        label_after="Final State",
    )

    print(diff.format())

    # Show diff statistics
    print("\n   Statistics:")
    print(f"     - Added paths: {len(diff.added_paths)}")
    print(f"     - Changed paths: {len(diff.changed_paths)}")
    print(f"     - Removed paths: {len(diff.removed_paths)}")

    print("\n💡 State inspection helps you:")
    print("   • Debug complex workflows by visualizing state")
    print("   • Track what changed during execution")
    print("   • Find missing or unexpected values")
    print("   • Validate workflow state at any point")
    print()


def cli_inspection_guide() -> None:
    """Show how to use CLI for inspection."""
    print("=" * 70)
    print("💻 CLI INSPECTION GUIDE")
    print("=" * 70)

    print("""
You can inspect workflow executions using the CLI:

1. Table format (default):
   $ wyrdflow inspect <workflow-run-id>

2. Tree format with visual representation:
   $ wyrdflow inspect <workflow-run-id> --format tree

3. JSON format for programmatic access:
   $ wyrdflow inspect <workflow-run-id> --format json

4. Filter by specific node:
   $ wyrdflow inspect <workflow-run-id> --node multiply

5. Show input/output data:
   $ wyrdflow inspect <workflow-run-id> --show-data

Example output:

┌─────────────────────────────────────────────────────────────┐
│            Workflow Execution History                        │
├──────────┬─────────────┬─────────┬──────────┬───────────────┤
│ Node ID  │ Node Type   │ Status  │ Duration │ Start Time    │
├──────────┼─────────────┼─────────┼──────────┼───────────────┤
│ multiply │ MultiplyNode│ success │ 102.45ms │ 2025-12-02... │
│ add      │ AddNode     │ success │  51.23ms │ 2025-12-02... │
│ retry    │ FailingNode │ success │ 205.67ms │ 2025-12-02... │
└──────────┴─────────────┴─────────┴──────────┴───────────────┘

Summary: Total: 3 | Success: 3 | Failed: 0 | Total Duration: 359.35ms
    """)


async def main() -> None:
    """Run the complete observability demonstration."""
    # Run workflow with automatic observability
    workflow_run_id, final_state = await run_workflow_with_observability()

    # Inspect execution history
    inspect_execution_history(workflow_run_id)

    # Analyze metrics
    analyze_metrics(workflow_run_id)

    # Demonstrate state inspection
    demonstrate_state_inspection(final_state)

    # Show tracing configuration
    demonstrate_tracing_config()

    # Show CLI guide
    cli_inspection_guide()

    # Export execution history to file for CLI inspection
    exec_log = get_execution_log()
    json_output = exec_log.export_to_json(workflow_run_id)

    # Create traces directory if it doesn't exist
    traces_dir = Path("traces")
    traces_dir.mkdir(exist_ok=True)

    # Save execution log to traces directory
    output_file = traces_dir / f"execution_{workflow_run_id}.json"
    with output_file.open("w") as f:
        f.write(json_output)

    print("=" * 70)
    print("🎉 OBSERVABILITY EXAMPLE COMPLETE")
    print("=" * 70)
    print(f"""
✅ All observability features demonstrated!

Key Takeaways:
1. Execution history is automatically captured for all node executions
2. Metrics are automatically collected for performance analysis
3. State inspection helps debug and visualize workflow state changes
4. LangSmith tracing provides deep visibility (when configured)
5. CLI tools make it easy to inspect executions
6. All features work together seamlessly with zero boilerplate

Workflow Run ID: {workflow_run_id}

📁 Execution history saved to: {output_file}

Try it yourself:
    $ wyrdflow inspect {workflow_run_id} --from-file traces/execution_{workflow_run_id}.json
    """)


if __name__ == "__main__":
    asyncio.run(main())
