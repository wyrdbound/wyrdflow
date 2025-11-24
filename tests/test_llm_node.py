from unittest.mock import AsyncMock, MagicMock

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from pydantic import BaseModel
import pytest

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.llm import LLMNode, LLMNodeInput, LLMNodeOutput


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mock response"))
    # Setup for chain invocation
    # When chain is invoked: prompt | llm | parser
    # We need to mock the chain execution or the components
    return llm


class TestLLMNode:
    @pytest.mark.asyncio
    async def test_initialization(self):
        llm = MagicMock(spec=BaseChatModel)
        node = LLMNode(node_id="test_llm", llm=llm, prompt="Hello {name}")
        assert node.node_id == "test_llm"
        assert node.llm == llm
        assert node.prompt_template is not None

    @pytest.mark.asyncio
    async def test_execution_text(self):
        # Mock the chain directly since constructing it involves LangChain internals
        llm = MagicMock(spec=BaseChatModel)
        node = LLMNode(node_id="test_llm", llm=llm, prompt="Hello {name}")

        # Mock the chain's ainvoke method
        node._chain = MagicMock()
        node._chain.ainvoke = AsyncMock(return_value="Hello World")

        input_data = LLMNodeInput(prompt_variables={"name": "World"})
        result = await node.execute(input_data)

        assert isinstance(result, LLMNodeOutput)
        assert result.content == "Hello World"
        node._chain.ainvoke.assert_called_once_with({"name": "World"})

    @pytest.mark.asyncio
    async def test_execution_structured(self):
        class ResultModel(BaseModel):
            greeting: str

        llm = MagicMock(spec=BaseChatModel)
        # Mock with_structured_output if checked
        llm.with_structured_output = MagicMock()

        node = LLMNode(
            node_id="test_llm",
            llm=llm,
            prompt="Hello {name}",
            output_schema=ResultModel,
        )

        expected_model = ResultModel(greeting="Hello World")
        # Since we mock with_structured_output, the node expects a dict with "parsed" key
        # because it assumes include_raw=True was used
        expected_result = {
            "parsed": expected_model,
            "raw": AIMessage(content="raw response"),
            "parsing_error": None,
        }

        node._chain = MagicMock()
        node._chain.ainvoke = AsyncMock(return_value=expected_result)

        input_data = LLMNodeInput(prompt_variables={"name": "World"})
        result = await node.execute(input_data)

        assert result.content == expected_model
        assert isinstance(result.content, ResultModel)

    @pytest.mark.asyncio
    async def test_from_model_factory(self):
        class Output(BaseModel):
            summary: str

        llm = MagicMock(spec=BaseChatModel)
        node = LLMNode.from_model(
            output_model=Output,
            node_id="factory_node",
            llm=llm,
            prompt="Summarize {text}",
        )

        assert node.structured_output_schema == Output
        assert node.node_id == "factory_node"

    @pytest.mark.asyncio
    async def test_input_mapping_integration(self):
        """Test that BaseNode's input mapping works with LLMNode."""
        llm = MagicMock(spec=BaseChatModel)
        node = LLMNode(
            node_id="test_llm",
            llm=llm,
            prompt="Hello {name}",
            input_map={"name": "user.name"},
        )

        # Mock chain
        node._chain = MagicMock()
        node._chain.ainvoke = AsyncMock(return_value="Hello Alice")

        # Create LangGraph wrapper
        wrapper = node.as_langraph_node()

        # Execute with state
        state = {
            "user": {"name": "Alice"},
            "workflow_state": WorkflowState.create_new().model_dump(),
        }

        await wrapper(state)

        # Verify chain was called with mapped input
        # Note: BaseNode maps "user.name" -> "name" in the input dict passed to execute
        # LLMNode.execute takes that input dict.
        # If "name" is not in LLMNodeInput fields, it goes to model_extra (if allowed)
        # LLMNodeInput has ConfigDict(extra="allow")

        # The execute method merges prompt_variables and extra fields
        node._chain.ainvoke.assert_called_once()
        call_args = node._chain.ainvoke.call_args[0][0]
        assert call_args["name"] == "Alice"
