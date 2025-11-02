"""Django Signals for Cache Invalidation.

Automatically invalidates cache when PHI models are updated.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from receiver.models import Session, PatientMapping, Scan

logger = logging.getLogger(__name__)


# Cache key prefixes (must match query.py)
CACHE_PREFIX_STUDY = "study:"
CACHE_PREFIX_PATIENT = "patient:"
CACHE_PREFIX_SCAN = "scan:"


@receiver(post_save, sender=Session)
def invalidate_study_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate study cache when a Session is saved.

    Args:
        sender: The model class (Session)
        instance: The actual instance being saved
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_STUDY}{instance.study_instance_uid}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for study: {instance.study_instance_uid}")


@receiver(post_delete, sender=Session)
def invalidate_study_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate study cache when a Session is deleted.

    Args:
        sender: The model class (Session)
        instance: The actual instance being deleted
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_STUDY}{instance.study_instance_uid}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for deleted study: {instance.study_instance_uid}")


@receiver(post_save, sender=PatientMapping)
def invalidate_patient_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate patient cache when a PatientMapping is saved.

    Args:
        sender: The model class (PatientMapping)
        instance: The actual instance being saved
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_PATIENT}{instance.anonymous_patient_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for patient: {instance.anonymous_patient_id}")


@receiver(post_delete, sender=PatientMapping)
def invalidate_patient_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate patient cache when a PatientMapping is deleted.

    Args:
        sender: The model class (PatientMapping)
        instance: The actual instance being deleted
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_PATIENT}{instance.anonymous_patient_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for deleted patient: {instance.anonymous_patient_id}")


@receiver(post_save, sender=Scan)
def invalidate_scan_cache_on_save(sender, instance, **kwargs):
    """
    Invalidate scan cache when a Scan is saved.

    Args:
        sender: The model class (Scan)
        instance: The actual instance being saved
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_SCAN}{instance.series_instance_uid}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for scan: {instance.series_instance_uid}")


@receiver(post_delete, sender=Scan)
def invalidate_scan_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate scan cache when a Scan is deleted.

    Args:
        sender: The model class (Scan)
        instance: The actual instance being deleted
        kwargs: Additional keyword arguments
    """
    cache_key = f"{CACHE_PREFIX_SCAN}{instance.series_instance_uid}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for deleted scan: {instance.series_instance_uid}")
