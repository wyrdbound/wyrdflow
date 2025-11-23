"""Example workflow demonstrating HumanApprovalNode v2 API.

This example demonstrates the improved API for Wyrdflow nodes:
1. Constructor-based configuration (separating static config from runtime data)
2. Declarative input/output mapping (eliminating prep/extract nodes)
3. Simplified graph construction
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from wyrdflow.core.state import WorkflowState

# In the future API, we would import these:
from wyrdflow.nodes.human_approval import HumanApprovalNode


# Define LangGraph state schema
class DocumentReviewState(TypedDict, total=False):
    """State schema for LangGraph document review workflow."""

    # Domain data
    document_data: dict[str, Any]

    # Approval results (flat structure, no generic 'decision' keys needed)
    content_decision: str
    content_feedback: str
    content_approved: bool

    legal_decision: str
    legal_feedback: str
    legal_approved: bool

    final_decision: str
    final_feedback: str
    final_approved: bool

    # Workflow metadata
    workflow_state: dict[str, Any]


def create_sample_document_data() -> dict[str, Any]:
    return {
        "id": "DOC-2025-001",
        "title": "Quarterly Performance Report",
        "requires_legal_review": True,
    }


async def document_review_workflow_v2() -> None:
    """Example workflow using the improved v2 API."""
    print("🔄 Starting Document Review Workflow (v2 API)\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()

    # 1. Define Nodes with Declarative Configuration
    # Static config goes in constructor, dynamic data is mapped via input_map

    content_reviewer = HumanApprovalNode(
        node_id="content_review",
        title="📄 Content Review",
        description="Review the document content, structure, and accuracy",
        approval_prompt="Does the document meet our content quality standards?",
        allow_feedback=True,
        # Map state["document_data"] -> node input "data_to_review"
        input_map={"data_to_review": "document_data"},
        # Map node outputs -> state keys
        output_map={
            "decision": "content_decision",
            "feedback": "content_feedback",
            "approved": "content_approved",
        },
    )

    legal_reviewer = HumanApprovalNode(
        node_id="legal_review",
        title="⚖️ Legal Review",
        description="Review document for legal compliance",
        input_map={
            "data_to_review": "document_data",
            # Can also map other state values to context
            "context": "content_feedback",
        },
        output_map={
            "decision": "legal_decision",
            "feedback": "legal_feedback",
            "approved": "legal_approved",
        },
    )

    final_reviewer = HumanApprovalNode(
        node_id="final_approval",
        title="🏢 Management Approval",
        input_map={"data_to_review": "document_data"},
        output_map={
            "decision": "final_decision",
            "feedback": "final_feedback",
            "approved": "final_approved",
        },
    )

    # Create LangGraph workflow
    print("🔧 Building LangGraph workflow...")
    graph = StateGraph(DocumentReviewState)

    # Add nodes directly - NO prep or extract nodes needed!
    graph.add_node("content_review", content_reviewer.as_langraph_node())
    graph.add_node("legal_review", legal_reviewer.as_langraph_node())
    graph.add_node("final_approval", final_reviewer.as_langraph_node())

    # Define workflow edges with simple logic
    graph.add_edge(START, "content_review")

    # Conditional logic remains the same, but operates on clean state keys
    def should_do_legal_review(state: DocumentReviewState) -> str:
        document_data = state.get("document_data", {})
        if state.get("content_approved") and document_data.get("requires_legal_review"):
            return "legal_review"
        return "final_approval"

    graph.add_conditional_edges(
        "content_review",
        should_do_legal_review,
        {"legal_review": "legal_review", "final_approval": "final_approval"},
    )

    graph.add_edge("legal_review", "final_approval")
    graph.add_edge("final_approval", END)

    # Compile the graph
    workflow = graph.compile()

    # Prepare initial state
    initial_state: DocumentReviewState = {
        "document_data": create_sample_document_data(),
        "workflow_state": workflow_state.model_dump(),
    }

    print("\n🎯 Executing workflow...")
    result = await workflow.ainvoke(initial_state)

    print("\n✅ Workflow completed!")
    print(f"Content Decision: {result.get('content_decision')}")
    print(f"Legal Decision: {result.get('legal_decision')}")
    print(f"Final Decision: {result.get('final_decision')}")


if __name__ == "__main__":
    asyncio.run(document_review_workflow_v2())
