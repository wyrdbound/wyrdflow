# Observability & Debugging Guide

Wyrdflow provides comprehensive observability features to help you understand, debug, and optimize your workflows. All observability features work automatically with zero configuration required.

## Overview

Wyrdflow includes four main observability systems:

1. **Execution Logging**: Automatic capture of execution history for all nodes
2. **Metrics Collection**: Performance statistics and aggregation across runs
3. **LangSmith Tracing**: Distributed tracing integration (optional)
4. **State Inspection**: Debug and visualize workflow state changes

All systems work together seamlessly and are integrated into the `BaseNode` class, so every node execution is automatically tracked.

## Execution Logging

### Automatic Capture

Every node execution is automatically logged with:

- Node ID, name, and type
- Execution status (pending, running, success, failed, timeout, retry)
- Start time, end time, and duration
- Input and output data (with configurable size limits)
- Error details (message, type, traceback)
- Retry attempts

### Accessing Execution Logs

```python
from wyrdflow import get_execution_log

# Get the global execution log
exec_log = get_execution_log()

# Get all records for a specific workflow run
records = exec_log.get_records_by_run(workflow_run_id)

# Get all records for a specific node
node_records = exec_log.get_records_by_node("my_node")

# Get the latest record for a node in a specific run
latest = exec_log.get_latest_record("my_node", workflow_run_id)

# Export to JSON
json_output = exec_log.export_to_json(workflow_run_id)
```

### Execution Record Details

Each execution record contains:

```python
from wyrdflow import NodeExecutionRecord

record = records[0]
print(f"Node: {record.node_id}")
print(f"Status: {record.status}")
print(f"Duration: {record.duration_ms}ms")
print(f"Input: {record.input_data}")
print(f"Output: {record.output_data}")
print(f"Retries: {record.retry_attempt}")

if record.error_message:
    print(f"Error: {record.error_message}")
    print(f"Type: {record.error_type}")
    print(f"Traceback: {record.error_traceback}")
```

### Configuration

You can configure the execution log behavior:

```python
from wyrdflow import WorkflowExecutionLog, set_execution_log

# Create custom execution log
custom_log = WorkflowExecutionLog(
    max_records=50000,        # Maximum records to keep
    max_data_size=20480,      # Max size for input/output data (bytes)
    retention_seconds=86400   # Keep records for 24 hours
)

# Set as global instance
set_execution_log(custom_log)
```

## Metrics Collection

### Automatic Collection

Performance metrics are automatically collected for:

- Execution counts (total, success, failure)
- Duration statistics (min, max, avg, p50, p95, p99)
- Retry counts
- Timeout counts
- Token usage (for LLM nodes)
- Cost tracking
- Custom metrics

### Accessing Metrics

```python
from wyrdflow import get_metrics_collector

# Get the global metrics collector
metrics = get_metrics_collector()

# Get metrics for a specific node type
node_metrics = metrics.get_node_type_metrics("LLMNode")
print(f"Executions: {node_metrics.execution_count}")
print(f"Success rate: {node_metrics.success_rate}%")
print(f"Avg duration: {node_metrics.avg_duration_ms}ms")
print(f"P95 duration: {node_metrics.p95_duration_ms}ms")
print(f"Total tokens: {node_metrics.total_tokens}")
print(f"Total cost: ${node_metrics.total_cost}")

# Get all node type metrics
all_metrics = metrics.get_all_node_type_metrics()
for node_type, node_metric in all_metrics.items():
    print(f"{node_type}: {node_metric.execution_count} executions")

# Get workflow-level metrics
workflow_metrics = metrics.get_workflow_metrics(workflow_id)
print(f"Total executions: {workflow_metrics.total_executions}")
print(f"Total successes: {workflow_metrics.total_successes}")

# Get summary
summary = metrics.get_summary()
print(f"Total workflows: {summary['total_workflows']}")
print(f"Total node types: {summary['total_node_types']}")
```

### Recording Custom Metrics

```python
from wyrdflow import get_metrics_collector

metrics = get_metrics_collector()

# Record custom metric for a node type
metrics.record_custom_metric(
    workflow_id=workflow_id,
    node_type="MyCustomNode",
    metric_name="api_calls",
    value=42
)
```

## LangSmith Tracing

### Overview

LangSmith tracing provides distributed tracing for all workflow executions. Every node execution is automatically traced with full input/output capture, error tracking, and timing information.

### Configuration

#### Environment Variables

The simplest way to enable LangSmith tracing:

```bash
export LANGSMITH_API_KEY="your-api-key"
export LANGSMITH_TRACING=true
```

#### Programmatic Configuration

```python
from wyrdflow import configure_tracing

# Enable tracing with custom settings
configure_tracing(
    enabled=True,
    project_name="my-workflow-project",
    tags=["production", "v1.0"],
    metadata={"team": "ml-engineering"}
)
```

