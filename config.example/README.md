# Config Setup

The `config/` directory contains proprietary constants and prompt templates that are excluded from version control.

## Quick Start

```bash
cp -r config.example/ config/
```

Then edit each file in `config/` to fill in your actual values:

- **`validation_rules.py`** — Domain constants (categories, materials, styles), strategy rules, banned keywords, regex patterns
- **`prompt_templates.py`** — LLM prompt templates with `{variable}` placeholders, validation keyword sets, fallback directions
- **`prompt_tool_definitions.py`** — Tool schemas for the agentic prompt generation loop

## Template Format

All files are plain Python (`.py`). Templates use `str.format()` placeholders — literal braces are escaped as `{{` and `}}`.

## Running Tests

Tests import constants through `config_loader.py`, which loads from `config/`. Ensure `config/` exists before running:

```bash
uv run pytest tests/ -v
```
