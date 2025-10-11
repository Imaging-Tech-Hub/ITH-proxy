"""PHI Query Helpers."""
from typing import Optional
from receiver.models import Session, PatientMapping


def get_study(study_uid: str) -> Optional[Session]:
    """
    Get study from database.

    Args:
        study_uid: Study Instance UID

    Returns:
        Session object or None if not found
    """
    try:
        return Session.objects.get(study_instance_uid=study_uid)
    except Session.DoesNotExist:
        return None


def get_patient_mapping(patient_id: str) -> Optional[PatientMapping]:
    """
    Get patient mapping from database.

    Args:
        patient_id: Anonymous patient ID

    Returns:
        PatientMapping object or None if not found
    """
    try:
        return PatientMapping.objects.get(anonymous_patient_id=patient_id)
    except PatientMapping.DoesNotExist:
        return None
