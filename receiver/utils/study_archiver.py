"""
Study Archiver Utility
Creates ZIP archives of completed DICOM studies.
"""
import logging
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StudyArchiver:
    """
    Creates ZIP archives of DICOM studies for upload.
    """

    def __init__(self, archive_dir: str = 'archives'):
        """
        Initialize study archiver.

        Args:
            archive_dir: Directory to store ZIP archives
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Study archiver initialized with archive directory: {self.archive_dir}")

    def create_study_archive(self, study_path: Path, archive_name: str) -> Optional[Path]:
        """
        Create a ZIP archive of a study directory.

        Args:
            study_path: Path to the study directory
            archive_name: Name for the archive (without .zip extension)

        Returns:
            Path to created ZIP file or None if failed
        """
        try:
            if not archive_name or not archive_name.strip():
                logger.error("Archive name cannot be empty")
                return None

            sanitized_name = archive_name.replace('/', '_').replace('\\', '_').replace('..', '_')
            if sanitized_name != archive_name:
                logger.warning(f"Archive name sanitized: '{archive_name}' -> '{sanitized_name}'")
                archive_name = sanitized_name

            if not study_path.exists():
                logger.error(f"Study path does not exist: {study_path}")
                return None

            if not study_path.is_dir():
                logger.error(f"Study path is not a directory: {study_path}")
                return None

            study_path = study_path.resolve()
            if '..' in str(study_path):
                logger.error(f"Suspicious path detected: {study_path}")
                return None

            import shutil
            stat = shutil.disk_usage(self.archive_dir)
            available_gb = stat.free / (1024 ** 3)

            if available_gb < 1.0:
                logger.error(f"⚠️  Low disk space: {available_gb:.2f} GB available")
                logger.error("Cannot create archive - insufficient disk space")
                return None

            zip_path = self.archive_dir / f"{archive_name}.zip"

            if zip_path.exists():
                logger.warning(f"Archive already exists, will overwrite: {zip_path}")
                zip_path.unlink()

            logger.info(f"Creating archive: {zip_path}")
            logger.info(f"Source directory: {study_path}")

            file_count = 0
            total_size = 0

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in study_path.rglob('*'):
                    if file_path.is_file():
                        # Calculate relative path for ZIP
                        arcname = file_path.relative_to(study_path.parent)
                        zipf.write(file_path, arcname)
                        file_count += 1
                        total_size += file_path.stat().st_size

            if file_count == 0:
                logger.error(f"No files found in study directory: {study_path}")
                if zip_path.exists():
                    zip_path.unlink()
                return None

            zip_size = zip_path.stat().st_size

            logger.info(f"✅ Archive created successfully:")
            logger.info(f"   Files: {file_count}")
            logger.info(f"   Original size: {total_size / 1024 / 1024:.2f} MB")
            logger.info(f"   Archive size: {zip_size / 1024 / 1024:.2f} MB")
            logger.info(f"   Compression: {(1 - zip_size / total_size) * 100:.1f}%")

            return zip_path

        except Exception as e:
            logger.error(f"Failed to create study archive: {e}", exc_info=True)
            return None

    def cleanup_archive(self, zip_path: Path) -> bool:
        """
        Delete a ZIP archive file.

        Args:
            zip_path: Path to ZIP file to delete

        Returns:
            bool: True if successful
        """
        try:
            if zip_path.exists():
                zip_path.unlink()
                logger.info(f"Deleted archive: {zip_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete archive {zip_path}: {e}")
            return False

    def cleanup_study_directory(self, study_path: Path) -> bool:
        """
        Delete a study directory and all its contents.

        Args:
            study_path: Path to study directory to delete

        Returns:
            bool: True if successful
        """
        try:
            if study_path.exists() and study_path.is_dir():
                import shutil
                shutil.rmtree(study_path)
                logger.info(f"Deleted study directory: {study_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete study directory {study_path}: {e}")
            return False
