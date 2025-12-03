# SwitchNode

The `SwitchNode` provides value-based routing similar to switch/case statements in programming languages, with support for exact matching, patterns, value lists, and custom predicates.

## Overview

This node routes workflow execution based on matching a value against defined cases. It's ideal for routing based on enums, status codes, types, or any categorizable value.

## Features

- **Exact Value Matching**: Direct equality checks
- **Pattern Matching**: Regex patterns for strings
- **Value Lists**: Match against multiple values
- **Custom Predicates**: Function-based matching
- **Case Sensitivity**: Configurable for string matching
- **Default Route**: Fallback for unmatched values
- **Pre-compiled Patterns**: Regex patterns compiled at initialization

## Basic Usage

```python
from wyrdflow.nodes import SwitchNode, CaseCondition

# Simple value matching
status_switch = SwitchNode(
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
email_switch = SwitchNode(
    node_id="email_router",
    cases=[
        CaseCondition(route="internal", pattern=r".*@company\.com$"),
        CaseCondition(route="customer", pattern=r".*@gmail\.com$"),
    ],
    default_route="external",
    input_map={"switch_value": "email_address"}
)
```

## Input Schema

```python
class SwitchNodeInput(NodeInput):
    switch_value: Any  # Value to match against cases
```

## Output Schema

```python
class SwitchNodeOutput(NodeOutput):
    route: str                    # Name of the selected route
    matched_case: Optional[str]   # Name of the matched case route
    switch_value: Any            # The value that was switched on
```

## Configuration Options

### Constructor Parameters

- **`node_id`** (str, required): Unique identifier for the node
- **`cases`** (list[CaseCondition], required): List of case conditions
- **`default_route`** (str, optional): Fallback route when no cases match
  - Default: `"default"`
- **`case_sensitive`** (bool, optional): Case-sensitive string matching
  - Default: `True`
- **`input_map`** (dict, optional): Map state keys to input fields
- **`output_map`** (dict, optional): Map output fields to state keys

### CaseCondition

Each case must have exactly one matching strategy:

```python
class CaseCondition(BaseModel):
    route: str                              # Route name
    value: Optional[Any]                    # Exact value to match
    pattern: Optional[str]                  # Regex pattern
    value_list: Optional[list[Any]]         # List of values
    predicate: Optional[Callable]           # Custom function
```

## Matching Strategies

### 1. Exact Value Matching

Match against a specific value:

```python
cases = [
    CaseCondition(route="admin", value="admin"),
    CaseCondition(route="user", value="user"),
    CaseCondition(route="guest", value="guest"),
]
```

### 2. Pattern Matching

Match strings using regex patterns:

```python
cases = [
    # Email domains
    CaseCondition(route="work_email", pattern=r".*@(company|org)\.com$"),
    CaseCondition(route="personal_email", pattern=r".*@(gmail|yahoo|hotmail)\.com$"),

    # Phone numbers
    CaseCondition(route="us_phone", pattern=r"^\+1\d{10}$"),
    CaseCondition(route="uk_phone", pattern=r"^\+44\d{10}$"),

    # File extensions
    CaseCondition(route="image", pattern=r".*\.(jpg|png|gif)$"),
    CaseCondition(route="document", pattern=r".*\.(pdf|doc|docx)$"),
]
```

### 3. Value List Matching

Match against any value in a list:

```python
cases = [
    CaseCondition(
        route="error_states",
        value_list=["error", "failed", "rejected", "cancelled"]
    ),
    CaseCondition(
        route="success_states",
        value_list=["completed", "approved", "confirmed"]
    ),
    CaseCondition(
        route="pending_states",
        value_list=["pending", "processing", "reviewing"]
    ),
]
```

### 4. Custom Predicate

Use custom functions for complex matching:

```python
def is_high_priority(value):
    return isinstance(value, dict) and value.get("priority", 0) > 7

def is_overdue(value):
    from datetime import datetime
    due_date = value.get("due_date")
    return due_date and datetime.fromisoformat(due_date) < datetime.now()

cases = [
    CaseCondition(route="urgent", predicate=is_high_priority),
    CaseCondition(route="overdue", predicate=is_overdue),
    CaseCondition(
        route="normal",
        predicate=lambda v: not is_high_priority(v) and not is_overdue(v)
    ),
]
```

## Use Cases

### 1. HTTP Status Code Routing

```python
http_switch = SwitchNode(
    node_id="http_status_router",
    cases=[
        CaseCondition(route="success", value_list=[200, 201, 204]),
        CaseCondition(route="redirect", value_list=[301, 302, 307, 308]),
        CaseCondition(route="client_error", predicate=lambda v: 400 <= v < 500),
        CaseCondition(route="server_error", predicate=lambda v: 500 <= v < 600),
    ],
    default_route="unknown_status",
    input_map={"switch_value": "response_status"}
)
```

### 2. File Type Processing

```python
file_processor = SwitchNode(
    node_id="file_type_router",
    case_sensitive=False,
    cases=[
        CaseCondition(route="image_pipeline", pattern=r".*\.(jpg|jpeg|png|gif|webp)$"),
        CaseCondition(route="video_pipeline", pattern=r".*\.(mp4|avi|mov|mkv)$"),
        CaseCondition(route="document_pipeline", pattern=r".*\.(pdf|doc|docx|txt)$"),
        CaseCondition(route="archive_pipeline", pattern=r".*\.(zip|tar|gz|rar)$"),
    ],
    default_route="unknown_file_type",
    input_map={"switch_value": "filename"}
)
```

### 3. User Role Routing

