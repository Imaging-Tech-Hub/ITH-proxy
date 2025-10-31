from django.db import models
from django.utils import timezone


class Session(models.Model):
    """
    Represents a DICOM Session (Study) - a collection of scans for a single exam.
    """
    STATUS_CHOICES = [
        ('incomplete', 'Incomplete'),
        ('complete', 'Complete'),
        ('uploaded', 'Uploaded'),
        ('archived', 'Archived'),
    ]

    study_instance_uid = models.CharField(max_length=255, unique=True, db_index=True)

    patient_name = models.CharField(max_length=255)
    patient_id = models.CharField(max_length=255, db_index=True)

    study_date = models.DateField(null=True, blank=True)
    study_time = models.TimeField(null=True, blank=True)
    study_description = models.TextField(blank=True)
    accession_number = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='incomplete')
    last_received_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    storage_path = models.CharField(max_length=500)

    # Study-level PHI metadata (original values before anonymization)
    # Stores: StudyDate, StudyTime, StudyID, Institution info, Physician names, etc.
    phi_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sessions'
        ordering = ['-last_received_at']
        indexes = [
            models.Index(fields=['study_instance_uid']),
            models.Index(fields=['patient_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-last_received_at']),
        ]

    def __str__(self):
        return f"Session {self.study_instance_uid} - {self.patient_name}"

    def get_phi_metadata(self) -> dict:
        """Get stored study-level PHI metadata."""
        return self.phi_metadata or {}

    def set_phi_metadata(self, metadata: dict):
        """Store study-level PHI metadata."""
        self.phi_metadata = metadata
        self.save(update_fields=['phi_metadata'])

    def delete(self, *args, **kwargs):
        """
        Override delete to clean up orphaned patient mappings.
        Also removes storage directory and all files.
        """
        import shutil
        from pathlib import Path
        from .patient_mapping import PatientMapping

        patient_id = self.patient_id
        storage_path = self.storage_path

        super().delete(*args, **kwargs)

        remaining_sessions = Session.objects.filter(patient_id=patient_id).exists()

        if not remaining_sessions:
            try:
                mapping = PatientMapping.objects.get(anonymous_patient_id=patient_id)
                mapping.delete()
            except PatientMapping.DoesNotExist:
                pass

        if storage_path:
            storage_dir = Path(storage_path)
            if storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)
