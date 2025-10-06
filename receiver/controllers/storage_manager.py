"""
Storage Manager Module
Handles DICOM file storage and study organization.
Thread-safe operations for concurrent file storage.
Instance metadata is stored in XML files for performance.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List
from pydicom import Dataset
from django.utils import timezone
from django.conf import settings
from receiver.models import Session, Scan
from receiver.utils.instance_metadata import InstanceMetadataHandler

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages DICOM file storage and study/series organization.
    Provides thread-safe file operations and study lifecycle management.
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self.storage_dir: Path = Path(storage_dir or getattr(settings, 'DICOM_STORAGE_DIR', 'storage'))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock: threading.Lock = threading.Lock()
        self._study_timers: Dict[str, Any] = {}
        self.instance_metadata_handler: InstanceMetadataHandler = InstanceMetadataHandler()

    def _sanitize_uid(self, uid: str) -> str:
        """Sanitize UID for use in filesystem paths."""
        sanitized = uid.replace('.', '_').replace('/', '_').replace('\\', '_')

        if '..' in sanitized:
            logger.warning(f"Suspicious UID detected: {uid}")
            sanitized = sanitized.replace('..', '_')

        if len(sanitized) > 255:
            logger.warning(f"UID too long ({len(sanitized)} chars), truncating")
            sanitized = sanitized[:255]

        return sanitized

    def _sanitize_patient_id(self, patient_id: str) -> str:
        """Sanitize patient ID for safe directory names."""
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

    def _get_patient_path(self, patient_id: str) -> Path:
        """Get storage path for a patient."""
        sanitized_patient_id = self._sanitize_patient_id(patient_id)
        return self.storage_dir / sanitized_patient_id

    def _get_study_path(self, patient_id: str, study_instance_uid: str) -> Path:
        """Get storage path for a study."""
        patient_path = self._get_patient_path(patient_id)
        sanitized_uid = self._sanitize_uid(study_instance_uid)
        return patient_path / sanitized_uid

    def _get_series_path(self, patient_id: str, study_instance_uid: str, series_instance_uid: str) -> Path:
        """Get storage path for a series."""
        study_path = self._get_study_path(patient_id, study_instance_uid)
        sanitized_series_uid = self._sanitize_uid(series_instance_uid)
        return study_path / sanitized_series_uid

    def store_dicom_file(self, dataset: Dataset, filename: str) -> Dict[str, Any]:
        """
        Store a DICOM file and update database records.
        Instance metadata is stored in XML file for performance.

        Args:
            dataset: pydicom Dataset object
            filename: Filename for the DICOM file

        Returns:
            Dict containing study and series objects
        """
        with self._lock:
            study_uid = dataset.StudyInstanceUID
            series_uid = dataset.SeriesInstanceUID
            sop_uid = dataset.SOPInstanceUID

            patient_name = getattr(dataset, 'PatientName', 'UNKNOWN')
            patient_id = getattr(dataset, 'PatientID', 'UNKNOWN')

            study, study_created = Session.objects.get_or_create(
                study_instance_uid=study_uid,
                defaults={
                    'patient_name': str(patient_name),
                    'patient_id': str(patient_id),
                    'study_date': getattr(dataset, 'StudyDate', None),
                    'study_time': getattr(dataset, 'StudyTime', None),
                    'study_description': getattr(dataset, 'StudyDescription', ''),
                    'accession_number': getattr(dataset, 'AccessionNumber', ''),
                    'storage_path': str(self._get_study_path(str(patient_id), study_uid)),
                    'status': 'incomplete',
                }
            )

            if not study_created:
                study.last_received_at = timezone.now()
                study.save(update_fields=['last_received_at'])

            series, series_created = Scan.objects.get_or_create(
                series_instance_uid=series_uid,
                defaults={
                    'session': study,
                    'series_number': getattr(dataset, 'SeriesNumber', None),
                    'series_description': getattr(dataset, 'SeriesDescription', ''),
                    'modality': getattr(dataset, 'Modality', ''),
                    'storage_path': str(self._get_series_path(str(patient_id), study_uid, series_uid)),
                    'instances_count': 0,
                }
            )

            series_path = Path(series.storage_path)
            series_path.mkdir(parents=True, exist_ok=True)

            file_path = series_path / filename

            if file_path.exists():
                logger.warning(f"Duplicate instance detected, overwriting: {filename}")

            dataset.save_as(str(file_path), enforce_file_format=True)

            file_size = os.path.getsize(file_path)

            xml_path = series.get_instances_xml_path()
            instance_number = getattr(dataset, 'InstanceNumber', 0)
            transfer_syntax = ''
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)

            instance_added = self.instance_metadata_handler.add_instance(
                xml_path=xml_path,
                sop_instance_uid=sop_uid,
                instance_number=instance_number,
                file_name=filename,
                file_size=file_size,
                transfer_syntax_uid=transfer_syntax
            )

            if instance_added:
                new_count = self.instance_metadata_handler.get_instance_count(xml_path)
                series.instances_count = new_count
                series.save(update_fields=['instances_count'])

            return {
                'study': study,
                'series': series,
            }

    def get_study(self, study_instance_uid: str) -> Optional[Session]:
        """Get a study by UID."""
        try:
            return Session.objects.get(study_instance_uid=study_instance_uid)
        except Session.DoesNotExist:
            return None

    def mark_study_complete(self, study_instance_uid: str) -> bool:
        """
        Mark a study as complete.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            try:
                study = Session.objects.get(study_instance_uid=study_instance_uid)
                study.status = 'complete'
                study.completed_at = timezone.now()
                study.save(update_fields=['status', 'completed_at'])
                return True
            except Session.DoesNotExist:
                return False

    def get_incomplete_studies(self) -> List[Session]:
        """Get all incomplete studies."""
        return list(Session.objects.filter(status='incomplete'))

    def get_study_statistics(self, study_instance_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a study.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            Dict with study statistics or None
        """
        try:
            study = Session.objects.get(study_instance_uid=study_instance_uid)
            series_count = study.scans.count()
            total_instances = sum(s.instances_count for s in study.scans.all())

            return {
                'study_uid': study.study_instance_uid,
                'patient_name': study.patient_name,
                'patient_id': study.patient_id,
                'series_count': series_count,
                'instances_count': total_instances,
                'status': study.status,
                'storage_path': study.storage_path,
            }
        except Session.DoesNotExist:
            return None
