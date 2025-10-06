"""
PHI Resolver Module
Handles de-anonymization of patient data for authorized access.
Thread-safe operations for concurrent queries.
"""
import threading
from typing import Dict, Optional, List, Any
from pydicom import Dataset
from receiver.models import PatientMapping


class PHIResolver:
    """
    Resolves (de-anonymizes) patient health information.
    Restores original patient data from anonymous identifiers.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()

    def resolve_patient(self, anonymous_name: Optional[str] = None, anonymous_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Resolve anonymous patient identifiers to original data.

        Args:
            anonymous_name: Anonymous patient name (e.g., "ANON-00001")
            anonymous_id: Anonymous patient ID (e.g., "ANON-00001")

        Returns:
            Dict containing original patient information, or None if not found
        """
        with self._lock:
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
                    'original_name': mapping.original_patient_name,
                    'original_id': mapping.original_patient_id,
                    'anonymous_name': mapping.anonymous_patient_name,
                    'anonymous_id': mapping.anonymous_patient_id,
                }

            return None

    def resolve_dataset(self, dataset: Dataset) -> Dataset:
        """
        De-anonymize patient data in a DICOM dataset.
        Restores all removed PHI data including dates, physician names, etc.

        Args:
            dataset: pydicom Dataset object with anonymous patient data

        Returns:
            Dataset with original patient information and PHI restored
        """
        anonymous_name = getattr(dataset, 'PatientName', None)
        anonymous_id = getattr(dataset, 'PatientID', None)

        if not anonymous_name and not anonymous_id:
            return dataset

        mapping_info = self.resolve_patient(
            anonymous_name=str(anonymous_name) if anonymous_name else None,
            anonymous_id=str(anonymous_id) if anonymous_id else None
        )

        if mapping_info:
            dataset.PatientName = mapping_info['original_name']
            dataset.PatientID = mapping_info['original_id']

            with self._lock:
                from receiver.models import PatientMapping
                mapping = PatientMapping.objects.filter(
                    anonymous_patient_name=mapping_info['anonymous_name']
                ).first()

                if mapping:
                    phi_metadata = mapping.get_phi_metadata()
                    self._restore_phi_metadata(dataset, phi_metadata)

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
                import logging
                logging.getLogger(__name__).warning(f"Could not restore tag {tag_name}: {e}")

    def get_all_mappings(self) -> List[Dict[str, Any]]:
        """
        Get all patient mappings.

        Returns:
            List of all patient mapping dictionaries
        """
        mappings = PatientMapping.objects.all()
        return [
            {
                'original_name': m.original_patient_name,
                'original_id': m.original_patient_id,
                'anonymous_name': m.anonymous_patient_name,
                'anonymous_id': m.anonymous_patient_id,
                'created_at': m.created_at,
            }
            for m in mappings
        ]

    def reverse_lookup(self, original_name: Optional[str] = None, original_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Lookup anonymous identifiers from original patient data.

        Args:
            original_name: Original patient name
            original_id: Original patient ID

        Returns:
            Dict containing anonymous patient information, or None if not found
        """
        with self._lock:
            query_params = {}
            if original_name:
                query_params['original_patient_name'] = original_name
            if original_id:
                query_params['original_patient_id'] = original_id

            if not query_params:
                return None

            mapping = PatientMapping.objects.filter(**query_params).first()

            if mapping:
                return {
                    'anonymous_name': mapping.anonymous_patient_name,
                    'anonymous_id': mapping.anonymous_patient_id,
                    'original_name': mapping.original_patient_name,
                    'original_id': mapping.original_patient_id,
                }

            return None

    def resolve_to_anonymous(self, original_name: Optional[str] = None, original_id: Optional[str] = None) -> Optional[str]:
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
