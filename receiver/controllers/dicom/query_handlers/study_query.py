"""
Study Query Handler for DICOM C-FIND operations at STUDY level.
"""
import logging
from typing import Dict
from pydicom import Dataset
from receiver.models import Session
from django.db.models import Q

logger = logging.getLogger('receiver.query.study')


def dicom_wildcard_to_django(value: str) -> tuple:
    """
    Convert DICOM wildcard pattern to Django query.
    DICOM uses * for any characters, ? for single character.

    Args:
        value: DICOM query value with wildcards

    Returns:
        Tuple of (lookup_type, converted_value)
        - If no wildcards: ('exact', value)
        - If wildcards: ('regex', regex_pattern)
    """
    if not value:
        return ('exact', value)

    if '*' in value or '?' in value:

        import re
        pattern = value.replace('*', '.*').replace('?', '.')
        pattern = f'^{pattern}$'
        return ('iregex', pattern)
    else:
        return ('iexact', value)


class StudyQueryHandler:
    """Handler for study-level C-FIND queries."""

    def __init__(self, storage_manager, resolver, api_query_service=None):
        """
        Initialize the study query handler.

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
        Find studies matching the query.
        Always queries the API instead of local database.

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info("📚 Processing STUDY level C-FIND - Querying API")

        filters = {}

        if hasattr(query_ds, 'PatientID') and query_ds.PatientID:
            patient_id_value = str(query_ds.PatientID)
            anonymized_id = self.resolver.resolve_to_anonymous(original_id=patient_id_value)
            if anonymized_id:
                lookup_type, lookup_value = dicom_wildcard_to_django(anonymized_id)
                filters[f'patient_id__{lookup_type}'] = lookup_value
                logger.info(f"Filtering by Patient ID: {patient_id_value} (anonymized: {anonymized_id})")
            else:
                lookup_type, lookup_value = dicom_wildcard_to_django(patient_id_value)
                filters[f'patient_id__{lookup_type}'] = lookup_value
                logger.info(f"Filtering by Patient ID: {patient_id_value}")

        if hasattr(query_ds, 'PatientName') and query_ds.PatientName:
            patient_name_value = str(query_ds.PatientName)
            anonymized_name = self.resolver.resolve_to_anonymous(original_name=patient_name_value)
            if anonymized_name:
                lookup_type, lookup_value = dicom_wildcard_to_django(anonymized_name)
                filters[f'patient_name__{lookup_type}'] = lookup_value
                logger.info(f"Filtering by Patient Name: {patient_name_value} (anonymized: {anonymized_name})")
            else:
                lookup_type, lookup_value = dicom_wildcard_to_django(patient_name_value)
                filters[f'patient_name__{lookup_type}'] = lookup_value
                logger.info(f"Filtering by Patient Name: {patient_name_value}")

        if hasattr(query_ds, 'StudyInstanceUID') and query_ds.StudyInstanceUID:
            filters['study_instance_uid'] = query_ds.StudyInstanceUID
            logger.info(f"Filtering by Study UID: {query_ds.StudyInstanceUID}")

        if hasattr(query_ds, 'StudyDate') and query_ds.StudyDate:
            study_date = query_ds.StudyDate
            if '-' in study_date:
                start_date, end_date = study_date.split('-')
                if start_date:
                    filters['study_date__gte'] = start_date
                if end_date:
                    filters['study_date__lte'] = end_date
                logger.info(f"Filtering by Study Date range: {study_date}")
            else:
                filters['study_date'] = study_date
                logger.info(f"Filtering by Study Date: {study_date}")

        if hasattr(query_ds, 'AccessionNumber') and query_ds.AccessionNumber:
            filters['accession_number'] = query_ds.AccessionNumber
            logger.info(f"Filtering by Accession Number: {query_ds.AccessionNumber}")

        if self.api_query_service:
            logger.info("🌐 Querying ITH API for studies...")
            try:
                api_studies = self.api_query_service.query_all_studies()
                if api_studies:
                    logger.info(f" Found {len(api_studies)} studies from API")
                    response_count = 0
                    for study_info in api_studies:
                        if not self._matches_filters(study_info, query_ds):
                            continue

                        response_ds = Dataset()
                        response_ds.QueryRetrieveLevel = 'STUDY'

                        anonymous_patient_name = study_info.get('PatientName', '')
                        anonymous_patient_id = study_info.get('PatientID', '')

                        original_info = self.resolver.resolve_patient(
                            anonymous_name=anonymous_patient_name,
                            anonymous_id=anonymous_patient_id
                        )

                        if original_info:
                            response_ds.PatientName = original_info['original_name']
                            response_ds.PatientID = original_info['original_id']
                            logger.debug(f"De-anonymized: {anonymous_patient_name} → {original_info['original_name']}")

                            phi_metadata = self._get_phi_metadata(original_info['anonymous_name'])
                            if phi_metadata:
                                logger.debug(f"Restoring {len(phi_metadata)} PHI fields")
                        else:
                            response_ds.PatientName = anonymous_patient_name
                            response_ds.PatientID = anonymous_patient_id
                            logger.warning(f"No mapping found for {anonymous_patient_name}, using as-is")
                            phi_metadata = {}

                        response_ds.StudyInstanceUID = study_info.get('StudyInstanceUID', '')

                        response_ds.StudyDescription = phi_metadata.get('StudyDescription', study_info.get('StudyDescription', ''))
                        response_ds.StudyDate = phi_metadata.get('StudyDate', study_info.get('StudyDate', ''))
                        response_ds.StudyTime = phi_metadata.get('StudyTime', study_info.get('StudyTime', ''))
                        response_ds.AccessionNumber = study_info.get('AccessionNumber', '')

                        birth_date = phi_metadata.get('PatientBirthDate') or study_info.get('PatientBirthDate')
                        if birth_date:
                            response_ds.PatientBirthDate = birth_date

                        patient_sex = study_info.get('PatientSex')
                        if patient_sex:
                            response_ds.PatientSex = patient_sex

                        if study_info.get('NumberOfStudyRelatedSeries'):
                            response_ds.NumberOfStudyRelatedSeries = study_info['NumberOfStudyRelatedSeries']
                        if study_info.get('NumberOfStudyRelatedInstances'):
                            response_ds.NumberOfStudyRelatedInstances = study_info['NumberOfStudyRelatedInstances']

                        logger.info(f"Returning study #{response_count + 1}:")
                        logger.info(f"Patient: {response_ds.PatientName} (ID: {response_ds.PatientID})")
                        logger.info(f"Study: {response_ds.StudyDescription or 'No Description'}")
                        logger.info(f" Date: {response_ds.StudyDate or 'Unknown'}")
                        logger.info(f"UID: {response_ds.StudyInstanceUID}")

                        response_count += 1
                        yield 0xFF00, response_ds

                    logger.info(f"STUDY query completed (API) - returned {response_count} studies")
                    logger.info("=" * 60)
                    yield 0x0000, None
                    return
                else:
                    logger.warning("API query returned no data")
            except Exception as e:
                logger.error(f"Error querying API: {e}", exc_info=True)
        else:
            logger.warning("API query service not available - cannot query studies")

        logger.info("=" * 60)
        logger.info("STUDY query completed - 0 results (API only mode)")
        logger.info("=" * 60)
        yield 0x0000, None 

    def _get_phi_metadata(self, anonymous_name: str) -> Dict[str, str]:
        """
        Get stored PHI metadata for a patient.

        Args:
            anonymous_name: Anonymous patient name

        Returns:
            Dict of PHI metadata
        """
        try:
            mapping = Session.objects.filter(
                patient_name=anonymous_name
            ).first()

            if mapping:
                from receiver.models import PatientMapping
                patient_mapping = PatientMapping.objects.filter(
                    anonymous_patient_name=anonymous_name
                ).first()

                if patient_mapping:
                    return patient_mapping.get_phi_metadata()
        except Exception as e:
            logger.warning(f"Could not retrieve PHI metadata: {e}")

        return {}

    def _matches_filters(self, study_info: Dict[str, str], query_ds) -> bool:
        """
        Check if study info from API matches the query filters.

        Args:
            study_info: Study information dictionary from API
            query_ds: Query dataset with filter criteria

        Returns:
            bool: True if matches all filters
        """
        if hasattr(query_ds, 'PatientID') and query_ds.PatientID:
            if study_info.get('PatientID') != str(query_ds.PatientID):
                return False

        if hasattr(query_ds, 'PatientName') and query_ds.PatientName:
            if study_info.get('PatientName') != str(query_ds.PatientName):
                return False

        if hasattr(query_ds, 'StudyInstanceUID') and query_ds.StudyInstanceUID:
            if study_info.get('StudyInstanceUID') != query_ds.StudyInstanceUID:
                return False

        if hasattr(query_ds, 'StudyDate') and query_ds.StudyDate:
            study_date = query_ds.StudyDate
            if '-' in study_date:
                start_date, end_date = study_date.split('-')
                study_info_date = study_info.get('StudyDate', '')
                if start_date and study_info_date < start_date:
                    return False
                if end_date and study_info_date > end_date:
                    return False
            else:
                if study_info.get('StudyDate') != study_date:
                    return False

        if hasattr(query_ds, 'AccessionNumber') and query_ds.AccessionNumber:
            if study_info.get('AccessionNumber') != query_ds.AccessionNumber:
                return False

        return True
