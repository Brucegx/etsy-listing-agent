#!/usr/bin/env python3
"""Excel file loader for Etsy Listing Agent.

Loads product data from supplier Excel files.
"""

from pathlib import Path
from typing import Any

import pandas as pd


def load_excel_row(
    excel_path: str | Path,
    row_id: str,
    id_column: str = "款号",
) -> dict[str, Any]:
    """Load a single row from Excel file by product ID.

    Args:
        excel_path: Path to Excel file
        row_id: Product ID to find (e.g., "R001")
        id_column: Column name containing product IDs (default: "款号")

    Returns:
        Dictionary with row data

    Raises:
        FileNotFoundError: If Excel file doesn't exist
        ValueError: If row_id not found in Excel
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    # Read Excel file
    df = pd.read_excel(excel_path, engine="openpyxl")

    # Find row by product ID
    mask = df[id_column] == row_id
    if not mask.any():
        available_ids = df[id_column].dropna().tolist()[:10]
        raise ValueError(
            f"Product ID '{row_id}' not found in column '{id_column}'. "
            f"Available IDs: {available_ids}..."
        )

    # Get the row as dict
    row = df[mask].iloc[0].to_dict()

    # Convert NaN to None for JSON compatibility
    row = {k: (None if pd.isna(v) else v) for k, v in row.items()}

    return row


def list_product_ids(
    excel_path: str | Path,
    id_column: str = "款号",
) -> list[str]:
    """List all product IDs in an Excel file.

    Args:
        excel_path: Path to Excel file
        id_column: Column name containing product IDs

    Returns:
        List of product IDs
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    df = pd.read_excel(excel_path, engine="openpyxl")
    return df[id_column].dropna().astype(str).tolist()


def detect_category_from_path(excel_path: str | Path) -> str | None:
    """Detect product category from Excel file path.

    Args:
        excel_path: Path to Excel file

    Returns:
        Category string or None if not detected
    """
    path_str = str(excel_path).lower()

    category_keywords = {
        "ring": "rings",
        "earring": "earrings",
        "necklace": "necklaces",
        "bracelet": "bracelets",
        "pendant": "pendants",
    }

    for keyword, category in category_keywords.items():
        if keyword in path_str:
            return category

    return None
