"""
Patient Query Handler for DICOM C-FIND operations at PATIENT level.
"""
import logging
from pydicom import Dataset
from receiver.models import Session

logger = logging.getLogger('receiver.query.patient')


class PatientQueryHandler:
    """Handler for patient-level C-FIND queries."""

    def __init__(self, storage_manager, resolver, api_query_service=None):
        """
        Initialize the patient query handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver instance
            api_query_service: APIQueryService instance (optional)
        """
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.api_query_service = api_query_service

    def find(self, query_ds):
        """
        Find patients matching the query.
        Always queries from API only.

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info("👥 Processing PATIENT level C-FIND - Querying API")

        if not self.api_query_service:
            logger.error("API query service not available")
            yield 0x0000, None
            return

        logger.info("Querying ITH API for patients...")
        api_patients = self.api_query_service.query_all_patients()

        if not api_patients:
            logger.info("No patients found from API")
            yield 0x0000, None
            return

        logger.info(f"Found {len(api_patients)} patients from API")

        response_count = 0
        for patient_info in api_patients:
            response_ds = Dataset()
            response_ds.QueryRetrieveLevel = 'PATIENT'

            response_ds.PatientName = patient_info.get('PatientName', '')
            response_ds.PatientID = patient_info.get('PatientID', '')

            if patient_info.get('PatientBirthDate'):
                response_ds.PatientBirthDate = patient_info['PatientBirthDate']
            if patient_info.get('PatientSex'):
                response_ds.PatientSex = patient_info['PatientSex']

            logger.info(f"   Returning patient #{response_count + 1}:")
            logger.info(f"   Patient: {response_ds.PatientName} (ID: {response_ds.PatientID})")

            response_count += 1
            yield 0xFF00, response_ds

        logger.info(f"PATIENT query completed (API) - returned {response_count} patients")
        logger.info("=" * 60)
        yield 0x0000, None
