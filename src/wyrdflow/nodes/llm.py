from typing import Any, Optional, Union

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field

from wyrdflow.core.base import BaseNode
from wyrdflow.core.schemas import NodeInput, NodeOutput


class LLMNodeInput(NodeInput):
    """Input for LLMNode."""

    model_config = ConfigDict(extra="allow")

    prompt_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables to inject into the prompt template",
    )
    system_prompt_override: Optional[str] = Field(
        default=None, description="Override the default system prompt"
    )


class LLMNodeOutput(NodeOutput):
    """Output from LLMNode."""

    model_config = ConfigDict(extra="allow")

    content: Any = Field(description="The generated content (text or structured data)")
    raw_response: Optional[Any] = Field(
        default=None, description="Raw response object from the LLM provider"
    )
    usage: dict[str, int] = Field(
        default_factory=dict, description="Token usage statistics"
    )
    model_name: str = Field(description="Name of the model used")


class LLMNode(BaseNode[LLMNodeInput, LLMNodeOutput]):
    """Node for interacting with LLMs using LangChain."""

    input_schema = LLMNodeInput
    output_schema = LLMNodeOutput

    def __init__(
        self,
        node_id: str,
        llm: BaseChatModel,
        prompt: Union[str, ChatPromptTemplate],
        output_schema: Optional[type[BaseModel]] = None,
        system_message: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize the LLM node.

        Args:
            node_id: Unique identifier for the node
            llm: LangChain ChatModel instance (e.g. ChatOpenAI)
            prompt: Prompt template string or ChatPromptTemplate object
            output_schema: Optional Pydantic model for structured output
            system_message: Optional default system message
            **kwargs: Additional arguments passed to BaseNode
        """
        super().__init__(node_id=node_id, **kwargs)
        self.llm = llm
        self.structured_output_schema = output_schema
        self.system_message = system_message

        # Initialize prompt template
        if isinstance(prompt, str):
            messages: list[Union[BaseMessage, tuple[str, str]]] = []
            if system_message:
                messages.append(("system", system_message))
            messages.append(("user", prompt))
            self.prompt_template = ChatPromptTemplate.from_messages(messages)
        else:
            self.prompt_template = prompt
            # If system message provided but not in template, prepend it
            if system_message:
                # This is a simplification; modifying compiled templates is tricky.
                # We assume if they pass a template, they handle the system message,
                # or we might need to wrap it.
                pass

        # Initialize chain
        self._chain = self._build_chain()

    def _build_chain(self) -> Runnable:  # type: ignore
        """Build the LangChain runnable."""
        chain = self.prompt_template | self.llm

        if self.structured_output_schema:
            # Use structured output if supported/configured
            if hasattr(self.llm, "with_structured_output"):
                # Modern LangChain method
                # Use include_raw=True to get metadata
                chain = self.prompt_template | self.llm.with_structured_output(  # type: ignore
                    self.structured_output_schema, include_raw=True
                )
            else:
                # Fallback to PydanticOutputParser
                parser = PydanticOutputParser(
                    pydantic_object=self.structured_output_schema
                )
                # We need to inject format instructions into the prompt if using parser
                # This is complex to do post-hoc.
                # For now, assume modern LLM or user handles format instructions in prompt.
                chain = chain | parser
        else:
            # Return the message directly so we can extract metadata
            # We will parse to string in execute
            pass

        return chain

    async def execute(
        self,
        input_data: LLMNodeInput,
        context: Any = None,  # noqa: ARG002
        state: Any = None,  # noqa: ARG002
    ) -> LLMNodeOutput:
        """Execute the LLM chain."""

        # Merge input variables
        # 1. Variables from input_map (mapped to top-level keys in input_data dict)
        # 2. Explicit prompt_variables dict

        # Since BaseNode validates input into LLMNodeInput, extra fields end up in model_extra
        # or we need to look at how BaseNode handles mapping.

        # If input_map mapped "user_name" -> "name", then input_data.prompt_variables might be empty
        # but input_data.name would exist if we allowed extra fields.
        # LLMNodeInput allows extra fields.

        variables = input_data.prompt_variables.copy()

        # Add any extra fields from input_data to variables
        if input_data.model_extra:
            variables.update(input_data.model_extra)

        # Handle system prompt override
        # Note: Modifying the chain at runtime is not ideal.
        # Better to use a placeholder in the prompt template if overrides are needed.
        # For now, we'll ignore override if not using placeholders.

        try:
            # Invoke chain
            result = await self._chain.ainvoke(variables)

            content = None
            raw_response = None
            usage = {}
            model_name = getattr(self.llm, "model_name", str(self.llm))

            if self.structured_output_schema:
                if hasattr(self.llm, "with_structured_output"):
                    # Result is dict with "parsed", "raw", "parsing_error"
                    content = result["parsed"]
                    raw_response = result["raw"]  # BaseMessage
                    if hasattr(raw_response, "response_metadata"):
                        meta = raw_response.response_metadata
                        if "token_usage" in meta:
                            usage = meta["token_usage"]
                        elif "usage" in meta:
                            usage = meta["usage"]
                        else:
                            # Try to find anything that looks like usage
                            # For Ollama: prompt_eval_count, eval_count
                            usage = {
                                k: v
                                for k, v in meta.items()
                                if isinstance(v, int)
                                and ("count" in k or "tokens" in k)
                            }
                            # If still empty, just take all int values?
                            if not usage:
                                usage = {
                                    k: v for k, v in meta.items() if isinstance(v, int)
                                }
                else:
                    # PydanticOutputParser result is the object directly
                    content = result
                    # Can't easily get raw response/usage here without callbacks
            # Result is BaseMessage (if we removed StrOutputParser)
            elif isinstance(result, BaseMessage):
                content = result.content
                raw_response = result
                if hasattr(result, "response_metadata"):
                    meta = result.response_metadata
                    if "token_usage" in meta:
                        usage = meta["token_usage"]
                    elif "usage" in meta:
                        usage = meta["usage"]
                    else:
                        usage = {
                            k: v
                            for k, v in meta.items()
                            if isinstance(v, int) and ("count" in k or "tokens" in k)
                        }
                        if not usage:
                            usage = {
                                k: v for k, v in meta.items() if isinstance(v, int)
                            }
            else:
                # Fallback for unexpected return types
                content = str(result)

            output = LLMNodeOutput(
                content=content,
                raw_response=raw_response,
                usage=usage,
                model_name=model_name,
                **{
                    k: v
                    for k, v in variables.items()
                    if k not in ["content", "usage", "model_name", "raw_response"]
                },
            )
            return output

        except Exception as e:
            # Let BaseNode handle retry/error logging
            raise e

    @classmethod
    def from_model(
        cls,
        output_model: type[BaseModel],
        node_id: str,
        llm: BaseChatModel,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs: Any,
    ) -> "LLMNode":
        """Create an LLMNode that outputs a specific Pydantic model.

        Args:
            output_model: The Pydantic model class to generate
            node_id: Node identifier
            llm: ChatModel instance
            prompt: User prompt template string
            system_message: Optional system message
            **kwargs: Passed to constructor
        """
        return cls(
            node_id=node_id,
            llm=llm,
            prompt=prompt,
            output_schema=output_model,
            system_message=system_message,
            **kwargs,
        )
