# HumanApprovalNode

The `HumanApprovalNode` enables human-in-the-loop workflows by pausing execution and requesting approval from a human reviewer before proceeding.

## Overview

This node displays data to a human reviewer through a rich terminal interface and collects their approval decision (approved/rejected) along with optional feedback. It's essential for workflows requiring human oversight, compliance checks, or quality control.

## Features

- **Rich Terminal Interface**: Beautiful formatted display using Rich library
- **Approval/Rejection**: Binary decision with optional feedback
- **Data Presentation**: Table-based display of review data
- **Approval Records**: Timestamped records of decisions
- **Cancellation Support**: Users can cancel the approval process
- **Customizable Interface**: Abstract interface for custom implementations

## Basic Usage

```python
from wyrdflow.nodes import HumanApprovalNode

# Create approval node
approval_node = HumanApprovalNode(
    node_id="content_approval",
    name="Content Review",
    approval_prompt="Do you approve this content for publication?",
    allow_feedback=True,
    input_map={
        "data_for_approval": "content_data",
    }
)

# Use in workflow
result = await approval_node.execute(
    approval_node.input_schema(
        data_for_approval={
            "title": "New Article",
            "author": "John Doe",
            "word_count": 1500,
            "category": "Technology"
        }
    ),
    context,
    state
)

# Check decision
if result.decision == "approved":
    print(f"Approved! Feedback: {result.feedback}")
else:
    print(f"Rejected. Feedback: {result.feedback}")
```

## Input Schema

```python
class HumanApprovalNodeInput(NodeInput):
    data_for_approval: dict[str, Any]  # Data to display for review
```

## Output Schema

```python
class HumanApprovalNodeOutput(NodeOutput):
    decision: ApprovalDecision  # "approved" or "rejected"
    feedback: Optional[str]     # Optional feedback from reviewer
    record: ApprovalRecord      # Full approval record with timestamp
```

## Configuration Options

### Constructor Parameters

- **`node_id`** (str, required): Unique identifier for the node
- **`approval_prompt`** (str, optional): Custom prompt for approval decision
  - Default: `"Do you approve?"`
- **`title`** (str, optional): Title displayed in approval interface
  - Default: `"Approval Required"`
- **`description`** (str, optional): Description text shown to reviewer
- **`allow_feedback`** (bool, optional): Whether to collect optional feedback
  - Default: `False`
- **`approval_interface`** (ApprovalInterface, optional): Custom interface implementation
  - Default: `RichApprovalInterface()`
- **`input_map`** (dict, optional): Map state keys to input fields
- **`output_map`** (dict, optional): Map output fields to state keys

## Use Cases

### 1. Content Moderation

```python
moderation_node = HumanApprovalNode(
    node_id="moderate_content",
    title="Content Moderation Review",
    description="Review this user-generated content",
    approval_prompt="Approve this content for publication?",
    allow_feedback=True,
    input_map={"data_for_approval": "user_content"}
)
```

### 2. Financial Transaction Approval

```python
transaction_approval = HumanApprovalNode(
    node_id="approve_transaction",
    title="High-Value Transaction Approval",
    description="Review and approve this transaction",
    approval_prompt="Approve this transaction?",
    allow_feedback=True,
    input_map={"data_for_approval": "transaction_details"}
)
```

### 3. Document Review Workflow

```python
document_review = HumanApprovalNode(
    node_id="review_document",
    title="Document Review",
    description="Review document before final submission",
    approval_prompt="Approve document for submission?",
    allow_feedback=True,
    input_map={"data_for_approval": "document_metadata"}
)
```

## Custom Approval Interface

You can implement a custom approval interface for web-based or other UI systems:

```python
from wyrdflow.nodes.human_approval import ApprovalInterface, ApprovalDecision

class WebApprovalInterface(ApprovalInterface):
    def display_data_for_approval(
        self,
        title: str,
        data: dict[str, Any],
        description: Optional[str] = None
    ) -> None:
        # Send data to web UI
        self.web_client.display_approval_request(title, data, description)

    def collect_approval_decision(
        self,
        prompt: str,
        allow_feedback: bool = False
    ) -> tuple[ApprovalDecision, Optional[str]]:
        # Wait for user decision from web UI
        decision, feedback = self.web_client.wait_for_decision()
        return decision, feedback

    def show_error(self, message: str) -> None:
        self.web_client.show_error(message)

# Use custom interface
approval_node = HumanApprovalNode(
    node_id="web_approval",
    approval_interface=WebApprovalInterface()
)
```

## Error Handling

The node raises specific exceptions for different error conditions:

- **`UserCancelledError`**: User cancelled the approval process
- **`ApprovalValidationError`**: Invalid approval data or configuration

```python
from wyrdflow.nodes.human_approval import UserCancelledError

try:
    result = await approval_node.execute(input_data, context, state)
except UserCancelledError:
    print("User cancelled the approval process")
    # Handle cancellation
```

## Approval Records

Each approval generates a timestamped record:

```python
class ApprovalRecord(BaseModel):
    decision: ApprovalDecision      # approved or rejected
    feedback: Optional[str]         # optional feedback
    timestamp: datetime             # when decision was made
    execution_id: str               # unique execution identifier
```

Access the record from the output:

```python
result = await approval_node.execute(input_data, context, state)
record = result.record

print(f"Decision: {record.decision}")
print(f"Made at: {record.timestamp}")
print(f"Execution ID: {record.execution_id}")
if record.feedback:
    print(f"Feedback: {record.feedback}")
```

## Integration with LangGraph

```python
from langgraph.graph import StateGraph
from wyrdflow.core.state import WorkflowState

# Create graph
graph = StateGraph(WorkflowState)

# Add approval node
approval = HumanApprovalNode(
    node_id="approve_content",
    title="Content Approval",
    allow_feedback=True
)
graph.add_node("approve", approval.as_langraph_node())

# Add conditional edges based on decision
graph.add_conditional_edges(
    "approve",
    lambda state: state.data.get("decision"),
    {
        "approved": "publish_content",
        "rejected": "archive_content"
    }
)
```

## Best Practices

1. **Clear Titles and Descriptions**: Provide context to help reviewers make informed decisions
2. **Structured Data**: Present data in a clear, organized format
3. **Feedback Collection**: Enable feedback for rejected items to understand reasons
4. **Timeout Handling**: Consider implementing timeouts for approval requests
5. **Audit Trail**: Store approval records for compliance and auditing
6. **Error Recovery**: Handle user cancellations gracefully

## Performance Considerations

- **Blocking Operation**: This node blocks workflow execution until approval is received
- **User Availability**: Workflows will wait indefinitely unless timeout mechanisms are implemented
- **State Persistence**: Consider persisting workflow state during long approval waits

## See Also

- [HumanInputNode](human_input.md) - For collecting arbitrary user input
- [IfNode](if_node.md) - For automated conditional branching
- [RouterNode](router_node.md) - For multi-condition routing
