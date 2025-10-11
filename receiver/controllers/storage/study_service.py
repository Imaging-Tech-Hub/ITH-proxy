"""
Study Service Module

Handles study lifecycle management including:
- Study and series creation
- Study completion tracking
- Study statistics
- Database operations for sessions/scans
"""
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List
from django.utils import timezone
from pydicom import Dataset

from receiver.models import Session, Scan
from receiver.utils.storage import InstanceMetadataHandler

logger = logging.getLogger(__name__)


class StudyService:
    """
    Manages study and series lifecycle operations.

    Responsibilities:
    - Study creation and updates
    - Series creation and updates
    - Study completion tracking
    - Study statistics and queries
    - Instance metadata management
    """

    def __init__(self) -> None:
        """Initialize study service."""
        self._lock: threading.Lock = threading.Lock()
        self.instance_metadata_handler: InstanceMetadataHandler = InstanceMetadataHandler()

    def get_or_create_study(
        self,
        study_uid: str,
        patient_name: str,
        patient_id: str,
        storage_path: str,
        dataset: Dataset
    ) -> tuple[Session, bool]:
        """
        Get or create a study (Session) in the database.

        Args:
            study_uid: Study Instance UID
            patient_name: Patient name
            patient_id: Patient ID
            storage_path: Path where study files are stored
            dataset: DICOM dataset containing study metadata

        Returns:
            Tuple of (study, created) where created is True if newly created
        """
        with self._lock:
            study, created = Session.objects.get_or_create(
                study_instance_uid=study_uid,
                defaults={
                    'patient_name': str(patient_name),
                    'patient_id': str(patient_id),
                    'study_date': getattr(dataset, 'StudyDate', None),
                    'study_time': getattr(dataset, 'StudyTime', None),
                    'study_description': getattr(dataset, 'StudyDescription', ''),
                    'accession_number': getattr(dataset, 'AccessionNumber', ''),
                    'storage_path': storage_path,
                    'status': 'incomplete',
                }
            )

            if created:
                logger.info(f"Created new study: {study_uid} for patient {patient_id}")
            else:
                study.last_received_at = timezone.now()
                study.save(update_fields=['last_received_at'])
                logger.debug(f"Updated study timestamp: {study_uid}")

            return study, created

    def get_or_create_series(
        self,
        series_uid: str,
        study: Session,
        storage_path: str,
        dataset: Dataset
    ) -> tuple[Scan, bool]:
        """
        Get or create a series (Scan) in the database.

        Args:
            series_uid: Series Instance UID
            study: Parent study (Session) object
            storage_path: Path where series files are stored
            dataset: DICOM dataset containing series metadata

        Returns:
            Tuple of (series, created) where created is True if newly created
        """
        with self._lock:
            series, created = Scan.objects.get_or_create(
                series_instance_uid=series_uid,
                defaults={
                    'session': study,
                    'series_number': getattr(dataset, 'SeriesNumber', None),
                    'series_description': getattr(dataset, 'SeriesDescription', ''),
                    'modality': getattr(dataset, 'Modality', ''),
                    'storage_path': storage_path,
                    'instances_count': 0,
                }
            )

            if created:
                logger.info(f"Created new series: {series_uid} in study {study.study_instance_uid}")
            else:
                logger.debug(f"Using existing series: {series_uid}")

            return series, created

    def add_instance_to_series(
        self,
        series: Scan,
        sop_instance_uid: str,
        filename: str,
        file_size: int,
        dataset: Dataset
    ) -> bool:
        """
        Add an instance to a series and update instance count.

        Args:
            series: Series (Scan) object
            sop_instance_uid: SOP Instance UID
            filename: Name of the DICOM file
            file_size: Size of the file in bytes
            dataset: DICOM dataset

        Returns:
            True if instance was added (new instance), False if duplicate
        """
        with self._lock:
            xml_path = series.get_instances_xml_path()
            instance_number = getattr(dataset, 'InstanceNumber', 0)

            transfer_syntax = ''
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)

            instance_added = self.instance_metadata_handler.add_instance(
                xml_path=xml_path,
                sop_instance_uid=sop_instance_uid,
                instance_number=instance_number,
                file_name=filename,
                file_size=file_size,
                transfer_syntax_uid=transfer_syntax
            )

            if instance_added:
                new_count = self.instance_metadata_handler.get_instance_count(xml_path)
                series.instances_count = new_count
                series.save(update_fields=['instances_count'])

                logger.debug(f"Added instance {sop_instance_uid} to series {series.series_instance_uid} (count: {new_count})")
                return True
            else:
                logger.debug(f"Duplicate instance {sop_instance_uid} in series {series.series_instance_uid}")
                return False

    def get_study(self, study_instance_uid: str) -> Optional[Session]:
        """
        Get a study by UID.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            Study (Session) object or None if not found
        """
        try:
            return Session.objects.get(study_instance_uid=study_instance_uid)
        except Session.DoesNotExist:
            logger.debug(f"Study not found: {study_instance_uid}")
            return None

    def mark_study_complete(self, study_instance_uid: str) -> bool:
        """
        Mark a study as complete.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            True if successful, False if study not found
        """
        with self._lock:
            try:
                study = Session.objects.get(study_instance_uid=study_instance_uid)
                study.status = 'complete'
                study.completed_at = timezone.now()
                study.save(update_fields=['status', 'completed_at'])

                logger.info(f"Marked study complete: {study_instance_uid}")
                return True

            except Session.DoesNotExist:
                logger.warning(f"Cannot mark study complete - not found: {study_instance_uid}")
                return False

    def get_incomplete_studies(self) -> List[Session]:
        """
        Get all incomplete studies.

        Returns:
            List of incomplete study (Session) objects
        """
        return list(Session.objects.filter(status='incomplete'))

    def get_study_statistics(self, study_instance_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a study.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            Dict with study statistics:
                - study_uid: Study Instance UID
                - patient_name: Patient name
                - patient_id: Patient ID
                - series_count: Number of series
                - instances_count: Total instances across all series
                - status: Study status
                - storage_path: Study storage path
            Returns None if study not found
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
            logger.debug(f"Study not found for statistics: {study_instance_uid}")
            return None

    def get_series_by_uid(self, series_instance_uid: str) -> Optional[Scan]:
        """
        Get a series by UID.

        Args:
            series_instance_uid: Series Instance UID

        Returns:
            Series (Scan) object or None if not found
        """
        try:
            return Scan.objects.get(series_instance_uid=series_instance_uid)
        except Scan.DoesNotExist:
            logger.debug(f"Series not found: {series_instance_uid}")
            return None

    def get_study_series(self, study_instance_uid: str) -> List[Scan]:
        """
        Get all series for a study.

        Args:
            study_instance_uid: Study Instance UID

        Returns:
            List of series (Scan) objects
        """
        try:
            study = Session.objects.get(study_instance_uid=study_instance_uid)
            return list(study.scans.all())
        except Session.DoesNotExist:
            logger.debug(f"Study not found: {study_instance_uid}")
            return []

    def get_instance_metadata(self, series: Scan) -> List[Dict[str, Any]]:
        """
        Get instance metadata for a series.

        Args:
            series: Series (Scan) object

        Returns:
            List of instance metadata dictionaries
        """
        xml_path = series.get_instances_xml_path()
        return self.instance_metadata_handler.get_all_instances(xml_path)

    def update_study_metadata(
        self,
        study_instance_uid: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update study metadata fields.

        Args:
            study_instance_uid: Study Instance UID
            updates: Dict of field names and values to update

        Returns:
            True if successful, False if study not found
        """
        with self._lock:
            try:
                study = Session.objects.get(study_instance_uid=study_instance_uid)

                allowed_fields = [
                    'patient_name', 'patient_id', 'study_date', 'study_time',
                    'study_description', 'accession_number', 'status'
                ]

                updated_fields = []
                for field, value in updates.items():
                    if field in allowed_fields and hasattr(study, field):
                        setattr(study, field, value)
                        updated_fields.append(field)

                if updated_fields:
                    study.save(update_fields=updated_fields)
                    logger.info(f"Updated study {study_instance_uid} fields: {updated_fields}")
                    return True

                return False

            except Session.DoesNotExist:
                logger.warning(f"Cannot update study - not found: {study_instance_uid}")
                return False