```python
role_router = SwitchNode(
    node_id="role_based_router",
    cases=[
        CaseCondition(route="admin_workflow", value="admin"),
        CaseCondition(route="moderator_workflow", value="moderator"),
        CaseCondition(route="premium_workflow", value_list=["premium", "pro", "enterprise"]),
        CaseCondition(route="basic_workflow", value="basic"),
    ],
    default_route="guest_workflow",
    input_map={"switch_value": "user_role"}
)
```

### 4. Geographic Routing

```python
def is_eu_country(country_code):
    eu_countries = {"DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL", "SE", "DK"}
    return country_code in eu_countries

geo_router = SwitchNode(
    node_id="geo_router",
    cases=[
        CaseCondition(route="us_pipeline", value="US"),
        CaseCondition(route="uk_pipeline", value="GB"),
        CaseCondition(route="eu_pipeline", predicate=is_eu_country),
        CaseCondition(
            route="asia_pipeline",
            value_list=["JP", "CN", "KR", "SG", "IN"]
        ),
    ],
    default_route="international_pipeline",
    input_map={"switch_value": "country_code"}
)
```

### 5. Content Type Routing

```python
content_switch = SwitchNode(
    node_id="content_type_router",
    cases=[
        CaseCondition(route="review_pipeline", value="review"),
        CaseCondition(route="question_pipeline", value="question"),
        CaseCondition(route="support_pipeline", value="support"),
        CaseCondition(route="feedback_pipeline", value="feedback"),
    ],
    default_route="general_pipeline",
    input_map={"switch_value": "content_type"}
)
```

## Case Sensitivity

Control case sensitivity for string matching:

```python
# Case-sensitive matching (default)
sensitive_switch = SwitchNode(
    node_id="router",
    case_sensitive=True,
    cases=[
        CaseCondition(route="route1", value="ACTIVE"),  # Won't match "active"
    ]
)

# Case-insensitive matching
insensitive_switch = SwitchNode(
    node_id="router",
    case_sensitive=False,
    cases=[
        CaseCondition(route="route1", value="ACTIVE"),  # Will match "active", "Active", "ACTIVE"
    ]
)
```

## Pattern Compilation

Regex patterns are compiled once during initialization for performance:

```python
# Patterns are compiled at node creation
switch = SwitchNode(
    node_id="email_router",
    cases=[
        CaseCondition(route="gmail", pattern=r".*@gmail\.com$"),
        # Pattern is compiled and cached
    ]
)

# No compilation overhead during execution
result = await switch.execute(input_data, context, state)  # Fast!
```

## Integration with LangGraph

```python
from langgraph.graph import StateGraph
from wyrdflow.core.state import WorkflowState

graph = StateGraph(WorkflowState)

# Add switch node
status_router = SwitchNode(
    node_id="route_by_status",
    cases=[
        CaseCondition(route="new", value="new"),
        CaseCondition(route="pending", value="pending"),
        CaseCondition(route="completed", value="completed"),
    ],
    default_route="unknown",
    input_map={"switch_value": "order_status"},
    output_map={"route": "status_route"}
)
graph.add_node("route_status", status_router.as_langraph_node())

# Add conditional edges
graph.add_conditional_edges(
    "route_status",
    lambda state: state.data.get("status_route"),
    {
        "new": "process_new_order",
        "pending": "check_order_status",
        "completed": "archive_order",
        "unknown": "investigate_status"
    }
)
```

## Getting Available Routes

```python
switch = SwitchNode(
    node_id="switch",
    cases=[
        CaseCondition(route="route1", value="a"),
        CaseCondition(route="route2", value="b"),
    ],
    default_route="other"
)

# Get all possible route names
all_routes = switch.get_routes()
# Returns: ["route1", "route2", "other"]
```

## Validation

The node validates:

- Each case has exactly one matching strategy
- Route names are unique
- Patterns are valid regex

```python
# This will raise ValueError
switch = SwitchNode(
    node_id="switch",
    cases=[
        CaseCondition(route="route1", value="a", pattern=r".*"),  # Two strategies!
    ]
)
```

## Best Practices

1. **Choose Right Strategy**:

   - Use `value` for exact matches (enums, status codes)
   - Use `pattern` for string patterns (emails, URLs, filenames)
   - Use `value_list` for multiple possible values
   - Use `predicate` for complex logic

2. **Order Matters**:

   - More specific cases first
   - Default route as fallback

3. **Pattern Design**:

   - Test regex patterns thoroughly
   - Use case-insensitive mode when appropriate
   - Escape special characters (`.` becomes `\.`)

4. **Performance**:

   - Patterns are compiled once (minimal overhead)
   - Exact value matching is fastest
   - Predicates add function call overhead

5. **Maintainability**:
   - Use descriptive route names
   - Document pattern meanings
   - Group related cases together

## Performance Considerations

- **Value Matching**: O(1) for exact values
- **Pattern Matching**: O(n) where n is pattern complexity
- **Value List**: O(m) where m is list length
- **Predicate**: Depends on function complexity
- **Pattern Compilation**: One-time cost at initialization

## Comparison with Other Nodes

| Node           | Use Case              | Evaluation Method                |
| -------------- | --------------------- | -------------------------------- |
| **IfNode**     | Binary logic          | Boolean conditions               |
| **RouterNode** | Multi-condition logic | Expression/function evaluation   |
| **SwitchNode** | Value-based routing   | Value/pattern/predicate matching |

## See Also

- [IfNode](if_node.md) - For binary conditional routing
- [RouterNode](router_node.md) - For expression-based multi-routing
- [HumanInputNode](human_input.md) - For collecting user input
