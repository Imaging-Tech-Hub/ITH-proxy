"""
Admin interface for UploadLog model.
Provides read-only view of upload history for debugging and auditing.
"""
from django.contrib import admin
from django.utils.html import format_html
from receiver.models import UploadLog


@admin.register(UploadLog)
class UploadLogAdmin(admin.ModelAdmin):
    """
    Admin interface for UploadLog model.
    Shows all upload attempts with their status, errors, and timing information.
    """
    list_display = [
        'attempt_number_display',
        'session_link',
        'status_badge',
        'started_at',
        'duration_display',
        'api_response_id_short',
        'error_short',
    ]

    list_filter = [
        'status',
        'attempt_number',
        'started_at',
    ]

    search_fields = [
        'session__study_instance_uid',
        'session__patient_name',
        'session__patient_id',
        'api_response_id',
        'error_message',
    ]

    readonly_fields = [
        'session',
        'attempt_number',
        'status',
        'api_response_id',
        'upload_file_size',
        'error_message_display',
        'error_code',
        'started_at',
        'completed_at',
        'duration_display',
        'chunk_index',
        'total_chunks',
        'created_at',
    ]

    fieldsets = (
        ('Session & Attempt', {
            'fields': ('session', 'attempt_number'),
        }),
        ('Status', {
            'fields': ('status', 'api_response_id'),
        }),
        ('File Information', {
            'fields': ('upload_file_size', 'chunk_index', 'total_chunks'),
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration_display'),
        }),
        ('Error Details', {
            'fields': ('error_code', 'error_message_display'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def attempt_number_display(self, obj):
        """Display attempt number."""
        return f"Attempt #{obj.attempt_number}"
    attempt_number_display.short_description = 'Attempt'

    def session_link(self, obj):
        """Link to parent session."""
        from django.urls import reverse
        from django.utils.html import escape
        url = reverse('admin:receiver_session_change', args=[obj.session.id])
        study_uid_short = obj.session.study_instance_uid[:20] + '...' if len(obj.session.study_instance_uid) > 20 else obj.session.study_instance_uid
        return format_html(
            '<a href="{}">{} ({})</a>',
            url,
            escape(obj.session.patient_name),
            study_uid_short
        )
    session_link.short_description = 'Session'

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'pending': '#6c757d',        # gray
            'in_progress': '#ffc107',    # yellow
            'success': '#28a745',        # green
            'failed': '#dc3545',         # red
            'retrying': '#fd7e14',       # orange
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        """Display formatted duration."""
        return obj.get_duration_display()
    duration_display.short_description = 'Duration'

    def api_response_id_short(self, obj):
        """Show shortened API response ID."""
        if not obj.api_response_id:
            return format_html('<em>-</em>')
        uid = obj.api_response_id
        if len(uid) > 15:
            return f"{uid[:15]}..."
        return uid
    api_response_id_short.short_description = 'Response ID'

    def error_short(self, obj):
        """Show shortened error message."""
        if not obj.error_message:
            return format_html('<em>-</em>')
        msg = obj.error_message
        if len(msg) > 50:
            return f"{msg[:50]}..."
        return msg
    error_short.short_description = 'Error'

    def error_message_display(self, obj):
        """Display formatted error message."""
        if not obj.error_message:
            return format_html('<em>No error</em>')
        return format_html(
            '<pre style="padding: 10px; border-radius: 4px; '
            'background: #f8d7da; border: 1px solid #f5c6cb; '
            'overflow: auto; max-height: 300px;">{}</pre>',
            obj.error_message
        )
    error_message_display.short_description = 'Error Message'

    def has_add_permission(self, request):
        """Disable adding UploadLog records manually."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting UploadLog records manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make UploadLog read-only."""
        return False
