"""Example workflow demonstrating human approval functionality using LangGraph.

This example shows how to use the HumanApprovalNode in a document review workflow
where a document goes through multiple approval stages, orchestrated with LangGraph.
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.human_approval import (
    HumanApprovalNode,
    HumanApprovalNodeInput,
)


# Define LangGraph state schema for document review
class DocumentReviewState(TypedDict, total=False):
    """State schema for LangGraph document review workflow."""

    # Document data (required)
    document_data: dict[str, Any]

    # Approval inputs for each stage
    content_review_input: dict[str, Any]
    legal_review_input: dict[str, Any]
    final_approval_input: dict[str, Any]

    # Node input/output fields
    input: dict[str, Any]
    decision: str
    feedback: str
    approved: bool

    # Approval results from each stage
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
    last_node: str
    workflow_complete: bool


# Define LangGraph state schema for simple approval
class SimpleApprovalState(TypedDict, total=False):
    """State schema for LangGraph simple approval workflow."""

    input: dict[str, Any]  # Input configuration for the approval node
    task_data: dict[str, Any]
    decision: str
    feedback: str
    approved: bool
    workflow_state: dict[str, Any]
    last_node: str


def create_sample_document_data() -> dict[str, Any]:
    """Create sample document data for the review workflow."""
    return {
        "id": "DOC-2025-001",
        "title": "Quarterly Performance Report",
        "author": "Jane Smith",
        "department": "Analytics",
        "created_date": "2025-11-01",
        "word_count": 2847,
        "sections": ["Executive Summary", "Key Metrics", "Analysis", "Recommendations"],
        "content_preview": "This quarterly report presents a comprehensive analysis of our performance metrics, highlighting a 15% increase in customer satisfaction and 23% growth in revenue compared to the previous quarter...",
        "classification": "Internal Use",
        "contains_sensitive_data": False,
        "requires_legal_review": True,
    }


def create_approval_nodes() -> tuple[
    HumanApprovalNode, HumanApprovalNode, HumanApprovalNode
]:
    """Create the approval nodes for the document review workflow."""
    content_reviewer = HumanApprovalNode(node_id="content_review")
    legal_reviewer = HumanApprovalNode(node_id="legal_review")
    final_reviewer = HumanApprovalNode(node_id="final_approval")

    return content_reviewer, legal_reviewer, final_reviewer


async def content_review_preparation(state: DocumentReviewState) -> DocumentReviewState:
    """Prepare the content review input."""
    document_data = state.get("document_data", {})

    content_review_input = HumanApprovalNodeInput(
        data_to_review=document_data,
        title="📄 Content Review - Stage 1",
        description="Review the document content, structure, and accuracy",
        approval_prompt="Does the document meet our content quality standards?",
        allow_feedback=True,
        state_path="document.reviews.content",
    )

    new_state = state.copy()
    new_state["input"] = content_review_input.model_dump()  # Set as input for the node
    new_state["content_review_input"] = (
        content_review_input.model_dump()
    )  # Keep for reference
    new_state["last_node"] = "content_prep"
    return new_state


async def legal_review_preparation(state: DocumentReviewState) -> DocumentReviewState:
    """Prepare the legal review input based on content review results."""
    document_data = state.get("document_data", {})

    # Check if legal review is required and content was approved
    if not document_data.get("requires_legal_review", False) or not state.get(
        "content_approved", False
    ):
        # Skip legal review
        new_state = state.copy()
        new_state["legal_decision"] = "skipped"
        new_state["legal_approved"] = True  # Auto-approve if not needed
        new_state["last_node"] = "legal_prep_skipped"
        return new_state

    # Add legal review specific data
    legal_review_data = document_data.copy()
    legal_review_data.update(
        {
            "content_approval": state.get("content_decision", "unknown"),
            "content_reviewer_feedback": state.get("content_feedback")
            or "No feedback provided",
            "legal_considerations": [
                "Contains financial projections",
                "References customer data (anonymized)",
                "Includes competitive analysis",
                "May require SEC compliance review",
            ],
            "compliance_requirements": ["SOX", "GDPR", "Company Policy 2.1.3"],
        }
    )

    legal_review_input = HumanApprovalNodeInput(
        data_to_review=legal_review_data,
        title="⚖️ Legal Review - Stage 2",
        description="Review document for legal compliance and risk assessment",
        approval_prompt="Does this document meet legal and compliance requirements?",
        allow_feedback=True,
        state_path="document.reviews.legal",
    )

    new_state = state.copy()
    new_state["input"] = legal_review_input.model_dump()  # Set as input for the node
    new_state["legal_review_input"] = (
        legal_review_input.model_dump()
    )  # Keep for reference
    new_state["last_node"] = "legal_prep"
    return new_state


async def final_approval_preparation(state: DocumentReviewState) -> DocumentReviewState:
    """Prepare the final approval input based on previous reviews."""
    document_data = state.get("document_data", {})

    # Check if previous stages were approved
    if not state.get("content_approved", False) or not state.get(
        "legal_approved", False
    ):
        # Skip final approval if previous stages failed
        new_state = state.copy()
        new_state["final_decision"] = "rejected"
        new_state["final_approved"] = False
        new_state["workflow_complete"] = True
        new_state["last_node"] = "final_prep_rejected"
        return new_state

    # Prepare final review data with all previous approvals
    final_review_data = {
        "document_summary": {
            "id": document_data["id"],
            "title": document_data["title"],
            "author": document_data["author"],
            "word_count": document_data["word_count"],
            "classification": document_data["classification"],
        },
        "approval_history": {
            "content_review": {
                "decision": state.get("content_decision"),
                "feedback": state.get("content_feedback"),
            },
        },
        "final_approval_required": True,
        "publication_channels": ["Internal Portal", "Management Dashboard"],
        "estimated_impact": "High - Quarterly strategic decisions",
    }

    # Add legal review results if it happened
    legal_decision = state.get("legal_decision")
    if legal_decision and legal_decision != "skipped":
        approval_history = final_review_data.get("approval_history", {})
        if isinstance(approval_history, dict):
            approval_history["legal_review"] = {
                "decision": legal_decision,
                "feedback": state.get("legal_feedback"),
            }
            final_review_data["approval_history"] = approval_history

    final_approval_input = HumanApprovalNodeInput(
        data_to_review=final_review_data,
        title="🏢 Management Approval - Final Stage",
        description="Final approval for document publication and distribution",
        approval_prompt="Approve this document for publication?",
        allow_feedback=True,
        state_path="document.reviews.final",
    )

    new_state = state.copy()
    new_state["input"] = final_approval_input.model_dump()  # Set as input for the node
    new_state["final_approval_input"] = (
        final_approval_input.model_dump()
    )  # Keep for reference
    new_state["last_node"] = "final_prep"
    return new_state


async def extract_content_result(state: DocumentReviewState) -> DocumentReviewState:
    """Extract content review results and store in state."""
    new_state = state.copy()

    # Extract results from the approval node output
    new_state["content_decision"] = state.get("decision", "unknown")
    new_state["content_feedback"] = state.get("feedback", "")
    new_state["content_approved"] = state.get("approved", False)
    new_state["last_node"] = "content_extract"

    print(f"\n✅ Content Review Result: {new_state['content_decision'].upper()}")
    if new_state["content_feedback"]:
        print(f"💬 Reviewer Feedback: {new_state['content_feedback']}")

    return new_state


async def extract_legal_result(state: DocumentReviewState) -> DocumentReviewState:
    """Extract legal review results and store in state."""
    new_state = state.copy()

    # Extract results from the approval node output
    new_state["legal_decision"] = state.get("decision", "unknown")
    new_state["legal_feedback"] = state.get("feedback", "")
    new_state["legal_approved"] = state.get("approved", False)
    new_state["last_node"] = "legal_extract"

    print(f"\n✅ Legal Review Result: {new_state['legal_decision'].upper()}")
    if new_state["legal_feedback"]:
        print(f"💬 Legal Reviewer Feedback: {new_state['legal_feedback']}")

    return new_state


async def extract_final_result(state: DocumentReviewState) -> DocumentReviewState:
    """Extract final approval results and store in state."""
    new_state = state.copy()

    # Extract results from the approval node output
    new_state["final_decision"] = state.get("decision", "unknown")
    new_state["final_feedback"] = state.get("feedback", "")
    new_state["final_approved"] = state.get("approved", False)
    new_state["last_node"] = "final_extract"

    print(f"\n✅ Final Approval Result: {new_state['final_decision'].upper()}")
    if new_state["final_feedback"]:
        print(f"💬 Management Feedback: {new_state['final_feedback']}")

    return new_state


async def workflow_completion(state: DocumentReviewState) -> DocumentReviewState:
    """Complete the workflow and display results."""
    new_state = state.copy()
    new_state["workflow_complete"] = True
    new_state["last_node"] = "completion"

    # Display final workflow result
    if new_state.get("final_approved", False):
        print("\n🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        print("✨ Document approved for publication")
        document_data = new_state.get("document_data", {})
        print(f"📊 Document ID: {document_data.get('id', 'Unknown')}")
    else:
        print("\n❌ Document workflow completed with rejection")
        print("🔄 Document needs revision before publication")

    return new_state


async def document_review_workflow() -> None:
    """Example workflow: Document review with multiple approval stages using LangGraph."""
    print("🔄 Starting Document Review Workflow with LangGraph\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()
    print(f"Created workflow run: {workflow_state.workflow_run_id}")

    # Create nodes
    content_reviewer, legal_reviewer, final_reviewer = create_approval_nodes()
    document_data = create_sample_document_data()

    # Create LangGraph workflow
    print("🔧 Building document review LangGraph workflow...")
    graph = StateGraph(DocumentReviewState)

    # Add preparation nodes (regular functions)
    graph.add_node("content_prep", content_review_preparation)
    graph.add_node("legal_prep", legal_review_preparation)
    graph.add_node("final_prep", final_approval_preparation)
    graph.add_node("completion", workflow_completion)

    # Add result extraction nodes
    graph.add_node("content_extract", extract_content_result)
    graph.add_node("legal_extract", extract_legal_result)
    graph.add_node("final_extract", extract_final_result)

    # Add approval nodes (using as_langraph_node)
    graph.add_node("content_review", content_reviewer.as_langraph_node())
    graph.add_node("legal_review", legal_reviewer.as_langraph_node())
    graph.add_node("final_approval", final_reviewer.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "content_prep")
    graph.add_edge("content_prep", "content_review")
    graph.add_edge("content_review", "content_extract")

    # After content extract, go to legal prep
    graph.add_edge("content_extract", "legal_prep")

    # Conditional: if legal review needed, do it; otherwise skip to final prep
    def should_do_legal_review(state: DocumentReviewState) -> str:
        """Route to legal review or skip based on content approval and requirements."""
        # After content review, extract the approval status
        approved = state.get("approved", False)
        requires_legal = state.get("document_data", {}).get(
            "requires_legal_review", False
        )

        if approved and requires_legal:
            return "legal_review"
        return "final_prep"

    graph.add_conditional_edges(
        "legal_prep",
        should_do_legal_review,
        {"legal_review": "legal_review", "final_prep": "final_prep"},
    )

    graph.add_edge("legal_review", "legal_extract")
    graph.add_edge("legal_extract", "final_prep")

    # Conditional: if previous stages approved, do final approval; otherwise complete
    def should_do_final_approval(state: DocumentReviewState) -> str:
        """Route to final approval or skip based on previous approvals."""
        # Check if both content and legal (if needed) were approved
        content_ok = state.get("content_approved", False)
        legal_ok = state.get("legal_approved", True)  # Default to True if not needed

        # If legal review was required, check its status
        if state.get("document_data", {}).get("requires_legal_review", False):
            legal_ok = state.get("legal_approved", False)

        if content_ok and legal_ok:
            return "final_approval"
        return "completion"

    graph.add_conditional_edges(
        "final_prep",
        should_do_final_approval,
        {"final_approval": "final_approval", "completion": "completion"},
    )

    graph.add_edge("final_approval", "final_extract")
    graph.add_edge("final_extract", "completion")
    graph.add_edge("completion", END)

    # Compile the graph
    workflow = graph.compile()
    print("✅ Document review LangGraph workflow compiled successfully")

    # Prepare initial state for LangGraph
    initial_state: DocumentReviewState = {
        "document_data": document_data,
        "workflow_state": workflow_state.model_dump(),
    }

    try:
        print("\n🎯 Executing document review LangGraph workflow...")

        # Execute the workflow
        result = await workflow.ainvoke(initial_state)

        print("\n✅ Document review workflow completed!")

        # Display final state summary
        print("\n" + "=" * 60)
        print("📊 WORKFLOW STATE SUMMARY")
        print("=" * 60)

        stages = ["content", "legal", "final"]
        for stage in stages:
            decision = result.get(f"{stage}_decision")
            if decision and decision != "skipped":
                print(f"\n{stage.title()} Review:")
                print(f"  Decision: {decision}")
                feedback = result.get(f"{stage}_feedback")
                print(f"  Feedback: {feedback or 'No feedback'}")

        # Extract the final workflow state
        final_workflow_state = WorkflowState.model_validate(result["workflow_state"])
        print(f"\nWorkflow ID: {final_workflow_state.workflow_id}")
        print(f"Workflow Run ID: {final_workflow_state.workflow_run_id}")

        print("\n🎉 LangGraph document review workflow completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⏹️  Workflow cancelled by user")
    except Exception as e:
        print(f"\n❌ Workflow failed with error: {e}")


def create_sample_task_data() -> dict[str, Any]:
    """Create sample task data for simple approval."""
    return {
        "task_id": "TASK-001",
        "title": "Deploy new feature to production",
        "description": "Deploy the new user dashboard feature to production environment",
        "requester": "Development Team",
        "risk_level": "Medium",
        "estimated_downtime": "5 minutes",
        "rollback_plan": "Automated rollback via deployment script",
        "affected_systems": ["User Dashboard", "Analytics API", "Notification Service"],
        "deployment_window": "2025-11-02 02:00 UTC",
    }


async def simple_approval_example() -> None:
    """Simple example showing basic approval functionality using LangGraph."""
    print("🔄 Simple Approval Example with LangGraph\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()
    print(f"Created workflow run: {workflow_state.workflow_run_id}")

    # Sample data to approve
    task_data = create_sample_task_data()

    # Create approval node
    approval_node = HumanApprovalNode(node_id="deployment_approval")

    # Prepare input
    approval_input = HumanApprovalNodeInput(
        data_to_review=task_data,
        title="🚀 Production Deployment Approval",
        description="Review the deployment request for production release",
        approval_prompt="Do you approve this production deployment?",
        allow_feedback=True,
    )

    # Create LangGraph workflow
    print("🔧 Building simple approval LangGraph workflow...")
    graph = StateGraph(SimpleApprovalState)

    # Add the approval node
    graph.add_node("deployment_approval", approval_node.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "deployment_approval")
    graph.add_edge("deployment_approval", END)

    # Compile the graph
    workflow = graph.compile()
    print("✅ Simple approval LangGraph workflow compiled successfully")

    # Prepare initial state for LangGraph
    initial_state: SimpleApprovalState = {
        "input": approval_input.model_dump(),
        "task_data": task_data,
        "workflow_state": workflow_state.model_dump(),
    }

    try:
        print("\n🎯 Executing simple approval LangGraph workflow...")

        # Execute workflow
        result = await workflow.ainvoke(initial_state)

        print("\n✅ Simple approval completed!")
        print(f"👤 Decision: {result.get('decision', 'Unknown').upper()}")
        print(f"👤 Approved: {result.get('approved', False)}")
        if result.get("feedback"):
            print(f"💬 Feedback: {result['feedback']}")

        # Extract the final workflow state
        final_workflow_state = WorkflowState.model_validate(result["workflow_state"])

        # Show what was stored in state
        approval_record = final_workflow_state.get("deployment_approval_approval")
        if approval_record:
            print(f"\n📊 State Record: {approval_record}")

        print("\n🎉 LangGraph simple approval completed successfully!")

    except KeyboardInterrupt:
        print("\n⏹️  Approval cancelled by user")
    except Exception as e:
        print(f"\n❌ Approval failed: {e}")


if __name__ == "__main__":
    print("🎯 Wyrdflow Human Approval Examples")
    print("=" * 50)

    while True:
        print("\nChoose an example:")
        print("1. 📄 Document Review Workflow (Multi-stage)")
        print("2. 🚀 Simple Deployment Approval")
        print("3. 🚪 Exit")

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            print("\n" + "=" * 60)
            asyncio.run(document_review_workflow())
            print("\n" + "=" * 60)
        elif choice == "2":
            print("\n" + "=" * 60)
            asyncio.run(simple_approval_example())
            print("\n" + "=" * 60)
        elif choice == "3":
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
