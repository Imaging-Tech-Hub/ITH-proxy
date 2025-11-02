"""
DRF Serializers for PHI metadata API.
"""
from rest_framework import serializers


class PHIMetadataSerializer(serializers.Serializer):
    """
    Serializer for PHI metadata response with three-level structure.

    Returns PHI metadata organized by hierarchical level:
    - patient_phi: Patient-level PHI (demographics)
    - study_phi: Study-level PHI (institution, physicians, study dates)
    - series_phi: Series-level PHI (acquisition dates, device info) - list of dicts per series
    """
    study_instance_uid = serializers.CharField()
    patient_name = serializers.CharField()
    patient_id = serializers.CharField()

    # Three-level PHI metadata structure
    patient_phi = serializers.JSONField(help_text="Patient-level PHI metadata")
    study_phi = serializers.JSONField(help_text="Study-level PHI metadata")
    series_phi = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of series-level PHI metadata (one per series)"
    )

    # Original patient identifiers
    original_patient_name = serializers.CharField()
    original_patient_id = serializers.CharField()

    # Study metadata (anonymized values currently in DB)
    study_date = serializers.DateField(allow_null=True)
    study_time = serializers.TimeField(allow_null=True)
    study_description = serializers.CharField(allow_blank=True)
    accession_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()

    # Series count
    series_count = serializers.IntegerField(help_text="Number of series in this study")


class StudyUIDSerializer(serializers.Serializer):
    """
    Serializer for study UID input.
    """
    study_instance_uid = serializers.CharField(required=True, help_text="DICOM Study Instance UID")


# ============================================================================
# Serializers for Three-Level PHI APIs
# ============================================================================

class PatientPHIInputSerializer(serializers.Serializer):
    """Input serializer for patient PHI API."""
    anonymous_patient_id = serializers.CharField(
        required=True,
        help_text="Anonymous patient ID (e.g., 'ANON-a1b2c3d4e5f6')"
    )


class PatientPHIResponseSerializer(serializers.Serializer):
    """Response serializer for patient-level PHI."""
    anonymous_patient_id = serializers.CharField()
    anonymous_patient_name = serializers.CharField()
    original_patient_id = serializers.CharField()
    original_patient_name = serializers.CharField()
    patient_phi = serializers.JSONField(help_text="Patient-level PHI metadata (demographics)")


class StudyPHIInputSerializer(serializers.Serializer):
    """Input serializer for study PHI API."""
    study_instance_uid = serializers.CharField(
        required=True,
        help_text="DICOM Study Instance UID"
    )


class StudyPHIResponseSerializer(serializers.Serializer):
    """Response serializer for study-level PHI."""
    study_instance_uid = serializers.CharField()
    patient_id = serializers.CharField()
    patient_name = serializers.CharField()
    study_date = serializers.DateField(allow_null=True)
    study_time = serializers.TimeField(allow_null=True)
    study_description = serializers.CharField(allow_blank=True)
    accession_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    study_phi = serializers.JSONField(help_text="Study-level PHI metadata (institution, physicians, dates)")


class SeriesPHIInputSerializer(serializers.Serializer):
    """Input serializer for series PHI API."""
    series_instance_uid = serializers.CharField(
        required=True,
        help_text="DICOM Series Instance UID"
    )


class SeriesPHIResponseSerializer(serializers.Serializer):
    """Response serializer for series-level PHI."""
    series_instance_uid = serializers.CharField()
    series_number = serializers.IntegerField(allow_null=True)
    modality = serializers.CharField()
    series_description = serializers.CharField(allow_blank=True)
    series_phi = serializers.JSONField(help_text="Series-level PHI metadata (acquisition dates, device info)")


# ============================================================================
# Batch Serializers for Multiple Items
# ============================================================================

class PatientPHIBatchInputSerializer(serializers.Serializer):
    """Input serializer for batch patient PHI API."""
    anonymous_patient_ids = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        min_length=1,
        max_length=100,
        help_text="List of anonymous patient IDs (max 100 per request)"
    )


class PatientPHIBatchResponseSerializer(serializers.Serializer):
    """Response serializer for batch patient-level PHI."""
    results = serializers.ListField(
        child=PatientPHIResponseSerializer(),
        help_text="List of patient PHI results"
    )
    total = serializers.IntegerField(help_text="Total number of results returned")
    requested = serializers.IntegerField(help_text="Total number of IDs requested")
    not_found = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of IDs that were not found"
    )


class StudyPHIBatchInputSerializer(serializers.Serializer):
    """Input serializer for batch study PHI API."""
    study_instance_uids = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        min_length=1,
        max_length=100,
        help_text="List of study instance UIDs (max 100 per request)"
    )


class StudyPHIBatchResponseSerializer(serializers.Serializer):
    """Response serializer for batch study-level PHI."""
    results = serializers.ListField(
        child=StudyPHIResponseSerializer(),
        help_text="List of study PHI results"
    )
    total = serializers.IntegerField(help_text="Total number of results returned")
    requested = serializers.IntegerField(help_text="Total number of UIDs requested")
    not_found = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of UIDs that were not found"
    )


class SeriesPHIBatchInputSerializer(serializers.Serializer):
    """Input serializer for batch series PHI API."""
    series_instance_uids = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        min_length=1,
        max_length=100,
        help_text="List of series instance UIDs (max 100 per request)"
    )


class SeriesPHIBatchResponseSerializer(serializers.Serializer):
    """Response serializer for batch series-level PHI."""
    results = serializers.ListField(
        child=SeriesPHIResponseSerializer(),
        help_text="List of series PHI results"
    )
    total = serializers.IntegerField(help_text="Total number of results returned")
    requested = serializers.IntegerField(help_text="Total number of UIDs requested")
    not_found = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of UIDs that were not found"
    )
