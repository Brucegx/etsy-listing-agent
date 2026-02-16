"""Tool definitions for agentic prompt loop — PLACEHOLDER VALUES.

Copy to config/prompt_tool_definitions.py and customize.
"""

READ_REFERENCE_TOOL = {
    "name": "read_reference",
    "description": "Read a reference file. TODO: Add your description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path to reference file",
            }
        },
        "required": ["file_path"],
    },
}

VALIDATE_PROMPT_TOOL = {
    "name": "validate_prompt",
    "description": "Validate generated prompt. TODO: Add your description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt_text": {
                "type": "string",
                "description": "The prompt text to validate",
            }
        },
        "required": ["prompt_text"],
    },
}
