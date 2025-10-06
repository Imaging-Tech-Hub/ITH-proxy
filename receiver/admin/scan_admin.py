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
    """
    list_display = [
        'series_instance_uid_short',
        'session_link',
        'series_number',
        'modality',
        'instances_count',
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
