"""
Patient mapping service for database operations.

Handles all database queries and operations for PHI mapping.
Separates database logic from business logic.
"""
import threading
import logging
from typing import Dict, Optional, List, Any

from receiver.models import PatientMapping

logger = logging.getLogger(__name__)


class PatientMappingService:
    """
    Service for patient mapping database operations.

    Handles:
    - Querying mappings by anonymous identifiers
    - Querying mappings by original identifiers
    - Creating new mappings
    - Retrieving all mappings
    - Thread-safe database operations
    """

    def __init__(self) -> None:
        """Initialize the mapping service with thread safety."""
        self._lock: threading.RLock = threading.RLock()

    def find_by_anonymous(
        self,
        anonymous_name: Optional[str] = None,
        anonymous_id: Optional[str] = None
    ) -> Optional[PatientMapping]:
        """
        Find mapping by anonymous patient identifiers.

        Args:
            anonymous_name: Anonymous patient name
            anonymous_id: Anonymous patient ID

        Returns:
            PatientMapping object or None if not found
        """
        with self._lock:
            if anonymous_name:
                return PatientMapping.objects.filter(
                    anonymous_patient_name=anonymous_name
                ).first()
            elif anonymous_id:
                return PatientMapping.objects.filter(
                    anonymous_patient_id=anonymous_id
                ).first()

        return None

    def find_by_original(
        self,
        original_name: Optional[str] = None,
        original_id: Optional[str] = None
    ) -> Optional[PatientMapping]:
        """
        Find mapping by original patient identifiers.

        Args:
            original_name: Original patient name
            original_id: Original patient ID

        Returns:
            PatientMapping object or None if not found
        """
        with self._lock:
            query_params = {}
            if original_name:
                query_params['original_patient_name'] = original_name
            if original_id:
                query_params['original_patient_id'] = original_id

            if not query_params:
                return None

            return PatientMapping.objects.filter(**query_params).first()

    def get_all(self) -> List[PatientMapping]:
        """
        Get all patient mappings.

        Returns:
            List of all PatientMapping objects
        """
        return list(PatientMapping.objects.all())

    def create_mapping(
        self,
        original_name: str,
        original_id: str,
        anonymous_name: str,
        anonymous_id: str,
        phi_metadata: Optional[Dict[str, str]] = None
    ) -> PatientMapping:
        """
        Create a new patient mapping.

        Args:
            original_name: Original patient name
            original_id: Original patient ID
            anonymous_name: Anonymous patient name
            anonymous_id: Anonymous patient ID
            phi_metadata: Optional dict of PHI metadata to store

        Returns:
            Created PatientMapping object
        """
        with self._lock:
            mapping = PatientMapping.objects.create(
                original_patient_name=original_name,
                original_patient_id=original_id,
                anonymous_patient_name=anonymous_name,
                anonymous_patient_id=anonymous_id
            )

            if phi_metadata:
                mapping.set_phi_metadata(phi_metadata)
                mapping.save()

            logger.info(f"Created mapping: {original_name} → {anonymous_name}")
            return mapping

    def get_or_create_mapping(
        self,
        original_name: str,
        original_id: str,
        anonymous_name: str,
        anonymous_id: str,
        phi_metadata: Optional[Dict[str, str]] = None
    ) -> tuple[PatientMapping, bool]:
        """
        Get existing mapping or create new one.

        Args:
            original_name: Original patient name
            original_id: Original patient ID
            anonymous_name: Anonymous patient name
            anonymous_id: Anonymous patient ID
            phi_metadata: Optional dict of PHI metadata to store

        Returns:
            Tuple of (PatientMapping, created) where created is True if new mapping was created
        """
        with self._lock:
            # Use Django's atomic get_or_create to prevent race conditions
            defaults = {
                'anonymous_patient_name': anonymous_name,
                'anonymous_patient_id': anonymous_id,
            }

            try:
                mapping, created = PatientMapping.objects.get_or_create(
                    original_patient_name=original_name,
                    original_patient_id=original_id,
                    defaults=defaults
                )

                if created and phi_metadata:
                    mapping.set_phi_metadata(phi_metadata)
                    mapping.save()
                    logger.info(f"Created mapping: {original_name} → {anonymous_name}")
                else:
                    logger.info(f"Reusing existing mapping for patient {original_id}: {mapping.anonymous_patient_id}")

                return mapping, created

            except Exception as e:
                logger.error(f"Error in get_or_create_mapping: {e}", exc_info=True)
                raise

    def to_dict(self, mapping: PatientMapping) -> Dict[str, Any]:
        """
        Convert PatientMapping to dictionary.

        Args:
            mapping: PatientMapping object

        Returns:
            Dictionary representation
        """
        return {
            'original_name': mapping.original_patient_name,
            'original_id': mapping.original_patient_id,
            'anonymous_name': mapping.anonymous_patient_name,
            'anonymous_id': mapping.anonymous_patient_id,
            'created_at': mapping.created_at,
        }
