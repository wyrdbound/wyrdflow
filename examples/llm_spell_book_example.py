"""Example: Spell Book Generation using LLMNode with JSON structured output.

This example demonstrates JSON structured output with floating-point numbers,
showing robustness across different numeric types and schema structures.
"""

import asyncio

from langchain_ollama import ChatOllama
from pydantic import BaseModel

from wyrdflow.nodes.llm import LLMNode

OLLAMA_MODEL_NAME = "gemma2"  # or "gemma2", "qwen2.5", etc.


# Define Pydantic models for spell data
class Spell(BaseModel):
    """A magical spell in the spell book."""

    name: str
    mana_cost: float
    damage: float
    cooldown: float
    description: str


class SpellBook(BaseModel):
    """Collection of spells for a mage."""

    spells: list[Spell]


async def main() -> None:
    """Generate a spell book using JSON structured output."""
    print("=== Spell Book Generation with JSON Structured Output ===\n")

    # 1. Configure the LLM
    llm = ChatOllama(
        model=OLLAMA_MODEL_NAME,
        temperature=0.9,
    )
    print(f"Using model: {OLLAMA_MODEL_NAME}")

    # 2. Create the LLMNode with JSON structured output
    system_message = (
        "You are a game designer creating magical spells for a fantasy RPG. "
        "Generate creative spells with balanced stats using decimal values."
    )

    node = LLMNode(
        node_id="generate_spells",
        llm=llm,
        system_message=system_message,
        prompt=(
            "Create 4 diverse magical spells for a mage's spell book. "
            "Use creative elemental names (Fire, Ice, Lightning, Shadow, Nature, etc.). "
            "Mana cost should be 10.0-100.0, damage 5.0-80.0, cooldown 1.0-10.0 seconds. "
            "Use decimal values for all numeric fields."
        ),
        output_schema=SpellBook,
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
    spell_book = result.content
    assert isinstance(spell_book, SpellBook), "Result should be a SpellBook"
    assert len(spell_book.spells) >= 1, "Should have at least 1 spell"

    print(f"\n✅ Success! Generated {len(spell_book.spells)} spells")
    print("   JSON output was correctly parsed into Pydantic models.")

    # 6. Display individual spells
    print("\n--- Generated Spell Book ---")
    for i, spell in enumerate(spell_book.spells, 1):
        efficiency = spell.damage / spell.mana_cost if spell.mana_cost > 0 else 0
        print(
            f"{i}. {spell.name}\n"
            f"   Description: {spell.description}\n"
            f"   Mana: {spell.mana_cost:.1f} | Damage: {spell.damage:.1f} | "
            f"Cooldown: {spell.cooldown:.1f}s\n"
            f"   Efficiency: {efficiency:.2f} damage per mana"
        )

    # 7. Calculate statistics
    print("\n--- Spell Book Statistics ---")
    avg_mana = sum(s.mana_cost for s in spell_book.spells) / len(spell_book.spells)
    avg_damage = sum(s.damage for s in spell_book.spells) / len(spell_book.spells)
    avg_cooldown = sum(s.cooldown for s in spell_book.spells) / len(spell_book.spells)

    print(f"Average Mana Cost: {avg_mana:.1f}")
    print(f"Average Damage: {avg_damage:.1f}")
    print(f"Average Cooldown: {avg_cooldown:.1f}s")

    # Find most efficient spell
    most_efficient = max(
        spell_book.spells,
        key=lambda s: s.damage / s.mana_cost if s.mana_cost > 0 else 0,
    )
    print(f"\nMost Efficient Spell: {most_efficient.name}")

    # 8. Demonstrate float type handling
    print("\n--- Float Type Verification ---")
    sample_spell = spell_book.spells[0]
    print(f"Spell name (str): {sample_spell.name!r}")
    print(
        f"Mana cost (float): {sample_spell.mana_cost!r} - "
        f"type: {type(sample_spell.mana_cost).__name__}"
    )
    print(
        f"Damage (float): {sample_spell.damage!r} - "
        f"type: {type(sample_spell.damage).__name__}"
    )
    print(
        f"Cooldown (float): {sample_spell.cooldown!r} - "
        f"type: {type(sample_spell.cooldown).__name__}"
    )


if __name__ == "__main__":
    asyncio.run(main())
