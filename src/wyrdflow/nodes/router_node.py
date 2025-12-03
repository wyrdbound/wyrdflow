"""Router node for multi-condition routing with named branches."""

from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class RouteCondition(BaseModel):
    """Definition of a single route condition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Name of the route")
    expression: Optional[str] = Field(
        default=None, description="Python expression to evaluate"
    )
    condition_func: Optional[Callable[[Any], bool]] = Field(
        default=None, description="Custom condition function"
    )


class RouterNodeInput(NodeInput):
    """Input for RouterNode."""

    model_config = ConfigDict(extra="allow")

    routing_value: Any = Field(description="Value to use for routing decisions")


class RouterNodeOutput(NodeOutput):
    """Output from RouterNode."""

    model_config = ConfigDict(extra="allow")

    route: str = Field(description="Name of the selected route")
    matched_conditions: list[str] = Field(
        default_factory=list,
        description="List of all conditions that matched (if match_all=True)",
    )
    evaluated_value: Any = Field(
        default=None, description="The value that was evaluated"
    )


class RouterNode(BaseNode[RouterNodeInput, RouterNodeOutput]):
    """Multi-condition router node for complex branching logic.

    Routes workflow execution to one of multiple named paths based on
    condition evaluation. Supports:
    - Multiple named routes with conditions
    - List-order evaluation (routes evaluated first-to-last)
    - First-match vs all-match modes
    - Default/fallback route for unmatched conditions
    - AND/OR logic between conditions

    Examples:
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
    """

    input_schema = RouterNodeInput
    output_schema = RouterNodeOutput

    def __init__(
        self,
        node_id: str,
        routes: list[RouteCondition],
        default_route: str = "default",
        match_mode: Literal["first", "all"] = "first",
        null_handling: Literal["default", "error"] = "default",
        **kwargs: Any,
    ):
        """Initialize the Router node.

        Args:
            node_id: Unique identifier for the node
            routes: List of route conditions to evaluate
            default_route: Route to take if no conditions match
            match_mode: How to handle multiple matches:
                - 'first': Return first matching route (by priority)
                - 'all': Return all matching routes
            null_handling: How to handle None/null values:
                - 'default': Use default route
                - 'error': Raise an error
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.routes = routes
        self.default_route = default_route
        self.match_mode = match_mode
        self.null_handling = null_handling

        # Validate routes have unique names
        route_names = [r.name for r in routes]
        if len(route_names) != len(set(route_names)):
            raise ValueError("Route names must be unique")

        # Validate each route has exactly one condition method
        for route in routes:
            methods_specified = sum(
                [
                    route.expression is not None,
                    route.condition_func is not None,
                ]
            )
            if methods_specified != 1:
                raise ValueError(
                    f"Route '{route.name}' must have exactly one condition "
                    "method: expression or condition_func"
                )

    async def execute(
        self,
        input_data: RouterNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> RouterNodeOutput:
        """Execute routing logic.

        Args:
            input_data: Input containing the value for routing
            context: Execution context
            state: Current workflow state

        Returns:
            Output with selected route and matched conditions
        """
        value = input_data.routing_value

        # Handle null/None values
        if value is None:
            if self.null_handling == "error":
                raise ValueError("Routing value is None/null")
            self._logger.info(
                f"Router {self.node_id}: null value, using default route "
                f"'{self.default_route}'"
            )
            return RouterNodeOutput(
                route=self.default_route,
                matched_conditions=[],
                evaluated_value=value,
            )

        # Evaluate all conditions and collect matches
        matched_routes = []

        for route in self.routes:
            try:
                if self._evaluate_route(route, value):
                    matched_routes.append(route.name)
                    if self.match_mode == "first":
                        break
            except Exception as e:
                self._logger.warning(
                    f"Error evaluating route '{route.name}': {e}, skipping"
                )
                continue

        # Determine final route
        if not matched_routes:
            final_route = self.default_route
            self._logger.info(
                f"Router {self.node_id}: no matches, using default route "
                f"'{final_route}'"
            )
        else:
            final_route = matched_routes[0]
            self._logger.info(
                f"Router {self.node_id}: matched routes {matched_routes}, "
                f"selected '{final_route}'"
            )

        return RouterNodeOutput(
            route=final_route,
            matched_conditions=matched_routes,
            evaluated_value=value,
        )

    def _evaluate_route(self, route: RouteCondition, value: Any) -> bool:
        """Evaluate a single route condition.

        Args:
            route: Route condition to evaluate
            value: Value to evaluate against

        Returns:
            Boolean result of condition evaluation
        """
        if route.expression:
            return self._evaluate_expression(route.expression, value)
        elif route.condition_func:
            return route.condition_func(value)
        return False

    def _evaluate_expression(self, expression: str, value: Any) -> bool:
        """Safely evaluate a Python expression.

        Args:
            expression: Expression to evaluate
            value: Value to use in expression evaluation

        Returns:
            Boolean result of expression evaluation
        """
        # Create safe evaluation environment
        safe_globals = {
            "__builtins__": {
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "float": float,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "str": str,
                "sum": sum,
            }
        }
        safe_locals = {"value": value}

        try:
            result = eval(expression, safe_globals, safe_locals)
            return bool(result)
        except Exception as e:
            self._logger.error(
                f"Expression evaluation failed: {expression}, error: {e}"
            )
            raise ValueError(
                f"Failed to evaluate expression '{expression}': {e}"
            ) from e

    def get_routes(self) -> list[str]:
        """Get list of all possible routes from this node.

        Returns:
            List of route names including default
        """
        route_names = [r.name for r in self.routes]
        if self.default_route not in route_names:
            route_names.append(self.default_route)
        return route_names
