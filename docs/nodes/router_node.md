# RouterNode

The `RouterNode` enables multi-condition routing with named branches, allowing workflows to route execution based on multiple conditions evaluated in list order.

## Overview

This node evaluates multiple route conditions and selects the appropriate path. Unlike IfNode's binary logic, RouterNode supports any number of named routes and can match multiple conditions.

## Features

- **Named Routes**: Any number of custom route names
- **List-Order Evaluation**: Routes evaluated in the order they appear
- **Match Modes**: First-match or all-match
- **Expression Support**: Safe Python expressions
- **Custom Functions**: Lambda or named functions
- **Default Route**: Fallback for unmatched conditions
- **Graceful Errors**: Skips failing conditions instead of breaking

## Basic Usage

```python
from wyrdflow.nodes import RouterNode, RouteCondition

# Route based on score ranges
router = RouterNode(
    node_id="score_router",
    routes=[
        RouteCondition(name="excellent", expression="value >= 90"),
        RouteCondition(name="good", expression="value >= 70"),
        RouteCondition(name="fair", expression="value >= 50"),
    ],
    default_route="poor",
    input_map={"routing_value": "score"}
)

# Custom functions
def is_urgent(value):
    return value.get("priority") == "high"

router = RouterNode(
    node_id="priority_router",
    routes=[
        RouteCondition(name="urgent", condition_func=is_urgent),
        RouteCondition(name="normal", condition_func=lambda v: not is_urgent(v)),
    ],
    input_map={"routing_value": "task"}
)
```

## Input Schema

```python
class RouterNodeInput(NodeInput):
    routing_value: Any  # Value to use for routing decisions
```

## Output Schema

```python
class RouterNodeOutput(NodeOutput):
    route: str                     # Name of the selected route
    matched_conditions: list[str]  # All conditions that matched
    evaluated_value: Any          # The value that was evaluated
```

## Configuration Options

### Constructor Parameters

- **`node_id`** (str, required): Unique identifier for the node
- **`routes`** (list[RouteCondition], required): List of route conditions
- **`default_route`** (str, optional): Fallback route when no conditions match
  - Default: `"default"`
- **`match_mode`** (str, optional): How to match conditions
  - `"first"` (default): Return first matching route
  - `"all"`: Evaluate all routes, return first but record all matches
- **`null_handling`** (str, optional): How to handle None values
  - `"default"` (default): Use default route
  - `"error"`: Raise an error
- **`input_map`** (dict, optional): Map state keys to input fields
- **`output_map`** (dict, optional): Map output fields to state keys

### RouteCondition

Each route must have exactly one condition method:

```python
class RouteCondition(BaseModel):
    name: str                                    # Route name
    expression: Optional[str]                    # Python expression
    condition_func: Optional[Callable]           # Custom function
```

## Route Conditions

### Expression-Based Routes

```python
routes = [
    RouteCondition(
        name="high_value",
        expression="value > 1000"
    ),
    RouteCondition(
        name="medium_value",
        expression="value > 100 and value <= 1000"
    ),
    RouteCondition(
        name="low_value",
        expression="value <= 100"
    ),
]
```

### Function-Based Routes

```python
def is_vip(customer):
    return customer.get("tier") == "platinum"

def is_new_customer(customer):
    return customer.get("signup_days", 999) < 30

routes = [
    RouteCondition(name="vip", condition_func=is_vip),
    RouteCondition(name="new", condition_func=is_new_customer),
    RouteCondition(
        name="regular",
        condition_func=lambda c: not is_vip(c) and not is_new_customer(c)
    ),
]
```

### Complex Conditions

```python
routes = [
    # VIP with negative sentiment
    RouteCondition(
        name="vip_urgent",
        condition_func=lambda v: (
            v.get("user_tier") == "platinum"
            and v.get("sentiment_score", 0.5) < 0.3
        )
    ),
    # Any negative review
    RouteCondition(
        name="negative_review",
        expression="value.get('sentiment_score', 0.5) < 0.3 and value.get('type') == 'review'"
    ),
    # Support requests
    RouteCondition(
        name="support",
        expression="value.get('type') == 'support'"
    ),
]
```

## Use Cases

### 1. Priority-Based Routing

```python
priority_router = RouterNode(
    node_id="task_router",
    routes=[
        RouteCondition(
            name="critical",
            expression="value.get('priority') == 'critical' and value.get('age_hours', 0) < 24"
        ),
        RouteCondition(
            name="high",
            expression="value.get('priority') == 'high'"
        ),
        RouteCondition(
            name="normal",
            expression="value.get('priority') == 'normal'"
        ),
    ],
    default_route="low",
    input_map={"routing_value": "task_data"}
)
```

### 2. Content Moderation

```python
moderation_router = RouterNode(
    node_id="content_router",
    routes=[
        RouteCondition(
            name="auto_reject",
            expression="value.get('toxicity_score', 0) > 0.8"
        ),
        RouteCondition(
            name="human_review",
            expression="value.get('toxicity_score', 0) > 0.5"
        ),
        RouteCondition(
            name="auto_approve",
            expression="value.get('toxicity_score', 0) <= 0.5"
        ),
    ],
    input_map={"routing_value": "content_analysis"}
)
```

### 3. Customer Segmentation

```python
def is_enterprise(customer):
    return customer.get("employees", 0) > 500

def is_smb(customer):
    return 10 < customer.get("employees", 0) <= 500

segment_router = RouterNode(
    node_id="customer_segment",
    routes=[
        RouteCondition(name="enterprise", condition_func=is_enterprise),
        RouteCondition(name="smb", condition_func=is_smb),
        RouteCondition(name="solopreneur", condition_func=lambda c: c.get("employees", 0) <= 10),
    ],
    input_map={"routing_value": "customer_data"}
)
```

