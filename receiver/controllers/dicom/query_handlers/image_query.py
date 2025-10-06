"""
Image Query Handler for DICOM C-FIND operations at IMAGE level.
Note: Instance metadata is now stored in XML files, not database.
This handler queries from XML metadata files.
"""
import logging
from pathlib import Path
from pydicom import Dataset
from receiver.models import Session, Scan
from receiver.utils.instance_metadata import InstanceMetadataHandler

logger = logging.getLogger('receiver.query.image')


class ImageQueryHandler:
    """Handler for image-level C-FIND queries."""

    def __init__(self, storage_manager, resolver, api_query_service=None):
        """
        Initialize the image query handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver instance
            api_query_service: APIQueryService instance (optional)
        """
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.api_query_service = api_query_service
        self.metadata_handler = InstanceMetadataHandler()

    def find(self, query_ds):
        """
        Find images matching the query.

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info(f"Processing IMAGE level C-FIND")

        filters = {}
        study_filters = {}
        sop_instance_uid = None

        if hasattr(query_ds, 'StudyInstanceUID') and query_ds.StudyInstanceUID:
            study_filters['study_instance_uid'] = query_ds.StudyInstanceUID
            logger.info(f"Filtering by Study UID: {query_ds.StudyInstanceUID}")

        if hasattr(query_ds, 'SeriesInstanceUID') and query_ds.SeriesInstanceUID:
            filters['series_instance_uid'] = query_ds.SeriesInstanceUID
            logger.info(f"Filtering by Series UID: {query_ds.SeriesInstanceUID}")

        if hasattr(query_ds, 'SOPInstanceUID') and query_ds.SOPInstanceUID:
            sop_instance_uid = query_ds.SOPInstanceUID
            logger.info(f"Filtering by SOP Instance UID: {sop_instance_uid}")

        instance_number = None
        if hasattr(query_ds, 'InstanceNumber') and query_ds.InstanceNumber:
            instance_number = int(query_ds.InstanceNumber)
            logger.info(f"Filtering by Instance Number: {instance_number}")

        if hasattr(query_ds, 'PatientID') and query_ds.PatientID:
            anonymized_id = self.resolver.resolve_to_anonymous(original_id=query_ds.PatientID)
            if anonymized_id:
                study_filters['patient_id'] = anonymized_id
                logger.info(f"Filtering by Patient ID: {query_ds.PatientID} (anonymized)")
            else:
                study_filters['patient_id'] = query_ds.PatientID
                logger.info(f"Filtering by Patient ID: {query_ds.PatientID}")

        if hasattr(query_ds, 'PatientName') and query_ds.PatientName:
            anonymized_name = self.resolver.resolve_to_anonymous(original_name=str(query_ds.PatientName))
            if anonymized_name:
                study_filters['patient_name'] = anonymized_name
                logger.info(f"Filtering by Patient Name: {query_ds.PatientName} (anonymized)")
            else:
                study_filters['patient_name'] = str(query_ds.PatientName)
                logger.info(f"Filtering by Patient Name: {query_ds.PatientName}")

        if study_filters:
            for key, value in study_filters.items():
                filters[f'session__{key}'] = value

        series_list = Scan.objects.filter(**filters).select_related('session')
        logger.info(f" Found {len(series_list)} series matching query")

        response_count = 0
        for series in series_list:
            xml_path = series.get_instances_xml_path()
            if not xml_path.exists():
                logger.debug(f"No instances XML for series {series.series_instance_uid}")
                continue

            instances = self.metadata_handler.get_all_instances(xml_path)
            study = series.session

            for instance in instances:
                if sop_instance_uid and instance['sop_instance_uid'] != sop_instance_uid:
                    continue

                if instance_number is not None and int(instance.get('instance_number', 0)) != instance_number:
                    continue
                response_ds = Dataset()
                response_ds.QueryRetrieveLevel = 'IMAGE'

                original = self.resolver.resolve_patient(anonymous_name=study.patient_name)

                if original:
                    response_ds.PatientName = original['original_name']
                    response_ds.PatientID = original['original_id']
                else:
                    response_ds.PatientName = study.patient_name
                    response_ds.PatientID = study.patient_id

                response_ds.StudyInstanceUID = study.study_instance_uid
                response_ds.SeriesInstanceUID = series.series_instance_uid

                response_ds.SOPInstanceUID = instance['sop_instance_uid']
                response_ds.InstanceNumber = int(instance.get('instance_number', 0))


                if hasattr(query_ds, 'SOPClassUID') or True:
                    try:
                        from pathlib import Path
                        from pydicom import dcmread
                        file_path = Path(series.storage_path) / instance['file_name']
                        if file_path.exists():
                            ds = dcmread(str(file_path), stop_before_pixels=True)
                            if hasattr(ds, 'SOPClassUID'):
                                response_ds.SOPClassUID = ds.SOPClassUID
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).debug(f"Could not read SOPClassUID: {e}")

                logger.info(f" Returning instance #{response_count + 1}:")
                logger.info(f"Instance: {response_ds.InstanceNumber}")
                logger.info(f"SOP UID: {response_ds.SOPInstanceUID}")

                response_count += 1
                yield 0xFF00, response_ds

        logger.info(f" IMAGE query completed - returned {response_count} instances")
        logger.info("=" * 60)
        yield 0x0000, None
