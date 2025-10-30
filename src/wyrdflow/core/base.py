"""Base node implementation for workflow orchestration."""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable
import logging
from typing import Any, Callable, Generic, Optional, TypeVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)

from .config import NodeConfig
from .schemas import NodeContext, NodeInput, NodeOutput
from .state import WorkflowState

# Type variables for input/output validation
InputType = TypeVar("InputType", bound=NodeInput)
OutputType = TypeVar("OutputType", bound=NodeOutput)

logger = logging.getLogger(__name__)


class NodeExecutionError(Exception):
    """Exception raised during node execution."""

    def __init__(
        self, message: str, node_id: str, original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.node_id = node_id
        self.original_exception = original_exception


class BaseNode(ABC, Generic[InputType, OutputType]):
    """Abstract base class for all workflow nodes.

    This class provides the core functionality for workflow nodes including:
    - Typed input/output validation using Pydantic models
    - Configurable retry logic with exponential backoff
    - Error handling and logging
    - Integration with LangGraph workflows
    - Thread-safe execution

    Subclasses must implement:
    - input_schema: Pydantic model class for input validation
    - output_schema: Pydantic model class for output validation
    - execute(): Core node logic

    Example:
        ```python
        class DataProcessorNode(BaseNode[ProcessorInput, ProcessorOutput]):
            input_schema = ProcessorInput
            output_schema = ProcessorOutput

            async def execute(
                self,
                input_data: ProcessorInput,
                context: NodeContext,
                state: WorkflowState
            ) -> ProcessorOutput:
                # Process the data
                result = await self.process_data(input_data.data)
                return ProcessorOutput(processed_data=result)
        ```
    """

    # Abstract class attributes - must be defined by subclasses
    input_schema: type[InputType]
    output_schema: type[OutputType]

    def __init__(
        self,
        node_id: str,
        config: Optional[NodeConfig] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize the base node.

        Args:
            node_id: Unique identifier for the node
            config: Node configuration including retry and timeout settings
            name: Human-readable name for the node
            description: Description of what the node does
        """
        self.node_id = node_id
        self.config = config or NodeConfig()
        self.name = name or node_id
        self.description = description or f"Node {node_id}"
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{node_id}")

    @abstractmethod
    async def execute(
        self, input_data: InputType, context: NodeContext, state: WorkflowState
    ) -> OutputType:
        """Execute the node's core logic.

        This method must be implemented by subclasses to define the specific
        behavior of the node. It receives validated input data and must return
        validated output data.

        Args:
            input_data: Validated input data conforming to input_schema
            context: Execution context with metadata and runtime information
            state: Current workflow state for reading/writing shared data

        Returns:
            Validated output data conforming to output_schema

        Raises:
            NodeExecutionError: If execution fails
        """
        pass

    def validate_input(self, raw_input: dict[str, Any]) -> InputType:
        """Validate raw input data against the input schema.

        Args:
            raw_input: Raw input data dictionary

        Returns:
            Validated input data instance

        Raises:
            ValidationError: If input validation fails
        """
        try:
            return self.input_schema(**raw_input)
        except Exception as e:
            self._logger.error(f"Input validation failed for node {self.node_id}: {e}")
            raise NodeExecutionError(
                f"Input validation failed: {e}", self.node_id, e
            ) from e

    def validate_output(self, raw_output: dict[str, Any]) -> OutputType:
        """Validate raw output data against the output schema.

        Args:
            raw_output: Raw output data dictionary

        Returns:
            Validated output data instance

        Raises:
            ValidationError: If output validation fails
        """
        try:
            return self.output_schema(**raw_output)
        except Exception as e:
            self._logger.error(f"Output validation failed for node {self.node_id}: {e}")
            raise NodeExecutionError(
                f"Output validation failed: {e}", self.node_id, e
            ) from e

    def _create_retry_decorator(self) -> Callable[..., Any]:
        """Create a retry decorator based on node configuration.

        Returns:
            Configured retry decorator
        """
        # Configure wait strategy based on exponential backoff settings
        if self.config.retry_exponential_base > 1.0:
            wait_strategy: Any = wait_exponential(
                multiplier=self.config.retry_delay,
                max=self.config.retry_max_delay,
                exp_base=self.config.retry_exponential_base,
            )
        else:
            wait_strategy = wait_fixed(self.config.retry_delay)

        # Configure retry decorator
        return retry(
            stop=stop_after_attempt(self.config.retry_attempts),
            wait=wait_strategy,
            retry=retry_if_exception_type(Exception),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )

    def _log_retry_attempt(self, retry_state: Any) -> None:
        """Log retry attempts for debugging.

        Args:
            retry_state: Tenacity retry state object
        """
        self._logger.warning(
            f"Node {self.node_id} retry attempt {retry_state.attempt_number} "
            f"after {retry_state.seconds_since_start:.2f}s due to: {retry_state.outcome.exception()}"
        )

    async def run(
        self,
        raw_input: dict[str, Any],
        context: Optional[NodeContext] = None,
        state: Optional[WorkflowState] = None,
    ) -> dict[str, Any]:
        """Run the node with full validation and error handling.

        This is the main entry point for node execution. It handles:
        - Input validation
        - Retry logic
        - Timeout enforcement
        - Output validation
        - Error handling and logging

        Args:
            raw_input: Raw input data dictionary
            context: Optional execution context
            state: Optional workflow state

        Returns:
            Validated output data as dictionary

        Raises:
            NodeExecutionError: If execution fails after all retries
        """
        # Set up default context and state if not provided
        if context is None:
            # Create default context using state's workflow IDs
            if state is None:
                state = WorkflowState.create_new()
            context = NodeContext(
                workflow_id=state.workflow_id,
                workflow_run_id=state.workflow_run_id,
                node_id=self.node_id,
            )
        elif state is None:
            state = WorkflowState.create_new()

        # Create a copy of state for this node
        node_state = state.copy_for_node(self.node_id)

        self._logger.info(f"Starting execution of node {self.node_id}")

        try:
            # Check if output is pinned for testing
            if self.config.is_output_pinned():
                self._logger.info(f"Using pinned output for node {self.node_id}")
                pinned_output = self.config.pinned_output

                if pinned_output is None:
                    raise NodeExecutionError(
                        f"Node {self.node_id} has output pinning enabled but no pinned output data",
                        self.node_id,
                    )

                # Convert pinned output to dictionary format
                if hasattr(pinned_output, "model_dump"):
                    # It's a Pydantic model
                    output_dict: dict[str, Any] = pinned_output.model_dump()
                elif isinstance(pinned_output, dict):
                    # It's already a dictionary - validate it through our output schema
                    validated_output = self.validate_output(pinned_output)
                    output_dict = validated_output.model_dump()
                else:
                    # Try to create a dict and validate it
                    try:
                        raw_dict = (
                            {"result": pinned_output}
                            if not isinstance(pinned_output, dict)
                            else pinned_output
                        )
                        validated_output = self.validate_output(raw_dict)
                        output_dict = validated_output.model_dump()
                    except Exception as e:
                        raise NodeExecutionError(
                            f"Node {self.node_id} pinned output could not be validated: {e}",
                            self.node_id,
                            e,
                        ) from e

                return output_dict

            # Validate input
            validated_input = self.validate_input(raw_input)

            # Create retry decorator
            retry_decorator = self._create_retry_decorator()

            # Create the executable function with timeout
            async def _execute_with_timeout() -> OutputType:
                if self.config.timeout > 0:
                    return await asyncio.wait_for(
                        self.execute(validated_input, context, node_state),
                        timeout=self.config.timeout,
                    )
                else:
                    return await self.execute(validated_input, context, node_state)

            # Apply retry decorator and execute
            retryable_execute = retry_decorator(_execute_with_timeout)
            output = await retryable_execute()

            # Convert Pydantic model to dictionary for serialization
            if hasattr(output, "model_dump"):
                result_dict: dict[str, Any] = output.model_dump()
            else:
                result_dict = dict(output) if hasattr(output, "__dict__") else {}

            # Update the original state with changes from node execution
            if state is not None:
                # Copy data and metadata changes back to original state
                state.update(node_state.data)
                for key, value in node_state.metadata.items():
                    state.set_metadata(key, value)

            self._logger.info(
                f"Successfully completed execution of node {self.node_id}"
            )
            return result_dict

        except asyncio.TimeoutError as e:
            error_msg = (
                f"Node {self.node_id} execution timed out after {self.config.timeout}s"
            )
            self._logger.error(error_msg)
            raise NodeExecutionError(error_msg, self.node_id, e) from e

        except RetryError as e:
            error_msg = f"Node {self.node_id} failed after {self.config.retry_attempts} attempts"
            self._logger.error(error_msg)
            # Handle potential None from last_attempt.exception()
            last_exception = e.last_attempt.exception()
            if isinstance(last_exception, Exception):
                raise NodeExecutionError(error_msg, self.node_id, last_exception) from e
            else:
                raise NodeExecutionError(error_msg, self.node_id, None) from e

        except Exception as e:
            error_msg = f"Node {self.node_id} execution failed: {e}"
            self._logger.error(error_msg)
            raise NodeExecutionError(error_msg, self.node_id, e) from e

    def as_langraph_node(self) -> Callable[..., Awaitable[dict[str, Any]]]:
        """Convert this node to a LangGraph-compatible function.

        This method creates a wrapper function that can be used directly
        in LangGraph workflows while maintaining all the validation and
        error handling capabilities of the BaseNode.

        Returns:
            Async function compatible with LangGraph

        Example:
            ```python
            from langgraph.graph import Graph

            node = DataProcessorNode("processor")
            graph = Graph()
            graph.add_node("processor", node.as_langraph_node())
            ```
        """

        async def langraph_wrapper(state_dict: dict[str, Any]) -> dict[str, Any]:
            """LangGraph-compatible wrapper function."""
            # Extract node input from the state dictionary
            # For the first node, check if there's an explicit "input" key
            # Otherwise, use the entire state (excluding internal metadata)
            if "input" in state_dict and "last_node" not in state_dict:
                # First node in the workflow - use explicit input
                node_input = state_dict["input"]
            else:
                # Subsequent nodes - use the entire state as input
                node_input = state_dict.copy()
                # Remove internal LangGraph metadata that shouldn't be passed to the node
                internal_keys = {"workflow_state", "context", "last_node", "input"}
                for key in internal_keys:
                    node_input.pop(key, None)  # Extract context and workflow state
            context_data = state_dict.get("context", {})
            workflow_state_data = state_dict.get("workflow_state", {})

            # Create state object first to get required IDs
            if workflow_state_data:
                workflow_state = WorkflowState(**workflow_state_data)
            else:
                workflow_state = WorkflowState.create_new()

            # Create context with required workflow IDs
            context = NodeContext(
                workflow_id=workflow_state.workflow_id,
                workflow_run_id=workflow_state.workflow_run_id,
                node_id=self.node_id,
                execution_metadata=context_data,
            )

            # Execute the node
            result = await self.run(node_input, context, workflow_state)

            # Update the state with the result data
            new_state = state_dict.copy()
            new_state.update(result)  # Merge result into state
            new_state["workflow_state"] = workflow_state.model_dump()
            new_state["last_node"] = self.node_id

            return new_state

        return langraph_wrapper

    def __repr__(self) -> str:
        """String representation of the node."""
        return f"{self.__class__.__name__}(id='{self.node_id}', name='{self.name}')"
