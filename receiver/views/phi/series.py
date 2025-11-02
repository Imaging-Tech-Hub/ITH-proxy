"""Series-Level PHI Metadata API.

Endpoint for retrieving series-level PHI (acquisition dates, device info).
"""
import logging
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from receiver.serializers import (
    SeriesPHIInputSerializer,
    SeriesPHIResponseSerializer,
)
from receiver.guard import IsAuthenticated
from .query import get_scan

logger = logging.getLogger(__name__)


class SeriesPHIMetadataView(APIView):
    """
    API endpoint to retrieve series-level PHI metadata.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/series/
    Authorization: Bearer <token>
    {
        "series_instance_uid": "1.2.3.4.5..."
    }

    Returns series-level PHI including acquisition dates and device information.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = SeriesPHIInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        series_uid = input_serializer.validated_data['series_instance_uid']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed series-level PHI for: {series_uid} "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_series_phi(series_uid)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_series_phi(self, series_uid: str) -> Response:
        """
        Retrieve series-level PHI metadata.

        Args:
            series_uid: Series Instance UID

        Returns:
            DRF Response with series-level PHI metadata
        """
        try:
            scan = get_scan(series_uid)

            if not scan:
                return Response(
                    {"error": f"Series not found: {series_uid}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            response_data = {
                "series_instance_uid": scan.series_instance_uid,
                "series_number": scan.series_number,
                "modality": scan.modality,
                "series_description": scan.series_description,
                "series_phi": scan.get_phi_metadata(),
            }

            serializer = SeriesPHIResponseSerializer(response_data)
            logger.info(
                f"Retrieved series-level PHI for: {series_uid} "
                f"({len(response_data['series_phi'])} fields)"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving series PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
