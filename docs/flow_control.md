# Flow Control Nodes

Flow control nodes enable conditional logic and routing in Wyrdflow workflows. They allow you to create dynamic, multi-path workflows that adapt based on data conditions.

## Overview

Wyrdflow provides three flow control nodes:

1. **IfNode**: Binary branching (true/false paths)
2. **RouterNode**: Multi-condition routing with priorities
3. **SwitchNode**: Value-based routing (like switch/case statements)

## IfNode

Simple binary conditional branching.

### Features

- Boolean value evaluation
- Python expression evaluation (safe)
- Comparison operations (eq, ne, lt, le, gt, ge)
- Custom condition functions
- Configurable null/None handling

### Usage

```python
from wyrdflow.nodes.if_node import IfNode

# Simple boolean check
if_node = IfNode(
    node_id="check_approved",
    input_map={"condition_value": "is_approved"}
)

# Expression evaluation
if_node = IfNode(
    node_id="check_threshold",
    expression="value > 10",
    input_map={"condition_value": "score"}
)

# Comparison operation
if_node = IfNode(
    node_id="check_status",
    comparison_op="eq",
    comparison_value="active",
    input_map={"condition_value": "user_status"}
)

# Custom function
def is_valid(value):
    return value is not None and len(value) > 0

if_node = IfNode(
    node_id="check_valid",
    condition_func=is_valid,
    input_map={"condition_value": "data"}
)
```

### Routes

- `"true"`: Condition evaluates to True
- `"false"`: Condition evaluates to False

### Null Handling

Configure how None/null values are handled:

- `"false"` (default): Treat as False
- `"true"`: Treat as True
- `"error"`: Raise an error

```python
if_node = IfNode(
    node_id="check_value",
    null_handling="error",  # Raise error if value is None
    input_map={"condition_value": "optional_field"}
)
```

## RouterNode

Multi-condition routing with named routes.

### Features

- Multiple named routes
- List-order evaluation (first-to-last)
- First-match or all-match modes
- Python expression support
- Custom condition functions
- Default/fallback route

### Usage

```python
from wyrdflow.nodes.router_node import RouteCondition, RouterNode

# Route based on sentiment score
router = RouterNode(
    node_id="sentiment_router",
    routes=[
        RouteCondition(
            name="positive",
            expression="value > 0.7"
        ),
        RouteCondition(
            name="negative",
            expression="value < 0.3"
        ),
        RouteCondition(
            name="neutral",
            expression="value >= 0.3 and value <= 0.7"
        ),
    ],
    default_route="neutral",
    input_map={"routing_value": "sentiment_score"}
)

# Route with custom functions
def is_urgent(value):
    return value.get("priority") == "high"

def is_important(value):
    return value.get("importance") > 8

router = RouterNode(
    node_id="task_router",
    routes=[
        RouteCondition(
            name="urgent_important",
            condition_func=lambda v: is_urgent(v) and is_important(v)
        ),
        RouteCondition(
            name="urgent",
            condition_func=is_urgent
        ),
        RouteCondition(
            name="important",
            condition_func=is_important
        ),
    ],
    default_route="normal",
    input_map={"routing_value": "task_data"}
)
```

### Match Modes

- `"first"` (default): Return first matching route (in list order)
- `"all"`: Evaluate all routes and return all matches

```python
router = RouterNode(
    node_id="multi_match_router",
    routes=[...],
    match_mode="all",  # Track all matching routes
    input_map={"routing_value": "data"}
)
```

### List Order Evaluation

Routes are evaluated in the order they appear in the list (first to last). This allows you to control the evaluation order:

```python
routes = [
    RouteCondition(
        name="specific_case",  # Checked first
        expression="value == 'special'"
    ),
    RouteCondition(
        name="general_case",  # Checked second
        expression="value in ['normal', 'special']"
    ),
]
```

**Tip**: Place more specific conditions before more general ones to ensure correct routing.

## SwitchNode

Value-based routing, similar to switch/case statements.

### Features

- Exact value matching
- Regex pattern matching (for strings)
- List of values matching
- Custom predicate functions
- Case-sensitive or case-insensitive matching
- Default/fallback route

### Usage

```python
from wyrdflow.nodes.switch_node import CaseCondition, SwitchNode

# Simple value matching
switch = SwitchNode(
    node_id="status_router",
    cases=[
        CaseCondition(route="process_new", value="new"),
        CaseCondition(route="process_pending", value="pending"),
        CaseCondition(route="process_completed", value="completed"),
        CaseCondition(
            route="process_error",
            value_list=["error", "failed", "rejected"]
        ),
    ],
    default_route="unknown",
    input_map={"switch_value": "order_status"}
)

# Pattern matching
switch = SwitchNode(
    node_id="email_router",
    cases=[
        CaseCondition(
            route="internal",
            pattern=r".*@company\.com$"
        ),
        CaseCondition(
            route="customer",
            pattern=r".*@gmail\.com$"
        ),
    ],
    default_route="external",
    input_map={"switch_value": "email_address"}
)

# Custom predicate
def is_high_value(amount):
    return amount > 10000

switch = SwitchNode(
    node_id="order_router",
    cases=[
        CaseCondition(
            route="vip_processing",
            predicate=is_high_value
        ),
        CaseCondition(
            route="standard_processing",
            predicate=lambda x: x <= 10000
        ),
    ],
    default_route="review",
    input_map={"switch_value": "order_amount"}
)
```

