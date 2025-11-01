"""
Admin interface for Scan model.
"""
from django.contrib import admin
from django.utils.html import format_html
from receiver.models import Scan


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    """
    Admin interface for Scan model.

    Overrides delete methods to ensure storage cleanup.
    """
    list_display = [
        'series_instance_uid_short',
        'session_link',
        'series_number',
        'modality',
        'instances_count',
        'phi_metadata_preview',
        'series_description_short',
        'created_at',
    ]
    list_filter = ['modality', 'created_at']
    search_fields = [
        'series_instance_uid',
        'series_description',
        'session__study_instance_uid',
        'session__patient_name',
    ]
    readonly_fields = [
        'series_instance_uid',
        'session',
        'storage_path',
        'instances_metadata_file',
        'created_at',
        'updated_at',
        'phi_metadata_display',
    ]

    fieldsets = (
        ('DICOM Identifiers', {
            'fields': ('series_instance_uid', 'session')
        }),
        ('Scan Metadata', {
            'fields': (
                'series_number',
                'modality',
                'series_description',
            )
        }),
        ('Instance Tracking', {
            'fields': ('instances_count', 'instances_metadata_file')
        }),
        ('Storage', {
            'fields': ('storage_path',),
            'classes': ('collapse',),
        }),
        ('Series-Level PHI Metadata', {
            'fields': ('phi_metadata_display',),
            'classes': ('collapse',),
            'description': 'Original series-level PHI metadata stored for de-anonymization (SeriesDate, AcquisitionDate/Time, DeviceSerialNumber, etc.)',
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def series_instance_uid_short(self, obj):
        """Show shortened UID."""
        uid = obj.series_instance_uid
        if len(uid) > 30:
            return f"{uid[:30]}..."
        return uid
    series_instance_uid_short.short_description = 'Series UID'

    def session_link(self, obj):
        """Link to parent session."""
        from django.urls import reverse
        from django.utils.html import escape
        url = reverse('admin:receiver_session_change', args=[obj.session.id])
        return format_html('<a href="{}">{}</a>', url, escape(obj.session.patient_name))
    session_link.short_description = 'Session'

    def series_description_short(self, obj):
        """Show shortened description."""
        desc = obj.series_description
        if len(desc) > 40:
            return f"{desc[:40]}..."
        return desc or '-'
    series_description_short.short_description = 'Description'

    def phi_metadata_preview(self, obj):
        """Show preview of series-level PHI metadata."""
        metadata = obj.get_phi_metadata()
        if metadata:
            keys = list(metadata.keys())[:3]
            preview = ', '.join(keys)
            if len(metadata) > 3:
                preview += f' (+{len(metadata) - 3} more)'
            return preview
        return '-'
    phi_metadata_preview.short_description = 'Series PHI'

    def phi_metadata_display(self, obj):
        """Display formatted series-level PHI metadata."""
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
        return format_html('<em>No series-level PHI metadata stored</em>')
    phi_metadata_display.short_description = 'Series-Level PHI Metadata (JSON)'

    def delete_model(self, request, obj):
        """
        Override delete_model to ensure custom delete() is called for single object deletion.

        This is called when deleting a single scan from the detail page.
        Ensures storage directory is cleaned up.
        """
        obj.delete()

    def delete_queryset(self, request, queryset):
        """
        Override delete_queryset to ensure custom delete() is called for each object.

        This is called when using the bulk delete action (selecting multiple scans).
        Django's default queryset.delete() bypasses the model's custom delete() method.
        """
        for obj in queryset:
            obj.delete()
