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
        ('Patient-Level PHI Metadata', {
            'fields': ('phi_metadata_display',),
            'classes': ('collapse',),
            'description': 'Patient-level PHI metadata (PatientBirthDate, PatientSex, PatientWeight, etc.). Study and series PHI are stored in their respective tables.',
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )

    def phi_metadata_preview(self, obj):
        """Show preview of patient-level PHI metadata."""
        metadata = obj.get_phi_metadata()
        if metadata:
            keys = list(metadata.keys())[:3]
            preview = ', '.join(keys)
            if len(metadata) > 3:
                preview += f' (+{len(metadata) - 3} more)'
            return preview
        return '-'
    phi_metadata_preview.short_description = 'Patient PHI'

    def phi_metadata_display(self, obj):
        """Display formatted patient-level PHI metadata."""
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
        return format_html('<em>No patient-level PHI metadata stored</em>')
    phi_metadata_display.short_description = 'Patient-Level PHI Metadata (JSON)'