### Case Sensitivity

Control case sensitivity for string matching:

```python
switch = SwitchNode(
    node_id="status_router",
    cases=[
        CaseCondition(route="approved", value="approved"),
    ],
    case_sensitive=False,  # "APPROVED", "Approved" all match
    input_map={"switch_value": "status"}
)
```

## Integration with LangGraph

All flow control nodes integrate seamlessly with LangGraph workflows using conditional edges:

```python
from langgraph.graph import StateGraph
from wyrdflow.nodes.if_node import IfNode
from wyrdflow.core.state import WorkflowState

# Create nodes
check_node = IfNode(
    node_id="check_condition",
    expression="value > 10",
    input_map={"condition_value": "score"}
)
process_high = SomeNode(node_id="process_high")
process_low = SomeNode(node_id="process_low")

# Create graph
graph = StateGraph(WorkflowState)
graph.add_node("check", check_node.as_langraph_node())
graph.add_node("high", process_high.as_langraph_node())
graph.add_node("low", process_low.as_langraph_node())

# Add conditional edges based on route
def route_condition(state):
    return state.data.get("route", "false")

graph.add_conditional_edges(
    "check",
    route_condition,
    {
        "true": "high",
        "false": "low",
    }
)
```

## Best Practices

### 1. Choose the Right Node

- **IfNode**: Use for simple binary decisions (yes/no, true/false)
- **RouterNode**: Use for complex multi-condition routing
- **SwitchNode**: Use for value-based routing (status codes, types, etc.)

### 2. Handle Edge Cases

Always define a default route to handle unexpected values:

```python
router = RouterNode(
    node_id="router",
    routes=[...],
    default_route="fallback",  # Handle unmatched cases
)
```

### 3. Use Null Handling

Explicitly configure how None/null values are handled:

```python
if_node = IfNode(
    node_id="check",
    null_handling="error",  # Or "false"/"true" based on your logic
    input_map={"condition_value": "optional_field"}
)
```

### 4. Expression Safety

The expression evaluators use a restricted set of built-in functions for security. Available functions:

- IfNode: `abs`, `bool`, `float`, `int`, `len`, `max`, `min`, `str`, `sum`
- RouterNode: Same as IfNode, plus `all`, `any`, `dict`, `list`

### 5. Route Ordering

In RouterNode, the order of routes matters:

- Routes are evaluated first-to-last in the list
- Place more specific conditions before general ones
- Document route ordering decisions in comments

### 6. Testing Routes

Test all possible routes in your workflows:

```python
# Test each route
for test_value, expected_route in test_cases:
    result = await node.execute(input_data, context, state)
    assert result.route == expected_route
```

## Error Handling

All flow control nodes handle errors gracefully:

- Invalid expressions raise `ValueError` with helpful messages
- Failed condition functions are logged and skipped (RouterNode, SwitchNode)
- All routes have a default/fallback option

## Performance Considerations

- **Expression evaluation**: ~0.1ms overhead per expression
- **Custom functions**: No overhead beyond the function itself
- **Pattern matching**: Regex patterns are compiled once at initialization
- **List evaluation**: Routes checked in order until match found

## Examples

See `examples/flow_control_example.py` for a comprehensive example demonstrating all three flow control nodes in a content moderation workflow.

## API Reference

### IfNode

```python
IfNode(
    node_id: str,
    expression: Optional[str] = None,
    condition_func: Optional[Callable[[Any], bool]] = None,
    comparison_op: Optional[Literal["eq", "ne", "lt", "le", "gt", "ge"]] = None,
    comparison_value: Optional[Any] = None,
    null_handling: Literal["false", "true", "error"] = "false",
    **kwargs
)
```

### RouterNode

```python
RouterNode(
    node_id: str,
    routes: list[RouteCondition],
    default_route: str = "default",
    match_mode: Literal["first", "all"] = "first",
    null_handling: Literal["default", "error"] = "default",
    **kwargs
)

RouteCondition(
    name: str,
    expression: Optional[str] = None,
    condition_func: Optional[Callable[[Any], bool]] = None
)
```

### SwitchNode

```python
SwitchNode(
    node_id: str,
    cases: list[CaseCondition],
    default_route: str = "default",
    case_sensitive: bool = True,
    null_handling: Literal["default", "error"] = "default",
    **kwargs
)

CaseCondition(
    route: str,
    value: Optional[Any] = None,
    pattern: Optional[str] = None,
    value_list: Optional[list[Any]] = None,
    predicate: Optional[Callable[[Any], bool]] = None
)
```
