import io
from typing import Any

import pandas as pd


class ProductService:
    """Service for processing product data from Drive files."""

    def list_products_from_bytes(
        self, excel_bytes: bytes, id_column: str = "款号"
    ) -> list[str]:
        """Extract product IDs from Excel file bytes.

        Args:
            excel_bytes: Raw bytes of an Excel (.xlsx) file.
            id_column: Column name containing product IDs.

        Returns:
            List of product ID strings.
        """
        df = pd.read_excel(io.BytesIO(excel_bytes), engine="openpyxl")
        return df[id_column].dropna().astype(str).tolist()

    def get_row_from_bytes(
        self, excel_bytes: bytes, row_id: str, id_column: str = "款号"
    ) -> dict[str, Any]:
        """Extract a specific row from Excel file bytes by product ID.

        Args:
            excel_bytes: Raw bytes of an Excel (.xlsx) file.
            row_id: The product ID to look up.
            id_column: Column name containing product IDs.

        Returns:
            Dict mapping column names to values for the matched row.

        Raises:
            ValueError: If the product ID is not found.
        """
        df = pd.read_excel(io.BytesIO(excel_bytes), engine="openpyxl")
        mask = df[id_column] == row_id
        if not mask.any():
            raise ValueError(f"Product ID '{row_id}' not found")
        row = df[mask].iloc[0].to_dict()
        return {k: (None if pd.isna(v) else v) for k, v in row.items()}
