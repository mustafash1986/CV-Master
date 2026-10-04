"""
Google Drive synchronization and Drop-Folder watcher.
Manages automatic backup of Excel Tracker and application dossiers,
and watches for new job ad images dropped from mobile or desktop.
"""
import logging
import os
from pathlib import Path
import shutil
from typing import Any, List, Optional

from cv_servant.config import (
    DATA_DIR,
    EXCEL_TRACKER_PATH,
    GDRIVE_INBOX_DIR,
    GDRIVE_ARCHIVE_DIR,
    INBOX_IMAGES_DIR,
)

logger = logging.getLogger(__name__)


class GDriveSync:
    @staticmethod
    def _resolve_dir(path_val: Any, default_dir: Path) -> Path:
        if not path_val:
            return default_dir
        val_str = str(path_val).strip()
        if val_str.startswith("http://") or val_str.startswith("https://"):
            return default_dir
        try:
            p = Path(val_str)
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception as e:
            logger.warning(f"Invalid path '{val_str}', falling back to default: {e}")
            return default_dir

    def __init__(
        self,
        inbox_dir: Optional[Path] = None,
        archive_dir: Optional[Path] = None,
    ):
        self.drive_web_url = GDRIVE_INBOX_DIR if str(GDRIVE_INBOX_DIR).startswith("http") else ""
        self.inbox_dir = self._resolve_dir(inbox_dir or GDRIVE_INBOX_DIR, INBOX_IMAGES_DIR)
        self.archive_dir = self._resolve_dir(archive_dir or GDRIVE_ARCHIVE_DIR, DATA_DIR / "drive_backup")

        try:
            self.inbox_dir.mkdir(parents=True, exist_ok=True)
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            (self.inbox_dir / "processed").mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create directories: {e}")

    def scan_for_new_images(self) -> List[Path]:
        """Scan the inbox folder for newly dropped job ad images."""
        valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".jfif"}
        new_images = []

        for item in self.inbox_dir.iterdir():
            if item.is_file() and item.suffix.lower() in valid_extensions:
                new_images.append(item)

        return new_images

    def archive_processed_image(self, image_path: Path):
        """Move processed image to the 'processed' subfolder to prevent duplicate processing."""
        target = self.inbox_dir / "processed" / image_path.name
        try:
            shutil.move(str(image_path), str(target))
        except Exception as e:
            logger.error(f"Failed to archive image {image_path}: {e}")

    def sync_tracker_to_drive(self):
        """Copy the latest Job Applications Excel tracker to Google Drive backup."""
        if not EXCEL_TRACKER_PATH.exists():
            return
        target = self.archive_dir / EXCEL_TRACKER_PATH.name
        try:
            shutil.copy2(str(EXCEL_TRACKER_PATH), str(target))
            logger.info(f"Excel Tracker backed up to Drive: {target}")
        except Exception as e:
            logger.error(f"Failed to sync tracker to drive: {e}")

    def backup_application_package(self, local_package_folder: Path):
        """Backup an application folder (CV, Cover Letter, Email draft) to Google Drive."""
        if not local_package_folder.exists():
            return
        target_folder = self.archive_dir / "Applications" / local_package_folder.name
        try:
            if target_folder.exists():
                shutil.rmtree(str(target_folder))
            shutil.copytree(str(local_package_folder), str(target_folder))
            logger.info(f"Application package backed up to Drive: {target_folder}")
        except Exception as e:
            logger.error(f"Failed to backup application folder: {e}")
