"""Example: Multi-path workflow using flow control nodes.

This example demonstrates a content moderation workflow that uses all three
flow control nodes (If, Router, Switch) to route content through different
processing paths based on various criteria.
"""

import asyncio
from uuid import uuid4

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.if_node import IfNode
from wyrdflow.nodes.router_node import RouteCondition, RouterNode
from wyrdflow.nodes.switch_node import CaseCondition, SwitchNode


async def main():
    """Run the content moderation workflow example."""
    print("=" * 60)
    print("Content Moderation Workflow - Flow Control Example")
    print("=" * 60)

    # Create workflow state
    workflow_id = uuid4()
    workflow_run_id = uuid4()
    state = WorkflowState(
        workflow_id=workflow_id,
        workflow_run_id=workflow_run_id,
    )

    # Sample content items to process
    content_items = [
        {
            "id": 1,
            "text": "This is a great product! Highly recommended.",
            "type": "review",
            "sentiment_score": 0.85,
            "language": "en",
            "user_tier": "gold",
        },
        {
            "id": 2,
            "text": "Worst experience ever! Avoid at all costs!",
            "type": "review",
            "sentiment_score": 0.15,
            "language": "en",
            "user_tier": "bronze",
        },
        {
            "id": 3,
            "text": "Nous avons besoin d'aide avec ce produit.",
            "type": "support",
            "sentiment_score": 0.45,
            "language": "fr",
            "user_tier": "platinum",
        },
        {
            "id": 4,
            "text": "Average product, nothing special.",
            "type": "review",
            "sentiment_score": 0.5,
            "language": "en",
            "user_tier": "silver",
        },
    ]

    # Example 1: If Node - Check if content needs translation
    print("\n" + "=" * 60)
    print("Example 1: If Node - Translation Check")
    print("=" * 60)

    if_node = IfNode(
        node_id="check_translation",
        name="Check if Translation Needed",
        comparison_op="ne",
        comparison_value="en",
    )

    for item in content_items:
        state.data["language"] = item["language"]

        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id=if_node.node_id,
        )

        result = await if_node.execute(
            if_node.input_schema(condition_value=item["language"]),
            context,
            state,
        )

        print(f"\nContent #{item['id']} (Language: {item['language']})")
        print(f"  Route: {result.route}")
        print(
            f"  Action: {'Translate to English' if result.route == 'true' else 'Process as-is'}"
        )

    # Example 2: Router Node - Route by sentiment and user tier
    print("\n" + "=" * 60)
    print("Example 2: Router Node - Priority Routing")
    print("=" * 60)

    router_node = RouterNode(
        node_id="priority_router",
        name="Priority Content Router",
        routes=[
            RouteCondition(
                name="vip_urgent",
                condition_func=lambda v: (
                    v.get("user_tier") == "platinum"
                    and (
                        v.get("sentiment_score", 0.5) < 0.3
                        or v.get("sentiment_score", 0.5) > 0.8
                    )
                ),
            ),
            RouteCondition(
                name="negative_review",
                expression="value.get('sentiment_score', 0.5) < 0.3 and value.get('type') == 'review'",
            ),
            RouteCondition(
                name="positive_review",
                expression="value.get('sentiment_score', 0.5) > 0.7 and value.get('type') == 'review'",
            ),
            RouteCondition(
                name="support_request",
                expression="value.get('type') == 'support'",
            ),
        ],
        default_route="standard_processing",
    )

    for item in content_items:
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id=router_node.node_id,
        )

        result = await router_node.execute(
            router_node.input_schema(routing_value=item),
            context,
            state,
        )

        print(f"\nContent #{item['id']}")
        print(f"  Type: {item['type']}")
        print(f"  Sentiment: {item['sentiment_score']}")
        print(f"  User Tier: {item['user_tier']}")
        print(f"  → Routed to: {result.route}")
        print(f"  Matched: {result.matched_conditions}")

    # Example 3: Switch Node - Route by content type
    print("\n" + "=" * 60)
    print("Example 3: Switch Node - Content Type Routing")
    print("=" * 60)

    switch_node = SwitchNode(
        node_id="content_type_switch",
        name="Content Type Switch",
        cases=[
            CaseCondition(
                route="review_pipeline",
                value="review",
            ),
            CaseCondition(
                route="support_pipeline",
                value="support",
            ),
            CaseCondition(
                route="ugc_pipeline",
                value_list=["comment", "post", "message"],
            ),
            CaseCondition(
                route="media_pipeline",
                pattern=r"^(image|video|audio)$",
            ),
        ],
        default_route="general_pipeline",
    )

    for item in content_items:
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id=switch_node.node_id,
        )

        result = await switch_node.execute(
            switch_node.input_schema(switch_value=item["type"]),
            context,
            state,
        )

        print(f"\nContent #{item['id']} (Type: {item['type']})")
        print(f"  → Processing in: {result.route}")

    # Example 4: Combined workflow with all three nodes
    print("\n" + "=" * 60)
    print("Example 4: Combined Workflow")
    print("=" * 60)
    print("\nProcessing complete workflow for each content item:\n")

    for item in content_items:
        print(f"Content #{item['id']}: {item['text'][:50]}...")

        # Step 1: Check if translation needed
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="check_translation",
        )
        translation_result = await if_node.execute(
            if_node.input_schema(condition_value=item["language"]),
            context,
            state,
        )
        print(f"  1. Translation: {translation_result.route}")

        # Step 2: Route by priority
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="priority_router",
        )
        priority_result = await router_node.execute(
            router_node.input_schema(routing_value=item),
            context,
            state,
        )
        print(f"  2. Priority: {priority_result.route}")

        # Step 3: Route by content type
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id="content_type_switch",
        )
        type_result = await switch_node.execute(
            switch_node.input_schema(switch_value=item["type"]),
            context,
            state,
        )
        print(f"  3. Type Pipeline: {type_result.route}")
        print()

    # Example 5: Complex conditional logic
    print("\n" + "=" * 60)
    print("Example 5: Complex Conditional Logic")
    print("=" * 60)

    # Create a more complex router for risk assessment
    risk_router = RouterNode(
        node_id="risk_assessment",
        name="Content Risk Assessment",
        routes=[
            RouteCondition(
                name="high_risk",
                expression=(
                    "(value.get('sentiment_score', 0.5) < 0.2 or "
                    "value.get('sentiment_score', 0.5) > 0.9) and "
                    "len(value.get('text', '')) > 100"
                ),
            ),
            RouteCondition(
                name="medium_risk",
                expression=(
                    "(value.get('sentiment_score', 0.5) < 0.4 or "
                    "value.get('sentiment_score', 0.5) > 0.7) and "
                    "len(value.get('text', '')) > 50"
                ),
            ),
            RouteCondition(
                name="low_risk",
                expression="True",  # Catch-all
            ),
        ],
        default_route="unknown",
    )

    print("\nRisk Assessment Results:")
    for item in content_items:
        context = NodeContext(
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            node_id=risk_router.node_id,
        )

        result = await risk_router.execute(
            risk_router.input_schema(routing_value=item),
            context,
            state,
        )

        print(f"\nContent #{item['id']}")
        print(f"  Sentiment: {item['sentiment_score']}")
        print(f"  Length: {len(item['text'])} chars")
        print(f"  Risk Level: {result.route}")

    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
