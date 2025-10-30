"""Tests for BaseNode class and related functionality."""

import asyncio
from uuid import uuid4

from pydantic import Field
import pytest

from wyrdflow.core import (
    BaseNode,
    NodeConfig,
    NodeContext,
    NodeExecutionError,
    NodeInput,
    NodeOutput,
    WorkflowState,
)


# Test schema classes (prefixed with Mock to avoid pytest collection)
class MockTestInput(NodeInput):
    """Test input schema."""

    value: int = Field(description="Test integer value")
    name: str = Field(description="Test string name")


class MockTestOutput(NodeOutput):
    """Test output schema."""

    result: int = Field(description="Processed result")
    message: str = Field(description="Status message")


class MockBadInput(NodeInput):
    """Test input schema that will cause validation errors."""

    required_field: str = Field(description="Required field")


# Test node implementations
class MockTestNode(BaseNode[MockTestInput, MockTestOutput]):
    """Simple test node implementation."""

    input_schema = MockTestInput
    output_schema = MockTestOutput

    async def execute(
        self,
        input_data: MockTestInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> MockTestOutput:
        """Simple test execution."""
        result = input_data.value * 2
        message = f"Processed {input_data.name}"

        # Store some data in state
        state.set("last_processed", input_data.name)

        return MockTestOutput(result=result, message=message)


class MockFailingNode(BaseNode[MockTestInput, MockTestOutput]):
    """Node that always fails for testing error handling."""

    input_schema = MockTestInput
    output_schema = MockTestOutput

    async def execute(
        self,
        input_data: MockTestInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> MockTestOutput:
        """Always raises an exception."""
        raise ValueError(f"Test failure for {input_data.name}")


class MockSlowNode(BaseNode[MockTestInput, MockTestOutput]):
    """Node that takes time to execute for timeout testing."""

    input_schema = MockTestInput
    output_schema = MockTestOutput

    async def execute(
        self,
        input_data: MockTestInput,
        context: NodeContext,
        state: WorkflowState,
    ) -> MockTestOutput:
        """Sleeps for longer than timeout."""
        await asyncio.sleep(0.3)  # Sleep for 300ms
        return MockTestOutput(result=input_data.value, message="Slow result")


class TestBaseNode:
    """Test suite for BaseNode class."""

    def test_node_initialization(self):
        """Test basic node initialization."""
        config = NodeConfig(retry_attempts=2, timeout=30.0)
        node = MockTestNode(
            node_id="test_node",
            config=config,
            name="Test Node",
            description="A test node",
        )

        assert node.node_id == "test_node"
        assert node.config == config
        assert node.name == "Test Node"
        assert node.description == "A test node"
        assert node.input_schema == MockTestInput
        assert node.output_schema == MockTestOutput

    def test_node_initialization_defaults(self):
        """Test node initialization with defaults."""
        node = MockTestNode(node_id="test_node")

        assert node.node_id == "test_node"
        assert node.name == "test_node"
        assert node.description == "Node test_node"
        assert isinstance(node.config, NodeConfig)

    def test_validate_input_success(self):
        """Test successful input validation."""
        node = MockTestNode(node_id="test")
        raw_input = {"value": 42, "name": "test_data"}

        validated = node.validate_input(raw_input)

        assert isinstance(validated, MockTestInput)
        assert validated.value == 42
        assert validated.name == "test_data"

    def test_validate_input_failure(self):
        """Test input validation failure."""
        node = MockTestNode(node_id="test")
        raw_input = {"value": "not_an_int", "name": "test"}

        with pytest.raises(NodeExecutionError) as exc_info:
            node.validate_input(raw_input)

        assert "Input validation failed" in str(exc_info.value)
        assert exc_info.value.node_id == "test"

    def test_validate_output_success(self):
        """Test successful output validation."""
        node = MockTestNode(node_id="test")
        raw_output = {"result": 84, "message": "Success"}

        validated = node.validate_output(raw_output)

        assert isinstance(validated, MockTestOutput)
        assert validated.result == 84
        assert validated.message == "Success"

    def test_validate_output_failure(self):
        """Test output validation failure."""
        node = MockTestNode(node_id="test")
        raw_output = {"result": "not_an_int", "message": "Bad"}

        with pytest.raises(NodeExecutionError) as exc_info:
            node.validate_output(raw_output)

        assert "Output validation failed" in str(exc_info.value)
        assert exc_info.value.node_id == "test"

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful node execution."""
        node = MockTestNode(node_id="test_node")
        raw_input = {"value": 21, "name": "test_execution"}

        result = await node.run(raw_input)

        assert result["result"] == 42  # 21 * 2
        assert result["message"] == "Processed test_execution"

    @pytest.mark.asyncio
    async def test_execution_with_context_and_state(self):
        """Test node execution with custom context and state."""
        workflow_state = WorkflowState.create_new()
        context = NodeContext(
            workflow_id=workflow_state.workflow_id,
            workflow_run_id=workflow_state.workflow_run_id,
            node_id="test_node",
        )

        node = MockTestNode(node_id="test_node")
        raw_input = {"value": 10, "name": "test_with_context"}

        result = await node.run(raw_input, context=context, state=workflow_state)

        assert result["result"] == 20
        assert workflow_state.get("last_processed") == "test_with_context"

    @pytest.mark.asyncio
    async def test_execution_failure(self):
        """Test node execution failure handling."""
        node = MockFailingNode(node_id="failing_node")
        raw_input = {"value": 10, "name": "failure_test"}

        with pytest.raises(NodeExecutionError) as exc_info:
            await node.run(raw_input)

        assert "execution failed" in str(exc_info.value)
        assert exc_info.value.node_id == "failing_node"
        assert isinstance(exc_info.value.original_exception, ValueError)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling during execution."""
        config = NodeConfig(timeout=0.1)  # 100ms timeout
        node = MockSlowNode(node_id="slow_node", config=config)
        raw_input = {"value": 10, "name": "timeout_test"}

        with pytest.raises(NodeExecutionError) as exc_info:
            await node.run(raw_input)

        assert "timed out" in str(exc_info.value)
        assert exc_info.value.node_id == "slow_node"

    @pytest.mark.asyncio
    async def test_no_timeout_execution(self):
        """Test execution with very long timeout (effectively no timeout)."""
        config = NodeConfig(timeout=999.0)  # Very long timeout
        node = MockTestNode(node_id="no_timeout_node", config=config)
        raw_input = {"value": 25, "name": "no_timeout_test"}

        result = await node.run(raw_input)

        assert result["result"] == 50  # 25 * 2
        assert result["message"] == "Processed no_timeout_test"

    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test retry mechanism with failing then succeeding node."""
        # Create a mock node that fails twice then succeeds
        call_count = 0

        class RetryMockTestNode(BaseNode[MockTestInput, MockTestOutput]):
            input_schema = MockTestInput
            output_schema = MockTestOutput

            async def execute(
                self,
                input_data: MockTestInput,
                context: NodeContext,
                state: WorkflowState,
            ) -> MockTestOutput:
                nonlocal call_count
                call_count += 1

                if call_count < 3:  # Fail first 2 attempts
                    raise ValueError(f"Attempt {call_count} failed")

                return MockTestOutput(
                    result=input_data.value, message=f"Success on attempt {call_count}"
                )

        config = NodeConfig(retry_attempts=3, retry_delay=0.1)
        node = RetryMockTestNode(node_id="retry_node", config=config)
        raw_input = {"value": 42, "name": "retry_test"}

        result = await node.run(raw_input)

        assert result["result"] == 42
        assert "Success on attempt 3" in result["message"]
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test behavior when all retry attempts are exhausted."""
        config = NodeConfig(retry_attempts=2, retry_delay=0.1)
        node = MockFailingNode(node_id="exhausted_node", config=config)
        raw_input = {"value": 10, "name": "exhaustion_test"}

        with pytest.raises(NodeExecutionError) as exc_info:
            await node.run(raw_input)

        # The node should fail and show it made retry attempts
        error_msg = str(exc_info.value)
        assert "execution failed" in error_msg
        assert exc_info.value.node_id == "exhausted_node"

    def test_create_retry_decorator_fixed_delay(self):
        """Test retry decorator creation with fixed delay."""
        config = NodeConfig(
            retry_attempts=3,
            retry_delay=0.01,  # 10ms delay
            retry_exponential_base=1.0,  # Fixed delay
        )
        node = MockTestNode(node_id="test", config=config)

        decorator = node._create_retry_decorator()

        # Should be a function (decorator)
        assert callable(decorator)

    def test_create_retry_decorator_exponential_backoff(self):
        """Test retry decorator creation with exponential backoff."""
        config = NodeConfig(
            retry_attempts=3,
            retry_delay=0.01,  # 10ms initial delay
            retry_exponential_base=2.0,
            retry_max_delay=0.1,  # 100ms max delay
        )
        node = MockTestNode(node_id="test", config=config)

        decorator = node._create_retry_decorator()

        # Should be a function (decorator)
        assert callable(decorator)

    @pytest.mark.asyncio
    async def test_as_langraph_node(self):
        """Test conversion to LangGraph-compatible function."""
        node = MockTestNode(node_id="langraph_test")
        langraph_func = node.as_langraph_node()

        # Prepare LangGraph-style state
        state_dict = {
            "input": {"value": 15, "name": "langraph_test"},
            "context": {},
            "workflow_state": {},
        }

        result = await langraph_func(state_dict)

        # The result is merged directly into the state
        assert "result" in result
        assert "message" in result
        assert "workflow_state" in result
        assert "last_node" in result
        assert result["result"] == 30  # 15 * 2
        assert result["message"] == "Processed langraph_test"
        assert result["last_node"] == "langraph_test"

    @pytest.mark.asyncio
    async def test_as_langraph_node_with_existing_state(self):
        """Test LangGraph function with existing workflow state."""
        workflow_state = WorkflowState.create_new()
        workflow_state.set("existing_data", "test_value")

        node = MockTestNode(node_id="langraph_existing")
        langraph_func = node.as_langraph_node()

        state_dict = {
            "input": {"value": 5, "name": "existing_test"},
            "context": {"some_context": "value"},
            "workflow_state": workflow_state.model_dump(),
        }

        result = await langraph_func(state_dict)

        # Check that existing state was preserved and updated
        returned_state = WorkflowState(**result["workflow_state"])
        assert returned_state.get("existing_data") == "test_value"
        assert returned_state.get("last_processed") == "existing_test"

    def test_node_repr(self):
        """Test string representation of node."""
        node = MockTestNode(node_id="repr_test", name="Test Representation Node")

        repr_str = repr(node)

        assert "MockTestNode" in repr_str
        assert "repr_test" in repr_str
        assert "Test Representation Node" in repr_str

    @pytest.mark.asyncio
    async def test_state_isolation_between_runs(self):
        """Test that state is properly isolated between different runs."""
        node = MockTestNode(node_id="isolation_test")

        # First run
        state1 = WorkflowState.create_new()
        result1 = await node.run({"value": 10, "name": "first"}, state=state1)

        # Second run with different state
        state2 = WorkflowState.create_new()
        result2 = await node.run({"value": 20, "name": "second"}, state=state2)

        # States should be independent
        assert state1.get("last_processed") == "first"
        assert state2.get("last_processed") == "second"
        assert result1["result"] == 20
        assert result2["result"] == 40

    @pytest.mark.asyncio
    async def test_context_generation_without_state(self):
        """Test that context is properly generated when not provided."""
        node = MockTestNode(node_id="context_gen_test")
        raw_input = {"value": 5, "name": "context_test"}

        # Mock the execute method to capture the context
        original_execute = node.execute
        captured_context = None

        async def mock_execute(input_data, context, state):
            nonlocal captured_context
            captured_context = context
            return await original_execute(input_data, context, state)

        node.execute = mock_execute

        await node.run(raw_input)

        # Context should have been created with proper UUIDs
        assert captured_context is not None
        assert isinstance(captured_context.workflow_id, type(uuid4()))
        assert isinstance(captured_context.workflow_run_id, type(uuid4()))
        assert captured_context.node_id == "context_gen_test"


class TestNodeExecutionError:
    """Test suite for NodeExecutionError class."""

    def test_error_creation(self):
        """Test NodeExecutionError creation."""
        original_error = ValueError("Original error")
        error = NodeExecutionError("Test error message", "test_node", original_error)

        assert str(error) == "Test error message"
        assert error.node_id == "test_node"
        assert error.original_exception == original_error

    def test_error_without_original_exception(self):
        """Test NodeExecutionError without original exception."""
        error = NodeExecutionError("Test error message", "test_node")

        assert str(error) == "Test error message"
        assert error.node_id == "test_node"
        assert error.original_exception is None
