"""
PHI Metadata API
DRF API endpoint for retrieving PHI metadata by study UID.

WARNING: PROTECTED ENDPOINT - Requires Authentication
This endpoint returns Protected Health Information (PHI) and must be secured.
"""
import logging
from typing import Optional
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from receiver.models import Session, PatientMapping
from receiver.serializers import PHIMetadataSerializer, StudyUIDSerializer
from receiver.guard import IsAuthenticated

logger = logging.getLogger(__name__)


class PHIMetadataAPIView(APIView):
    """
    API endpoint to retrieve PHI metadata for a study.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/
    Authorization: Bearer <token>
    {
        "study_instance_uid": "1.2.3.4.5..."
    }

    Returns PHI metadata including original patient information.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = StudyUIDSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        study_uid = input_serializer.validated_data['study_instance_uid']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed PHI for study: {study_uid} "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_phi_metadata(study_uid)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_phi_metadata(self, study_uid: str) -> Response:
        """
        Retrieve PHI metadata for a study.

        Args:
            study_uid: Study Instance UID

        Returns:
            DRF Response with PHI metadata
        """
        try:
            study = _get_study(study_uid)

            if not study:
                return Response(
                    {"error": f"Study not found: {study_uid}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            mapping = _get_patient_mapping(study.patient_id)

            if not mapping:
                return Response(
                    {"error": f"Patient mapping not found for patient_id: {study.patient_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            response_data = {
                "study_instance_uid": study.study_instance_uid,
                "patient_name": study.patient_name,
                "patient_id": study.patient_id,
                "phi_metadata": mapping.get_phi_metadata(),
                "original_patient_name": mapping.original_patient_name,
                "original_patient_id": mapping.original_patient_id,
                "study_date": study.study_date,
                "study_time": study.study_time,
                "study_description": study.study_description,
                "accession_number": study.accession_number,
                "status": study.status,
            }

            serializer = PHIMetadataSerializer(response_data)
            logger.info(f"Retrieved PHI metadata for study: {study_uid}")

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving PHI metadata: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def _get_study(study_uid: str) -> Optional[Session]:
    """Get study from database."""
    try:
        return Session.objects.get(study_instance_uid=study_uid)
    except Session.DoesNotExist:
        return None


def _get_patient_mapping(patient_id: str) -> Optional[PatientMapping]:
    """Get patient mapping from database."""
    try:
        return PatientMapping.objects.get(anonymous_patient_id=patient_id)
    except PatientMapping.DoesNotExist:
        return None