"""Batch PHI Metadata API Views.

Endpoints for retrieving multiple PHI records in a single request.
Supports up to 100 items per batch request.
"""
import logging
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from receiver.serializers import (
    PatientPHIBatchInputSerializer,
    PatientPHIBatchResponseSerializer,
    StudyPHIBatchInputSerializer,
    StudyPHIBatchResponseSerializer,
    SeriesPHIBatchInputSerializer,
    SeriesPHIBatchResponseSerializer,
)
from receiver.guard import IsAuthenticated
from .query import get_patient_mapping, get_study, get_scan

logger = logging.getLogger(__name__)


class PatientPHIBatchView(APIView):
    """
    API endpoint to retrieve patient-level PHI metadata for multiple patients.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/patient/batch/
    Authorization: Bearer <token>
    {
        "anonymous_patient_ids": ["ANON-a1b2c3d4e5f6", "ANON-g7h8i9j0k1l2"]
    }

    Returns patient-level PHI for all found patients.
    Max 100 patients per request.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = PatientPHIBatchInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        patient_ids = input_serializer.validated_data['anonymous_patient_ids']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed batch patient-level PHI for {len(patient_ids)} patients "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_batch_patient_phi(patient_ids)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_batch_patient_phi(self, patient_ids: list) -> Response:
        """
        Retrieve patient-level PHI metadata for multiple patients.

        Args:
            patient_ids: List of anonymous patient IDs

        Returns:
            DRF Response with batch patient-level PHI metadata
        """
        try:
            results = []
            not_found = []

            for patient_id in patient_ids:
                mapping = get_patient_mapping(patient_id)

                if mapping:
                    results.append({
                        "anonymous_patient_id": mapping.anonymous_patient_id,
                        "anonymous_patient_name": mapping.anonymous_patient_name,
                        "original_patient_id": mapping.original_patient_id,
                        "original_patient_name": mapping.original_patient_name,
                        "patient_phi": mapping.get_phi_metadata(),
                    })
                else:
                    not_found.append(patient_id)

            response_data = {
                "results": results,
                "total": len(results),
                "requested": len(patient_ids),
                "not_found": not_found,
            }

            serializer = PatientPHIBatchResponseSerializer(response_data)
            logger.info(
                f"Retrieved batch patient-level PHI: {len(results)}/{len(patient_ids)} found"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving batch patient PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StudyPHIBatchView(APIView):
    """
    API endpoint to retrieve study-level PHI metadata for multiple studies.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/study/batch/
    Authorization: Bearer <token>
    {
        "study_instance_uids": ["1.2.3.4.5...", "1.2.3.4.6..."]
    }

    Returns study-level PHI for all found studies.
    Max 100 studies per request.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = StudyPHIBatchInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        study_uids = input_serializer.validated_data['study_instance_uids']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed batch study-level PHI for {len(study_uids)} studies "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_batch_study_phi(study_uids)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_batch_study_phi(self, study_uids: list) -> Response:
        """
        Retrieve study-level PHI metadata for multiple studies.

        Args:
            study_uids: List of study instance UIDs

        Returns:
            DRF Response with batch study-level PHI metadata
        """
        try:
            results = []
            not_found = []

            for study_uid in study_uids:
                study = get_study(study_uid)

                if study:
                    results.append({
                        "study_instance_uid": study.study_instance_uid,
                        "patient_id": study.patient_id,
                        "patient_name": study.patient_name,
                        "study_date": study.study_date,
                        "study_time": study.study_time,
                        "study_description": study.study_description,
                        "accession_number": study.accession_number,
                        "status": study.status,
                        "study_phi": study.get_phi_metadata(),
                    })
                else:
                    not_found.append(study_uid)

            response_data = {
                "results": results,
                "total": len(results),
                "requested": len(study_uids),
                "not_found": not_found,
            }

            serializer = StudyPHIBatchResponseSerializer(response_data)
            logger.info(
                f"Retrieved batch study-level PHI: {len(results)}/{len(study_uids)} found"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving batch study PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SeriesPHIBatchView(APIView):
    """
    API endpoint to retrieve series-level PHI metadata for multiple series.

    **REQUIRES AUTHENTICATION** - This endpoint returns Protected Health Information.

    POST /api/phi-metadata/series/batch/
    Authorization: Bearer <token>
    {
        "series_instance_uids": ["1.2.3.4.5...", "1.2.3.4.6..."]
    }

    Returns series-level PHI for all found series.
    Max 100 series per request.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Handle POST request with JSON body."""
        input_serializer = SeriesPHIBatchInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                input_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        series_uids = input_serializer.validated_data['series_instance_uids']

        logger.warning(
            f"PHI_ACCESS: User '{request.user.username}' (ID: {request.user.id}) "
            f"accessed batch series-level PHI for {len(series_uids)} series "
            f"from IP: {self._get_client_ip(request)}"
        )

        return self._get_batch_series_phi(series_uids)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _get_batch_series_phi(self, series_uids: list) -> Response:
        """
        Retrieve series-level PHI metadata for multiple series.

        Args:
            series_uids: List of series instance UIDs

        Returns:
            DRF Response with batch series-level PHI metadata
        """
        try:
            results = []
            not_found = []

            for series_uid in series_uids:
                scan = get_scan(series_uid)

                if scan:
                    results.append({
                        "series_instance_uid": scan.series_instance_uid,
                        "series_number": scan.series_number,
                        "modality": scan.modality,
                        "series_description": scan.series_description,
                        "series_phi": scan.get_phi_metadata(),
                    })
                else:
                    not_found.append(series_uid)

            response_data = {
                "results": results,
                "total": len(results),
                "requested": len(series_uids),
                "not_found": not_found,
            }

            serializer = SeriesPHIBatchResponseSerializer(response_data)
            logger.info(
                f"Retrieved batch series-level PHI: {len(results)}/{len(series_uids)} found"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving batch series PHI: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
