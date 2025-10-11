"""Public Health Check View."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger('receiver.views.health')


class PublicHealthCheckView(APIView):
    """
    Public health check endpoint - no authentication required.

    GET /api/health/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Returns basic health status from actual configuration.

        Example:
            curl http://localhost:8080/api/health/
        """
        from django.conf import settings

        try:
            response_data = {
                'status': 'healthy',
                'service': 'ith-proxy',
                'version': getattr(settings, 'PROXY_VERSION', '1.0.0'),
                'dicom': {
                    'status': 'online',
                    'port': settings.DICOM_PORT,
                    'ae_title': settings.DICOM_AE_TITLE,
                }
            }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error in health check: {e}", exc_info=True)
            return Response({
                'status': 'healthy',
                'service': 'ith-proxy',
                'version': getattr(settings, 'PROXY_VERSION', '1.0.0'),
                'error': 'Configuration unavailable'
            })
