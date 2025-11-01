from django.db import models
from django.utils import timezone
from .session import Session


class Scan(models.Model):
    """
    Represents DICOM Scan (Series) - a collection of instances within a session.
    Instance metadata is stored in instances.xml file in the scan directory.
    """
    series_instance_uid = models.CharField(max_length=255, unique=True, db_index=True)

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='scans')

    series_number = models.IntegerField(null=True, blank=True)
    series_description = models.TextField(blank=True)
    modality = models.CharField(max_length=16, blank=True)

    storage_path = models.CharField(max_length=500)

    instances_count = models.IntegerField(default=0)
    instances_metadata_file = models.CharField(max_length=500, default='instances.xml')

    # Series-level PHI metadata (original values before anonymization)
    # Stores: SeriesDate, SeriesTime, AcquisitionDate/Time, ContentDate/Time, DeviceSerialNumber, etc.
    phi_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scans'
        ordering = ['series_number']
        indexes = [
            models.Index(fields=['series_instance_uid']),
            models.Index(fields=['session']),
        ]

    def __str__(self):
        return f"Scan {self.series_number} - {self.modality}"

    def get_phi_metadata(self) -> dict:
        """Get stored series-level PHI metadata."""
        return self.phi_metadata or {}

    def set_phi_metadata(self, metadata: dict):
        """Store series-level PHI metadata."""
        self.phi_metadata = metadata
        self.save(update_fields=['phi_metadata'])

    def get_instances_xml_path(self):
        """Get full path to instances metadata XML file."""
        from pathlib import Path
        return Path(self.storage_path) / self.instances_metadata_file

    def delete(self, *args, **kwargs):
        """
        Override delete to clean up storage directory.

        When a scan is deleted:
        1. Remove the storage directory and all DICOM files
        2. Delete the scan record
        """
        import shutil
        from pathlib import Path

        storage_path = self.storage_path

        super().delete(*args, **kwargs)

        if storage_path:
            storage_dir = Path(storage_path)
            if storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)
