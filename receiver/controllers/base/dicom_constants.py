"""
DICOM constants for status codes, SOP Class UIDs, and Transfer Syntax UIDs.

Centralizes magic numbers and improves code readability.
"""
from enum import IntEnum
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian


class DICOMStatus(IntEnum):
    """
    DICOM status codes for various operations.

    References:
    - DICOM PS3.4: Service Class Specifications
    - DICOM PS3.7: Message Exchange
    """
    SUCCESS = 0x0000

    PENDING = 0xFF00

    CANCEL = 0xFE00

    FAILURE = 0xC000
    REFUSED_OUT_OF_RESOURCES = 0xA700
    IDENTIFIER_DOES_NOT_MATCH_SOP_CLASS = 0xA900
    UNABLE_TO_PROCESS = 0xC000

    OUT_OF_RESOURCES_SUB_OPERATIONS = 0xA701
    OUT_OF_RESOURCES_UNABLE_TO_CALCULATE = 0xA702
    OUT_OF_RESOURCES_UNABLE_TO_PERFORM = 0xA801
    MOVE_DESTINATION_UNKNOWN = 0xA801

    ACCESS_DENIED = 0xC001

    SUB_OPERATIONS_COMPLETE_WITH_FAILURES = 0xB000


class SOPClassUIDs:
    """
    Common SOP Class UIDs for DICOM operations.
    """

    CT_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.2'
    ENHANCED_CT_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.2.1'
    MR_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.4'
    ENHANCED_MR_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.4.1'
    PET_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.128'
    ENHANCED_PET_IMAGE_STORAGE = '1.2.840.10008.5.1.4.1.1.130'

    PATIENT_ROOT_QR_FIND = '1.2.840.10008.5.1.4.1.2.1.1'
    PATIENT_ROOT_QR_MOVE = '1.2.840.10008.5.1.4.1.2.1.2'
    PATIENT_ROOT_QR_GET = '1.2.840.10008.5.1.4.1.2.1.3'

    STUDY_ROOT_QR_FIND = '1.2.840.10008.5.1.4.1.2.2.1'
    STUDY_ROOT_QR_MOVE = '1.2.840.10008.5.1.4.1.2.2.2'
    STUDY_ROOT_QR_GET = '1.2.840.10008.5.1.4.1.2.2.3'

    VERIFICATION = '1.2.840.10008.1.1'

    @classmethod
    def is_storage_sop_class(cls, uid: str) -> bool:
        """Check if UID is a storage SOP class."""
        storage_uids = [
            cls.CT_IMAGE_STORAGE,
            cls.ENHANCED_CT_IMAGE_STORAGE,
            cls.MR_IMAGE_STORAGE,
            cls.ENHANCED_MR_IMAGE_STORAGE,
            cls.PET_IMAGE_STORAGE,
            cls.ENHANCED_PET_IMAGE_STORAGE,
        ]
        return uid in storage_uids

    @classmethod
    def is_qr_sop_class(cls, uid: str) -> bool:
        """Check if UID is a Query/Retrieve SOP class."""
        return uid.startswith('1.2.840.10008.5.1.4.1.2.')


class TransferSyntaxUIDs:
    """
    Common Transfer Syntax UIDs.
    """
    IMPLICIT_VR_LITTLE_ENDIAN = ImplicitVRLittleEndian
    EXPLICIT_VR_LITTLE_ENDIAN = ExplicitVRLittleEndian

    JPEG_BASELINE = '1.2.840.10008.1.2.4.50'
    JPEG_LOSSLESS = '1.2.840.10008.1.2.4.70'
    JPEG_2000_LOSSLESS = '1.2.840.10008.1.2.4.90'

    @classmethod
    def is_compressed(cls, uid: str) -> bool:
        """Check if transfer syntax is compressed."""
        compressed = [
            cls.JPEG_BASELINE,
            cls.JPEG_LOSSLESS,
            cls.JPEG_2000_LOSSLESS,
        ]
        return uid in compressed


class QueryRetrieveLevel:
    """Query/Retrieve hierarchy levels."""
    PATIENT = 'PATIENT'
    STUDY = 'STUDY'
    SERIES = 'SERIES'
    IMAGE = 'IMAGE'
