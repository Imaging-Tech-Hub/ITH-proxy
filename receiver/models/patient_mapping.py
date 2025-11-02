from django.db import models
from django.utils import timezone
import json


class PatientMapping(models.Model):
    """
    Stores reversible patient anonymization mappings.
    Maps original patient identifiers to anonymous identifiers.
    Preserves patient-level PHI data for authorized de-anonymization.

    Patient-level PHI includes: PatientBirthDate, PatientSize, PatientWeight, PatientSex
    Note: PatientAge is NOT stored as it can be calculated from PatientBirthDate + StudyDate
    """
    original_patient_name = models.CharField(max_length=512, db_index=True)
    original_patient_id = models.CharField(max_length=512, db_index=True)

    anonymous_patient_name = models.CharField(max_length=255, unique=True, db_index=True)
    anonymous_patient_id = models.CharField(max_length=255, unique=True, db_index=True)


    phi_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'patient_mappings'
        indexes = [
            models.Index(fields=['anonymous_patient_name']),
            models.Index(fields=['anonymous_patient_id']),
        ]

    def __str__(self):
        return f"{self.original_patient_name} -> {self.anonymous_patient_name}"

    def get_phi_metadata(self) -> dict:
        """Get stored PHI metadata."""
        return self.phi_metadata or {}

    def set_phi_metadata(self, metadata: dict):
        """Store PHI metadata."""
        self.phi_metadata = metadata
        self.save(update_fields=['phi_metadata'])

    def delete(self, *args, **kwargs):
        """
        Override delete to cascade delete all related sessions and scans.

        When a patient mapping is deleted (e.g., from Django admin):
        1. Find all sessions for this patient (by anonymous_patient_id)
        2. Delete each session (triggers Session.delete() which cleans up scans and storage)
        3. Delete the patient mapping

        Args:
            skip_session_cleanup: Internal flag to prevent circular deletion when called from Session.delete()
        """
        from receiver.models.session import Session
        import logging

        logger = logging.getLogger(__name__)

        skip_session_cleanup = kwargs.pop('skip_session_cleanup', False)

        if not skip_session_cleanup:
            anonymous_patient_id = self.anonymous_patient_id

            sessions = Session.objects.filter(patient_id=anonymous_patient_id)
            session_count = sessions.count()

            for session in sessions:
                session.delete(skip_patient_cleanup=True)

            logger.info(
                f"Patient mapping deleted: {self.original_patient_name} ({self.original_patient_id}) -> "
                f"{self.anonymous_patient_name}. Cascade deleted {session_count} sessions."
            )

        super().delete(*args, **kwargs)
