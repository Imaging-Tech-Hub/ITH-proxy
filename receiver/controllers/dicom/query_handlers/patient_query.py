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

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info("👥 Processing PATIENT level C-FIND")

        filters = {}

        if hasattr(query_ds, 'PatientID') and query_ds.PatientID:
            anonymized_id = self.resolver.resolve_to_anonymous(original_id=query_ds.PatientID)
            if anonymized_id:
                filters['patient_id'] = anonymized_id
                logger.info(f"Filtering by Patient ID: {query_ds.PatientID} (anonymized)")
            else:
                filters['patient_id'] = query_ds.PatientID
                logger.info(f"Filtering by Patient ID: {query_ds.PatientID}")

        if hasattr(query_ds, 'PatientName') and query_ds.PatientName:
            anonymized_name = self.resolver.resolve_to_anonymous(original_name=str(query_ds.PatientName))
            if anonymized_name:
                filters['patient_name'] = anonymized_name
                logger.info(f"Filtering by Patient Name: {query_ds.PatientName} (anonymized)")
            else:
                filters['patient_name'] = str(query_ds.PatientName)
                logger.info(f"Filtering by Patient Name: {query_ds.PatientName}")

        patient_ids = Session.objects.filter(**filters).values_list('patient_id', flat=True).distinct()
        logger.info(f" Found {len(patient_ids)} unique patients matching query")

        response_count = 0
        for patient_id in patient_ids:
            study = Session.objects.filter(patient_id=patient_id).first()
            if not study:
                continue

            response_ds = Dataset()
            response_ds.QueryRetrieveLevel = 'PATIENT'

            original = self.resolver.resolve_patient(anonymous_name=study.patient_name)

            if original:
                response_ds.PatientName = original['original_name']
                response_ds.PatientID = original['original_id']
            else:
                response_ds.PatientName = study.patient_name
                response_ds.PatientID = study.patient_id

            logger.info(f" Returning patient #{response_count + 1}:")
            logger.info(f" Patient: {response_ds.PatientName} (ID: {response_ds.PatientID})")

            response_count += 1
            yield 0xFF00, response_ds

        logger.info(f" PATIENT query completed - returned {response_count} patients")
        logger.info("=" * 60)
        yield 0x0000, None
