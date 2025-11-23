"""Example usage of HumanInputNode for novel plot generator using LangGraph."""

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.human_input import (
    FieldConfig,
    FieldValidationResult,
    HumanInputNode,
    HumanInputNodeInput,
)


# Define LangGraph state schema
class NovelPlannerState(TypedDict, total=False):
    """State schema for LangGraph novel planner workflow."""

    input: dict[str, Any]  # Input configuration for nodes
    collected_fields: dict[str, Any]
    workflow_state: dict[str, Any]
    fields_collected: list[str]
    execution_id: str
    last_node: str


def validate_genre(genre: str) -> FieldValidationResult:
    """Validate novel genre."""
    valid_genres = [
        "fantasy",
        "sci-fi",
        "mystery",
        "romance",
        "thriller",
        "literary",
    ]
    if genre.lower() not in valid_genres:
        return FieldValidationResult(
            is_valid=False,
            errors=[f"Genre must be one of: {', '.join(valid_genres)}"],
        )
    return FieldValidationResult(is_valid=True)


def validate_word_count(count: int) -> FieldValidationResult:
    """Validate word count is reasonable for a novel."""
    if count < 1000 or count > 200000:
        return FieldValidationResult(
            is_valid=False,
            errors=["Word count should be between 1,000 and 200,000 for a novel"],
        )
    return FieldValidationResult(is_valid=True)


def create_novel_fields() -> list[FieldConfig]:
    """Create the field configuration for novel planning."""
    return [
        FieldConfig(
            name="genre",
            field_type=str,
            prompt="What genre is your novel?",
            help_text=(
                "Choose from: fantasy, sci-fi, mystery, romance, thriller, literary"
            ),
            validation_fn=validate_genre,
            required=True,
            default_value="fantasy",
        ),
        FieldConfig(
            name="plot_summary",
            field_type=str,
            prompt="Provide a brief plot summary:",
            help_text="Keep it under 500 words - just the main story arc",
            required=True,
        ),
        FieldConfig(
            name="main_characters",
            field_type=list[str],
            prompt="Describe your main characters:",
            help_text="Enter one character per line, empty line when finished",
        ),
        FieldConfig(
            name="target_word_count",
            field_type=int,
            prompt="Target word count for the novel:",
            validation_fn=validate_word_count,
            default_value=80000,
        ),
        FieldConfig(
            name="include_romance",
            field_type=bool,
            prompt="Include a romantic subplot?",
            default_value=False,
        ),
        FieldConfig(
            name="target_audience",
            field_type=str,
            prompt="Target audience (YA, Adult, etc.):",
            default_value="Adult",
            required=False,
        ),
    ]


def create_input_node() -> HumanInputNode:
    """Create the human input node for collecting novel information."""
    return HumanInputNode(node_id="novel_input_collector")


async def run_novel_planner_langgraph() -> None:
    """Run the novel planner using LangGraph workflow orchestration."""
    print("🚀 Starting Novel Plot Generator with LangGraph\n")

    # Initialize workflow state
    workflow_state = WorkflowState.create_new()
    print(f"Created workflow run: {workflow_state.workflow_run_id}")

    # Create node and input configuration
    input_node = create_input_node()
    plot_fields = create_novel_fields()

    # Create input configuration with state mapping
    input_config = HumanInputNodeInput(
        fields=plot_fields,
        output_mapping={
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

    # Add the input collection node
    graph.add_node("collect_input", input_node.as_langraph_node())

    # Define workflow edges
    graph.add_edge(START, "collect_input")
    graph.add_edge("collect_input", END)

    # Compile the graph
    workflow = graph.compile()
    print("✅ LangGraph workflow compiled successfully")

    # Prepare initial state for LangGraph
    initial_state: NovelPlannerState = {
        "input": input_config.model_dump(),  # Pass input config as "input"
        "workflow_state": workflow_state.model_dump(),
    }

    print("\n=== Novel Plot Generator ===")
    print("Let's collect some information about your novel idea...\n")

    try:
        print("🎯 Executing LangGraph workflow...")

        # Execute workflow
        result = await workflow.ainvoke(initial_state)

        # Extract the updated workflow state
        final_workflow_state = WorkflowState.model_validate(result["workflow_state"])

        print("\n✅ Novel planner completed!")

        # Display collected information
        print("\n=== Collected Information ===")
        print(f"Genre: {final_workflow_state.get('novel.genre')}")
        print(
            f"Target Audience: {final_workflow_state.get('novel.requirements.audience')}"
        )
        word_count = final_workflow_state.get("novel.requirements.word_count")
        if word_count:
            print(f"Word Count: {word_count:,}")
        print(f"Romance Subplot: {final_workflow_state.get('novel.plot.romance')}")
        main_chars = final_workflow_state.get("novel.characters.main", [])
        print(f"Main Characters: {len(main_chars)} characters")
        if main_chars:
            for i, char in enumerate(main_chars, 1):
                print(f"  {i}. {char}")

        plot_summary = final_workflow_state.get("novel.plot.summary")
        if plot_summary:
            print(f"\nPlot Summary:\n{plot_summary}")

        print("\n=== Collected Fields ===")
        if "collected_fields" in result:
            for field_name, field_value in result["collected_fields"].items():
                print(f"  {field_name}: {field_value}")

        print("\n=== Ready for Next Steps ===")
        print("You can now use this information to generate:")
        print("- Detailed character profiles")
        print("- Chapter outlines")
        print("- Scene breakdowns")
        print("- Writing prompts")

        print("\n🎉 LangGraph novel planner completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⏹️  Workflow cancelled by user")
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")


# Keep the old function name for compatibility but redirect to LangGraph version
async def main() -> None:
    """Example: Collect inputs for a novel plot generator using LangGraph."""
    await run_novel_planner_langgraph()


if __name__ == "__main__":
    asyncio.run(main())
