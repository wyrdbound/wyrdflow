# IfNode

The `IfNode` provides simple binary conditional branching for workflows, routing execution to either a `"true"` or `"false"` path based on condition evaluation.

## Overview

This node evaluates a condition and routes workflow execution to one of two paths. It's ideal for simple yes/no decisions and binary logic in workflows.

## Features

- **Boolean Evaluation**: Direct true/false value checking
- **Expression Evaluation**: Safe Python expressions (e.g., `"value > 10"`)
- **Comparison Operations**: Built-in comparison operators (eq, ne, lt, le, gt, ge)
- **Custom Functions**: User-defined condition functions
- **Null Handling**: Configurable behavior for None/null values
- **Type Safety**: Full Pydantic validation

## Basic Usage

```python
from wyrdflow.nodes import IfNode

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

# Custom function
def is_valid(value):
    return value is not None and len(value) > 0

if_node = IfNode(
    node_id="check_valid",
    condition_func=is_valid,
    input_map={"condition_value": "data"}
)
```

## Input Schema

```python
class IfNodeInput(NodeInput):
    condition_value: Any  # Value to evaluate
```

## Output Schema

```python
class IfNodeOutput(NodeOutput):
    route: Literal["true", "false"]  # Route taken
    condition_result: bool           # Boolean evaluation result
    evaluated_value: Any            # The value that was evaluated
```

## Configuration Options

### Constructor Parameters

- **`node_id`** (str, required): Unique identifier for the node
- **`expression`** (str, optional): Python expression to evaluate
  - Example: `"value > 10"`, `"value == 'active'"`, `"len(value) > 0"`
- **`condition_func`** (Callable, optional): Custom condition function
  - Function signature: `(value: Any) -> bool`
- **`comparison_op`** (str, optional): Comparison operator
  - Options: `"eq"`, `"ne"`, `"lt"`, `"le"`, `"gt"`, `"ge"`
- **`comparison_value`** (Any, optional): Value for comparison operation
- **`null_handling`** (str, optional): How to handle None values
  - `"false"` (default): Treat None as False
  - `"true"`: Treat None as True
  - `"error"`: Raise an error
- **`input_map`** (dict, optional): Map state keys to input fields
- **`output_map`** (dict, optional): Map output fields to state keys

## Condition Methods

You must specify exactly ONE of these condition methods:

### 1. Boolean Evaluation (Default)

Evaluates the value as a boolean:

```python
if_node = IfNode(
    node_id="check_flag",
    input_map={"condition_value": "enabled"}
)
```

### 2. Expression Evaluation

Evaluates a safe Python expression:

```python
# Numeric comparison
if_node = IfNode(
    node_id="check_score",
    expression="value >= 80",
    input_map={"condition_value": "score"}
)

# String operations
if_node = IfNode(
    node_id="check_status",
    expression="value in ['active', 'pending']",
    input_map={"condition_value": "status"}
)

# Complex logic
if_node = IfNode(
    node_id="check_range",
    expression="value > 10 and value < 100",
    input_map={"condition_value": "amount"}
)
```

**Available Built-in Functions:**

- `abs`, `bool`, `float`, `int`, `len`, `max`, `min`, `str`, `sum`
- `all`, `any`, `sorted`, `enumerate`, `zip`, `range`
- `round`, `divmod`, `pow`

### 3. Comparison Operations

Use predefined comparison operators:

```python
# Greater than
if_node = IfNode(
    node_id="check_min",
    comparison_op="gt",
    comparison_value=100,
    input_map={"condition_value": "price"}
)

# Equal to
if_node = IfNode(
    node_id="check_status",
    comparison_op="eq",
    comparison_value="completed",
    input_map={"condition_value": "status"}
)
```

**Available Operators:**

- `eq`: Equal to (==)
- `ne`: Not equal to (!=)
- `lt`: Less than (<)
- `le`: Less than or equal to (<=)
- `gt`: Greater than (>)
- `ge`: Greater than or equal to (>=)

### 4. Custom Function

Provide your own condition function:

```python
def is_business_hours(timestamp):
    hour = timestamp.hour
    return 9 <= hour < 17

if_node = IfNode(
    node_id="check_hours",
    condition_func=is_business_hours,
    input_map={"condition_value": "current_time"}
)

# Lambda functions also work
if_node = IfNode(
    node_id="check_even",
    condition_func=lambda x: x % 2 == 0,
    input_map={"condition_value": "number"}
)
```

