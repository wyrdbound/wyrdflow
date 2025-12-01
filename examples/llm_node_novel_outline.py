"""Example of generating a novel outline using chained LLMNodes."""

import asyncio
from typing import Literal, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, model_validator

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.llm import LLMNode

MODEL_NAME = "gemma2"  # or 'llama3.2'

# --- 1. Define Data Models ---

Genre = Literal[
    "grimdark fantasy",
    "heroic fantasy",
    "epic fantasy",
    "techno fantasy",
    "steampunk",
    "cyberpunk",
    "sci-fi",
]


class NovelMetadata(BaseModel):
    """Metadata and initial setup for a novel."""

    genre: Genre = Field(description="The genre of the novel")
    setting: str = Field(description="Description of the setting")
    tentative_title: str = Field(description="A working title for the novel")
    target_word_count: int = Field(description="Target word count", gt=10000, lt=200000)
    target_chapters: int = Field(description="Target number of chapters")
    protagonist_summary: str = Field(description="Detailed summary of the protagonist")
    plot_summary: str = Field(description="High-level summary of the plot")
    character_summaries: list[str] = Field(
        description="List of summaries for other characters"
    )
    constraint_summaries: list[str] = Field(
        description="List of constraints or style guidelines"
    )

    @model_validator(mode="after")
    def validate_chapter_count(self) -> "NovelMetadata":
        """Ensure chapter count is reasonable for the word count.

        This validator computes reasonable limits for chapter counts based on
        standard novel pacing (approx. 2000-5000 words per chapter) and
        adjusts the LLM's output if it falls outside this range.
        """
        # Standard chapter length range
        min_words_per_chapter = 2000
        max_words_per_chapter = 5000

        # Calculate expected chapter range
        min_chapters = max(1, self.target_word_count // max_words_per_chapter)
        max_chapters = max(1, self.target_word_count // min_words_per_chapter)

        # Clamp the generated value to the calculated range
        if self.target_chapters < min_chapters:
            self.target_chapters = min_chapters
        elif self.target_chapters > max_chapters:
            self.target_chapters = max_chapters

        return self


class ChapterOutline(BaseModel):
    """Outline for a single chapter."""

    chapter_number: int = Field(description="The chapter number")
    title: str = Field(description="Chapter title")
    summary: str = Field(description="Summary of events in the chapter")
    key_beats: list[str] = Field(description="Key story beats or moments")


class NovelOutline(BaseModel):
    """Complete structured outline for the novel."""

    title: str = Field(description="Final title of the novel")
    logline: str = Field(description="One sentence summary")
    chapters: list[ChapterOutline] = Field(description="List of chapter outlines")


# --- 2. Define Workflow State ---


class NovelState(TypedDict, total=False):
    # Inputs
    concept: str

    # Intermediates/Outputs
    novel_metadata: dict  # Will hold NovelMetadata model dump
    novel_outline: dict  # Will hold NovelOutline model dump

    # Metadata
    workflow_state: dict


async def run_novel_example():
    print("🚀 Starting Novel Outline Generator Example")

    # Setup LLM
    try:
        llm = ChatOllama(model=MODEL_NAME, temperature=0.7)
    except ImportError:
        print("❌ langchain-ollama not installed.")
        return

    print(f"Using LLM: {getattr(llm, 'model', MODEL_NAME)}")

    # --- Node 1: Metadata Generator ---
    # Generates the initial novel setup based on a simple concept
    metadata_node = LLMNode.from_model(
        node_id="generate_metadata",
        llm=llm,
        output_model=NovelMetadata,
        prompt="Generate detailed metadata for a novel based on this concept: {concept}",
        output_map={"content": "novel_metadata"},
    )

    # --- Node 2: Outline Generator ---
    # Uses the metadata to generate a full outline
    # Note: We construct the prompt to match the user's requested template structure.
    # Since LangChain templates don't support Jinja2-style loops/ifs natively in the same way without
    # extra dependencies or complex setup, we'll use a simplified f-string style or standard
    # prompt template features. For lists, we'll ask the LLM to format them in the previous step
    # or rely on the Pydantic model's string representation which is usually readable enough for the LLM.

    outline_prompt = (
        "You are a creative fiction author writing a novel tentatively titled "
        '"{tentative_title}" in the {genre} genre set in {setting}.\n'
        "The length of the novel should target {target_word_count} words "
        "in about {target_chapters} chapters.\n\n"
        "The protagonist is {protagonist_summary}.\n\n"
        "{plot_summary}\n\n"
        "Your task is to develop a complete, structured plot outline for the novel, "
        "including unique twists and surprises for the reader.\n\n"
        "Include the following additional characters in the plot outline:\n"
        "{character_summaries}\n\n"
        "Include the following additional constraints:\n"
        "{constraint_summaries}"
    )

    outline_node = LLMNode.from_model(
        node_id="generate_outline",
        llm=llm,
        output_model=NovelOutline,
        prompt=outline_prompt,
        input_map={
            "tentative_title": "novel_metadata.tentative_title",
            "genre": "novel_metadata.genre",
            "setting": "novel_metadata.setting",
            "target_word_count": "novel_metadata.target_word_count",
            "target_chapters": "novel_metadata.target_chapters",
            "protagonist_summary": "novel_metadata.protagonist_summary",
            "plot_summary": "novel_metadata.plot_summary",
            "character_summaries": "novel_metadata.character_summaries",
            "constraint_summaries": "novel_metadata.constraint_summaries",
        },
        output_map={"content": "novel_outline"},
    )

    # --- Build Graph ---
    workflow_state = WorkflowState.create_new()
    graph = StateGraph(NovelState)

    graph.add_node("generate_metadata", metadata_node.as_langraph_node())
    graph.add_node("generate_outline", outline_node.as_langraph_node())

    graph.add_edge(START, "generate_metadata")
    graph.add_edge("generate_metadata", "generate_outline")
    graph.add_edge("generate_outline", END)

    app = graph.compile()

    # --- Run ---
    # We provide a concept that matches the user's example to guide the generation
    initial_state: NovelState = {
        "concept": "A grimdark fantasy about Crag'oth, a lonely troglodyte who finds a gem that lets him see sunlight, leading him to save the surface world.",
        "workflow_state": workflow_state.model_dump(),
    }

    print(f"\nInput Concept: {initial_state['concept']}")
    result = await app.ainvoke(initial_state)

    print("\n✅ Workflow completed!")

    meta = result["novel_metadata"]
    print("\n--- Generated Metadata ---")
    print(f"Title: {meta['tentative_title']}")
    print(f"Genre: {meta['genre']}")
    print(
        f"Target: {meta['target_word_count']} words, {meta['target_chapters']} chapters"
    )

    outline = result["novel_outline"]
    print("\n--- Generated Outline ---")
    print(f"Final Title: {outline['title']}")
    print(f"Logline: {outline['logline']}")
    print(f"\nChapters ({len(outline['chapters'])} generated):")
    for chapter in outline["chapters"][:3]:  # Print first 3 chapters
        print(f"\nChapter {chapter['chapter_number']}: {chapter['title']}")
        print(f"Summary: {chapter['summary'][:150]}...")


if __name__ == "__main__":
    asyncio.run(run_novel_example())
