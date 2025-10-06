"""
Series Query Handler for DICOM C-FIND operations at SERIES level.
"""
import logging
from pydicom import Dataset
from receiver.models import Session, Scan

logger = logging.getLogger('receiver.query.series')


class SeriesQueryHandler:
    """Handler for series-level C-FIND queries."""

    def __init__(self, storage_manager, resolver, api_query_service=None):
        """
        Initialize the series query handler.

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
        Find series matching the query.

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info("Processing SERIES level C-FIND")

        filters = {}
        study_filters = {}

        if hasattr(query_ds, 'StudyInstanceUID') and query_ds.StudyInstanceUID:
            study_filters['study_instance_uid'] = query_ds.StudyInstanceUID
            logger.debug(f"Filtering by Study UID: {query_ds.StudyInstanceUID}")

        if hasattr(query_ds, 'SeriesInstanceUID') and query_ds.SeriesInstanceUID:
            filters['series_instance_uid'] = query_ds.SeriesInstanceUID
            logger.debug(f"Filtering by Series UID: {query_ds.SeriesInstanceUID}")

        if hasattr(query_ds, 'SeriesNumber') and query_ds.SeriesNumber:
            filters['series_number'] = int(query_ds.SeriesNumber)
            logger.debug(f"Filtering by Series Number: {query_ds.SeriesNumber}")

        if hasattr(query_ds, 'Modality') and query_ds.Modality:
            filters['modality'] = query_ds.Modality
            logger.debug(f"Filtering by Modality: {query_ds.Modality}")

        if hasattr(query_ds, 'PatientID') and query_ds.PatientID:
            anonymized_id = self.resolver.resolve_to_anonymous(original_id=query_ds.PatientID)
            if anonymized_id:
                study_filters['patient_id'] = anonymized_id
                logger.debug(f"Filtering by Patient ID: {query_ds.PatientID} (anonymized)")
            else:
                study_filters['patient_id'] = query_ds.PatientID
                logger.debug(f"Filtering by Patient ID: {query_ds.PatientID}")

        if hasattr(query_ds, 'PatientName') and query_ds.PatientName:
            anonymized_name = self.resolver.resolve_to_anonymous(original_name=str(query_ds.PatientName))
            if anonymized_name:
                study_filters['patient_name'] = anonymized_name
                logger.debug(f"Filtering by Patient Name: {query_ds.PatientName} (anonymized)")
            else:
                study_filters['patient_name'] = str(query_ds.PatientName)
                logger.debug(f"Filtering by Patient Name: {query_ds.PatientName}")

        if study_filters:
            for key, value in study_filters.items():
                filters[f'session__{key}'] = value

        series_list = Scan.objects.filter(**filters).select_related('session')
        logger.info(f"Found {len(series_list)} series in local database")

        if not series_list and self.api_query_service:
            logger.info("No local series found, querying Laminate API...")
            study_uid = query_ds.StudyInstanceUID if hasattr(query_ds, 'StudyInstanceUID') else None
            if study_uid:
                api_series = self.api_query_service.query_series_for_study(study_uid)
                logger.info(f"Found {len(api_series)} series from API")

                response_count = 0
                for series_info in api_series:
                    response_ds = Dataset()
                    response_ds.QueryRetrieveLevel = 'SERIES'

                    response_ds.PatientName = series_info.get('PatientName', '')
                    response_ds.PatientID = series_info.get('PatientID', '')

                    response_ds.StudyInstanceUID = series_info.get('StudyInstanceUID', '')

                    response_ds.SeriesInstanceUID = series_info.get('SeriesInstanceUID', '')
                    response_ds.SeriesNumber = series_info.get('SeriesNumber', 0)
                    response_ds.SeriesDescription = series_info.get('SeriesDescription', '')
                    response_ds.Modality = series_info.get('Modality', '')
                    response_ds.NumberOfSeriesRelatedInstances = series_info.get('NumberOfSeriesRelatedInstances', 0)

                    logger.debug(f"Returning series: {response_ds.SeriesDescription or 'No Description'} "
                               f"(Number: {response_ds.SeriesNumber}, Modality: {response_ds.Modality})")

                    response_count += 1
                    yield 0xFF00, response_ds

                logger.info(f"SERIES query completed (API) - returned {response_count} series")
                logger.info("=" * 60)
                yield 0x0000, None
                return

        response_count = 0
        for series in series_list:
            study = series.session

            response_ds = Dataset()
            response_ds.QueryRetrieveLevel = 'SERIES'

            original = self.resolver.resolve_patient(anonymous_name=study.patient_name)

            if original:
                response_ds.PatientName = original['original_name']
                response_ds.PatientID = original['original_id']
            else:
                response_ds.PatientName = study.patient_name
                response_ds.PatientID = study.patient_id

            response_ds.StudyInstanceUID = study.study_instance_uid

            response_ds.SeriesInstanceUID = series.series_instance_uid
            response_ds.SeriesNumber = series.series_number or 0
            response_ds.SeriesDescription = series.series_description or ''
            response_ds.Modality = series.modality or ''
            response_ds.NumberOfSeriesRelatedInstances = series.instances_count

            logger.debug(f"Returning series: {response_ds.SeriesDescription or 'No Description'} "
                       f"(Number: {response_ds.SeriesNumber}, Modality: {response_ds.Modality})")

            response_count += 1
            yield 0xFF00, response_ds

        logger.info(f"SERIES query completed - returned {response_count} series")
        logger.info("=" * 60)
        yield 0x0000, None