## Use Cases

### 1. Validation Gate

```python
validation_gate = IfNode(
    node_id="validate_input",
    expression="len(value) > 0 and value is not None",
    input_map={"condition_value": "user_input"}
)
```

### 2. Threshold Check

```python
quality_check = IfNode(
    node_id="quality_gate",
    comparison_op="ge",
    comparison_value=0.8,
    input_map={"condition_value": "quality_score"}
)
```

### 3. Status Routing

```python
status_router = IfNode(
    node_id="check_completed",
    expression="value == 'completed'",
    input_map={"condition_value": "task_status"}
)
```

### 4. Feature Flag

```python
feature_flag = IfNode(
    node_id="check_feature_enabled",
    input_map={"condition_value": "feature_x_enabled"}
)
```

### 5. Translation Check

```python
needs_translation = IfNode(
    node_id="check_language",
    expression="value != 'en'",
    input_map={"condition_value": "content_language"}
)
```

## Null Handling

Configure how the node handles None/null values:

```python
# Treat None as False (default)
if_node = IfNode(
    node_id="check",
    expression="value > 0",
    null_handling="false"
)

# Treat None as True
if_node = IfNode(
    node_id="check",
    expression="value > 0",
    null_handling="true"
)

# Raise error on None
if_node = IfNode(
    node_id="check",
    expression="value > 0",
    null_handling="error"
)
```

## Integration with LangGraph

```python
from langgraph.graph import StateGraph
from wyrdflow.core.state import WorkflowState

graph = StateGraph(WorkflowState)

# Add if node
quality_gate = IfNode(
    node_id="quality_check",
    expression="value >= 0.8",
    input_map={"condition_value": "quality_score"},
    output_map={"route": "quality_route"}
)
graph.add_node("quality_check", quality_gate.as_langraph_node())

# Add conditional edges
graph.add_conditional_edges(
    "quality_check",
    lambda state: state.data.get("quality_route"),
    {
        "true": "approve_content",
        "false": "review_content"
    }
)
```

## Output Routing

The IfNode always outputs one of two routes:

- **`"true"`**: When condition evaluates to True
- **`"false"`**: When condition evaluates to False

Access the route in your workflow:

```python
result = await if_node.execute(input_data, context, state)
print(f"Route: {result.route}")  # "true" or "false"
print(f"Result: {result.condition_result}")  # True or False
print(f"Evaluated: {result.evaluated_value}")  # The value checked
```

## Error Handling

The node will raise errors for:

- **Multiple condition methods** specified
- **No condition method** specified
- **Invalid expressions** (syntax errors)
- **Null values** when `null_handling="error"`

```python
try:
    result = await if_node.execute(input_data, context, state)
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Evaluation error: {e}")
```

## Best Practices

1. **Choose the Right Method**:

   - Use boolean evaluation for simple flags
   - Use expressions for complex logic
   - Use comparison for simple numeric/string checks
   - Use custom functions for business logic

2. **Expression Safety**:

   - Expressions are evaluated safely with restricted built-ins
   - No access to dangerous functions like `eval`, `exec`, `__import__`
   - Test expressions with sample data first

3. **Null Handling**:

   - Set `null_handling="error"` for critical checks
   - Use `null_handling="false"` for optional checks
   - Document expected null behavior

4. **Clear Naming**:

   - Use descriptive node_ids like `"check_threshold"` not `"if1"`
   - Name reflects what's being checked

5. **Testing**:
   - Test both true and false paths
   - Test edge cases (null, empty, boundary values)
   - Verify routing works as expected

## Performance Considerations

- **Evaluation Time**: ~0.1ms per condition evaluation
- **Expression Compilation**: Compiled once during initialization
- **Memory**: Minimal overhead, expressions are lightweight

## Comparison with Other Nodes

| Node           | Use Case                | Output Routes               |
| -------------- | ----------------------- | --------------------------- |
| **IfNode**     | Simple binary logic     | 2 (true/false)              |
| **RouterNode** | Multi-condition routing | Multiple named routes       |
| **SwitchNode** | Value-based routing     | Multiple value-based routes |

## See Also

- [RouterNode](router_node.md) - For multiple conditions and routes
- [SwitchNode](switch_node.md) - For value-based routing
- [HumanApprovalNode](human_approval.md) - For human-in-the-loop decisions
