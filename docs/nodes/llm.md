# LLMNode

The `LLMNode` enables integration with Large Language Models (LLMs) using LangChain, supporting both text generation and structured output.

## Overview

This node provides a unified interface for interacting with various LLM providers through LangChain. It supports prompt templating, structured outputs via Pydantic models, and tracks token usage automatically.

## Features

- **LangChain Integration**: Works with any LangChain ChatModel
- **Prompt Templates**: Support for string templates and ChatPromptTemplate
- **Structured Output**: Optional Pydantic schema for structured responses
- **System Messages**: Configurable system prompts
- **Token Tracking**: Automatic usage statistics collection
- **Flexible Variables**: Dynamic prompt variable injection

## Basic Usage

### Simple Text Generation

```python
from wyrdflow.nodes import LLMNode
from langchain_openai import ChatOpenAI

# Create LLM node for text generation
llm_node = LLMNode(
    node_id="summarizer",
    llm=ChatOpenAI(model="gpt-4", temperature=0.7),
    prompt="Summarize the following text in 2-3 sentences:\n\n{text}",
    system_message="You are a helpful assistant that creates concise summaries.",
    input_map={"prompt_variables": "text_data"}
)

# Execute
result = await llm_node.execute(
    llm_node.input_schema(
        prompt_variables={"text": "Long article text here..."}
    ),
    context,
    state
)

print(result.content)  # The generated summary
print(result.usage)    # {'prompt_tokens': 150, 'completion_tokens': 45, ...}
```

### Structured Output

```python
from pydantic import BaseModel, Field
from wyrdflow.nodes import LLMNode
from langchain_openai import ChatOpenAI

# Define output structure
class ArticleMetadata(BaseModel):
    title: str = Field(description="Article title")
    summary: str = Field(description="Brief summary")
    tags: list[str] = Field(description="Relevant tags")
    sentiment: str = Field(description="Overall sentiment: positive, negative, or neutral")

# Create LLM node with structured output
llm_node = LLMNode(
    node_id="extract_metadata",
    llm=ChatOpenAI(model="gpt-4", temperature=0),
    prompt="Extract metadata from this article:\n\n{article_text}",
    output_schema=ArticleMetadata,
    input_map={"prompt_variables": "article"}
)

# Execute
result = await llm_node.execute(
    llm_node.input_schema(
        prompt_variables={"article_text": "Article content..."}
    ),
    context,
    state
)

# Access structured output
metadata: ArticleMetadata = result.content
print(f"Title: {metadata.title}")
print(f"Tags: {', '.join(metadata.tags)}")
print(f"Sentiment: {metadata.sentiment}")
```

## Input Schema

```python
class LLMNodeInput(NodeInput):
    prompt_variables: dict[str, Any]           # Variables for prompt template
    system_prompt_override: Optional[str]      # Override default system prompt
```

## Output Schema

```python
class LLMNodeOutput(NodeOutput):
    content: Any                    # Generated content (text or structured)
    raw_response: Optional[Any]     # Raw response from LLM provider
    usage: dict[str, int]          # Token usage statistics
    model_name: str                # Name of the model used
```

## Configuration Options

### Constructor Parameters

- **`node_id`** (str, required): Unique identifier for the node
- **`llm`** (BaseChatModel, required): LangChain ChatModel instance
  - Examples: `ChatOpenAI`, `ChatAnthropic`, `ChatOllama`
- **`prompt`** (str | ChatPromptTemplate, required): Prompt template
  - String with `{variable}` placeholders
  - Or ChatPromptTemplate for complex prompts
- **`output_schema`** (type[BaseModel], optional): Pydantic model for structured output
- **`system_message`** (str, optional): Default system message
- **`input_map`** (dict, optional): Map state keys to input fields
- **`output_map`** (dict, optional): Map output fields to state keys

## Use Cases

### 1. Content Generation

```python
content_writer = LLMNode(
    node_id="write_blog_post",
    llm=ChatOpenAI(model="gpt-4", temperature=0.8),
    prompt="""Write a blog post about {topic}.

    Target audience: {audience}
    Tone: {tone}
    Length: {word_count} words

    Include an engaging introduction and conclusion.""",
    system_message="You are an expert content writer.",
    input_map={"prompt_variables": "blog_parameters"}
)
```

### 2. Data Extraction

```python
from pydantic import BaseModel

class ExtractedData(BaseModel):
    names: list[str]
    dates: list[str]
    locations: list[str]
    organizations: list[str]

extractor = LLMNode(
    node_id="extract_entities",
    llm=ChatOpenAI(model="gpt-4", temperature=0),
    prompt="Extract all entities from this text:\n\n{text}",
    output_schema=ExtractedData,
    input_map={"prompt_variables": "document"}
)
```

### 3. Translation

