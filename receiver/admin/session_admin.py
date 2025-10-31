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
    """
    list_display = [
        'study_instance_uid_short',
        'patient_name',
        'patient_id',
        'study_date',
        'study_time',
        'status_badge',
        'scans_count',
        'phi_metadata_preview',
        'last_received_at',
    ]
    list_filter = ['status', 'study_date', 'last_received_at']
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
