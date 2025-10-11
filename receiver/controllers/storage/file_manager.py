"""
File Manager for DICOM storage operations.

Handles file system operations, path generation, and sanitization.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from pydicom import Dataset

logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages file system operations for DICOM storage.

    Responsibilities:
    - Path generation and sanitization
    - Directory creation
    - File storage operations
    - Path validation
    """

    def __init__(self, storage_dir: Path):
        """
        Initialize file manager.

        Args:
            storage_dir: Base directory for DICOM storage
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_uid(self, uid: str) -> str:
        """
        Sanitize UID for use in filesystem paths.

        Args:
            uid: DICOM UID to sanitize

        Returns:
            Sanitized UID safe for filesystem use
        """
        sanitized = uid.replace('.', '_').replace('/', '_').replace('\\', '_')

        if '..' in sanitized:
            logger.warning(f"Suspicious UID detected: {uid}")
            sanitized = sanitized.replace('..', '_')

        if len(sanitized) > 255:
            logger.warning(f"UID too long ({len(sanitized)} chars), truncating")
            sanitized = sanitized[:255]

        return sanitized

    def sanitize_patient_id(self, patient_id: str) -> str:
        """
        Sanitize patient ID for safe directory names.

        Args:
            patient_id: Patient ID to sanitize

        Returns:
            Sanitized patient ID
        """
        sanitized = "".join(c for c in patient_id if c.isalnum() or c in "._- ").strip()

        if not sanitized:
            sanitized = "unknown"

        if '..' in sanitized or '/' in sanitized or '\\' in sanitized:
            logger.warning(f"Suspicious patient_id detected: {patient_id}, using 'unknown'")
            sanitized = "unknown"

        if len(sanitized) > 255:
            logger.warning(f"Patient ID too long ({len(sanitized)} chars), truncating")
            sanitized = sanitized[:255]

        return sanitized

    def get_patient_path(self, patient_id: str) -> Path:
        """
        Get storage path for a patient.

        Args:
            patient_id: Patient ID

        Returns:
            Path to patient directory
        """
        sanitized_patient_id = self.sanitize_patient_id(patient_id)
        return self.storage_dir / sanitized_patient_id

    def get_study_path(self, patient_id: str, study_uid: str) -> Path:
        """
        Get storage path for a study.

        Args:
            patient_id: Patient ID
            study_uid: Study Instance UID

        Returns:
            Path to study directory
        """
        patient_path = self.get_patient_path(patient_id)
        sanitized_uid = self.sanitize_uid(study_uid)
        return patient_path / sanitized_uid

    def get_series_path(self, patient_id: str, study_uid: str, series_uid: str) -> Path:
        """
        Get storage path for a series.

        Args:
            patient_id: Patient ID
            study_uid: Study Instance UID
            series_uid: Series Instance UID

        Returns:
            Path to series directory
        """
        study_path = self.get_study_path(patient_id, study_uid)
        sanitized_series_uid = self.sanitize_uid(series_uid)
        return study_path / sanitized_series_uid

    def ensure_directory_exists(self, path: Path) -> bool:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path

        Returns:
            True if directory exists or was created
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}", exc_info=True)
            return False

    def save_dicom_file(self, dataset: Dataset, file_path: Path) -> bool:
        """
        Save a DICOM dataset to a file.

        Args:
            dataset: DICOM dataset to save
            file_path: Path where file should be saved

        Returns:
            True if successful
        """
        try:
            if file_path.exists():
                logger.warning(f"Duplicate instance detected, overwriting: {file_path.name}")

            dataset.save_as(str(file_path), write_like_original=False)

            logger.debug(f"Saved DICOM file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving DICOM file to {file_path}: {e}", exc_info=True)
            return False

    def get_file_size(self, file_path: Path) -> Optional[int]:
        """
        Get size of a file in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes, or None if error
        """
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Error getting file size for {file_path}: {e}")
            return None

    def file_exists(self, file_path: Path) -> bool:
        """
        Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists
        """
        return file_path.exists() and file_path.is_file()

    def directory_exists(self, dir_path: Path) -> bool:
        """
        Check if a directory exists.

        Args:
            dir_path: Path to check

        Returns:
            True if directory exists
        """
        return dir_path.exists() and dir_path.is_dir()
