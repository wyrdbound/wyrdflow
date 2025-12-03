# Wyrdflow Node Documentation

This directory contains comprehensive documentation for all available Wyrdflow nodes.

## Node Types

### Flow Control Nodes

Flow control nodes enable conditional logic and routing in workflows.

- **[IfNode](if_node.md)** - Binary conditional branching (true/false paths)
- **[RouterNode](router_node.md)** - Multi-condition routing with named branches
- **[SwitchNode](switch_node.md)** - Value-based routing (switch/case pattern)

### Human-in-the-Loop Nodes

Nodes that pause workflow execution for human interaction.

- **[HumanInputNode](human_input.md)** - Collect arbitrary input from users
- **[HumanApprovalNode](human_approval.md)** - Request approval/rejection decisions

### LLM Integration Nodes

Nodes for integrating Large Language Models into workflows.

- **[LLMNode](llm.md)** - LangChain-based LLM integration with structured output support

## Quick Reference

| Node                  | Primary Use Case         | Input                               | Output                     |
| --------------------- | ------------------------ | ----------------------------------- | -------------------------- |
| **IfNode**            | Simple yes/no decisions  | `condition_value`                   | `route`: "true" or "false" |
| **RouterNode**        | Multi-path routing       | `routing_value`                     | `route`: named route       |
| **SwitchNode**        | Value-based routing      | `switch_value`                      | `route`: matched case      |
| **HumanInputNode**    | User input collection    | `input_prompt`, `validation_schema` | `user_input`               |
| **HumanApprovalNode** | Approval workflows       | `data_for_approval`                 | `decision`, `feedback`     |
| **LLMNode**           | LLM text/data generation | `prompt_variables`                  | `content`, `usage`         |

## Getting Started

Each node documentation includes:

- **Overview**: What the node does and when to use it
- **Features**: Key capabilities and options
- **Basic Usage**: Simple examples to get started
- **Input/Output Schemas**: Data structures for inputs and outputs
- **Configuration Options**: All available parameters
- **Use Cases**: Real-world application examples
- **Integration Examples**: How to use with LangGraph
- **Best Practices**: Tips for effective usage
- **Performance Considerations**: Efficiency and optimization notes

## Common Patterns

### Conditional Workflow

```python
from wyrdflow.nodes import IfNode, RouterNode

# Binary decision
quality_check = IfNode(
    node_id="check_quality",
    expression="value >= 0.8",
    input_map={"condition_value": "quality_score"}
)

# Multi-way routing
priority_router = RouterNode(
    node_id="route_priority",
    routes=[
        RouteCondition(name="urgent", expression="value == 'high'"),
        RouteCondition(name="normal", expression="value == 'medium'"),
        RouteCondition(name="low", expression="value == 'low'"),
    ],
    input_map={"routing_value": "priority"}
)
```

### Human Oversight

```python
from wyrdflow.nodes import HumanApprovalNode, HumanInputNode

# Approval gate
approval = HumanApprovalNode(
    node_id="approve_content",
    title="Content Review",
    allow_feedback=True
)

# Collect additional info
user_input = HumanInputNode(
    node_id="get_details",
    input_prompt="Please provide additional context:",
    validation_schema={"type": "string", "minLength": 10}
)
```

### LLM Processing

```python
from wyrdflow.nodes import LLMNode
from langchain_openai import ChatOpenAI

# Text generation
summarizer = LLMNode(
    node_id="summarize",
    llm=ChatOpenAI(model="gpt-4"),
    prompt="Summarize this text: {text}",
    input_map={"prompt_variables": "content"}
)
```

## Node Selection Guide

**When to use each node:**

- **IfNode**: Simple binary decisions (approved/rejected, valid/invalid, above/below threshold)
- **RouterNode**: Complex multi-condition logic with multiple named paths
- **SwitchNode**: Routing based on discrete values (status codes, types, categories)
- **HumanInputNode**: Need arbitrary user input (text, numbers, selections)
- **HumanApprovalNode**: Require explicit approval/rejection with optional feedback
- **LLMNode**: Generate text, extract data, or transform content using AI

## Architecture

All nodes inherit from `BaseNode[InputType, OutputType]` and provide:

- Type-safe inputs and outputs via Pydantic schemas
- State management integration
- LangGraph compatibility via `as_langraph_node()`
- Input/output mapping to workflow state
- Consistent error handling

## Examples

For complete working examples, see:

- `/examples/flow_control_example.py` - Flow control nodes in action
- `/examples/human_input_example.py` - Human input collection
- `/examples/human_approval_example.py` - Approval workflows
- `/examples/llm_node_example.py` - LLM integration

## Contributing

When adding new node types:

1. Create the node implementation in `/src/wyrdflow/nodes/`
2. Add comprehensive tests in `/tests/test_<node_name>.py`
3. Create documentation following the template in existing node docs
4. Export the node in `/src/wyrdflow/nodes/__init__.py`
5. Update this README with the new node

## See Also

- [Core Architecture](../../README.md#architecture) - Understanding the BaseNode system
- [State Management](../../README.md#state-management) - How nodes interact with workflow state
- [LangGraph Integration](../../README.md#langgraph-integration) - Using nodes in LangGraph workflows
