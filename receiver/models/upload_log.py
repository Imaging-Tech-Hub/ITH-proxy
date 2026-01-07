"""
Upload Log Model - Tracks all upload attempts for audit trail and re-upload capability.
"""
from django.db import models
from django.utils import timezone


class UploadLog(models.Model):
    """
    Tracks all upload attempts for a session.
    Provides audit trail, error tracking, and enables re-upload functionality.

    Each time a session is uploaded (or re-uploaded), a new UploadLog record is created
    to track:
    - Which attempt number (1st, 2nd, 3rd retry, or manual re-upload)
    - Status of that attempt (in_progress, success, failed)
    - Exact error message from API if it failed
    - Timestamps for monitoring upload duration
    - API response ID for successful uploads
    - File size and chunk information for large file uploads
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]

    # Foreign key to Session
    session = models.ForeignKey(
        'Session',
        on_delete=models.CASCADE,
        related_name='upload_logs',
        help_text='The session/study being uploaded'
    )

    # Attempt tracking
    attempt_number = models.IntegerField(
        default=1,
        help_text='Which attempt this is (1st, 2nd, 3rd auto-retry, or manual re-upload)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Current status of this upload attempt'
    )

    # API response tracking
    api_response_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Dataset ID returned from platform API on success'
    )
    upload_file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Size of uploaded file in bytes'
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text='Error message from API or system (truncated to 500 chars)'
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text='HTTP status code (e.g., 401, 413, 500)'
    )

    # Timing information
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='When upload attempt started'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When upload attempt completed (success or failure)'
    )
    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text='How long the upload took in seconds'
    )

    # Large file handling
    chunk_index = models.IntegerField(
        null=True,
        blank=True,
        help_text='Which chunk this is (for files > 2GB)'
    )
    total_chunks = models.IntegerField(
        null=True,
        blank=True,
        help_text='Total number of chunks for this upload'
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this log record was created'
    )

    class Meta:
        db_table = 'upload_logs'
        ordering = ['-started_at']
        verbose_name = 'Upload Log'
        verbose_name_plural = 'Upload Logs'
        indexes = [
            models.Index(fields=['session', '-started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['attempt_number']),
            models.Index(fields=['-started_at']),
        ]

    def __str__(self):
        return f"Upload Attempt #{self.attempt_number} for {self.session.study_instance_uid} - {self.get_status_display()}"

    def is_success(self) -> bool:
        """Check if this upload was successful."""
        return self.status == 'success'

    def is_failed(self) -> bool:
        """Check if this upload failed."""
        return self.status == 'failed'

    def is_in_progress(self) -> bool:
        """Check if this upload is currently in progress."""
        return self.status == 'in_progress'

    def get_duration_display(self) -> str:
        """Get human-readable duration."""
        if self.duration_seconds is None:
            return 'N/A'
        if self.duration_seconds < 60:
            return f"{self.duration_seconds}s"
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}m {seconds}s"

    def get_file_size_display(self) -> str:
        """Get human-readable file size."""
        if self.upload_file_size is None:
            return 'N/A'
        size = self.upload_file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
