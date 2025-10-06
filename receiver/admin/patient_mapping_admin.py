"""
Admin interface for PatientMapping model.
"""
from django.contrib import admin
from django.utils.html import format_html
from receiver.models import PatientMapping


@admin.register(PatientMapping)
class PatientMappingAdmin(admin.ModelAdmin):
    """
    Admin interface for PatientMapping model.
    """
    list_display = [
        'id',
        'anonymous_patient_id',
        'anonymous_patient_name',
        'original_patient_id',
        'original_patient_name',
        'created_at',
        'phi_metadata_preview',
    ]
    list_filter = ['created_at']
    search_fields = [
        'anonymous_patient_id',
        'anonymous_patient_name',
        'original_patient_id',
        'original_patient_name',
    ]
    readonly_fields = ['created_at', 'phi_metadata_display']

    fieldsets = (
        ('Anonymous Patient Information', {
            'fields': ('anonymous_patient_id', 'anonymous_patient_name')
        }),
        ('Original Patient Information', {
            'fields': ('original_patient_id', 'original_patient_name'),
            'classes': ('collapse',),
        }),
        ('PHI Metadata', {
            'fields': ('phi_metadata_display',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )

    def phi_metadata_preview(self, obj):
        """Show preview of PHI metadata."""
        metadata = obj.get_phi_metadata()
        if metadata:
            keys = list(metadata.keys())[:3]
            preview = ', '.join(keys)
            if len(metadata) > 3:
                preview += f' (+{len(metadata) - 3} more)'
            return preview
        return '-'
    phi_metadata_preview.short_description = 'PHI Metadata'

    def phi_metadata_display(self, obj):
        """Display formatted PHI metadata."""
        import json
        metadata = obj.get_phi_metadata()
        if metadata:
            formatted = json.dumps(metadata, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        return '-'
    phi_metadata_display.short_description = 'PHI Metadata (JSON)'
