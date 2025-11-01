"""PHI Query Helpers with Caching."""
from typing import Optional
from django.core.cache import cache
from receiver.models import Session, PatientMapping, Scan


# Cache key prefixes
CACHE_PREFIX_STUDY = "study:"
CACHE_PREFIX_PATIENT = "patient:"
CACHE_PREFIX_SCAN = "scan:"


def get_study(study_uid: str) -> Optional[Session]:
    """
    Get study from database with caching.

    Args:
        study_uid: Study Instance UID

    Returns:
        Session object or None if not found
    """
    cache_key = f"{CACHE_PREFIX_STUDY}{study_uid}"

    # Try to get from cache first
    cached_study = cache.get(cache_key)
    if cached_study is not None:
        return cached_study

    # If not in cache, query database
    try:
        study = Session.objects.get(study_instance_uid=study_uid)
        # Cache the result
        cache.set(cache_key, study)
        return study
    except Session.DoesNotExist:
        # Cache negative result (None) to avoid repeated DB queries for non-existent items
        cache.set(cache_key, None, timeout=60)  # Cache misses for 1 minute only
        return None


def get_patient_mapping(patient_id: str) -> Optional[PatientMapping]:
    """
    Get patient mapping from database with caching.

    Args:
        patient_id: Anonymous patient ID

    Returns:
        PatientMapping object or None if not found
    """
    cache_key = f"{CACHE_PREFIX_PATIENT}{patient_id}"

    # Try to get from cache first
    cached_mapping = cache.get(cache_key)
    if cached_mapping is not None:
        return cached_mapping

    # If not in cache, query database
    try:
        mapping = PatientMapping.objects.get(anonymous_patient_id=patient_id)
        # Cache the result
        cache.set(cache_key, mapping)
        return mapping
    except PatientMapping.DoesNotExist:
        # Cache negative result (None) to avoid repeated DB queries for non-existent items
        cache.set(cache_key, None, timeout=60)  # Cache misses for 1 minute only
        return None


def get_scan(series_uid: str) -> Optional[Scan]:
    """
    Get scan (series) from database with caching.

    Args:
        series_uid: Series Instance UID

    Returns:
        Scan object or None if not found
    """
    cache_key = f"{CACHE_PREFIX_SCAN}{series_uid}"

    # Try to get from cache first
    cached_scan = cache.get(cache_key)
    if cached_scan is not None:
        return cached_scan

    # If not in cache, query database
    try:
        scan = Scan.objects.get(series_instance_uid=series_uid)
        # Cache the result
        cache.set(cache_key, scan)
        return scan
    except Scan.DoesNotExist:
        # Cache negative result (None) to avoid repeated DB queries for non-existent items
        cache.set(cache_key, None, timeout=60)  # Cache misses for 1 minute only
        return None


def invalidate_study_cache(study_uid: str) -> None:
    """
    Invalidate cache for a specific study.

    Args:
        study_uid: Study Instance UID
    """
    cache_key = f"{CACHE_PREFIX_STUDY}{study_uid}"
    cache.delete(cache_key)


def invalidate_patient_cache(patient_id: str) -> None:
    """
    Invalidate cache for a specific patient.

    Args:
        patient_id: Anonymous patient ID
    """
    cache_key = f"{CACHE_PREFIX_PATIENT}{patient_id}"
    cache.delete(cache_key)


def invalidate_scan_cache(series_uid: str) -> None:
    """
    Invalidate cache for a specific scan.

    Args:
        series_uid: Series Instance UID
    """
    cache_key = f"{CACHE_PREFIX_SCAN}{series_uid}"
    cache.delete(cache_key)