### Trace Structure

All node executions are automatically traced with:

- Node-level spans with accurate timing
- Input/output data capture
- Error tracking with full stack traces
- Retry attempt tracking
- Custom tags and metadata

Example trace structure in LangSmith:

```
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
```

### Graceful Degradation

If LangSmith is unavailable or not configured, all tracing operations gracefully no-op. Your workflows will continue to work normally, just without distributed tracing.

## State Inspection

### Overview

The StateInspector provides powerful tools for debugging and understanding workflow state changes. It allows you to:

- Compare state before and after node execution (diffs)
- Visualize state as a tree structure
- Search for specific values in state
- Track what changed during workflow execution

### Basic Usage

```python
from wyrdflow import get_state_inspector, WorkflowState

# Get the global state inspector
inspector = get_state_inspector()

# Create initial state
state = WorkflowState.create_new()
state.set("user.name", "Alice")
state.set("user.age", 30)

# Visualize current state
inspector.visualize(state, title="Initial State")

# Make changes
state.set("user.age", 31)
state.set("user.city", "NYC")

# Create a diff to see what changed
diff = inspector.diff(
    before=state.get_snapshot(0),  # Initial state
    after=state.get_snapshot(1),   # Current state
    label_before="Before",
    label_after="After"
)

# Display the diff
print(diff)
```

### State Diffs

The `diff()` method creates a detailed comparison showing exactly what changed:

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Get state snapshots from workflow execution
before = state.get_snapshot(0)
after = state.get_snapshot(1)

# Create diff
diff = inspector.diff(before, after)

# Access diff information
print(f"Added paths: {diff.added_paths}")      # New keys
print(f"Removed paths: {diff.removed_paths}")  # Deleted keys
print(f"Changed paths: {diff.changed_paths}")  # Modified values

# Format as string
print(diff.format())
```

Example output:

```
State Diff: Before → After

Added Paths:
  + user.city = "NYC"

Changed Paths:
  ~ user.age: 30 → 31

Removed Paths:
  (none)
```

### State Visualization

The `visualize()` method renders state as an interactive tree:

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Visualize complete state
inspector.visualize(
    state,
    title="Workflow State",
    show_metadata=True,  # Show timestamps, versions
    max_depth=5          # Limit nesting depth
)
```

Example output:

```
╭─────────────────── Workflow State ────────────────────╮
│                                                        │
│ WorkflowState                                          │
│ ├── user                                               │
│ │   ├── name: "Alice"                                  │
│ │   ├── age: 31                                        │
│ │   └── city: "NYC"                                    │
│ ├── items                                              │
│ │   ├── [0]: "apple"                                   │
│ │   ├── [1]: "banana"                                  │
│ │   └── [2]: "cherry"                                  │
│ └── metadata                                           │
│     ├── version: 2                                     │
│     └── created_at: "2025-12-02T10:15:30"              │
│                                                        │
╰────────────────────────────────────────────────────────╯
```

### Searching State

The `search()` method helps find values in complex state:

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Search by path pattern
results = inspector.search(state, path_pattern="user.*")
# Returns: [
#   {"path": "user.name", "value": "Alice"},
#   {"path": "user.age", "value": 31},
#   {"path": "user.city", "value": "NYC"}
# ]

# Search by value
results = inspector.search(state, value="NYC")
# Returns: [{"path": "user.city", "value": "NYC"}]

# Search with regex
results = inspector.search(state, path_pattern=r".*\.age$")
# Returns: [{"path": "user.age", "value": 31}]

# Limit results
results = inspector.search(state, path_pattern="*", max_results=10)
```

### Debugging with State Inspector

Common debugging patterns:

#### 1. Track Changes Across Nodes

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Before node execution
before = state.get_snapshot()

# Execute node
result = await node.run(state)

# After node execution
after = state.get_snapshot()

# See what the node changed
diff = inspector.diff(before, after, label_before="Before Node", label_after="After Node")
print(diff.format())
```

#### 2. Find Missing Values

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Search for a value you expect
results = inspector.search(state, path_pattern="config.api_key")

if not results:
    print("API key not found in state!")
    # Visualize state to debug
    inspector.visualize(state, title="State Missing API Key")
```

#### 3. Validate State Structure

```python
from wyrdflow import get_state_inspector

inspector = get_state_inspector()

# Check what's actually in state
inspector.visualize(state, title="Current State Structure")

# Search for expected paths
required_paths = ["user.id", "user.name", "session.token"]
for path in required_paths:
    results = inspector.search(state, path_pattern=path)
    if not results:
        print(f"Missing required path: {path}")
```

### Thread Safety

The StateInspector is thread-safe and can be used in concurrent workflows:

```python
import asyncio
from wyrdflow import get_state_inspector

