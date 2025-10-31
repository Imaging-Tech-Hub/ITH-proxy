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
