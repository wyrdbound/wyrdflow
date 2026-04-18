"""Example of chaining LLMNodes with Pydantic models."""

import asyncio
from typing import Any, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from wyrdflow.core.state import WorkflowState
from wyrdflow.nodes.llm import LLMNode

MODEL_NAME = "gemma2"  # or 'llama3.2'

# --- 1. Define Data Models ---


class Theme(BaseModel):
    """Output for the first node: A campaign theme."""

    description: str = Field(description="A one-sentence description of the theme")
    tone: str = Field(
        description="The tone of the setting (e.g. dark, whimsical, futuristic)"
    )
    difficulty: str = Field(
        description="Recommended difficulty level (Low, Medium, High)"
    )


class NPCDescription(BaseModel):
    """Output for the second node: An NPC fitting the theme."""

    name: str = Field(description="The name of the NPC")
    race: str = Field(description="The race/ancestry of the NPC")
    occupation: str = Field(description="The NPC's job or role")
    personality: str = Field(description="A brief description of their personality")
    quirk: str = Field(description="A unique quirk or mannerism")
    stats: dict = Field(description="Simple stats (STR, DEX, INT)")


# --- 2. Define Workflow State ---


class ChainState(TypedDict, total=False):
    # Inputs
    genre: str

    # Intermediates/Outputs
    theme_data: dict  # Will hold Theme model dump
    npc_data: dict  # Will hold NPCDescription model dump

    # Raw responses
    theme_raw: Any
    npc_raw: Any

    # Metadata
    workflow_state: dict


async def run_chained_example():
    print("🚀 Starting Chained LLM Node Example")

    # Setup LLM
    try:
        llm = ChatOllama(model=MODEL_NAME, temperature=0.7)
    except ImportError:
        print("❌ langchain-ollama not installed.")
        return

    print(f"Using LLM: {getattr(llm, 'model', MODEL_NAME)}")

    # --- Node 1: Theme Generator ---
    # Generates a Theme object based on 'genre' from state
    theme_node = LLMNode.from_model(
        node_id="generate_theme",
        llm=llm,
        output_model=Theme,
        prompt="Generate a unique RPG campaign theme based on the genre: {genre}",
        # Map the 'content' of the output (which is the Theme object) to 'theme_data' in state
        output_map={"content": "theme_data", "raw_response": "theme_raw"},
    )

    # --- Node 2: NPC Generator ---
    # Uses the output from Node 1 to generate an NPC
    # We map fields from 'theme_data' in state to prompt variables
    npc_node = LLMNode.from_model(
        node_id="generate_npc",
        llm=llm,
        output_model=NPCDescription,
        prompt=(
            "Create an NPC for a {tone} setting.\n"
            "Theme Description: {description}\n"
            "Difficulty: {difficulty}"
        ),
        # Map nested state fields to prompt variables
        input_map={
            "description": "theme_data.description",
            "tone": "theme_data.tone",
            "difficulty": "theme_data.difficulty",
        },
        output_map={"content": "npc_data", "raw_response": "npc_raw"},
    )

    # --- Build Graph ---
    workflow_state = WorkflowState.create_new()
    graph = StateGraph(ChainState)

    graph.add_node("generate_theme", theme_node.as_langraph_node())
    graph.add_node("generate_npc", npc_node.as_langraph_node())

    graph.add_edge(START, "generate_theme")
    graph.add_edge("generate_theme", "generate_npc")
    graph.add_edge("generate_npc", END)

    app = graph.compile()

    # --- Run ---
    initial_state: ChainState = {
        "genre": "Grimdark Fantasy",
        "workflow_state": workflow_state.model_dump(),
    }

    print(f"\nInput State: {initial_state}")
    result = await app.ainvoke(initial_state)

    print("\n✅ Workflow completed!")

    print("\n--- Step 1 Output: Theme ---")
    print(f"Description: {result['theme_data']['description']}")
    print(f"Tone: {result['theme_data']['tone']}")
    print(f"Raw Response (Type): {type(result.get('theme_raw'))}")
    if result.get("theme_raw"):
        # Print first 100 chars of content to show it's there
        content = getattr(result["theme_raw"], "content", str(result["theme_raw"]))
        print(f"Raw Content: {content}")

    print("\n--- Step 2 Output: NPC ---")
    print(f"Name: {result['npc_data']['name']}")
    print(f"Role: {result['npc_data']['occupation']}")
    print(f"Quirk: {result['npc_data']['quirk']}")
    print(f"Raw Response (Type): {type(result.get('npc_raw'))}")
    if result.get("npc_raw"):
        # Print first 100 chars of content to show it's there
        content = getattr(result["npc_raw"], "content", str(result["npc_raw"]))
        print(f"Raw Content: {content}")

    # Validate that the output matches our Pydantic models
    # (In a real app, the nodes already validated this, but we can check the dict structure)
    print("\nValidation:")
    print(f"Theme keys: {list(result['theme_data'].keys())}")
    print(f"NPC keys: {list(result['npc_data'].keys())}")


if __name__ == "__main__":
    asyncio.run(run_chained_example())
