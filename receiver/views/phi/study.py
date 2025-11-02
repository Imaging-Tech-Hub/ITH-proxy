"""Study-Level PHI Metadata API.

Endpoint for retrieving study-level PHI (institution, physicians, dates).
"""
import logging
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from receiver.serializers import (
    StudyPHIInputSerializer,
    StudyPHIResponseSerializer,
)
from receiver.guard import IsAuthenticated
from .query import get_study

logger = logging.getLogger(__name__)


class StudyPHIMetadataView(APIView):
    """
    API endpoint to retrieve study-level PHI metadata.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/study/
    Authorization: Bearer <token>
    {
        "study_instance_uid": "1.2.3.4.5..."
    }

    Returns study-level PHI including institution info, physician names, and study dates.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = StudyPHIInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        study_uid = input_serializer.validated_data['study_instance_uid']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed study-level PHI for: {study_uid} "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_study_phi(study_uid)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_study_phi(self, study_uid: str) -> Response:
        """
        Retrieve study-level PHI metadata.

        Args:
            study_uid: Study Instance UID

        Returns:
            DRF Response with study-level PHI metadata
        """
        try:
            study = get_study(study_uid)

            if not study:
                return Response(
                    {"error": f"Study not found: {study_uid}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            response_data = {
                "study_instance_uid": study.study_instance_uid,
                "patient_id": study.patient_id,
                "patient_name": study.patient_name,
                "study_date": study.study_date,
                "study_time": study.study_time,
                "study_description": study.study_description,
                "accession_number": study.accession_number,
                "status": study.status,
                "study_phi": study.get_phi_metadata(),
            }

            serializer = StudyPHIResponseSerializer(response_data)
            logger.info(
                f"Retrieved study-level PHI for: {study_uid} "
                f"({len(response_data['study_phi'])} fields)"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving study PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
