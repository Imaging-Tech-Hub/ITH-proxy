"""
Image Query Handler for DICOM C-FIND operations at IMAGE level.
Note: Instance metadata is now stored in XML files, not database.
This handler queries from XML metadata files.
"""
import logging
from pathlib import Path
from pydicom import Dataset
from receiver.models import Session, Scan
from receiver.utils.storage import InstanceMetadataHandler

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
        Always queries from API only.

        Args:
            query_ds: Query dataset

        Yields:
            tuple: (status_code, response_dataset)
        """
        logger.info("Processing IMAGE level C-FIND - Querying API")

        if not self.api_query_service:
            logger.error("API query service not available")
            yield 0x0000, None
            return

        study_uid = query_ds.StudyInstanceUID if hasattr(query_ds, 'StudyInstanceUID') else None
        series_uid = query_ds.SeriesInstanceUID if hasattr(query_ds, 'SeriesInstanceUID') else None

        if not study_uid or not series_uid:
            logger.warning("IMAGE query requires both StudyInstanceUID and SeriesInstanceUID")
            yield 0x0000, None
            return

        logger.info(f"Querying ITH API for images in series {series_uid}...")
        api_images = self.api_query_service.query_images_for_series(study_uid, series_uid)

        if not api_images:
            logger.info("No images found from API")
            yield 0x0000, None
            return

        logger.info(f"Found {len(api_images)} images from API")

        response_count = 0
        for image_info in api_images:
            response_ds = Dataset()
            response_ds.QueryRetrieveLevel = 'IMAGE'

            response_ds.PatientName = image_info.get('PatientName', '')
            response_ds.PatientID = image_info.get('PatientID', '')
            response_ds.StudyInstanceUID = image_info.get('StudyInstanceUID', '')
            response_ds.SeriesInstanceUID = image_info.get('SeriesInstanceUID', '')
            response_ds.SOPInstanceUID = image_info.get('SOPInstanceUID', '')
            response_ds.InstanceNumber = image_info.get('InstanceNumber', 0)

            if image_info.get('SOPClassUID'):
                response_ds.SOPClassUID = image_info['SOPClassUID']

            logger.info(f"  Returning image #{response_count + 1}:")
            logger.info(f"   Instance: {response_ds.InstanceNumber}")
            logger.info(f"   SOP UID: {response_ds.SOPInstanceUID}")

            response_count += 1
            yield 0xFF00, response_ds

        logger.info(f"IMAGE query completed (API) - returned {response_count} images")
        logger.info("=" * 60)
        yield 0x0000, None