inspector = get_state_inspector()  # Singleton, thread-safe

async def debug_workflow(state):
    # Safe to use in concurrent contexts
    inspector.visualize(state)
```

## CLI Inspection

### Basic Usage

The `wyrdflow inspect` command provides powerful inspection capabilities:

```bash
# Inspect a workflow run (table format)
wyrdflow inspect <workflow-run-id>

# Tree format with visual representation
wyrdflow inspect <workflow-run-id> --format tree

# JSON format for programmatic access
wyrdflow inspect <workflow-run-id> --format json

# Filter by specific node
wyrdflow inspect <workflow-run-id> --node my_node

# Show input/output data
wyrdflow inspect <workflow-run-id> --show-data
```

### Output Formats

#### Table Format (default)

```
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
```

#### Tree Format

```
Workflow Execution: 2102c8aa-63b2-4b75-b024-d1f567b1ead7

├─ multiply (MultiplyNode)
│  Status: ✓ success
│  Duration: 102.45ms
│  Started: 2025-12-02 10:15:30
│
├─ add (AddNode)
│  Status: ✓ success
│  Duration: 51.23ms
│  Started: 2025-12-02 10:15:31
│
└─ retry (FailingSometimesNode)
   Status: ✓ success (after 1 retry)
   Duration: 205.67ms
   Started: 2025-12-02 10:15:32
```

#### JSON Format

```bash
wyrdflow inspect <workflow-run-id> --format json > execution.json
```

Output can be piped to `jq` or processed programmatically.

## Best Practices

### 1. Use Execution Logs for Debugging

When debugging workflow failures:

```python
from wyrdflow import get_execution_log

# Get all failed executions for a run
exec_log = get_execution_log()
records = exec_log.get_records_by_run(workflow_run_id)
failed = [r for r in records if r.status == ExecutionStatus.FAILED]

for record in failed:
    print(f"Failed node: {record.node_id}")
    print(f"Error: {record.error_message}")
    print(f"Input that caused failure: {record.input_data}")
```

### 2. Monitor Performance with Metrics

Track performance trends over time:

```python
from wyrdflow import get_metrics_collector

metrics = get_metrics_collector()

# Identify slow nodes
all_metrics = metrics.get_all_node_type_metrics()
slow_nodes = {
    node_type: m.p95_duration_ms
    for node_type, m in all_metrics.items()
    if m.p95_duration_ms > 1000  # Slower than 1 second
}
```

### 3. Configure Data Capture Limits

For workflows with large inputs/outputs, configure data limits:

```python
from wyrdflow import WorkflowExecutionLog, set_execution_log

# Limit data capture to 50KB per record
exec_log = WorkflowExecutionLog(max_data_size=51200)
set_execution_log(exec_log)
```

### 4. Use LangSmith for Production

Enable LangSmith tracing in production for:

- End-to-end visibility across distributed systems
- Automatic error aggregation and alerting
- Performance analysis and optimization
- Debugging customer-reported issues

### 5. Export and Archive Execution History

Periodically export execution history for long-term storage:

```python
import json
from wyrdflow import get_execution_log

exec_log = get_execution_log()

# Export all records for a workflow run
json_output = exec_log.export_to_json(workflow_run_id)

# Save to file
with open(f"execution_{workflow_run_id}.json", "w") as f:
    f.write(json_output)

# Clear old records
exec_log.clear()
```

### 6. Thread Safety

All observability components are thread-safe. You can safely use them in concurrent environments:

```python
import asyncio
from wyrdflow import WorkflowState, get_execution_log

async def run_concurrent_workflows():
    # Multiple workflows can run concurrently
    # All executions are safely logged
    tasks = [
        workflow1.run(state=WorkflowState.create_new()),
        workflow2.run(state=WorkflowState.create_new()),
        workflow3.run(state=WorkflowState.create_new()),
    ]
    await asyncio.gather(*tasks)
```

### 7. Performance Overhead

Observability features are designed for minimal overhead:

- Execution logging: < 1ms per node
- Metrics collection: < 0.5ms per node
- LangSmith tracing: < 2ms per node (network-dependent)

Total overhead is typically < 5% of execution time.

### 8. Memory Management

Configure retention policies to manage memory:

```python
from wyrdflow import WorkflowExecutionLog

exec_log = WorkflowExecutionLog(
    max_records=10000,         # Keep at most 10,000 records
    max_data_size=10240,       # Limit data to 10KB per record
    retention_seconds=3600     # Delete records older than 1 hour
)
```

## Examples

### Complete Observability Workflow

See `examples/observability_example.py` for a complete demonstration of:

- Automatic execution tracking
- Metrics collection
- LangSmith tracing configuration
- CLI inspection
- Retry tracking
- Error handling

Run the example:

```bash
uv run python examples/observability_example.py
```

### Debugging Failed Workflows

```python
from wyrdflow import get_execution_log, ExecutionStatus

