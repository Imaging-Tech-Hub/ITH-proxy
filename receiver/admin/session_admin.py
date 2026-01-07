"""
Admin interface for Session model.
"""
from django.contrib import admin
from django.utils.html import format_html
from receiver.models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """
    Admin interface for Session model.

    Overrides delete methods to ensure cascade deletion of scans and storage cleanup.
    Includes re-upload action for failed uploads.
    """
    actions = ['retry_failed_uploads']

    list_display = [
        'study_instance_uid_short',
        'patient_name',
        'patient_id',
        'study_date',
        'study_time',
        'status_badge',
        'upload_status_badge',
        'upload_attempt_count',
        'scans_count',
        'last_received_at',
    ]
    list_filter = ['status', 'upload_status', 'study_date', 'last_received_at']
    search_fields = [
        'study_instance_uid',
        'patient_name',
        'patient_id',
        'accession_number',
        'study_description',
    ]
    readonly_fields = [
        'study_instance_uid',
        'storage_path',
        'created_at',
        'updated_at',
        'completed_at',
        'phi_metadata_display',
        'upload_status',
        'upload_attempt_count',
        'last_upload_attempt_at',
        'last_upload_error_display',
        'upload_history_display',
    ]

    fieldsets = (
        ('DICOM Identifiers', {
            'fields': ('study_instance_uid',)
        }),
        ('Patient Information', {
            'fields': ('patient_name', 'patient_id')
        }),
        ('Session Metadata', {
            'fields': (
                'study_date',
                'study_time',
                'study_description',
                'accession_number',
            )
        }),
        ('Status', {
            'fields': ('status', 'last_received_at', 'completed_at')
        }),
        ('Upload Status', {
            'fields': (
                'upload_status',
                'upload_attempt_count',
                'last_upload_attempt_at',
                'last_upload_error_display',
                'upload_history_display',
            ),
        }),
        ('Storage', {
            'fields': ('storage_path',),
            'classes': ('collapse',),
        }),
        ('Study-Level PHI Metadata', {
            'fields': ('phi_metadata_display',),
            'classes': ('collapse',),
            'description': 'Original study-level PHI metadata stored for de-anonymization (StudyDate, Institution, Physicians, etc.)',
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def study_instance_uid_short(self, obj):
        """Show shortened UID."""
        uid = obj.study_instance_uid
        if len(uid) > 30:
            return f"{uid[:30]}..."
        return uid
    study_instance_uid_short.short_description = 'Study UID'

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'incomplete': '#ffc107',
            'complete': '#28a745',
            'uploaded': '#17a2b8',
            'archived': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def scans_count(self, obj):
        """Show number of scans."""
        return obj.scans.count()
    scans_count.short_description = 'Scans'

    def phi_metadata_preview(self, obj):
        """Show preview of study-level PHI metadata."""
        metadata = obj.get_phi_metadata()
        if metadata:
            keys = list(metadata.keys())[:3]
            preview = ', '.join(keys)
            if len(metadata) > 3:
                preview += f' (+{len(metadata) - 3} more)'
            return preview
        return '-'
    phi_metadata_preview.short_description = 'Study PHI'

    def phi_metadata_display(self, obj):
        """Display formatted study-level PHI metadata."""
        import json
        metadata = obj.get_phi_metadata()
        if metadata:
            formatted = json.dumps(metadata, indent=2)
            return format_html(
                '<pre style="padding: 10px; border-radius: 4px; '
                'background: rgba(0, 0, 0, 0.05); '
                'border: 1px solid rgba(0, 0, 0, 0.1); '
                'max-height: 400px; overflow: auto;">'
                '{}</pre>',
                formatted
            )
        return format_html('<em>No study-level PHI metadata stored</em>')
    phi_metadata_display.short_description = 'Study-Level PHI Metadata (JSON)'

    def upload_status_badge(self, obj):
        """Display upload status with color badge."""
        colors = {
            'not_started': '#6c757d',      # gray
            'in_progress': '#ffc107',      # yellow
            'success': '#28a745',          # green
            'failed': '#dc3545',           # red
            'pending_retry': '#fd7e14',    # orange
        }
        color = colors.get(obj.upload_status, '#6c757d')
        status_display = dict(obj._meta.get_field('upload_status').choices).get(obj.upload_status, obj.upload_status)

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            status_display
        )
    upload_status_badge.short_description = 'Upload Status'

    def last_upload_error_display(self, obj):
        """Display last upload error message."""
        if not obj.last_upload_error:
            return format_html('<em>No error</em>')

        return format_html(
            '<pre style="padding: 10px; border-radius: 4px; '
            'background: #f8d7da; border: 1px solid #f5c6cb; '
            'overflow: auto; max-height: 300px;">{}</pre>',
            obj.last_upload_error
        )
    last_upload_error_display.short_description = 'Last Error'

    def upload_history_display(self, obj):
        """Display upload attempt history."""
        logs = obj.upload_logs.all().order_by('-started_at')
        if not logs:
            return format_html('<em>No upload attempts</em>')

        html = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">'
        html += '<tr style="background: #f5f5f5;"><th style="border: 1px solid #ddd; padding: 8px;">Attempt</th><th style="border: 1px solid #ddd; padding: 8px;">Status</th><th style="border: 1px solid #ddd; padding: 8px;">Started</th><th style="border: 1px solid #ddd; padding: 8px;">Duration</th><th style="border: 1px solid #ddd; padding: 8px;">Error (first 100 chars)</th></tr>'

        for log in logs:
            status_color = {
                'in_progress': '#ffc107',
                'success': '#28a745',
                'failed': '#dc3545',
                'pending': '#fd7e14',
            }.get(log.status, '#6c757d')

            error_preview = log.error_message[:100] if log.error_message else '-'

            html += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center;"><strong>#{log.attempt_number}</strong></td>
                <td style="border: 1px solid #ddd; padding: 8px;"><span style="background: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{log.get_status_display()}</span></td>
                <td style="border: 1px solid #ddd; padding: 8px; font-size: 11px;">{log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else '-'}</td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 11px;">{log.get_duration_display()}</td>
                <td style="border: 1px solid #ddd; padding: 8px; font-size: 11px; max-width: 300px; overflow: auto;"><code>{error_preview}</code></td>
            </tr>
            '''

        html += '</table>'
        return format_html(html)
    upload_history_display.short_description = 'Upload Attempt History'

    @admin.action(description='Retry failed uploads')
    def retry_failed_uploads(self, request, queryset):
        """
        Re-upload studies that failed previously.
        This action allows manual re-upload of failed studies without re-ingesting DICOM files.
        """
        from pathlib import Path
        from receiver.controllers.storage.archive_service import ArchiveService
        from receiver.services.upload import get_study_uploader
        from django.contrib import messages

        retried = 0
        failed = 0

        for session in queryset:
            if session.upload_status != 'failed':
                messages.warning(request, f"Skipped {session.study_instance_uid[:20]}...: not in failed state (current: {session.get_upload_status_display()})")
                continue

            try:
                # Check if DICOM files still exist
                study_path = Path(session.storage_path)
                if not study_path.exists():
                    messages.error(request, f"DICOM files missing for {session.study_instance_uid[:20]}...")
                    failed += 1
                    continue

                # Re-archive the study
                archive_service = ArchiveService()
                archive_name = f"{session.patient_id}_{session.study_instance_uid}_retry_{session.upload_attempt_count}"
                zip_path = archive_service.create_study_archive(study_path, archive_name)

                if not zip_path:
                    messages.error(request, f"Failed to create archive for {session.study_instance_uid[:20]}...")
                    failed += 1
                    continue

                # Get uploader
                uploader = get_study_uploader()
                if not uploader:
                    messages.error(request, f"Uploader not available for {session.study_instance_uid[:20]}...")
                    archive_service.cleanup_archive(zip_path)
                    failed += 1
                    continue

                # Prepare study info
                study_info = {
                    'name': session.patient_name,
                    'patient_id': session.patient_id,
                    'description': session.study_description,
                    'metadata': {
                        'study_uid': session.study_instance_uid,
                        'study_date': str(session.study_date) if session.study_date else None,
                    }
                }

                # Re-upload (this will create a new UploadLog entry)
                success, response_data = uploader.upload_study(zip_path, study_info, attempt_override=None)

                if success:
                    retried += 1
                    messages.success(request, f"✓ Successfully re-uploaded: {session.study_instance_uid[:20]}... (Dataset: {response_data.get('id', 'N/A')})")
                else:
                    failed += 1
                    messages.error(request, f"✗ Re-upload failed for: {session.study_instance_uid[:20]}...")

                # Cleanup archive after upload
                archive_service.cleanup_archive(zip_path)

            except Exception as e:
                failed += 1
                messages.error(request, f"Error retrying {session.study_instance_uid[:20]}...: {str(e)[:100]}")

        # Summary message
        if retried > 0:
            messages.success(request, f"✓ Successfully re-uploaded {retried} session(s)")
        if failed > 0:
            messages.error(request, f"✗ Failed to re-upload {failed} session(s)")
        if retried == 0 and failed == 0:
            messages.warning(request, "No failed sessions selected")

    def delete_model(self, request, obj):
        """
        Override delete_model to ensure custom delete() is called for single object deletion.

        This is called when deleting a single session from the detail page.
        Ensures scans are deleted, storage is cleaned up, and orphaned patients are removed.
        """
        obj.delete()

    def delete_queryset(self, request, queryset):
        """
        Override delete_queryset to ensure custom delete() is called for each object.

        This is called when using the bulk delete action (selecting multiple sessions).
        Django's default queryset.delete() bypasses the model's custom delete() method.
        """
        for obj in queryset:
            obj.delete()
