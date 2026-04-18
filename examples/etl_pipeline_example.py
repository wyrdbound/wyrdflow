"""ETL Pipeline Example using Data Transformation Nodes.

This example demonstrates how to build a complete ETL (Extract, Transform, Load)
pipeline using Wyrdflow's transformation nodes: SplitNode, TransformNode,
MergeNode, and AggregateNode.

The pipeline processes a dataset of customer orders:
1. Split orders into chunks for parallel processing
2. Transform each chunk (filter, enrich, calculate metrics)
3. Aggregate results from parallel processing
4. Merge final results

Run this example:
    python examples/etl_pipeline_example.py
"""

import asyncio
from datetime import datetime

from wyrdflow.nodes.aggregate_node import AggregateNode
from wyrdflow.nodes.merge_node import MergeNode
from wyrdflow.nodes.split_node import SplitNode
from wyrdflow.nodes.transform_node import TransformNode


async def etl_pipeline_example():
    """Run a complete ETL pipeline example."""
    print("=" * 70)
    print("ETL Pipeline Example: Customer Order Processing")
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

    # =========================================================================
    # Step 1: Split orders into chunks for parallel processing
    # =========================================================================
    print("Step 1: Splitting orders into 3 chunks for parallel processing...")
    split_node = SplitNode(
        node_id="split_orders",
        strategy="by_count",
        chunk_count=3,
        name="Split Orders",
        description="Split orders into parallel processing chunks",
    )

    split_result = await split_node.run({"data": orders})
    chunks = split_result["chunks"]
    print(f"  Created {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"    Chunk {i + 1}: {len(chunk)} orders")
    print()

    # =========================================================================
    # Step 2: Transform each chunk (filter completed orders)
    # =========================================================================
    print("Step 2: Filtering completed orders in each chunk...")
    filter_nodes = []
    filtered_chunks = []

    for i, chunk in enumerate(chunks):
        filter_node = TransformNode(
            node_id=f"filter_chunk_{i}",
            transform_type="filter",
            filter_func=lambda x: x["status"] == "completed",
            name=f"Filter Chunk {i + 1}",
        )
        filter_nodes.append(filter_node)

        result = await filter_node.run({"data": chunk})
        filtered_chunks.append(result["result"])
        print(
            f"  Chunk {i + 1}: {len(chunk)} orders -> {len(result['result'])} completed"
        )

    print()

    # =========================================================================
    # Step 3: Calculate total amount per chunk
    # =========================================================================
    print("Step 3: Calculating total amount per chunk...")
    chunk_totals = []

    for i, chunk in enumerate(filtered_chunks):
        reduce_node = TransformNode(
            node_id=f"sum_chunk_{i}",
            transform_type="reduce",
            reduce_func=lambda acc, x: acc + x["amount"],
            reduce_initial=0,
            name=f"Sum Chunk {i + 1}",
        )

        result = await reduce_node.run({"data": chunk})
        chunk_totals.append(result["result"])
        print(f"  Chunk {i + 1} total: ${result['result']}")

    print()

    # =========================================================================
    # Step 4: Aggregate chunk totals
    # =========================================================================
    print("Step 4: Aggregating totals from all chunks...")
    aggregate_node = AggregateNode(
        node_id="aggregate_totals",
        strategy="sum",
        name="Aggregate Totals",
        description="Sum all chunk totals",
    )

    aggregate_result = await aggregate_node.run({"results": chunk_totals})
    grand_total = aggregate_result["result"]
    print(f"  Grand total: ${grand_total}")
    print()

    # =========================================================================
    # Step 5: Group orders by customer
    # =========================================================================
    print("Step 5: Grouping completed orders by customer...")

    # First, concatenate all filtered chunks
    concat_node = AggregateNode(
        node_id="concat_chunks",
        strategy="concat",
        name="Concatenate Chunks",
    )

    concat_result = await concat_node.run({"results": filtered_chunks})
    all_completed_orders = concat_result["result"]

    # Group by customer
    group_node = TransformNode(
        node_id="group_by_customer",
        transform_type="group_by",
        group_by_key="customer",
        name="Group by Customer",
    )

    group_result = await group_node.run({"data": all_completed_orders})
    customer_groups = group_result["result"]

    print(f"  Grouped into {len(customer_groups)} customers:")
    for customer, orders_list in customer_groups.items():
        print(f"    {customer}: {len(orders_list)} completed orders")
    print()

    # =========================================================================
    # Step 6: Calculate per-customer metrics
    # =========================================================================
    print("Step 6: Calculating metrics per customer...")
    customer_metrics = {}

    for customer, orders_list in customer_groups.items():
        # Calculate total
        total_node = TransformNode(
            node_id=f"total_{customer}",
            transform_type="reduce",
            reduce_func=lambda acc, x: acc + x["amount"],
            reduce_initial=0,
        )
        total_result = await total_node.run({"data": orders_list})

        # Calculate average
        avg_node = TransformNode(
            node_id=f"avg_{customer}",
            transform_type="map",
            map_func=lambda x: x["amount"],
        )
        amounts_result = await avg_node.run({"data": orders_list})
        avg_amount = sum(amounts_result["result"]) / len(amounts_result["result"])

        customer_metrics[customer] = {
            "total_amount": total_result["result"],
            "avg_amount": avg_amount,
            "order_count": len(orders_list),
        }

        print(
            f"  {customer}: "
            f"${total_result['result']} total, "
            f"${avg_amount:.2f} avg, "
            f"{len(orders_list)} orders"
        )

    print()

    # =========================================================================
    # Step 7: Find top customer
    # =========================================================================
    print("Step 7: Finding top customer by total amount...")

    # Sort customers by total amount
    sorted_customers = sorted(
        customer_metrics.items(), key=lambda x: x[1]["total_amount"], reverse=True
    )

    top_customer = sorted_customers[0]
    print(
        f"  Top customer: {top_customer[0]} (${top_customer[1]['total_amount']} total)"
    )
    print()

    # =========================================================================
    # Step 8: Merge all results into final report
    # =========================================================================
    print("Step 8: Creating final ETL report...")

    final_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_orders_processed": len(orders),
            "completed_orders": len(all_completed_orders),
            "grand_total": grand_total,
            "unique_customers": len(customer_metrics),
        },
        "customer_metrics": customer_metrics,
        "top_customer": {
            "name": top_customer[0],
            "metrics": top_customer[1],
        },
    }

    print("  ETL Pipeline Complete!")
    print()
    print("Final Report:")
    print(f"  Timestamp: {final_report['timestamp']}")
    print(f"  Total Orders: {final_report['summary']['total_orders_processed']}")
    print(f"  Completed Orders: {final_report['summary']['completed_orders']}")
    print(f"  Grand Total: ${final_report['summary']['grand_total']}")
    print(f"  Unique Customers: {final_report['summary']['unique_customers']}")
    print(f"  Top Customer: {final_report['top_customer']['name']}")
    print()

    # =========================================================================
    # Advanced Example: Parallel transformation with merge
    # =========================================================================
    print("=" * 70)
    print("Advanced Example: Parallel Branch Processing")
    print("=" * 70)
    print()

    # Split orders by status
    print("Splitting orders by status (using condition)...")
    status_split = SplitNode(
        node_id="split_by_status",
        strategy="by_condition",
        condition_func=lambda x: x["status"],
    )

    status_result = await status_split.run({"data": orders})
    print(f"  Created {len(status_result['chunks'])} status groups")
    print()

    # Process each status group in "parallel" (simulated)
    print("Processing each status group...")
    status_summaries = []

    for chunk in status_result["chunks"]:
        if not chunk:
            continue

        status = chunk[0]["status"]

        # Count and sum for this status
        count = len(chunk)
        total_node = TransformNode(
            node_id=f"sum_status_{status}",
            transform_type="reduce",
            reduce_func=lambda acc, x: acc + x["amount"],
            reduce_initial=0,
        )
        total_result = await total_node.run({"data": chunk})

        summary = {
            "status": status,
            "count": count,
            "total": total_result["result"],
        }
        status_summaries.append(summary)

        print(f"  {status}: {count} orders, ${total_result['result']} total")

    print()

    # Merge all status summaries
    print("Merging status summaries...")
    merge_node = MergeNode(
        node_id="merge_summaries",
        strategy="last_write_wins",
        deep_merge=False,
    )

    # Convert to dict format for merging
    status_dicts = [
        {f"{s['status']}_count": s["count"], f"{s['status']}_total": s["total"]}
        for s in status_summaries
    ]

    merge_result = await merge_node.run({"sources": status_dicts})
    print("  Merged summary:")
    for key, value in merge_result["result"].items():
        print(f"    {key}: {value}")

    print()
    print("=" * 70)
    print("ETL Pipeline Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(etl_pipeline_example())
