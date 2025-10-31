"""
C-STORE Handler for receiving DICOM files.
Handles incoming DICOM images and stores them with anonymization.
"""
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING
from pydicom import dcmread, dataset as pydicom_dataset
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
import pydicom

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi.anonymizer import PHIAnonymizer
    from receiver.services.config.proxy_config_service import ProxyConfigService

logger = logging.getLogger('receiver.handlers.store')


class StoreHandler:
    """Handler for C-STORE operations - receives and stores DICOM files."""

    SUPPORTED_MODALITIES = ['CT', 'PT', 'MR']

    def __init__(
        self,
        storage_manager: 'StorageManager',
        anonymizer: 'PHIAnonymizer',
        config_service: 'ProxyConfigService' = None
    ) -> None:
        """
        Initialize the store handler.

        Args:
            storage_manager: StorageManager instance
            anonymizer: PHIAnonymizer instance
            config_service: ProxyConfigService instance (optional)
        """
        self.storage_manager = storage_manager
        self.anonymizer = anonymizer
        self.config_service = config_service

    def _fix_dicom_metadata(self, dataset: Any) -> None:
        """
        Fix DICOM file metadata to ensure compatibility with PACS viewers.

        This ensures:
        - 128-byte preamble (required by DICOM standard)
        - Proper TransferSyntaxUID preservation
        - All required file meta elements
        - PatientName format compliance

        Args:
            dataset: DICOM dataset to fix
        """
        try:
            if not hasattr(dataset, 'preamble') or dataset.preamble is None:
                dataset.preamble = b'\x00' * 128
                logger.debug("Added 128-byte DICOM preamble for viewer compatibility")

            if not hasattr(dataset, 'file_meta') or dataset.file_meta is None:
                dataset.file_meta = pydicom_dataset.FileMetaDataset()
                logger.debug("Created file_meta dataset")

            if not hasattr(dataset.file_meta, 'TransferSyntaxUID') or dataset.file_meta.TransferSyntaxUID is None:
                dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
                logger.debug(f"No TransferSyntaxUID found, setting default: {ExplicitVRLittleEndian}")
            else:
                logger.debug(f"Preserving original TransferSyntaxUID: {dataset.file_meta.TransferSyntaxUID}")

            dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
            dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
            dataset.file_meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
            dataset.file_meta.ImplementationVersionName = "PYDICOM"

            dataset.file_meta.FileMetaInformationVersion = b'\x00\x01'

        except Exception as e:
            logger.warning(f"Error fixing DICOM metadata: {e}", exc_info=True)

    def handle_store(self, event: Any) -> int:
        """
        Handle incoming C-STORE request.
        Only accepts CT, PET (PT), and MR modalities.

        Args:
            event: pynetdicom event object

        Returns:
            int: DICOM status code (0x0000 = success, 0xC000 = failure)
        """
        try:
            from receiver.services.config.access_control_service import extract_calling_ae_title, extract_requester_address, get_access_control_service
            calling_ae = extract_calling_ae_title(event)
            requester_ip = extract_requester_address(event)

            access_control = get_access_control_service()

            if access_control:
                allowed, reason = access_control.can_accept_store(calling_ae, requester_ip)
                if not allowed:
                    logger.warning(f"C-STORE REJECTED from {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")
                    return 0xC001
                logger.debug(f"C-STORE access granted to {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")
            else:
                logger.warning("Access control service not available, allowing C-STORE (fail-open mode)")

            dataset = event.dataset

            required_tags = ['StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
            missing_tags = [tag for tag in required_tags if not hasattr(dataset, tag)]

            if missing_tags:
                logger.error(f" Missing required DICOM tags: {', '.join(missing_tags)}")
                return 0xC000

            modality = getattr(dataset, 'Modality', 'UNKNOWN')
            if modality not in self.SUPPORTED_MODALITIES:
                logger.warning(f" Rejected unsupported modality: {modality}")
                logger.warning(f"Supported modalities: {', '.join(self.SUPPORTED_MODALITIES)}")
                return 0xC001

            logger.info("=" * 60)
            logger.info(" RECEIVED C-STORE REQUEST")
            logger.info(f"From: {calling_ae}")
            logger.info(f"Modality: {modality}")
            logger.info(f"Patient: {getattr(dataset, 'PatientName', 'Unknown')}")
            logger.info(f"Study UID: {dataset.StudyInstanceUID}")
            logger.info(f"Series UID: {dataset.SeriesInstanceUID}")
            logger.info(f"Instance UID: {dataset.SOPInstanceUID}")
            logger.info("=" * 60)

            should_anonymize = True
            if self.config_service:
                should_anonymize = self.config_service.is_phi_anonymization_enabled()
                logger.info(f" PHI Anonymization: {'Enabled' if should_anonymize else 'Disabled'}")

            study_phi = None
            series_phi = None

            if should_anonymize:
                dataset, phi_data = self.anonymizer.anonymize_dataset(dataset)
                mapping = phi_data['mapping']
                study_phi = phi_data['study_phi']
                series_phi = phi_data['series_phi']
                logger.info(f" Anonymized: {mapping['original_name']} → {mapping['anonymous_name']}")
                logger.debug(f" PHI extracted - Study: {len(study_phi)} fields, Series: {len(series_phi)} fields")
            else:
                logger.info(f"Storing with original PHI (anonymization disabled)")

            self._fix_dicom_metadata(dataset)

            filename = f"{dataset.SOPInstanceUID}.dcm"

            result = self.storage_manager.store_dicom_file(
                dataset,
                filename,
                study_phi_metadata=study_phi,
                series_phi_metadata=series_phi
            )

            logger.info(f" Stored to: {result['series'].storage_path}")
            logger.info(f" Study stats: {result['series'].instances_count} instances in series")

            return 0x0000

        except Exception as e:
            logger.error(f" Error storing DICOM file: {e}", exc_info=True)
            return 0xC000