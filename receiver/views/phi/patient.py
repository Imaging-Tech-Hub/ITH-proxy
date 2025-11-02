"""Patient-Level PHI Metadata API.

Endpoint for retrieving patient-level PHI (demographics).
"""
import logging
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from receiver.serializers import (
    PatientPHIInputSerializer,
    PatientPHIResponseSerializer,
)
from receiver.guard import IsAuthenticated
from .query import get_patient_mapping

logger = logging.getLogger(__name__)


class PatientPHIMetadataView(APIView):
    """
    API endpoint to retrieve patient-level PHI metadata.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/patient/
    Authorization: Bearer <token>
    {
        "anonymous_patient_id": "ANON-a1b2c3d4e5f6"
    }

    Returns patient-level PHI including demographics.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = PatientPHIInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        anonymous_patient_id = input_serializer.validated_data['anonymous_patient_id']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed patient-level PHI for: {anonymous_patient_id} "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_patient_phi(anonymous_patient_id)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_patient_phi(self, anonymous_patient_id: str) -> Response:
        """
        Retrieve patient-level PHI metadata.

        Args:
            anonymous_patient_id: Anonymous patient ID

        Returns:
            DRF Response with patient-level PHI metadata
        """
        try:
            mapping = get_patient_mapping(anonymous_patient_id)

            if not mapping:
                return Response(
                    {"error": f"Patient not found: {anonymous_patient_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            response_data = {
                "anonymous_patient_id": mapping.anonymous_patient_id,
                "anonymous_patient_name": mapping.anonymous_patient_name,
                "original_patient_id": mapping.original_patient_id,
                "original_patient_name": mapping.original_patient_name,
                "patient_phi": mapping.get_phi_metadata(),
            }

            serializer = PatientPHIResponseSerializer(response_data)
            logger.info(
                f"Retrieved patient-level PHI for: {anonymous_patient_id} "
                f"({len(response_data['patient_phi'])} fields)"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving patient PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
