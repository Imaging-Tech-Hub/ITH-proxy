"""
DICOM-specific validators for controllers.

Validates UIDs, query levels, datasets, and DICOM-specific parameters.
"""
import re
from typing import Optional, Tuple, Any

from pydicom import Dataset


class DICOMUIDValidator:
    """
    Validates DICOM UIDs (Unique Identifiers).

    DICOM UIDs should follow the format:
    - Numeric components separated by dots
    - No leading zeros (except single 0)
    - Maximum 64 characters
    """

    UID_PATTERN = re.compile(r'^[0-9]+(\.[0-9]+)*$')

    @classmethod
    def validate(cls, uid: str, uid_type: str = "UID") -> Tuple[bool, Optional[str]]:
        """
        Validate a DICOM UID.

        Args:
            uid: UID string to validate
            uid_type: Type of UID for error messages

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not uid:
            return False, f"{uid_type} is required"

        if not isinstance(uid, str):
            return False, f"{uid_type} must be a string"

        uid = uid.strip()

        if len(uid) > 64:
            return False, f"{uid_type} exceeds maximum length of 64 characters"

        if len(uid) == 0:
            return False, f"{uid_type} cannot be empty"

        if not cls.UID_PATTERN.match(uid):
            return False, f"{uid_type} has invalid format (must be numeric components separated by dots)"

        components = uid.split('.')
        for component in components:
            if len(component) > 1 and component[0] == '0':
                return False, f"{uid_type} has component with leading zero: {component}"

        return True, None

    @classmethod
    def validate_study_uid(cls, uid: str) -> Tuple[bool, Optional[str]]:
        """Validate a Study Instance UID."""
        return cls.validate(uid, "StudyInstanceUID")

    @classmethod
    def validate_series_uid(cls, uid: str) -> Tuple[bool, Optional[str]]:
        """Validate a Series Instance UID."""
        return cls.validate(uid, "SeriesInstanceUID")

    @classmethod
    def validate_sop_uid(cls, uid: str) -> Tuple[bool, Optional[str]]:
        """Validate a SOP Instance UID."""
        return cls.validate(uid, "SOPInstanceUID")


class QueryLevelValidator:
    """
    Validates DICOM Query/Retrieve levels.

    Valid levels: PATIENT, STUDY, SERIES, IMAGE
    """

    VALID_LEVELS = {'PATIENT', 'STUDY', 'SERIES', 'IMAGE'}

    @classmethod
    def validate(cls, level: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a query/retrieve level.

        Args:
            level: Query level string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not level:
            return False, "Query level is required"

        if not isinstance(level, str):
            return False, "Query level must be a string"

        level = level.strip().upper()

        if level not in cls.VALID_LEVELS:
            return False, f"Invalid query level '{level}'. Must be one of: {', '.join(cls.VALID_LEVELS)}"

        return True, None

    @classmethod
    def get_valid_levels(cls) -> set:
        """Get set of valid query levels."""
        return cls.VALID_LEVELS.copy()


class DICOMDatasetValidator:
    """
    Validates DICOM datasets for required attributes.
    """

    STORAGE_REQUIRED_ATTRS = [
        'SOPClassUID',
        'SOPInstanceUID',
        'StudyInstanceUID',
        'SeriesInstanceUID',
        'PatientID',
    ]

    STORAGE_RECOMMENDED_ATTRS = [
        'PatientName',
        'StudyDate',
        'SeriesNumber',
        'InstanceNumber',
        'Modality',
    ]

    @classmethod
    def validate_for_storage(cls, dataset: Dataset) -> Tuple[bool, list, list]:
        """
        Validate dataset has required attributes for storage.

        Args:
            dataset: pydicom Dataset

        Returns:
            Tuple of (is_valid, missing_required, missing_recommended)
        """
        missing_required = []
        missing_recommended = []

        for attr in cls.STORAGE_REQUIRED_ATTRS:
            if not hasattr(dataset, attr) or getattr(dataset, attr) is None:
                missing_required.append(attr)

        for attr in cls.STORAGE_RECOMMENDED_ATTRS:
            if not hasattr(dataset, attr) or getattr(dataset, attr) is None:
                missing_recommended.append(attr)

        is_valid = len(missing_required) == 0

        return is_valid, missing_required, missing_recommended

    @classmethod
    def validate_uids(cls, dataset: Dataset) -> Tuple[bool, list]:
        """
        Validate all UIDs in dataset.

        Args:
            dataset: pydicom Dataset

        Returns:
            Tuple of (all_valid, list of invalid UIDs)
        """
        invalid_uids = []

        uid_attrs = [
            ('StudyInstanceUID', 'StudyInstanceUID'),
            ('SeriesInstanceUID', 'SeriesInstanceUID'),
            ('SOPInstanceUID', 'SOPInstanceUID'),
            ('SOPClassUID', 'SOPClassUID'),
        ]

        for attr_name, uid_type in uid_attrs:
            if hasattr(dataset, attr_name):
                uid_value = getattr(dataset, attr_name)
                if uid_value:
                    is_valid, error = DICOMUIDValidator.validate(str(uid_value), uid_type)
                    if not is_valid:
                        invalid_uids.append(f"{attr_name}: {error}")

        return len(invalid_uids) == 0, invalid_uids


class ModalityValidator:
    """
    Validates DICOM modality codes.
    """

    KNOWN_MODALITIES = {
        'CT', 'MR', 'PT', 'US', 'XA', 'RF', 'DX', 'CR', 'MG',
        'NM', 'OT', 'SC', 'SR', 'DOC', 'REG', 'SEG', 'RTDOSE',
        'RTPLAN', 'RTSTRUCT', 'RTIMAGE'
    }

    @classmethod
    def validate(cls, modality: str, strict: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate a modality code.

        Args:
            modality: Modality string (e.g., 'CT', 'MR', 'PT')
            strict: If True, only allow known modalities. If False, allow any non-empty string.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not modality:
            return False, "Modality is required"

        if not isinstance(modality, str):
            return False, "Modality must be a string"

        modality = modality.strip().upper()

        if len(modality) == 0:
            return False, "Modality cannot be empty"

        if strict and modality not in cls.KNOWN_MODALITIES:
            return False, f"Unknown modality '{modality}'. Known modalities: {', '.join(sorted(cls.KNOWN_MODALITIES))}"

        return True, None

    @classmethod
    def is_known_modality(cls, modality: str) -> bool:
        """Check if modality is in the known list."""
        return modality.strip().upper() in cls.KNOWN_MODALITIES


class SOPClassValidator:
    """
    Validates SOP Class UIDs and checks if they're supported.
    """

    STORAGE_SOP_CLASSES = {
        '1.2.840.10008.5.1.4.1.1.2',      # CT Image Storage
        '1.2.840.10008.5.1.4.1.1.2.1',    # Enhanced CT Image Storage
        '1.2.840.10008.5.1.4.1.1.4',      # MR Image Storage
        '1.2.840.10008.5.1.4.1.1.4.1',    # Enhanced MR Image Storage
        '1.2.840.10008.5.1.4.1.1.128',    # PET Image Storage
        '1.2.840.10008.5.1.4.1.1.130',    # Enhanced PET Image Storage
    }

    QR_SOP_CLASSES = {
        '1.2.840.10008.5.1.4.1.2.1.1',    # Patient Root QR Find
        '1.2.840.10008.5.1.4.1.2.1.2',    # Patient Root QR Move
        '1.2.840.10008.5.1.4.1.2.1.3',    # Patient Root QR Get
        '1.2.840.10008.5.1.4.1.2.2.1',    # Study Root QR Find
        '1.2.840.10008.5.1.4.1.2.2.2',    # Study Root QR Move
        '1.2.840.10008.5.1.4.1.2.2.3',    # Study Root QR Get
    }

    @classmethod
    def is_storage_sop_class(cls, uid: str) -> bool:
        """Check if UID is a storage SOP class."""
        return uid in cls.STORAGE_SOP_CLASSES

    @classmethod
    def is_qr_sop_class(cls, uid: str) -> bool:
        """Check if UID is a Query/Retrieve SOP class."""
        return uid in cls.QR_SOP_CLASSES or uid.startswith('1.2.840.10008.5.1.4.1.2.')

    @classmethod
    def validate_for_operation(
        cls,
        sop_class_uid: str,
        operation: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate SOP Class UID is appropriate for operation.

        Args:
            sop_class_uid: SOP Class UID
            operation: Operation type ('STORAGE', 'QUERY', 'RETRIEVE')

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not sop_class_uid:
            return False, "SOP Class UID is required"

        is_valid, error = DICOMUIDValidator.validate(sop_class_uid, "SOP Class UID")
        if not is_valid:
            return False, error

        if operation == 'STORAGE':
            if not cls.is_storage_sop_class(sop_class_uid):
                return False, f"SOP Class UID {sop_class_uid} is not a storage SOP class"
        elif operation in ['QUERY', 'RETRIEVE']:
            if not cls.is_qr_sop_class(sop_class_uid):
                return False, f"SOP Class UID {sop_class_uid} is not a Query/Retrieve SOP class"

        return True, None


class AETitleValidator:
    """
    Validates DICOM Application Entity (AE) Titles.

    AE Titles must:
    - Be 1-16 characters long
    - Contain only uppercase letters, numbers, spaces, hyphens, underscores
    """

    AE_PATTERN = re.compile(r'^[A-Z0-9 _-]+$')

    @classmethod
    def validate(cls, ae_title: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an AE Title.

        Args:
            ae_title: AE Title string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not ae_title:
            return False, "AE Title is required"

        if not isinstance(ae_title, str):
            return False, "AE Title must be a string"

        if len(ae_title) < 1:
            return False, "AE Title cannot be empty"

        if len(ae_title) > 16:
            return False, f"AE Title exceeds maximum length of 16 characters (got {len(ae_title)})"

        ae_upper = ae_title.upper()
        if not cls.AE_PATTERN.match(ae_upper):
            return False, "AE Title must contain only uppercase letters, numbers, spaces, hyphens, and underscores"

        return True, None
