"""Example: Quest Log Generation using LLMNode with JSON structured output.

This example demonstrates JSON structured output with a complex structure containing
multiple fields including different data types (strings, integers, booleans).
"""

import asyncio

from langchain_ollama import ChatOllama
from pydantic import BaseModel

from wyrdflow.nodes.llm import LLMNode


# Define Pydantic models for quest data
class Quest(BaseModel):
    """A quest in the adventure log."""

    name: str
    difficulty: int
    completed: bool
    reward_gold: int


class QuestLog(BaseModel):
    """Collection of quests for an adventure."""

    quests: list[Quest]


async def main() -> None:
    """Generate a quest log using JSON structured output."""
    print("=== Quest Log Generation with JSON Structured Output ===\n")

    # 1. Configure the LLM
    llm = ChatOllama(
        model="llama3.1",
        temperature=0.8,
    )
    print("Using model: llama3.1")

    # 2. Create the LLMNode with JSON structured output
    system_message = (
        "You are a tabletop RPG game master creating quest logs. "
        "Generate engaging quests with varied difficulty levels and completion status."
    )

    node = LLMNode(
        node_id="generate_quests",
        llm=llm,
        system_message=system_message,
        prompt=(
            "Create 5 quests for a fantasy adventure. "
            "Include a mix of completed and incomplete quests with varying difficulty (1-10). "
            "Make the quest names creative and thematic."
        ),
        output_schema=QuestLog,
    )

    # 3. Execute the node
    print("Executing node...")
    print("Calling Ollama... (this may take a moment)\n")

    result = await node.execute(input_data=node.input_schema(prompt_variables={}))

    # 4. Display Results
    print("\n--- Parsed Content (Pydantic Model) ---")
    print(result.content)
    print(f"\nType: {type(result.content)}")

    # 5. Verify Structure
    quest_log = result.content
    assert isinstance(quest_log, QuestLog), "Result should be a QuestLog"
    assert len(quest_log.quests) >= 1, "Should have at least 1 quest"

    print(f"\n✅ Success! Generated {len(quest_log.quests)} quests")
    print("   JSON output was correctly parsed into Pydantic models.")

    # 6. Display individual quests with statistics
    print("\n--- Generated Quest Log ---")
    completed_count = 0
    total_rewards = 0

    for i, quest in enumerate(quest_log.quests, 1):
        status = "✓ Complete" if quest.completed else "○ Incomplete"
        print(
            f"{i}. [{status}] {quest.name}\n"
            f"   Difficulty: {quest.difficulty}/10 | Reward: {quest.reward_gold} gold"
        )
        if quest.completed:
            completed_count += 1
            total_rewards += quest.reward_gold

    # 7. Show statistics
    print("\n--- Statistics ---")
    print(f"Completed: {completed_count}/{len(quest_log.quests)}")
    print(f"Total Gold Earned: {total_rewards}")

    # 8. Demonstrate different data types
    print("\n--- Data Type Verification ---")
    sample_quest = quest_log.quests[0]
    print(f"Quest name (str): {sample_quest.name!r}")
    print(f"Difficulty (int): {sample_quest.difficulty!r}")
    print(f"Completed (bool): {sample_quest.completed!r}")
    print(f"Reward (int): {sample_quest.reward_gold!r}")


if __name__ == "__main__":
    asyncio.run(main())
