"""Switch/Case node for value-based routing."""

import re
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeContext, NodeInput, NodeOutput
from wyrdflow.core.state import WorkflowState


class CaseCondition(BaseModel):
    """Definition of a single case in a switch statement."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    route: str = Field(description="Name of the route for this case")
    value: Optional[Any] = Field(default=None, description="Exact value to match")
    pattern: Optional[str] = Field(
        default=None, description="Regex pattern to match (for strings)"
    )
    value_list: Optional[list[Any]] = Field(
        default=None, description="List of values to match (any match)"
    )
    predicate: Optional[Callable[[Any], bool]] = Field(
        default=None, description="Custom predicate function"
    )


class SwitchNodeInput(NodeInput):
    """Input for SwitchNode."""

    model_config = ConfigDict(extra="allow")

    switch_value: Any = Field(description="Value to match against case conditions")


class SwitchNodeOutput(NodeOutput):
    """Output from SwitchNode."""

    model_config = ConfigDict(extra="allow")

    route: str = Field(description="Name of the selected route")
    matched_case: Optional[str] = Field(
        default=None, description="Name of the matched case route"
    )
    switch_value: Any = Field(
        default=None, description="The value that was switched on"
    )


class SwitchNode(BaseNode[SwitchNodeInput, SwitchNodeOutput]):
    r"""Switch/Case node for value-based routing.

    Routes workflow execution based on matching a value against defined cases.
    Similar to switch/case statements in programming languages.

    Supports multiple matching strategies:
    - Exact value matching
    - Pattern matching (regex for strings)
    - List of values (match any)
    - Custom predicate functions

    Examples:
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
                CaseCondition(
                    route="partner",
                    pattern=r".*@partner\.com$"
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
    """

    input_schema = SwitchNodeInput
    output_schema = SwitchNodeOutput

    def __init__(
        self,
        node_id: str,
        cases: list[CaseCondition],
        default_route: str = "default",
        case_sensitive: bool = True,
        null_handling: Literal["default", "error"] = "default",
        **kwargs: Any,
    ):
        """Initialize the Switch node.

        Args:
            node_id: Unique identifier for the node
            cases: List of case conditions to match against
            default_route: Route to take if no cases match
            case_sensitive: Whether string matching is case-sensitive
            null_handling: How to handle None/null values:
                - 'default': Use default route
                - 'error': Raise an error
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)

        self.cases = cases
        self.default_route = default_route
        self.case_sensitive = case_sensitive
        self.null_handling = null_handling
        self._compiled_patterns: dict[int, re.Pattern[str]] = {}

        # Validate cases
        for i, case in enumerate(cases):
            methods_specified = sum(
                [
                    case.value is not None,
                    case.pattern is not None,
                    case.value_list is not None,
                    case.predicate is not None,
                ]
            )
            if methods_specified != 1:
                raise ValueError(
                    f"Case {i} (route='{case.route}') must have exactly one "
                    "matching method: value, pattern, value_list, or predicate"
                )

            # Compile regex patterns
            if case.pattern:
                try:
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    self._compiled_patterns[i] = re.compile(case.pattern, flags)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex pattern in case '{case.route}': {e}"
                    ) from e

    async def execute(
        self,
        input_data: SwitchNodeInput,
        context: NodeContext,  # noqa: ARG002
        state: WorkflowState,  # noqa: ARG002
    ) -> SwitchNodeOutput:
        """Execute switch/case routing logic.

        Args:
            input_data: Input containing the value to switch on
            context: Execution context
            state: Current workflow state

        Returns:
            Output with selected route and match information
        """
        value = input_data.switch_value

        # Handle null/None values
        if value is None:
            if self.null_handling == "error":
                raise ValueError("Switch value is None/null")
            self._logger.info(
                f"Switch {self.node_id}: null value, using default route "
                f"'{self.default_route}'"
            )
            return SwitchNodeOutput(
                route=self.default_route,
                matched_case=None,
                switch_value=value,
            )

        # Try to match against each case
        for i, case in enumerate(self.cases):
            if self._matches_case(case, value, i):
                self._logger.info(
                    f"Switch {self.node_id}: matched case '{case.route}' "
                    f"for value {value}"
                )
                return SwitchNodeOutput(
                    route=case.route,
                    matched_case=case.route,
                    switch_value=value,
                )

        # No match found, use default
        self._logger.info(
            f"Switch {self.node_id}: no match for value {value}, "
            f"using default route '{self.default_route}'"
        )
        return SwitchNodeOutput(
            route=self.default_route,
            matched_case=None,
            switch_value=value,
        )

    def _matches_case(  # noqa: PLR0911
        self, case: CaseCondition, value: Any, case_index: int
    ) -> bool:
        """Check if a value matches a case condition.

        Args:
            case: Case condition to check
            value: Value to match against
            case_index: Index of the case in the cases list

        Returns:
            True if the value matches the case
        """
        try:
            # Exact value match
            if case.value is not None:
                return self._compare_values(value, case.value)

            # Pattern match (for strings)
            if case.pattern is not None:
                if not isinstance(value, str):
                    return False
                pattern = self._compiled_patterns.get(case_index)
                if pattern is None:
                    # Compile on the fly if needed
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    pattern = re.compile(case.pattern, flags)
                match_result = pattern.match(value)
                return match_result is not None

            # Value list match
            if case.value_list is not None:
                return any(self._compare_values(value, v) for v in case.value_list)

            # Predicate match
            if case.predicate is not None:
                return case.predicate(value)

            return False

        except Exception as e:
            self._logger.warning(
                f"Error matching case '{case.route}' against value {value}: {e}"
            )
            return False

    def _compare_values(self, value1: Any, value2: Any) -> bool:
        """Compare two values with optional case-insensitive string matching.

        Args:
            value1: First value
            value2: Second value

        Returns:
            True if values are equal
        """
        # Handle string comparison with case sensitivity option
        if isinstance(value1, str) and isinstance(value2, str):
            if self.case_sensitive:
                return value1 == value2
            else:
                return value1.lower() == value2.lower()

        # Standard equality for other types
        return bool(value1 == value2)

    def get_routes(self) -> list[str]:
        """Get list of all possible routes from this node.

        Returns:
            List of route names including default
        """
        route_names = [c.route for c in self.cases]
        if self.default_route not in route_names:
            route_names.append(self.default_route)
        return route_names
