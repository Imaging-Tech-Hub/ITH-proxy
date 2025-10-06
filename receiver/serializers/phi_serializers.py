"""
DRF Serializers for PHI metadata API.
"""
from rest_framework import serializers


class PHIMetadataSerializer(serializers.Serializer):
    """
    Serializer for PHI metadata response.
    """
    study_instance_uid = serializers.CharField()
    patient_name = serializers.CharField()
    patient_id = serializers.CharField()
    phi_metadata = serializers.JSONField()
    original_patient_name = serializers.CharField()
    original_patient_id = serializers.CharField()
    study_date = serializers.DateField(allow_null=True)
    study_time = serializers.TimeField(allow_null=True)
    study_description = serializers.CharField(allow_blank=True)
    accession_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()


class StudyUIDSerializer(serializers.Serializer):
    """
    Serializer for study UID input.
    """
    study_instance_uid = serializers.CharField(required=True, help_text="DICOM Study Instance UID")
