"""
Storage Manager Module
Facade for DICOM file storage and study organization.
Delegates to specialized services for file operations, study lifecycle, and archiving.
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
from pydicom import Dataset
from django.conf import settings

from .storage import FileManager, StudyService, ArchiveService

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Facade for DICOM file storage and study management.

    Delegates operations to specialized services:
    - FileManager: File system operations and path management
    - StudyService: Study and series lifecycle management
    - ArchiveService: Study archiving and cleanup
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        """
        Initialize storage manager and underlying services.

        Args:
            storage_dir: Base directory for DICOM storage
        """
        self.storage_dir: Path = Path(storage_dir or getattr(settings, 'DICOM_STORAGE_DIR', 'storage'))

        self.file_manager = FileManager(self.storage_dir)
        self.study_service = StudyService()
        self.archive_service = ArchiveService(archive_dir=getattr(settings, 'ARCHIVE_DIR', str(Path('data') / 'archives')))

    def _sanitize_uid(self, uid: str) -> str:
        """Sanitize UID for use in filesystem paths."""
        return self.file_manager.sanitize_uid(uid)

    def _sanitize_patient_id(self, patient_id: str) -> str:
        """Sanitize patient ID for safe directory names."""
        return self.file_manager.sanitize_patient_id(patient_id)

    def _get_patient_path(self, patient_id: str) -> Path:
        """Get storage path for a patient."""
        return self.file_manager.get_patient_path(patient_id)

    def _get_study_path(self, patient_id: str, study_instance_uid: str) -> Path:
        """Get storage path for a study."""
        return self.file_manager.get_study_path(patient_id, study_instance_uid)

    def _get_series_path(self, patient_id: str, study_instance_uid: str, series_instance_uid: str) -> Path:
        """Get storage path for a series."""
        return self.file_manager.get_series_path(patient_id, study_instance_uid, series_instance_uid)

    def store_dicom_file(
        self,
        dataset: Dataset,
        filename: str,
        study_phi_metadata: Optional[Dict[str, str]] = None,
        series_phi_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Store a DICOM file and update database records.
        Instance metadata is stored in XML file for performance.

        Delegates to:
        - StudyService: Study and series creation/updates
        - FileManager: Directory creation and file storage

        Args:
            dataset: pydicom Dataset object
            filename: Filename for the DICOM file
            study_phi_metadata: Study-level PHI metadata to store
            series_phi_metadata: Series-level PHI metadata to store

        Returns:
            Dict containing study and series objects
        """
        study_uid = dataset.StudyInstanceUID
        series_uid = dataset.SeriesInstanceUID
        sop_uid = dataset.SOPInstanceUID

        patient_name = getattr(dataset, 'PatientName', 'UNKNOWN')
        patient_id = getattr(dataset, 'PatientID', 'UNKNOWN')

        study_path = str(self._get_study_path(str(patient_id), study_uid))
        study, study_created = self.study_service.get_or_create_study(
            study_uid=study_uid,
            patient_name=str(patient_name),
            patient_id=str(patient_id),
            storage_path=study_path,
            dataset=dataset,
            study_phi_metadata=study_phi_metadata
        )

        series_path = self._get_series_path(str(patient_id), study_uid, series_uid)
        series, series_created = self.study_service.get_or_create_series(
            series_uid=series_uid,
            study=study,
            storage_path=str(series_path),
            dataset=dataset,
            series_phi_metadata=series_phi_metadata
        )

        self.file_manager.ensure_directory_exists(series_path)

        file_path = series_path / filename
        success = self.file_manager.save_dicom_file(dataset, file_path)

        if not success:
            logger.error(f"Failed to save DICOM file: {file_path}")

        file_size = self.file_manager.get_file_size(file_path) or 0

        self.study_service.add_instance_to_series(
            series=series,
            sop_instance_uid=sop_uid,
            filename=filename,
            file_size=file_size,
            dataset=dataset
        )

        return {
            'study': study,
            'series': series,
        }

    def get_study(self, study_instance_uid: str) -> Optional[Any]:
        """Get a study by UID."""
        return self.study_service.get_study(study_instance_uid)

    def mark_study_complete(self, study_instance_uid: str) -> bool:
        """
        Mark a study as complete.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            True if successful, False otherwise
        """
        return self.study_service.mark_study_complete(study_instance_uid)

    def get_incomplete_studies(self) -> List[Any]:
        """Get all incomplete studies."""
        return self.study_service.get_incomplete_studies()

    def get_study_statistics(self, study_instance_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a study.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            Dict with study statistics or None
        """
        return self.study_service.get_study_statistics(study_instance_uid)