### 4. Error Handling

```python
error_router = RouterNode(
    node_id="error_handler",
    routes=[
        RouteCondition(
            name="retry",
            expression="value.get('error_type') == 'transient' and value.get('retry_count', 0) < 3"
        ),
        RouteCondition(
            name="fallback",
            expression="value.get('error_type') == 'transient' and value.get('retry_count', 0) >= 3"
        ),
        RouteCondition(
            name="alert",
            expression="value.get('error_type') == 'critical'"
        ),
    ],
    default_route="log_and_continue",
    input_map={"routing_value": "error_info"}
)
```

## Match Modes

### First Match Mode (Default)

Returns the first matching route:

```python
router = RouterNode(
    node_id="router",
    routes=[
        RouteCondition(name="route1", expression="value > 50"),
        RouteCondition(name="route2", expression="value > 30"),  # Won't match if route1 matches
    ],
    match_mode="first"
)
```

### All Match Mode

Evaluates all routes but returns the first, recording all matches:

```python
router = RouterNode(
    node_id="router",
    routes=[
        RouteCondition(name="route1", expression="value > 50"),
        RouteCondition(name="route2", expression="value > 30"),
        RouteCondition(name="route3", expression="value < 100"),
    ],
    match_mode="all"
)

result = await router.execute(input_data, context, state)
print(f"Selected route: {result.route}")  # First matching route
print(f"All matches: {result.matched_conditions}")  # All routes that matched
```

## List-Order Evaluation

Routes are evaluated in the order they appear in the routes list. Place more specific conditions before general ones:

```python
# Good: Specific first, general last
routes = [
    RouteCondition(name="vip_negative", expression="value.get('tier') == 'vip' and value.get('sentiment') < 0.3"),
    RouteCondition(name="vip", expression="value.get('tier') == 'vip'"),
    RouteCondition(name="negative", expression="value.get('sentiment') < 0.3"),
    RouteCondition(name="normal", expression="True"),  # Catch-all
]

# Bad: General first will block specific routes
routes = [
    RouteCondition(name="vip", expression="value.get('tier') == 'vip'"),  # Will match all VIPs
    RouteCondition(name="vip_negative", expression="value.get('tier') == 'vip' and value.get('sentiment') < 0.3"),  # Never reached
]
```

## Null Handling

Configure how the node handles None/null routing values:

```python
# Use default route for None (default behavior)
router = RouterNode(
    node_id="router",
    routes=[...],
    default_route="null_route",
    null_handling="default"
)

# Raise error on None
router = RouterNode(
    node_id="router",
    routes=[...],
    null_handling="error"
)
```

## Integration with LangGraph

```python
from langgraph.graph import StateGraph
from wyrdflow.core.state import WorkflowState

graph = StateGraph(WorkflowState)

# Add router node
sentiment_router = RouterNode(
    node_id="route_by_sentiment",
    routes=[
        RouteCondition(name="positive", expression="value > 0.7"),
        RouteCondition(name="negative", expression="value < 0.3"),
        RouteCondition(name="neutral", expression="True"),
    ],
    input_map={"routing_value": "sentiment_score"},
    output_map={"route": "sentiment_route"}
)
graph.add_node("route_sentiment", sentiment_router.as_langraph_node())

# Add conditional edges
graph.add_conditional_edges(
    "route_sentiment",
    lambda state: state.data.get("sentiment_route"),
    {
        "positive": "promote_content",
        "negative": "review_content",
        "neutral": "standard_processing"
    }
)
```

## Getting Available Routes

```python
router = RouterNode(
    node_id="router",
    routes=[
        RouteCondition(name="route1", expression="value > 0"),
        RouteCondition(name="route2", expression="value < 0"),
    ],
    default_route="zero"
)

# Get all possible route names
all_routes = router.get_routes()
# Returns: ["route1", "route2", "zero"]
```

## Error Handling

The router gracefully handles evaluation errors:

```python
routes = [
    # This might fail if value doesn't have the method
    RouteCondition(name="error_route", expression="value.nonexistent_method()"),
    # This will be tried if the first fails
    RouteCondition(name="safe_route", expression="value > 0"),
]

router = RouterNode(
    node_id="router",
    routes=routes,
    default_route="fallback"
)

# If error_route fails, router continues to safe_route
# If all routes fail, uses fallback
```

## Best Practices

1. **Order Matters**: Place specific conditions before general ones
2. **Mutually Exclusive**: Design routes to be mutually exclusive when using first-match
3. **Default Route**: Always provide a default route for unmatched cases
4. **Clear Names**: Use descriptive route names that indicate their purpose
5. **Test All Paths**: Ensure all routes are reachable and tested
6. **Error Handling**: Routes with errors are skipped, so have fallbacks

## Performance Considerations

- **Evaluation Time**: ~0.1ms × number of routes checked (with early exit in first-match mode)
- **Expression Compilation**: Expressions compiled once during initialization
- **Match Mode**: Use "first" for better performance with many routes

## Validation

The node validates:

- Route names are unique
- Each route has exactly one condition method (expression OR function)
- No duplicate route names

```python
# This will raise ValueError
router = RouterNode(
    node_id="router",
    routes=[
        RouteCondition(name="route1", expression="value > 0"),
        RouteCondition(name="route1", expression="value < 0"),  # Duplicate name!
    ]
)
```

## See Also

- [IfNode](if_node.md) - For simple binary routing
- [SwitchNode](switch_node.md) - For value-based routing
- [HumanApprovalNode](human_approval.md) - For human-in-the-loop routing decisions
