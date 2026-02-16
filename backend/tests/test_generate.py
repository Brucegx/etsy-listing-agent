from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.product_service import ProductService


@pytest.mark.asyncio
async def test_product_service_reads_excel_from_bytes():
    """ProductService can parse product IDs from Excel bytes."""
    import openpyxl
    import io

    # Create a minimal Excel file in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["款号", "材质", "尺寸"])
    ws.append(["R001", "925银", "adjustable"])
    ws.append(["R002", "铜镀金", "7"])

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()

    service = ProductService()
    product_ids = service.list_products_from_bytes(excel_bytes)
    assert product_ids == ["R001", "R002"]


@pytest.mark.asyncio
async def test_product_service_get_row_from_bytes():
    """ProductService can extract a specific row from Excel bytes."""
    import openpyxl
    import io

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["款号", "材质", "尺寸"])
    ws.append(["R001", "925银", "adjustable"])

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()

    service = ProductService()
    row = service.get_row_from_bytes(excel_bytes, "R001")
    assert row["款号"] == "R001"
    assert row["材质"] == "925银"
