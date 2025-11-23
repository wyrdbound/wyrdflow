"""Example usage of HumanInputNode v2 API for novel plot generator.

This example demonstrates the improved API for Wyrdflow nodes:
1. Pydantic-based input definition (replacing verbose FieldConfig lists)
2. Declarative state mapping (eliminating prep/extract steps)
3. Simplified node instantiation
"""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from wyrdflow.core.state import WorkflowState

# In the future API, we would import these:
from wyrdflow.nodes.human_input import HumanInputNode


# Define LangGraph state schema
class NovelPlannerState(TypedDict, total=False):
    """State schema for LangGraph novel planner workflow."""

    # Domain data
    novel: dict[str, Any]

    # Workflow metadata
    workflow_state: dict[str, Any]


# 1. Define Input Schema using Pydantic
# This replaces the verbose create_novel_fields() function and FieldConfig objects
class NovelInput(BaseModel):
    """Input schema for the novel planner."""

    genre: str = Field(
        ...,
        json_schema_extra={
            "prompt": "What genre is your novel?",
            "examples": [
                "fantasy",
                "sci-fi",
                "mystery",
                "romance",
                "thriller",
                "literary",
            ],
        },
        description="The literary genre of the work",
    )

    plot_summary: str = Field(
        ...,
        json_schema_extra={"prompt": "Provide a brief plot summary (under 500 words)"},
        description="High-level story arc",
    )

    main_characters: list[str] = Field(
        default_factory=list,
        json_schema_extra={"prompt": "Describe your main characters (one per line)"},
    )

    target_word_count: int = Field(
        default=80000,
        ge=1000,
        le=200000,
        json_schema_extra={"prompt": "Target word count for the novel"},
    )

    include_romance: bool = Field(
        default=False, json_schema_extra={"prompt": "Include a romantic subplot?"}
    )

    target_audience: str = Field(
        default="Adult",
        json_schema_extra={"prompt": "Target audience (YA, Adult, etc.)"},
    )


async def run_novel_planner_v2() -> None:
    """Run the novel planner using the improved v2 API."""
    print("🚀 Starting Novel Plot Generator (v2 API)\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()

    # 2. Create Node with Declarative Mapping
    # No need for separate input configuration or complex setup
    input_node = HumanInputNode.from_model(
        model=NovelInput,
        node_id="collect_input",
        # Map node outputs directly to state paths
        output_map={
            "genre": "novel.genre",
            "plot_summary": "novel.plot.summary",
            "main_characters": "novel.characters.main",
            "target_word_count": "novel.requirements.word_count",
            "include_romance": "novel.plot.romance",
            "target_audience": "novel.requirements.audience",
        },
    )

    # Create LangGraph workflow
    print("🔧 Building LangGraph workflow...")
    graph = StateGraph(NovelPlannerState)

    # Add the node directly - no prep/extract needed!
    graph.add_node("collect_input", input_node.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "collect_input")
    graph.add_edge("collect_input", END)

    # Compile the graph
    workflow = graph.compile()

    # Prepare initial state
    initial_state: NovelPlannerState = {
        "novel": {},
        "workflow_state": workflow_state.model_dump(),
    }

    print("\n🎯 Executing workflow...")
    result = await workflow.ainvoke(initial_state)

    print("\n✅ Workflow completed!")
    print(f"Result: {result.get('novel')}")


if __name__ == "__main__":
    asyncio.run(run_novel_planner_v2())
