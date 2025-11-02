"""Example usage of HumanInputNode for novel plot generator."""

import asyncio
from uuid import uuid4

from wyrdflow.core.schemas import NodeContext
from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.human_input import (
    FieldConfig,
    FieldValidationResult,
    HumanInputNode,
    HumanInputNodeInput,
)


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


async def main() -> None:
    """Example: Collect inputs for a novel plot generator."""

    # Define fields for novel planning
    plot_fields = [
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

    # Create the human input node
    input_node = HumanInputNode(node_id="novel_input_collector")

    # Create initial state and context
    workflow_id = uuid4()
    workflow_run_id = uuid4()

    initial_state = WorkflowState(
        workflow_id=workflow_id, workflow_run_id=workflow_run_id
    )

    context = NodeContext(
        workflow_id=workflow_id,
        workflow_run_id=workflow_run_id,
        node_id="novel_input_collector",
    )

    print("=== Novel Plot Generator ===")
    print("Let's collect some information about your novel idea...\n")

    try:
        # Execute the node
        result = await input_node.execute(input_config, context, initial_state)

        print("\n=== Collected Information ===")
        print(f"Genre: {initial_state.get('novel.genre')}")
        print(f"Target Audience: {initial_state.get('novel.requirements.audience')}")
        word_count = initial_state.get("novel.requirements.word_count")
        print(f"Word Count: {word_count:,}")
        print(f"Romance Subplot: {initial_state.get('novel.plot.romance')}")
        main_chars = initial_state.get("novel.characters.main", [])
        print(f"Main Characters: {len(main_chars)} characters")
        print(f"\nPlot Summary:\n{initial_state.get('novel.plot.summary')}")

        print("\n=== Collected Fields ===")
        for field_name, field_value in result.collected_fields.items():
            print(f"  {field_name}: {field_value}")

        print("\n=== Ready for Next Steps ===")
        print("You can now use this information to generate:")
        print("- Detailed character profiles")
        print("- Chapter outlines")
        print("- Scene breakdowns")
        print("- Writing prompts")

    except KeyboardInterrupt:
        print("\n\nWorkflow cancelled by user")
    except Exception as e:
        print(f"\nWorkflow failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
