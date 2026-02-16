"""LLM prompt templates — PLACEHOLDER VALUES.

Copy to config/prompt_templates.py and fill in your actual prompts.
All templates use str.format() placeholders. Literal braces: {{ and }}.
"""

# Variables: product_id, category, excel_row, image_files, product_path
PREPROCESS_PROMPT = """
Process product {product_id} in category {category}.
Excel data: {excel_row}
Images: {image_files}
Path: {product_path}

TODO: Add your preprocessing instructions here.
"""

# Variables: product_data_json, category
STRATEGY_PROMPT = """
Create an image strategy for:
{product_data_json}

Category: {category}

TODO: Add your strategy instructions here.
"""

# Variables: product_data_json, product_id
LISTING_PROMPT = """
Generate listing for:
{product_data_json}

Product ID: {product_id}

Output JSON:
{{
  "product_id": "{product_id}",
  "title": "...",
  "tags": "...",
  "description": "..."
}}

TODO: Add your listing instructions here.
"""

# Variables: category, materials, style, dimensions, selling_points, visual_features,
#            earring_note, direction, description, slot_context, creative_block,
#            reference_anchor, refs_list
PROMPT_NODE_USER_MESSAGE = """Generate prompt for {category} product.
Materials: {materials}
Style: {style}
Size: {dimensions}
Selling Points: {selling_points}
Visual Features: {visual_features}{earring_note}
Direction: {direction}
Description: {description}{slot_context}
{creative_block}
Anchor: {reference_anchor}
References: {refs_list}

TODO: Add your prompt generation instructions here.
"""

ANTI_AI_KEYWORDS = {"film grain", "dust particles"}
WEARING_BANNED = {"cafe", "beach"}

NANOBANANA_DIRECTIONS = [
    "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
    "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
]