```python
translator = LLMNode(
    node_id="translate_text",
    llm=ChatOpenAI(model="gpt-4", temperature=0.3),
    prompt="Translate the following text from {source_lang} to {target_lang}:\n\n{text}",
    system_message="You are a professional translator. Maintain the tone and style of the original text.",
    input_map={"prompt_variables": "translation_request"}
)
```

### 4. Sentiment Analysis

```python
class SentimentResult(BaseModel):
    sentiment: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(description="Confidence score 0-1")
    key_phrases: list[str] = Field(description="Key phrases supporting the sentiment")

sentiment_analyzer = LLMNode(
    node_id="analyze_sentiment",
    llm=ChatOpenAI(model="gpt-4", temperature=0),
    prompt="Analyze the sentiment of this text:\n\n{text}",
    output_schema=SentimentResult,
    input_map={"prompt_variables": "review_text"}
)
```

### 5. Question Answering

```python
qa_node = LLMNode(
    node_id="answer_question",
    llm=ChatOpenAI(model="gpt-4", temperature=0.5),
    prompt="""Context: {context}

    Question: {question}

    Provide a detailed answer based only on the given context.""",
    system_message="You are a helpful assistant that answers questions accurately based on provided context.",
    input_map={"prompt_variables": "qa_data"}
)
```

## Advanced Features

### Custom Chat Templates

```python
from langchain_core.prompts import ChatPromptTemplate

# Create complex multi-turn prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}."),
    ("human", "Here's the context: {context}"),
    ("ai", "I understand. I'll help you with that."),
    ("human", "{question}")
])

llm_node = LLMNode(
    node_id="custom_chat",
    llm=ChatOpenAI(model="gpt-4"),
    prompt=prompt
)
```

### System Prompt Override

```python
# Execute with overridden system prompt
result = await llm_node.execute(
    llm_node.input_schema(
        prompt_variables={"text": "..."},
        system_prompt_override="You are a creative storyteller."
    ),
    context,
    state
)
```

### Multiple LLM Providers

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

# OpenAI
openai_node = LLMNode(
    node_id="openai_node",
    llm=ChatOpenAI(model="gpt-4", temperature=0.7)
    prompt="..."
)

# Anthropic Claude
claude_node = LLMNode(
    node_id="claude_node",
    llm=ChatAnthropic(model="claude-3-opus-20240229"),
    prompt="..."
)

# Local Ollama
ollama_node = LLMNode(
    node_id="ollama_node",
    llm=ChatOllama(model="llama2"),
    prompt="..."
)
```

## Token Usage Tracking

Access token usage from the output:

```python
result = await llm_node.execute(input_data, context, state)

# Token usage statistics
print(f"Prompt tokens: {result.usage.get('prompt_tokens', 0)}")
print(f"Completion tokens: {result.usage.get('completion_tokens', 0)}")
print(f"Total tokens: {result.usage.get('total_tokens', 0)}")

# Model information
print(f"Model: {result.model_name}")
```

## Integration with LangGraph

```python
from langgraph.graph import StateGraph
from wyrdflow.core.state import WorkflowState

graph = StateGraph(WorkflowState)

# Add LLM node
summarizer = LLMNode(
    node_id="summarize",
    llm=ChatOpenAI(model="gpt-4"),
    prompt="Summarize: {text}",
    output_map={"content": "summary"}
)
graph.add_node("summarize", summarizer.as_langraph_node())

# Chain with other nodes
graph.add_edge("summarize", "next_step")
```

## Best Practices

1. **Temperature Settings**:

   - Use 0-0.3 for factual/structured tasks
   - Use 0.7-1.0 for creative tasks

2. **Prompt Engineering**:

   - Be specific and clear in instructions
   - Provide examples when possible
   - Use system messages to set context

3. **Structured Output**:

   - Use Pydantic schemas for predictable output format
   - Include field descriptions for better results
   - Validate output structure

4. **Error Handling**:

   - Handle API rate limits and timeouts
   - Validate LLM responses
   - Provide fallback behavior

5. **Cost Management**:
   - Monitor token usage
   - Choose appropriate models for tasks
   - Cache results when possible

## Performance Considerations

- **Latency**: LLM calls add 1-10 seconds depending on model and response length
- **Token Costs**: Varies by provider and model (track with `usage` field)
- **Rate Limits**: Consider provider rate limits for high-volume workflows
- **Streaming**: Not currently supported (future enhancement)

## Limitations

- No streaming support (responses are batch-only)
- Synchronous execution only
- Provider-specific features may require custom configuration

## See Also

- [IfNode](if_node.md) - For conditional routing based on LLM output
- [RouterNode](router_node.md) - For routing based on LLM decisions
- [HumanInputNode](human_input.md) - For fallback to human input when LLM fails
