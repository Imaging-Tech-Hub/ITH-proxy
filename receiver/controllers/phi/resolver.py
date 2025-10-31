"""
PHI Resolver Module
Handles de-anonymization of patient data for authorized access.
Thread-safe operations for concurrent queries.
Uses local database (PatientMapping) for resolution.
"""
import logging
from typing import Dict, Optional, List, Any

from pydicom import Dataset

from .mapping_service import PatientMappingService

logger = logging.getLogger(__name__)


class PHIResolver:
    """
    Resolves (de-anonymizes) patient health information.
    Restores original patient data from anonymous identifiers.

    Resolution source:
    - Local database (PatientMapping) - for data received by this proxy
    """

    def __init__(self, mapping_service: Optional[PatientMappingService] = None) -> None:
        """
        Initialize PHI Resolver.

        Args:
            mapping_service: Optional PatientMappingService instance (creates one if not provided)
        """
        self.mapping_service = mapping_service or PatientMappingService()

    def resolve_patient(
        self,
        anonymous_name: Optional[str] = None,
        anonymous_id: Optional[str] = None,
        subject_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Resolve anonymous patient identifiers to original data.
        Uses local database (PatientMapping) only.

        Args:
            anonymous_name: Anonymous patient name (e.g., "ANON-00001" or subject label)
            anonymous_id: Anonymous patient ID (e.g., "ANON-00001")
            subject_id: Backend subject ID (unused - kept for compatibility)

        Returns:
            Dict containing original patient information, or None if not found
        """
        # Try exact match first
        mapping = self.mapping_service.find_by_anonymous(
            anonymous_name=anonymous_name,
            anonymous_id=anonymous_id
        )

        if mapping:
            return {
                'original_name': mapping.original_patient_name,
                'original_id': mapping.original_patient_id,
                'anonymous_name': mapping.anonymous_patient_name,
                'anonymous_id': mapping.anonymous_patient_id,
            }

        # If not found and name contains ^, try removing trailing ^
        if anonymous_name and '^' in anonymous_name:
            clean_name = anonymous_name.rstrip('^')
            mapping = self.mapping_service.find_by_anonymous(
                anonymous_name=clean_name,
                anonymous_id=clean_name
            )
            if mapping:
                logger.info(f"Resolved using cleaned name: {anonymous_name} -> {clean_name}")
                return {
                    'original_name': mapping.original_patient_name,
                    'original_id': mapping.original_patient_id,
                    'anonymous_name': mapping.anonymous_patient_name,
                    'anonymous_id': mapping.anonymous_patient_id,
                }

        return None

    def resolve_dataset(
        self,
        dataset: Dataset,
        session=None,
        scan=None
    ) -> Dataset:
        """
        De-anonymize patient data in a DICOM dataset.
        Restores all removed PHI data from three levels: patient, study, and series.

        Args:
            dataset: pydicom Dataset object with anonymous patient data
            session: Optional Session object to restore study-level PHI
            scan: Optional Scan object to restore series-level PHI

        Returns:
            Dataset with original patient information and PHI restored from all levels
        """
        anonymous_name = getattr(dataset, 'PatientName', None)
        anonymous_id = getattr(dataset, 'PatientID', None)

        if not anonymous_name and not anonymous_id:
            return dataset

        # 1. Restore patient identifiers
        mapping_info = self.resolve_patient(
            anonymous_name=str(anonymous_name) if anonymous_name else None,
            anonymous_id=str(anonymous_id) if anonymous_id else None
        )

        if mapping_info:
            dataset.PatientName = mapping_info['original_name']
            dataset.PatientID = mapping_info['original_id']

            # 2. Restore patient-level PHI from PatientMapping
            mapping = self.mapping_service.find_by_anonymous(
                anonymous_name=mapping_info['anonymous_name']
            )

            if mapping:
                patient_phi = mapping.get_phi_metadata()
                if patient_phi:
                    logger.debug(f"Restoring patient-level PHI ({len(patient_phi)} fields)")
                    self._restore_phi_metadata(dataset, patient_phi)

            # 3. Restore study-level PHI from Session
            if session:
                study_phi = session.get_phi_metadata()
                if study_phi:
                    logger.debug(f"Restoring study-level PHI ({len(study_phi)} fields)")
                    self._restore_phi_metadata(dataset, study_phi)

            # 4. Restore series-level PHI from Scan
            if scan:
                series_phi = scan.get_phi_metadata()
                if series_phi:
                    logger.debug(f"Restoring series-level PHI ({len(series_phi)} fields)")
                    self._restore_phi_metadata(dataset, series_phi)

        return dataset

    def _restore_phi_metadata(self, dataset: Dataset, phi_metadata: Dict[str, str]) -> None:
        """
        Restore removed PHI metadata to dataset.

        Args:
            dataset: DICOM dataset
            phi_metadata: Dict of tag names and values to restore
        """
        if not phi_metadata:
            return

        for tag_name, value in phi_metadata.items():
            try:
                if tag_name in ['PatientName', 'PatientID']:
                    continue

                setattr(dataset, tag_name, value)
            except Exception as e:
                logger.warning(f"Could not restore tag {tag_name}: {e}")

    def get_all_mappings(self) -> List[Dict[str, Any]]:
        """
        Get all patient mappings.

        Returns:
            List of all patient mapping dictionaries
        """
        mappings = self.mapping_service.get_all()
        return [self.mapping_service.to_dict(m) for m in mappings]

    def reverse_lookup(
        self,
        original_name: Optional[str] = None,
        original_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Lookup anonymous identifiers from original patient data.

        Args:
            original_name: Original patient name
            original_id: Original patient ID

        Returns:
            Dict containing anonymous patient information, or None if not found
        """
        mapping = self.mapping_service.find_by_original(
            original_name=original_name,
            original_id=original_id
        )

        if mapping:
            return {
                'anonymous_name': mapping.anonymous_patient_name,
                'anonymous_id': mapping.anonymous_patient_id,
                'original_name': mapping.original_patient_name,
                'original_id': mapping.original_patient_id,
            }

        return None

    def resolve_to_anonymous(
        self,
        original_name: Optional[str] = None,
        original_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to get anonymous identifier from original patient data.
        Returns the anonymous name or ID for use in database queries.

        Args:
            original_name: Original patient name
            original_id: Original patient ID

        Returns:
            Anonymous patient name/ID string, or None if not found
        """
        mapping = self.reverse_lookup(original_name=original_name, original_id=original_id)
        if mapping:
            if original_name:
                return mapping['anonymous_name']
            elif original_id:
                return mapping['anonymous_id']
        return None
