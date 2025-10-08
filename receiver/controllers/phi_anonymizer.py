"""
PHI Anonymizer Module
Uses pydicom's built-in anonymization for DICOM de-identification.
Follows DICOM PS3.15 Annex E de-identification profiles.
"""
import threading
from typing import Dict, Tuple, Optional, List, Callable
from pydicom import Dataset
from pydicom.datadict import keyword_for_tag
from receiver.models import PatientMapping
import logging

logger = logging.getLogger(__name__)


class PHIAnonymizer:
    """
    Anonymizes patient health information (PHI) in DICOM files.
    Uses pydicom's standard anonymization with custom patient mapping.
    """

    # DICOM Basic Application Level Confidentiality Profile (PS3.15 Annex E)
    # Tags to store and clear/anonymize (will be restored on query)
    TAGS_TO_ANONYMIZE = [
        # Patient identifiers
        'PatientName',
        'PatientID',
        'PatientBirthDate',
        'PatientBirthName',
        'PatientAge',
        'PatientSize',
        'PatientWeight',
        'PatientSex',
        'OtherPatientIDs',
        'OtherPatientNames',
        'EthnicGroup',
        'Occupation',
        'AdditionalPatientHistory',
        'PatientComments',
        'MedicalRecordLocator',
        # Study/Series information - dates/times only
        'StudyDate',
        'SeriesDate',
        'AcquisitionDate',
        'ContentDate',
        'StudyTime',
        'SeriesTime',
        'AcquisitionTime',
        'ContentTime',
        'StudyID',
        # NOTE: ProtocolName excluded - needed for clinical interpretation
        # NOTE: SeriesDescription excluded - needed for scan identification
        # NOTE: StudyDescription excluded - needed for study context
        # Institution/Personnel information
        'InstitutionName',
        'InstitutionAddress',
        'InstitutionalDepartmentName',
        'StationName',
        'ReferringPhysicianName',
        'ReferringPhysicianAddress',
        'ReferringPhysicianTelephoneNumbers',
        'PhysiciansOfRecord',
        'PerformingPhysicianName',
        'NameOfPhysiciansReadingStudy',
        'OperatorsName',
        # Device/Technical information
        'DeviceSerialNumber',
        # Comments and other descriptive fields
        'ImageComments',
        'IssuerOfPatientID',
    ]

    TAGS_TO_REMOVE = [
        'FrameOfReferenceUID',
        'SynchronizationFrameOfReferenceUID',
        'RequestAttributesSequence',
        'UID',
        'StorageMediaFileSetUID',
        'ReferencedFrameOfReferenceUID',
        'RelatedFrameOfReferenceUID',
    ]

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._counter_cache: Optional[int] = None

    def _get_next_counter(self) -> int:
        """Get the next available counter for anonymous IDs."""
        if self._counter_cache is None:
            last_mapping = PatientMapping.objects.order_by('-id').first()
            if last_mapping:
                try:
                    self._counter_cache = int(last_mapping.anonymous_patient_name.split('-')[1]) + 1
                except (IndexError, ValueError):
                    self._counter_cache = 1
            else:
                self._counter_cache = 1
        else:
            self._counter_cache += 1

        return self._counter_cache

    def anonymize_patient(self, patient_name: str, patient_id: str) -> Dict[str, str]:
        """
        Anonymize patient information.

        Args:
            patient_name: Original patient name
            patient_id: Original patient ID

        Returns:
            Dict containing:
                - anonymous_name: Anonymous patient name (e.g., "ANON-00001")
                - anonymous_id: Anonymous patient ID (e.g., "ANON-00001")
                - original_name: Original patient name
                - original_id: Original patient ID
        """
        with self._lock:
            mapping = PatientMapping.objects.filter(
                original_patient_name=patient_name,
                original_patient_id=patient_id
            ).first()

            if mapping:
                return {
                    'anonymous_name': mapping.anonymous_patient_name,
                    'anonymous_id': mapping.anonymous_patient_id,
                    'original_name': mapping.original_patient_name,
                    'original_id': mapping.original_patient_id,
                }

            anonymous_name = f"ANON-{patient_id}"
            anonymous_id = f"ANON-{patient_id}"

            try:
                mapping = PatientMapping.objects.create(
                    original_patient_name=patient_name,
                    original_patient_id=patient_id,
                    anonymous_patient_name=anonymous_name,
                    anonymous_patient_id=anonymous_id
                )
            except Exception as e:
                mapping = PatientMapping.objects.filter(
                    anonymous_patient_id=anonymous_id
                ).first()

                if mapping:
                    logger.info(f"Reusing existing mapping for patient {patient_id}: {anonymous_id}")
                    return {
                        'anonymous_name': mapping.anonymous_patient_name,
                        'anonymous_id': mapping.anonymous_patient_id,
                        'original_name': mapping.original_patient_name,
                        'original_id': mapping.original_patient_id,
                    }
                else:
                    raise e

            logger.info(f"Created anonymization: {patient_name} ({patient_id}) → {anonymous_name} ({anonymous_id})")

            return {
                'anonymous_name': mapping.anonymous_patient_name,
                'anonymous_id': mapping.anonymous_patient_id,
                'original_name': mapping.original_patient_name,
                'original_id': mapping.original_patient_id,
            }

    def anonymize_dataset(self, dataset: Dataset) -> Tuple[Dataset, Dict[str, str]]:
        """
        Anonymize patient data in a DICOM dataset using pydicom built-in methods.
        Stores removed PHI data for later restoration.

        Args:
            dataset: pydicom Dataset object

        Returns:
            Tuple of (anonymized_dataset, mapping_info)
        """
        patient_name = str(getattr(dataset, 'PatientName', 'UNKNOWN'))
        patient_id = str(getattr(dataset, 'PatientID', 'UNKNOWN'))

        phi_metadata = self._extract_phi_metadata(dataset)

        mapping = self.anonymize_patient(patient_name, patient_id)

        self._store_phi_metadata(patient_name, patient_id, phi_metadata)

        self._apply_pydicom_anonymization(dataset, mapping)

        return dataset, mapping

    def _extract_phi_metadata(self, dataset: Dataset) -> Dict[str, str]:
        """
        Extract PHI metadata before anonymization.

        Args:
            dataset: DICOM dataset

        Returns:
            Dict of tag names and their values
        """
        phi_data = {}

        for tag_name in self.TAGS_TO_ANONYMIZE:
            if hasattr(dataset, tag_name):
                value = getattr(dataset, tag_name)
                if value:
                    phi_data[tag_name] = str(value)

        return phi_data

    def _store_phi_metadata(self, patient_name: str, patient_id: str, phi_metadata: Dict[str, str]) -> None:
        """
        Store PHI metadata in PatientMapping.

        Args:
            patient_name: Original patient name
            patient_id: Original patient ID
            phi_metadata: Extracted PHI data
        """
        try:
            mapping = PatientMapping.objects.filter(
                original_patient_name=patient_name,
                original_patient_id=patient_id
            ).first()

            if mapping and phi_metadata:
                existing_metadata = mapping.get_phi_metadata()
                existing_metadata.update(phi_metadata)
                mapping.set_phi_metadata(existing_metadata)
                logger.debug(f"Stored PHI metadata for {mapping.anonymous_patient_name}")
        except Exception as e:
            logger.error(f"Error storing PHI metadata: {e}", exc_info=True)

    def _apply_pydicom_anonymization(self, dataset: Dataset, mapping: Dict[str, str]) -> None:
        """
        Apply de-identification by clearing/anonymizing PHI fields.
        All PHI data is stored in mapping and can be restored later.

        Args:
            dataset: DICOM dataset to anonymize (modified in-place)
            mapping: Patient mapping information
        """

        for tag_name in self.TAGS_TO_ANONYMIZE:
            if hasattr(dataset, tag_name):
                if tag_name == 'PatientName':
                    setattr(dataset, tag_name, mapping['anonymous_name'])
                elif tag_name == 'PatientID':
                    setattr(dataset, tag_name, mapping['anonymous_id'])
                elif tag_name in ['PatientBirthDate']:
                    setattr(dataset, tag_name, '19700101')
                elif tag_name in ['StudyDate', 'SeriesDate', 'AcquisitionDate', 'ContentDate']:
                    setattr(dataset, tag_name, '19700101')
                elif tag_name in ['StudyTime', 'SeriesTime', 'AcquisitionTime', 'ContentTime']:
                    setattr(dataset, tag_name, '000000')
                else:
                    setattr(dataset, tag_name, '')

        for tag_name in self.TAGS_TO_REMOVE:
            if hasattr(dataset, tag_name):
                delattr(dataset, tag_name)

        dataset.remove_private_tags()

        logger.debug(f"Applied anonymization: {mapping['original_name']} → {mapping['anonymous_name']}")

    def anonymize_with_custom_actions(
        self,
        dataset: Dataset,
        custom_actions: Optional[List[Callable]] = None,
        remove_private_tags: bool = True
    ) -> Tuple[Dataset, Dict[str, str]]:
        """
        Anonymize with custom action callbacks.

        Args:
            dataset: DICOM dataset
            custom_actions: List of callback functions to apply (dataset, element) -> None
            remove_private_tags: Whether to remove private tags

        Returns:
            Tuple of (anonymized_dataset, mapping_info)
        """
        patient_name = str(getattr(dataset, 'PatientName', 'UNKNOWN'))
        patient_id = str(getattr(dataset, 'PatientID', 'UNKNOWN'))

        mapping = self.anonymize_patient(patient_name, patient_id)

        self._apply_pydicom_anonymization(dataset, mapping)

        if custom_actions:
            for action in custom_actions:
                dataset.walk(action)

        logger.info(f"Applied custom anonymization with {len(custom_actions or [])} custom actions")

        return dataset, mapping

    def get_mapping(self, anonymous_name: str = None, anonymous_id: str = None) -> Optional[Dict[str, str]]:
        """
        Retrieve mapping information by anonymous identifier.

        Args:
            anonymous_name: Anonymous patient name
            anonymous_id: Anonymous patient ID

        Returns:
            Mapping dictionary or None if not found
        """
        mapping = None

        if anonymous_name:
            mapping = PatientMapping.objects.filter(
                anonymous_patient_name=anonymous_name
            ).first()
        elif anonymous_id:
            mapping = PatientMapping.objects.filter(
                anonymous_patient_id=anonymous_id
            ).first()

        if mapping:
            return {
                'anonymous_name': mapping.anonymous_patient_name,
                'anonymous_id': mapping.anonymous_patient_id,
                'original_name': mapping.original_patient_name,
                'original_id': mapping.original_patient_id,
            }

        return None

    def validate_anonymization(self, dataset: Dataset) -> Dict[str, any]:
        """
        Validate that a dataset is properly anonymized.

        Args:
            dataset: DICOM dataset to validate

        Returns:
            Dict with validation results
        """
        issues = []
        phi_found = []

        for tag_name in self.TAGS_TO_REMOVE:
            if hasattr(dataset, tag_name):
                value = getattr(dataset, tag_name)
                if value:
                    phi_found.append(f"{tag_name}: {value} (should be removed)")

        private_tags = [elem for elem in dataset if elem.tag.is_private]
        if private_tags:
            issues.append(f"Found {len(private_tags)} private tags")

        if hasattr(dataset, 'PatientName'):
            patient_name = str(dataset.PatientName)
            if patient_name and not patient_name.startswith('ANON-'):
                issues.append(f"Non-standard patient name format: {dataset.PatientName}")

        if hasattr(dataset, 'PatientID'):
            patient_id = str(dataset.PatientID)
            if patient_id and not patient_id.startswith('ANON-'):
                issues.append(f"Non-standard patient ID format: {dataset.PatientID}")

        for date_field in ['StudyDate', 'SeriesDate', 'AcquisitionDate', 'ContentDate', 'PatientBirthDate']:
            if hasattr(dataset, date_field):
                value = str(getattr(dataset, date_field))
                if value and value != '19700101' and value != '':
                    phi_found.append(f"{date_field}: {value} (not anonymized)")

        return {
            'is_valid': len(issues) == 0 and len(phi_found) == 0,
            'issues': issues,
            'phi_found': phi_found,
        }
