"""If/Else conditional node for simple binary branching."""

from typing import Any, Callable, Literal, Optional

from pydantic import ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class IfNodeInput(NodeInput):
    """Input for IfNode."""

    model_config = ConfigDict(extra="allow")

    condition_value: Any = Field(description="Value to evaluate for the condition")


class IfNodeOutput(NodeOutput):
    """Output from IfNode."""

    model_config = ConfigDict(extra="allow")

    route: Literal["true", "false"] = Field(
        description="Route taken based on condition evaluation"
    )
    condition_result: bool = Field(description="Boolean result of condition evaluation")
    evaluated_value: Any = Field(
        default=None, description="The value that was evaluated"
    )


class IfNode(BaseNode[IfNodeInput, IfNodeOutput]):
    """Conditional node for simple if/else branching.

    Evaluates a condition and routes workflow execution to one of two paths:
    - 'true' branch if condition evaluates to True
    - 'false' branch if condition evaluates to False

    The node supports multiple ways to define conditions:
    1. Direct boolean value evaluation
    2. Python expression evaluation (safe)
    3. Custom condition function
    4. Comparison operations

    Examples:
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
    """

    input_schema = IfNodeInput
    output_schema = IfNodeOutput

    def __init__(
        self,
        node_id: str,
        expression: Optional[str] = None,
        condition_func: Optional[Callable[[Any], bool]] = None,
        comparison_op: Optional[Literal["eq", "ne", "lt", "le", "gt", "ge"]] = None,
        comparison_value: Optional[Any] = None,
        null_handling: Literal["false", "true", "error"] = "false",
        **kwargs: Any,
    ):
        """Initialize the If node.

        Args:
            node_id: Unique identifier for the node
            expression: Python expression to evaluate (e.g., "value > 10")
            condition_func: Custom function that takes a value and returns bool
            comparison_op: Comparison operator (eq, ne, lt, le, gt, ge)
            comparison_value: Value to compare against when using comparison_op
            null_handling: How to handle None/null values:
                - 'false': Treat as False (default)
                - 'true': Treat as True
                - 'error': Raise an error
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.expression = expression
        self.condition_func = condition_func
        self.comparison_op = comparison_op
        self.comparison_value = comparison_value
        self.null_handling = null_handling

        # Validate that exactly one condition method is specified
        methods_specified = sum(
            [
                expression is not None,
                condition_func is not None,
                comparison_op is not None,
            ]
        )

        if methods_specified > 1:
            raise ValueError(
                "Only one condition method can be specified: "
                "expression, condition_func, or comparison_op"
            )

    async def execute(
        self,
        input_data: IfNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> IfNodeOutput:
        """Execute the if/else condition evaluation.

        Args:
            input_data: Input containing the value to evaluate
            context: Execution context
            state: Current workflow state

        Returns:
            Output with route decision and evaluation result
        """
        value = input_data.condition_value

        # Handle null/None values
        if value is None:
            if self.null_handling == "error":
                raise ValueError("Condition value is None/null")
            result = self.null_handling == "true"
        # Evaluate based on configured method
        elif self.expression:
            result = self._evaluate_expression(value)
        elif self.condition_func:
            result = self.condition_func(value)
        elif self.comparison_op:
            result = self._evaluate_comparison(value)
        else:
            # Default: treat as boolean
            result = bool(value)

        route = "true" if result else "false"

        self._logger.info(
            f"If node {self.node_id} evaluated to {result}, routing to '{route}'"
        )

        return IfNodeOutput(
            route=route,  # type: ignore[arg-type]
            condition_result=result,
            evaluated_value=value,
        )

    def _evaluate_expression(self, value: Any) -> bool:
        """Safely evaluate a Python expression.

        Args:
            value: Value to use in expression evaluation

        Returns:
            Boolean result of expression evaluation
        """
        if not self.expression:
            return bool(value)

        # Create safe evaluation environment
        safe_globals = {
            "__builtins__": {
                "abs": abs,
                "bool": bool,
                "float": float,
                "int": int,
                "len": len,
                "max": max,
                "min": min,
                "str": str,
                "sum": sum,
            }
        }
        safe_locals = {"value": value}

        try:
            result = eval(self.expression, safe_globals, safe_locals)
            return bool(result)
        except Exception as e:
            self._logger.error(
                f"Expression evaluation failed: {self.expression}, error: {e}"
            )
            raise ValueError(
                f"Failed to evaluate expression '{self.expression}': {e}"
            ) from e

    def _evaluate_comparison(self, value: Any) -> bool:
        """Evaluate a comparison operation.

        Args:
            value: Value to compare

        Returns:
            Boolean result of comparison
        """
        if self.comparison_op is None or self.comparison_value is None:
            return bool(value)

        ops = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "lt": lambda a, b: a < b,
            "le": lambda a, b: a <= b,
            "gt": lambda a, b: a > b,
            "ge": lambda a, b: a >= b,
        }

        try:
            op_func = ops[self.comparison_op]
            # Type ignore for lambda function call
            return bool(op_func(value, self.comparison_value))  # type: ignore[no-untyped-call]
        except Exception as e:
            self._logger.error(
                f"Comparison failed: {value} {self.comparison_op} "
                f"{self.comparison_value}, error: {e}"
            )
            raise ValueError(
                f"Comparison failed: {value} {self.comparison_op} "
                f"{self.comparison_value}"
            ) from e

    def get_routes(self) -> list[str]:
        """Get list of possible routes from this node.

        Returns:
            List of route names
        """
        return ["true", "false"]
