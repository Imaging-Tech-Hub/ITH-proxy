"""
Health check and status endpoints.
Demonstrates authentication usage.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from receiver.guard import IsAuthenticated
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


class AuthenticatedStatusView(APIView):
    """
    Authenticated status endpoint - requires valid JWT token.

    GET /api/status/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns detailed status for authenticated users with actual configuration.

        Example:
            curl http://localhost:8080/api/status/ \
              -H "Authorization: Bearer <token>"
        """
        from receiver.models import Session, Scan
        from receiver.containers import container
        from django.conf import settings

        user_info = {
            'user_id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'role': request.user.role,
            'workspace_id': request.user.workspace_id,
            'is_superuser': request.user.is_superuser,
        }

        api_proxy_config = container.proxy_config_service().load_proxy_config()

        nodes = container.proxy_config_service().load_nodes()
        active_nodes = [n for n in nodes if n.is_active]
        reachable_nodes = [n for n in active_nodes if n.is_reachable]

        total_sessions = Session.objects.count()
        total_scans = Scan.objects.count()

        recent_sessions = Session.objects.order_by('-created_at')[:5]
        recent_activity = [{
            'patient_id': session.patient_id,
            'patient_name': session.patient_name,
            'study_uid': session.study_instance_uid,
            'scans': session.scans.count(),
            'status': session.status,
            'created_at': session.created_at.isoformat(),
        } for session in recent_sessions]

        return Response({
            'status': 'healthy',
            'service': 'ith-proxy',
            'version': getattr(settings, 'PROXY_VERSION', '1.0.0'),
            'timestamp': settings.USE_TZ,

            'user': user_info,

            'proxy': {
                'name': api_proxy_config.get('name') if api_proxy_config else 'Unknown',
                'workspace_id': api_proxy_config.get('workspace_id') if api_proxy_config else None,
                'is_active': api_proxy_config.get('is_active', False) if api_proxy_config else False,
                'health_status': api_proxy_config.get('health', {}).get('status') if api_proxy_config else 'unknown',
            },

            'dicom': {
                'port': settings.DICOM_PORT,
                'ae_title': settings.DICOM_AE_TITLE,
                'ip_address': settings.DICOM_BIND_ADDRESS or '0.0.0.0',
                'anonymization_enabled': settings.DICOM_ANONYMIZE_PATIENTS,
                'flairstar_auto_dispatch': api_proxy_config.get('flairstar_auto_dispatch_result', True) if api_proxy_config else True,
            },

            'nodes': {
                'total': len(nodes),
                'active': len(active_nodes),
                'reachable': len(reachable_nodes),
                'unreachable': len(active_nodes) - len(reachable_nodes),
            },

            'database': {
                'sessions': total_sessions,
                'scans': total_scans,
            },

            'recent_activity': recent_activity,
        })
