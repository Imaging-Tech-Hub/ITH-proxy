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