def debug_workflow_run(workflow_run_id):
    """Debug a failed workflow run."""
    exec_log = get_execution_log()
    records = exec_log.get_records_by_run(workflow_run_id)

    print(f"Analyzing workflow run: {workflow_run_id}\n")

    # Find failed nodes
    failed = [r for r in records if r.status == ExecutionStatus.FAILED]
    if failed:
        print(f"Found {len(failed)} failed nodes:\n")
        for record in failed:
            print(f"Node: {record.node_id} ({record.node_type})")
            print(f"Error: {record.error_message}")
            print(f"Input: {record.input_data}")
            print(f"Duration: {record.duration_ms}ms")
            print()

    # Find nodes that needed retries
    retried = [r for r in records if r.retry_attempt > 0]
    if retried:
        print(f"Found {len(retried)} nodes that needed retries:\n")
        for record in retried:
            print(f"Node: {record.node_id}")
            print(f"Attempts: {record.retry_attempt + 1}")
            print()

    # Performance summary
    total_duration = sum(r.duration_ms for r in records if r.duration_ms)
    print(f"Total execution time: {total_duration}ms")
    print(f"Success rate: {sum(1 for r in records if r.status == ExecutionStatus.SUCCESS) / len(records) * 100:.1f}%")
```

### Performance Analysis

```python
from wyrdflow import get_metrics_collector

def analyze_performance():
    """Analyze workflow performance across all runs."""
    metrics = get_metrics_collector()
    all_metrics = metrics.get_all_node_type_metrics()

    print("Performance Analysis\n")
    print(f"{'Node Type':<20} {'Count':<8} {'Avg (ms)':<10} {'P95 (ms)':<10} {'Success %':<10}")
    print("-" * 68)

    for node_type, node_metric in sorted(all_metrics.items()):
        print(
            f"{node_type:<20} "
            f"{node_metric.execution_count:<8} "
            f"{node_metric.avg_duration_ms:<10.2f} "
            f"{node_metric.p95_duration_ms:<10.2f} "
            f"{node_metric.success_rate:<10.1f}"
        )
```

## Troubleshooting

### Execution Records Not Appearing

Check if execution logging is enabled:

```python
from wyrdflow import get_execution_log

exec_log = get_execution_log()
print(f"Total records: {len(exec_log.get_all_records())}")
```

### LangSmith Traces Not Showing

1. Verify API key is set: `echo $LANGSMITH_API_KEY`
2. Check tracing is enabled: `echo $LANGSMITH_TRACING`
3. Verify network connectivity to LangSmith
4. Check for errors in logs

### High Memory Usage

Reduce retention and data limits:

```python
from wyrdflow import WorkflowExecutionLog, set_execution_log

exec_log = WorkflowExecutionLog(
    max_records=1000,      # Reduce from default 10,000
    max_data_size=1024,    # Reduce from default 10KB
)
set_execution_log(exec_log)
```

### CLI Command Not Found

Ensure Wyrdflow is installed:

```bash
uv run wyrdflow --help
```

## API Reference

### Execution Log

- `get_execution_log()` - Get global execution log instance
- `set_execution_log(log)` - Set custom execution log instance
- `WorkflowExecutionLog` - Execution log class
- `NodeExecutionRecord` - Execution record model
- `ExecutionStatus` - Status enum (PENDING, RUNNING, SUCCESS, FAILED, TIMEOUT, RETRY)

### Metrics

- `get_metrics_collector()` - Get global metrics collector
- `set_metrics_collector(collector)` - Set custom metrics collector
- `MetricsCollector` - Metrics collection class
- `NodeMetrics` - Node-level metrics model
- `WorkflowMetrics` - Workflow-level metrics model

### Tracing

- `get_tracer()` - Get global tracer instance
- `set_tracer(tracer)` - Set custom tracer instance
- `configure_tracing(**kwargs)` - Configure global tracing settings
- `WorkflowTracer` - Tracing integration class
- `TracingConfig` - Tracing configuration model

### State Inspection

- `get_state_inspector()` - Get global state inspector instance
- `StateInspector` - State inspection and debugging class
- `StateDiff` - State difference model with change tracking
- `.diff(before, after)` - Compare two state snapshots
- `.visualize(state)` - Render state as interactive tree
- `.search(state, pattern)` - Find values in state by path or value

## Next Steps

- Explore the [observability example](../examples/observability_example.py)
- Learn about [LangSmith tracing](https://docs.smith.langchain.com/)
- Read about [metrics best practices](https://www.datadoghq.com/blog/monitoring-best-practices/)
- Check out [structured logging](https://www.structlog.org/)
