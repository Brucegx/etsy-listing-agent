"""Temporary directory manager for product processing.

Downloads Drive files to a temp dir, provides paths to the workflow,
and cleans up after processing.
"""

import shutil
import time
import uuid
from pathlib import Path

from app.drive.client import DriveClient

# Global registry of scheduled cleanups: {run_id: (root_path, expiry_timestamp)}
_cleanup_registry: dict[str, tuple[Path, float]] = {}


class TempManager:
    """Manages a temporary directory for a single product generation run."""

    def __init__(self, base_dir: str = "/tmp") -> None:
        self.run_id = str(uuid.uuid4())[:8]
        self.base_dir = base_dir
        self.root = Path(base_dir) / f"etsy_agent_{self.run_id}"
        self.product_dir: Path | None = None

    def setup(self, product_id: str) -> Path:
        """Create the temp directory structure for a product."""
        self.product_dir = self.root / product_id
        self.product_dir.mkdir(parents=True, exist_ok=True)
        return self.product_dir

    async def download_files(
        self,
        client: DriveClient,
        folder_id: str,
        excel_file_id: str,
        product_id: str,
    ) -> tuple[Path, list[str]]:
        """Download Excel + product images from Drive to temp dir.

        Returns:
            Tuple of (excel_path, list of image filenames).
        """
        if not self.product_dir:
            self.setup(product_id)

        # Download Excel
        files = await client.list_files(folder_id)
        excel_file = next((f for f in files if f["id"] == excel_file_id), None)

        if excel_file and excel_file.get("mimeType") == "application/vnd.google-apps.spreadsheet":
            excel_bytes = await client.download_google_sheet_as_xlsx(excel_file_id)
        else:
            excel_bytes = await client.download_file(excel_file_id)

        excel_path = self.product_dir / "products.xlsx"
        excel_path.write_bytes(excel_bytes)

        # Find and download product images from subfolder matching product_id
        image_files: list[str] = []
        subfolders = [f for f in files if f.get("mimeType") == "application/vnd.google-apps.folder"]
        product_folder = next(
            (f for f in subfolders if product_id.lower() in f["name"].lower()),
            None,
        )

        if product_folder:
            product_files = await client.list_files(product_folder["id"])
            image_mimes = {"image/jpeg", "image/png", "image/webp"}
            for img in product_files:
                if img.get("mimeType") in image_mimes:
                    img_bytes = await client.download_file(img["id"])
                    img_path = self.product_dir / img["name"]
                    img_path.write_bytes(img_bytes)
                    image_files.append(img["name"])

        return excel_path, image_files

    def schedule_cleanup(self, ttl_seconds: int = 3600) -> None:
        """Schedule this temp dir for cleanup after TTL instead of immediate deletion."""
        _cleanup_registry[self.run_id] = (self.root, time.time() + ttl_seconds)

    def cleanup(self) -> None:
        """Remove the temp directory immediately."""
        _cleanup_registry.pop(self.run_id, None)
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def get_product_dir(run_id: str, product_id: str, base_dir: str = "/tmp") -> Path:
        """Get the product directory path for a given run_id."""
        return Path(base_dir) / f"etsy_agent_{run_id}" / product_id

    @staticmethod
    def purge_expired() -> None:
        """Remove all temp dirs that have passed their TTL."""
        now = time.time()
        expired = [rid for rid, (_, expiry) in _cleanup_registry.items() if now >= expiry]
        for rid in expired:
            root, _ = _cleanup_registry.pop(rid)
            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
