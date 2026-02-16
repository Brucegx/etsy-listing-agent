"""Validation constants — PLACEHOLDER VALUES.

Copy to config/validation_rules.py and fill in your actual domain values.
"""

import re

# ===== Domain Enum Sets =====
# Fill in the valid values for your product domain.

VALID_CATEGORIES = {"example_category_1", "example_category_2"}
VALID_STYLES = {"style_a", "style_b"}
VALID_AUDIENCES = {"male", "female", "neutral"}
VALID_OCCASIONS = {"daily", "gift", None}
VALID_MATERIALS = {"material_a", "material_b"}
VALID_ANGLES = {"front", "side", "back"}
VALID_IMAGE_TYPES = {"product_only", "wearing", "macro"}
VALID_SHAPES = {"round", "oval", "square"}
VALID_SIZE_SOURCES = {"excel", "estimated", "measured"}

VALID_MATERIAL_FINISH = {"matte", "glossy"}
VALID_COLOR_TONE = {"warm", "cool", "neutral"}
VALID_SURFACE_QUALITY = {"smooth", "textured"}
VALID_LIGHT_INTERACTION = {"reflective", "diffuse"}


# ===== Strategy Constants =====

VALID_STRATEGIC_TYPES = {"macro_detail", "art_still_life"}
BANNED_STRATEGIC_TYPES = set()
REQUIRED_SLOT_TYPES = ["hero", "size_reference", "wearing_a", "wearing_b", "packaging"]

VALID_STYLE_SERIES = {"S1", "S2", "S3"}
TIER_3_4_SERIES = {"S1", "S2"}

POSE_FEASIBILITY = {
    "example_category_1": {"A1", "B1"},
    "example_category_2": {"A1"},
}


# ===== Additional Constants =====

VALID_EARRING_DESIGN_TYPES = {"flat_front", "3d_sculptural", "drop_dangle"}

BANNED_TITLE_ADJECTIVES = {"unique", "beautiful", "perfect"}
BANNED_TITLE_PHRASES = {"gift for him", "gift for her", "free shipping"}

VALID_IMAGE_TYPES_NANOBANANA = set(REQUIRED_SLOT_TYPES) | VALID_STRATEGIC_TYPES

BANNED_KEYWORDS_HERO = {"hand", "finger"}
BANNED_KEYWORDS_WEARING = {"cafe", "beach"}
BANNED_KEYWORDS_MOISSANITE = {"rainbow"}
BANNED_HERO_BACKGROUND = {"dark background", "black velvet"}

SIZE_PATTERN = re.compile(
    r'\d+(?:\.\d+)?(?:\s*(?:x|×)\s*\d+(?:\.\d+)?)?\s*(?:mm|cm|g\b)',
    re.IGNORECASE,
)

ANTI_AI_REALISM_KEYWORDS = {"film grain", "dust particles", "micro-scratches"}
