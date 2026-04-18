"""ETL Pipeline Example using LangGraph and Wyrdflow Nodes.

This example demonstrates how to build a complete ETL workflow using LangGraph
to orchestrate Wyrdflow's transformation nodes. Unlike the standalone example,
this creates a unified workflow with:
- Single workflow execution context
- Unified tracing (one trace file for entire pipeline)
- Proper state management
- Production-ready pattern

The pipeline processes customer orders through a workflow graph:
1. Filter completed orders
2. Calculate grand total
3. Group orders by customer
4. Calculate per-customer metrics
5. Generate final report

Run this example:
    python examples/etl_pipeline_langgraph_example.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.transform_node import TransformNode


# ============================================================================
# Define Workflow State
# ============================================================================
class ETLState(TypedDict):
    """State that flows through the ETL pipeline.

    The workflow_state field is used by Wyrdflow's as_langraph_node() to
    track all node executions in a unified workflow trace.
    """

    # Input data
    orders: list[dict]

    # Intermediate results
    completed_orders: list[dict]
    grand_total: float
    customer_groups: dict[str, list[dict]]
    customer_metrics: dict[str, dict]

    # Final output
    report: dict

    # Wyrdflow observability (managed by as_langraph_node)
    workflow_state: dict  # Dict representation of WorkflowState


# ============================================================================
# Create Wyrdflow Nodes
# ============================================================================
# Nodes are configured with input_map and output_map to work seamlessly
# with LangGraph state. The as_langraph_node() helper handles all the
# wiring automatically!

# Node 1: Filter completed orders
filter_node = TransformNode(
    node_id="filter_completed",
    transform_type="filter",
    filter_func=lambda x: x["status"] == "completed",
    name="Filter Completed Orders",
    description="Filter only completed orders from input",
    input_map={"data": "orders"},
    output_map={"result": "completed_orders"},
)

# Node 2: Calculate grand total
total_node = TransformNode(
    node_id="calculate_total",
    transform_type="reduce",
    reduce_func=lambda acc, x: acc + x["amount"],
    reduce_initial=0,
    name="Calculate Grand Total",
    description="Sum all completed order amounts",
    input_map={"data": "completed_orders"},
    output_map={"result": "grand_total"},
)

# Node 3: Group by customer
group_node = TransformNode(
    node_id="group_by_customer",
    transform_type="group_by",
    group_by_key="customer",
    name="Group by Customer",
    description="Group completed orders by customer name",
    input_map={"data": "completed_orders"},
    output_map={"result": "customer_groups"},
)


# Node 4: Calculate customer metrics
def calculate_all_customer_metrics(customer_groups: dict) -> dict:
    """Calculate metrics for all customers."""
    customer_metrics = {}
    for customer, orders_list in customer_groups.items():
        amounts = [order["amount"] for order in orders_list]
        customer_metrics[customer] = {
            "total_amount": sum(amounts),
            "avg_amount": sum(amounts) / len(amounts),
            "order_count": len(orders_list),
        }
    return customer_metrics


metrics_node = TransformNode(
    node_id="calculate_metrics",
    custom_func=calculate_all_customer_metrics,
    name="Calculate Customer Metrics",
    description="Calculate total, average, and count for each customer",
    input_map={"data": "customer_groups"},
    output_map={"result": "customer_metrics"},
)


# Node 5: Generate final report
def create_final_report(state_data: dict) -> dict:
    """Create final ETL report from all collected data."""
    top_customer = max(
        state_data["customer_metrics"].items(), key=lambda x: x[1]["total_amount"]
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_orders_processed": len(state_data["orders"]),
            "completed_orders": len(state_data["completed_orders"]),
            "grand_total": state_data["grand_total"],
            "unique_customers": len(state_data["customer_metrics"]),
        },
        "customer_metrics": state_data["customer_metrics"],
        "top_customer": {
            "name": top_customer[0],
            "metrics": top_customer[1],
        },
    }


# For the report node, we need access to multiple state fields,
# so we use a custom wrapper that extracts everything
async def generate_report(state: ETLState) -> ETLState:
    """Generate final ETL report (needs access to full state)."""
    print("  [5/5] Generating final report...")

    report = create_final_report(state)
    print("        Report generated successfully")

    return {**state, "report": report}


# ============================================================================
# Build LangGraph Workflow
# ============================================================================


def create_etl_workflow() -> StateGraph:
    """Create the ETL workflow graph.

    This demonstrates how easy it is to use Wyrdflow nodes with LangGraph!
    The as_langraph_node() helper automatically handles:
    - Extracting inputs from state using input_map
    - Running the node with observability
    - Putting outputs back into state using output_map
    """
    # Create graph
    workflow = StateGraph(ETLState)

    # Add Wyrdflow nodes using as_langraph_node() - super simple!
    workflow.add_node("filter_completed", filter_node.as_langraph_node())
    workflow.add_node("calculate_total", total_node.as_langraph_node())
    workflow.add_node("group_customers", group_node.as_langraph_node())
    workflow.add_node("calculate_metrics", metrics_node.as_langraph_node())

    # Only the final report node needs a custom wrapper (accesses multiple state fields)
    workflow.add_node("generate_report", generate_report)

    # Define edges (execution order)
    workflow.set_entry_point("filter_completed")
    workflow.add_edge("filter_completed", "calculate_total")
    workflow.add_edge("calculate_total", "group_customers")
    workflow.add_edge("group_customers", "calculate_metrics")
    workflow.add_edge("calculate_metrics", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow


# ============================================================================
# Main Example
# ============================================================================


async def run_etl_pipeline():
    """Run the complete ETL pipeline using LangGraph."""
    print("=" * 70)
    print("ETL Pipeline LangGraph Example: Customer Order Processing")
    print("=" * 70)
    print()

    # Sample dataset: customer orders
    orders = [
        {"id": 1, "customer": "Alice", "amount": 100, "status": "completed"},
        {"id": 2, "customer": "Bob", "amount": 50, "status": "pending"},
        {"id": 3, "customer": "Charlie", "amount": 200, "status": "completed"},
        {"id": 4, "customer": "Alice", "amount": 150, "status": "completed"},
        {"id": 5, "customer": "Bob", "amount": 75, "status": "cancelled"},
        {"id": 6, "customer": "Diana", "amount": 300, "status": "completed"},
        {"id": 7, "customer": "Charlie", "amount": 120, "status": "pending"},
        {"id": 8, "customer": "Alice", "amount": 80, "status": "completed"},
        {"id": 9, "customer": "Bob", "amount": 90, "status": "completed"},
        {"id": 10, "customer": "Diana", "amount": 250, "status": "completed"},
    ]

    print(f"Input: {len(orders)} customer orders")
    print()

    # Create workflow
    print("Building ETL workflow graph...")
    workflow = create_etl_workflow()
    app = workflow.compile()
    print("  ✓ Workflow graph compiled")
    print()

    # Create initial state with shared workflow state for unified tracing
    print("Initializing workflow state...")
    workflow_state = WorkflowState.create_new()
    print(f"  ✓ Workflow Run ID: {workflow_state.workflow_run_id}")
    print()

    initial_state: ETLState = {
        "orders": orders,
        "completed_orders": [],
        "grand_total": 0.0,
        "customer_groups": {},
        "customer_metrics": {},
        "report": {},
        "workflow_state": workflow_state.model_dump(),  # Convert to dict
    }

    # Execute workflow
    print("Executing ETL pipeline...")
    print("  [1/5] Filtering completed orders...")
    print("  [2/5] Calculating grand total...")
    print("  [3/5] Grouping orders by customer...")
    print("  [4/5] Calculating per-customer metrics...")
    print("  [5/5] Generating final report...")
    print()

    result = await app.ainvoke(initial_state)

    print()
    print("=" * 70)
    print("Pipeline Execution Complete!")
    print("=" * 70)
    print()

    # Display final report
    report = result["report"]
    print("Final Report:")
    print(f"  Timestamp: {report['timestamp']}")
    print(f"  Total Orders: {report['summary']['total_orders_processed']}")
    print(f"  Completed Orders: {report['summary']['completed_orders']}")
    print(f"  Grand Total: ${report['summary']['grand_total']}")
    print(f"  Unique Customers: {report['summary']['unique_customers']}")
    print(
        f"  Top Customer: {report['top_customer']['name']} "
        f"(${report['top_customer']['metrics']['total_amount']} total)"
    )
    print()

    # Show trace file location
    traces_dir = Path("traces")
    trace_file = traces_dir / f"execution_{workflow_state.workflow_run_id}.json"
    if trace_file.exists():
        print("=" * 70)
        print("Observability")
        print("=" * 70)
        print(f"✓ Unified trace file: {trace_file}")
        print("  All node executions captured in single trace file")
        print()
        print("Inspect with:")
        print(f"  cat {trace_file} | python -m json.tool")
        print(f"  # or use: uv run wyrdflow inspect --from-file {trace_file}")
        print()


if __name__ == "__main__":
    asyncio.run(run_etl_pipeline())
