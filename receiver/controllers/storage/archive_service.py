"""
Archive Service Module

Handles study archiving and cleanup operations including:
- Study ZIP archive creation
- Archive cleanup
- Study directory cleanup
- Disk space management
"""
import logging
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ArchiveService:
    """
    Manages study archiving and cleanup operations.

    Responsibilities:
    - Create ZIP archives of completed studies
    - Clean up study directories after upload
    - Clean up ZIP archives
    - Monitor disk space
    - Thread-safe archive operations
    """

    def __init__(self, archive_dir: str = 'archives') -> None:
        """
        Initialize archive service.

        Args:
            archive_dir: Directory to store ZIP archives
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._lock: threading.Lock = threading.Lock()

    def _create_zip_archive(self, study_path: Path, archive_name: str) -> Path:
        """
        Internal method to create ZIP archive.

        Args:
            study_path: Path to the study directory
            archive_name: Name for the archive (without .zip extension)

        Returns:
            Path to created ZIP file

        Raises:
            Exception: If archive creation fails
        """
        if not archive_name.endswith('.zip'):
            archive_name = f"{archive_name}.zip"

        zip_path = self.archive_dir / archive_name

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in study_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(study_path.parent)
                    zipf.write(file_path, arcname)

        return zip_path

    def create_study_archive(
        self,
        study_path: Path,
        archive_name: str
    ) -> Optional[Path]:
        """
        Create a ZIP archive of a study directory.

        Thread-safe operation that validates disk space before creating archive.

        Args:
            study_path: Path to the study directory
            archive_name: Name for the archive (without .zip extension)

        Returns:
            Path to created ZIP file or None if failed
        """
        with self._lock:
            if not study_path or not study_path.exists():
                logger.error(f"Study path does not exist: {study_path}")
                return None

            if not study_path.is_dir():
                logger.error(f"Study path is not a directory: {study_path}")
                return None

            disk_space = self.get_disk_space_info()
            if disk_space['available_gb'] < 1.0:
                logger.error(
                    f"Cannot create archive - insufficient disk space: "
                    f"{disk_space['available_gb']:.2f} GB available"
                )
                return None

            logger.info(f"Creating archive for study: {study_path}")
            logger.info(f"Archive name: {archive_name}")

            try:
                zip_path = self._create_zip_archive(study_path, archive_name)
                logger.info(f"Successfully created archive: {zip_path}")
                return zip_path
            except Exception as e:
                logger.error(f"Failed to create archive for study: {study_path}: {e}", exc_info=True)
                return None

    def cleanup_archive(self, zip_path: Path) -> bool:
        """
        Delete a ZIP archive file.

        Args:
            zip_path: Path to ZIP file to delete

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if not zip_path or not zip_path.exists():
                logger.warning(f"Archive does not exist: {zip_path}")
                return False

            try:
                zip_path.unlink()
                logger.info(f"Cleaned up archive: {zip_path}")
                return True

            except FileNotFoundError:
                logger.warning(f"Archive not found: {zip_path}")
                return False
            except Exception as e:
                logger.error(f"Error cleaning up archive {zip_path}: {e}", exc_info=True)
                return False

    def cleanup_study_directory(self, study_path: Path) -> bool:
        """
        Delete a study directory and all its contents.

        CAUTION: This permanently deletes all DICOM files in the study directory.

        Args:
            study_path: Path to study directory to delete

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if not study_path or not study_path.exists():
                logger.warning(f"Study directory does not exist: {study_path}")
                return False

            if not study_path.is_dir():
                logger.error(f"Study path is not a directory: {study_path}")
                return False

            try:
                shutil.rmtree(study_path)
                logger.info(f"Cleaned up study directory: {study_path}")
                return True

            except FileNotFoundError:
                logger.warning(f"Study directory not found: {study_path}")
                return False
            except Exception as e:
                logger.error(f"Error cleaning up study directory {study_path}: {e}", exc_info=True)
                return False

    def archive_and_cleanup_study(
        self,
        study_path: Path,
        archive_name: str,
        cleanup_after_archive: bool = False
    ) -> Optional[Path]:
        """
        Create archive and optionally cleanup study directory.

        This is a convenience method that combines archiving and cleanup.

        Args:
            study_path: Path to the study directory
            archive_name: Name for the archive (without .zip extension)
            cleanup_after_archive: If True, delete study directory after successful archive

        Returns:
            Path to created ZIP file or None if failed
        """
        zip_path = self.create_study_archive(study_path, archive_name)

        if not zip_path:
            logger.error(f"Archive creation failed, skipping cleanup for: {study_path}")
            return None

        if cleanup_after_archive:
            logger.info(f"Cleaning up study directory after successful archive: {study_path}")
            cleanup_success = self.cleanup_study_directory(study_path)

            if not cleanup_success:
                logger.warning(
                    f"Archive created but cleanup failed: {study_path}. "
                    f"Archive at: {zip_path}"
                )

        return zip_path

    def get_disk_space_info(self) -> Dict[str, Any]:
        """
        Get disk space information for the archive directory.

        Returns:
            Dict with disk space information:
                - total_gb: Total disk space in GB
                - used_gb: Used disk space in GB
                - free_gb: Free disk space in GB
                - available_gb: Available disk space in GB
                - percent_used: Percentage of disk space used
        """
        try:
            stat = shutil.disk_usage(self.archive_dir)

            total_gb = stat.total / (1024 ** 3)
            used_gb = stat.used / (1024 ** 3)
            free_gb = stat.free / (1024 ** 3)
            percent_used = (stat.used / stat.total) * 100 if stat.total > 0 else 0

            return {
                'total_gb': total_gb,
                'used_gb': used_gb,
                'free_gb': free_gb,
                'available_gb': free_gb,
                'percent_used': percent_used,
            }

        except Exception as e:
            logger.error(f"Error getting disk space info: {e}")
            return {
                'total_gb': 0,
                'used_gb': 0,
                'free_gb': 0,
                'available_gb': 0,
                'percent_used': 0,
            }

    def check_disk_space(self, min_required_gb: float = 1.0) -> bool:
        """
        Check if sufficient disk space is available.

        Args:
            min_required_gb: Minimum required disk space in GB

        Returns:
            True if sufficient space available, False otherwise
        """
        disk_info = self.get_disk_space_info()
        available = disk_info['available_gb']

        if available < min_required_gb:
            logger.warning(
                f"Low disk space: {available:.2f} GB available "
                f"(minimum required: {min_required_gb:.2f} GB)"
            )
            return False

        return True

    def get_archive_path(self, archive_name: str) -> Path:
        """
        Get the full path for an archive file.

        Args:
            archive_name: Name of the archive (with or without .zip extension)

        Returns:
            Full path to the archive file
        """
        if not archive_name.endswith('.zip'):
            archive_name = f"{archive_name}.zip"

        return self.archive_dir / archive_name

    def archive_exists(self, archive_name: str) -> bool:
        """
        Check if an archive file exists.

        Args:
            archive_name: Name of the archive (with or without .zip extension)

        Returns:
            True if archive exists, False otherwise
        """
        archive_path = self.get_archive_path(archive_name)
        return archive_path.exists() and archive_path.is_file()

    def get_archive_size(self, archive_name: str) -> Optional[int]:
        """
        Get the size of an archive file in bytes.

        Args:
            archive_name: Name of the archive (with or without .zip extension)

        Returns:
            Size in bytes, or None if archive doesn't exist
        """
        archive_path = self.get_archive_path(archive_name)

        try:
            if archive_path.exists() and archive_path.is_file():
                return archive_path.stat().st_size
            return None
        except Exception as e:
            logger.error(f"Error getting archive size: {e}")
            return None

    def cleanup_old_archives(self, max_age_days: int = 7) -> int:
        """
        Delete archive files older than specified age.

        Args:
            max_age_days: Maximum age of archives to keep (in days)

        Returns:
            Number of archives deleted
        """
        with self._lock:
            import time

            try:
                deleted_count = 0
                max_age_seconds = max_age_days * 24 * 60 * 60
                current_time = time.time()

                for archive_file in self.archive_dir.glob('*.zip'):
                    try:
                        file_age = current_time - archive_file.stat().st_mtime

                        if file_age > max_age_seconds:
                            archive_file.unlink()
                            logger.info(
                                f"Deleted old archive ({file_age / 86400:.1f} days old): "
                                f"{archive_file.name}"
                            )
                            deleted_count += 1

                    except Exception as e:
                        logger.error(f"Error deleting archive {archive_file}: {e}")
                        continue

                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old archive(s)")
                else:
                    logger.debug("No old archives to clean up")

                return deleted_count

            except Exception as e:
                logger.error(f"Error cleaning up old archives: {e}", exc_info=True)
                return 0
