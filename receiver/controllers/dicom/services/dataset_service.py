"""
Dataset service for preparing DICOM datasets with correct metadata.

Handles transfer syntax, file meta information, and other dataset preparation.
"""
import logging
from typing import Any

import pydicom
from pydicom.uid import PYDICOM_IMPLEMENTATION_UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

logger = logging.getLogger('receiver.services.dataset')


class DICOMDatasetService:
    """
    Service for preparing DICOM datasets.

    Handles:
    - Setting transfer syntax
    - Configuring file meta information
    - Ensuring required DICOM attributes are present
    """

    @staticmethod
    def prepare_dataset(dataset: Any, transfer_syntax: str) -> None:
        """
        Prepare dataset with correct transfer syntax and file meta.

        Modifies the dataset in place to add:
        - File meta information dataset
        - Media Storage SOP Class and Instance UIDs
        - Transfer syntax
        - Implementation class and version
        - Encoding properties (is_little_endian, is_implicit_VR)

        Args:
            dataset: DICOM dataset to prepare
            transfer_syntax: Transfer syntax UID
        """
        try:
            # Set transfer syntax encoding properties (pydicom 2.4.4)
            dataset.is_little_endian = transfer_syntax in [
                ImplicitVRLittleEndian,
                ExplicitVRLittleEndian
            ]
            dataset.is_implicit_VR = transfer_syntax == ImplicitVRLittleEndian

            # Create file_meta if it doesn't exist
            if not hasattr(dataset, 'file_meta') or dataset.file_meta is None:
                dataset.file_meta = pydicom.dataset.FileMetaDataset()

            # Set required file meta elements
            dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
            dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
            dataset.file_meta.TransferSyntaxUID = transfer_syntax
            dataset.file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
            dataset.file_meta.ImplementationVersionName = "PYDICOM"
            dataset.file_meta.FileMetaInformationVersion = b'\x00\x01'

            # Validate and fix file meta information (pydicom 2.4.4)
            dataset.fix_meta_info(enforce_standard=True)

            logger.debug(f"Prepared dataset with transfer syntax: {transfer_syntax}")

        except Exception as e:
            logger.warning(f"Error preparing dataset: {e}")

    @staticmethod
    def validate_dataset(dataset: Any) -> bool:
        """
        Validate that a dataset has required DICOM attributes.

        Args:
            dataset: DICOM dataset to validate

        Returns:
            True if dataset is valid, False otherwise
        """
        required_attributes = [
            'SOPClassUID',
            'SOPInstanceUID',
            'StudyInstanceUID',
            'SeriesInstanceUID',
        ]

        for attr in required_attributes:
            if not hasattr(dataset, attr) or getattr(dataset, attr) is None:
                logger.error(f"Dataset missing required attribute: {attr}")
                return False

        return True

    @staticmethod
    def extract_dataset_info(dataset: Any) -> dict:
        """
        Extract key information from a dataset for logging.

        Args:
            dataset: DICOM dataset

        Returns:
            Dictionary with dataset information
        """
        return {
            'patient_name': getattr(dataset, 'PatientName', 'Unknown'),
            'patient_id': getattr(dataset, 'PatientID', 'Unknown'),
            'study_uid': getattr(dataset, 'StudyInstanceUID', 'Unknown'),
            'series_uid': getattr(dataset, 'SeriesInstanceUID', 'Unknown'),
            'sop_uid': getattr(dataset, 'SOPInstanceUID', 'Unknown'),
            'sop_class': getattr(dataset, 'SOPClassUID', 'Unknown'),
            'modality': getattr(dataset, 'Modality', 'Unknown'),
        }
