"""
Prompt Generator - Direction Definitions and Helpers

This module provides:
- ImageDirection dataclass for direction configuration
- DIRECTIONS list with all 9 image directions
- Helper functions for prompt extraction and cleaning

The actual prompt generation is handled by:
- prompt_node in nodes.py (uses traced_agent_query)
- prompt_aggregator_node in nodes.py (collects results)
- LangGraph fan-out in workflow.py (parallel execution)
"""

from dataclasses import dataclass


# ============================================================
# Direction Definitions
# ============================================================

@dataclass
class ImageDirection:
    """Image direction configuration"""
    type: str
    description: str


# 9 image directions for jewelry product photography
DIRECTIONS: list[ImageDirection] = [
    ImageDirection(
        type="hero",
        description="Hero shot - clean light background, product only. "
                    "⛔ HARD RULES: Clean LIGHT background (white/cream/beige), NO hands, NO fingers, "
                    "NO props, NO fabric, NO silk, NO model. Aperture MUST be f/8 or f/11."
    ),
    ImageDirection(
        type="size_reference",
        description="Size reference - hand or ruler for scale. "
                    "Help buyers understand actual jewelry dimensions."
    ),
    ImageDirection(
        type="art_abstract",
        description="Abstract/Conceptual art - creative composition, art installation feel, color experiments. "
                    "Creative composition, art installation feel, bold color experiments."
    ),
    ImageDirection(
        type="wearing_a",
        description="Wearing A - model wearing, DARK backdrop. "
                    "Elegant pose, moody lighting, dark solid or gradient background."
    ),
    ImageDirection(
        type="wearing_b",
        description="Wearing B - model wearing, LIGHT backdrop. "
                    "Elegant pose, bright lighting, light solid or gradient background."
    ),
    ImageDirection(
        type="macro_detail",
        description="Macro detail - extreme close-up. "
                    "Show craftsmanship, texture, gemstone details, fine workmanship."
    ),
    ImageDirection(
        type="art_still_life",
        description="Fine Art Still Life - oil painting texture, classical aesthetics, museum style. "
                    "Oil painting texture, classical aesthetics, museum-quality composition."
    ),
    ImageDirection(
        type="scene_daily",
        description="Scene daily - casual lifestyle. "
                    "Relatable context showing everyday wear, helps buyers envision owning the piece."
    ),
    ImageDirection(
        type="workshop",
        description="Workshop - tools, raw materials. "
                    "Behind-the-scenes, artisan feel, handmade authenticity."
    ),
]


# ============================================================
# Helper Functions for Hero Post-Processing
# ============================================================

def fix_hero_prompt(prompt: str) -> str:
    """Post-process hero prompt to fix common MiniMax violations.

    Fixes:
    - Replace wrong aperture with f/8
    - Ensure clean background keywords

    Note: "hand-engraved" in ANCHOR is legitimate product description.
    """
    import re

    # Fix aperture - replace f/1.4, f/1.8, f/2, f/2.8, f/4 with f/8
    prompt = re.sub(r'f/1\.\d', 'f/8', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'f/2(?:\.\d)?', 'f/8', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'f/4(?:\.\d)?', 'f/8', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'shallow depth of field', 'deep depth of field', prompt, flags=re.IGNORECASE)

    # Ensure clean background keywords are present
    if 'background' not in prompt.lower():
        prompt = prompt.replace(
            'Rigid constraint.',
            'Rigid constraint.\n\nClean light background (pure white or soft cream). No props. No fabric.'
        )

    return prompt
