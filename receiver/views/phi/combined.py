"""PHI Metadata API View."""
import logging
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from receiver.serializers import PHIMetadataSerializer, StudyUIDSerializer
from receiver.guard import IsAuthenticated
from .query import get_study, get_patient_mapping

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
        Retrieve PHI metadata for a study from all three levels.

        Collects:
        - Patient-level PHI from PatientMapping
        - Study-level PHI from Session
        - Series-level PHI from all Scans in the study

        Args:
            study_uid: Study Instance UID

        Returns:
            DRF Response with three-level PHI metadata
        """
        try:
            study = get_study(study_uid)

            if not study:
                return Response(
                    {"error": f"Study not found: {study_uid}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            mapping = get_patient_mapping(study.patient_id)

            if not mapping:
                return Response(
                    {"error": f"Patient mapping not found for patient_id: {study.patient_id}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get all scans (series) for this study
            scans = study.scans.all()

            # Collect series-level PHI from each scan
            series_phi_list = []
            for scan in scans:
                series_phi = scan.get_phi_metadata()
                if series_phi:
                    # Include series identifiers with PHI
                    series_phi_list.append({
                        "series_instance_uid": scan.series_instance_uid,
                        "series_number": scan.series_number,
                        "modality": scan.modality,
                        "phi_metadata": series_phi
                    })

            response_data = {
                "study_instance_uid": study.study_instance_uid,
                "patient_name": study.patient_name,
                "patient_id": study.patient_id,

                # Three-level PHI structure
                "patient_phi": mapping.get_phi_metadata(),
                "study_phi": study.get_phi_metadata(),
                "series_phi": series_phi_list,

                # Original patient identifiers
                "original_patient_name": mapping.original_patient_name,
                "original_patient_id": mapping.original_patient_id,

                # Study metadata (anonymized values currently in DB)
                "study_date": study.study_date,
                "study_time": study.study_time,
                "study_description": study.study_description,
                "accession_number": study.accession_number,
                "status": study.status,

                # Series count
                "series_count": scans.count(),
            }

            serializer = PHIMetadataSerializer(response_data)
            logger.info(
                f"Retrieved PHI metadata for study: {study_uid} "
                f"(Patient-level: {len(response_data['patient_phi'])} fields, "
                f"Study-level: {len(response_data['study_phi'])} fields, "
                f"Series: {len(series_phi_list)} series)"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving PHI metadata: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
