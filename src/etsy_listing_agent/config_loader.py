"""Loads proprietary config from external Python files in config/.

Config files are gitignored so the repo can be public without exposing IP.
Uses importlib to load .py files by path — no YAML/JSON dependency needed.
"""

import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType


def _find_config_dir() -> Path:
    """Find the config directory, checking source tree and PROJECT_ROOT env."""
    # Try source tree layout first (config/ at repo root)
    source_dir = Path(__file__).parent.parent.parent / "config"
    if source_dir.exists():
        return source_dir
    # Fall back to PROJECT_ROOT env var (set by backend for venv installs)
    project_root = os.environ.get("PROJECT_ROOT", "")
    if project_root:
        env_dir = Path(project_root) / "config"
        if env_dir.exists():
            return env_dir
    return source_dir  # return default even if missing


def _load_config_module(name: str) -> ModuleType:
    """Load a Python config file from config/ by module name.

    Args:
        name: Module name without .py extension (e.g. 'validation_rules')

    Returns:
        The loaded module object.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
    """
    config_dir = _find_config_dir()
    file_path = config_dir / f"{name}.py"
    if not file_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {file_path}\n"
            f"Copy config.example/ to config/ and fill in your values.\n"
            f"See config.example/README.md for instructions."
        )
    spec = importlib.util.spec_from_file_location(
        f"config.{name}", str(file_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load config module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ===== Load and re-export validation_rules =====
_vr = _load_config_module("validation_rules")

VALID_CATEGORIES: set[str] = _vr.VALID_CATEGORIES
VALID_STYLES: set[str] = _vr.VALID_STYLES
VALID_AUDIENCES: set[str] = _vr.VALID_AUDIENCES
VALID_OCCASIONS: set[str | None] = _vr.VALID_OCCASIONS
VALID_MATERIALS: set[str] = _vr.VALID_MATERIALS
VALID_ANGLES: set[str] = _vr.VALID_ANGLES
VALID_IMAGE_TYPES: set[str] = _vr.VALID_IMAGE_TYPES
VALID_SHAPES: set[str] = _vr.VALID_SHAPES
VALID_SIZE_SOURCES: set[str] = _vr.VALID_SIZE_SOURCES
VALID_MATERIAL_FINISH: set[str] = _vr.VALID_MATERIAL_FINISH
VALID_COLOR_TONE: set[str] = _vr.VALID_COLOR_TONE
VALID_SURFACE_QUALITY: set[str] = _vr.VALID_SURFACE_QUALITY
VALID_LIGHT_INTERACTION: set[str] = _vr.VALID_LIGHT_INTERACTION

VALID_STRATEGIC_TYPES: set[str] = _vr.VALID_STRATEGIC_TYPES
BANNED_STRATEGIC_TYPES: set[str] = _vr.BANNED_STRATEGIC_TYPES
REQUIRED_SLOT_TYPES: list[str] = _vr.REQUIRED_SLOT_TYPES
VALID_STYLE_SERIES: set[str] = _vr.VALID_STYLE_SERIES
TIER_3_4_SERIES: set[str] = _vr.TIER_3_4_SERIES
POSE_FEASIBILITY: dict[str, set[str]] = _vr.POSE_FEASIBILITY

VALID_EARRING_DESIGN_TYPES: set[str] = _vr.VALID_EARRING_DESIGN_TYPES
BANNED_TITLE_ADJECTIVES: set[str] = _vr.BANNED_TITLE_ADJECTIVES
BANNED_TITLE_PHRASES: set[str] = _vr.BANNED_TITLE_PHRASES
VALID_IMAGE_TYPES_NANOBANANA: set[str] = _vr.VALID_IMAGE_TYPES_NANOBANANA

BANNED_KEYWORDS_HERO: set[str] = _vr.BANNED_KEYWORDS_HERO
BANNED_KEYWORDS_WEARING: set[str] = _vr.BANNED_KEYWORDS_WEARING
BANNED_KEYWORDS_MOISSANITE: set[str] = _vr.BANNED_KEYWORDS_MOISSANITE
BANNED_HERO_BACKGROUND: set[str] = _vr.BANNED_HERO_BACKGROUND

SIZE_PATTERN: re.Pattern = _vr.SIZE_PATTERN
ANTI_AI_REALISM_KEYWORDS: set[str] = _vr.ANTI_AI_REALISM_KEYWORDS


# ===== Load and re-export prompt_templates =====
_pt = _load_config_module("prompt_templates")

PREPROCESS_PROMPT: str = _pt.PREPROCESS_PROMPT
STRATEGY_PROMPT: str = _pt.STRATEGY_PROMPT
LISTING_PROMPT: str = _pt.LISTING_PROMPT
PROMPT_NODE_USER_MESSAGE: str = _pt.PROMPT_NODE_USER_MESSAGE

ANTI_AI_KEYWORDS: set[str] = _pt.ANTI_AI_KEYWORDS
WEARING_BANNED: set[str] = _pt.WEARING_BANNED
NANOBANANA_DIRECTIONS: list[str] = _pt.NANOBANANA_DIRECTIONS


# ===== Load and re-export prompt_tool_definitions =====
_td = _load_config_module("prompt_tool_definitions")

READ_REFERENCE_TOOL: dict = _td.READ_REFERENCE_TOOL
VALIDATE_PROMPT_TOOL: dict = _td.VALIDATE_PROMPT_TOOL
