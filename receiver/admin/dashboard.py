"""
Custom Admin Dashboard for ITH Proxy.
Shows metrics for DICOM server and PACS nodes.
"""
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

logger = logging.getLogger(__name__)


def get_dashboard_context(request):
    """Get dashboard context with metrics."""
    from receiver.models import ProxyConfiguration
    from receiver.services.proxy_config_service import get_config_service
    from receiver.apps import ReceiverConfig

    context = {
        'title': 'Dashboard',
        'site_title': 'ITH Proxy',
        'site_header': 'ITH Proxy Administration',
        'has_permission': request.user.is_active and request.user.is_staff,
    }

    from django.apps import apps

    try:
        receiver_app = apps.get_app_config('receiver')
        dicom_server = getattr(receiver_app, 'dicom_server', None)

        if dicom_server and hasattr(dicom_server, 'is_running'):
            context['dicom_server'] = {
                'status': 'Running' if dicom_server.is_running else 'Stopped',
                'is_running': dicom_server.is_running,
            }
        else:
            context['dicom_server'] = {
                'status': 'Not Started',
                'is_running': False,
            }
    except Exception as e:
        logger.error(f"Error getting DICOM server status: {e}")
        context['dicom_server'] = {
            'status': 'Unknown',
            'is_running': False,
        }

    try:
        proxy_config = ProxyConfiguration.get_instance()
        context['proxy_config'] = {
            'ae_title': proxy_config.ae_title,
            'port': proxy_config.port,
            'ip_address': proxy_config.ip_address,
            'dicom_address': proxy_config.dicom_address,
            'resolver_api_url': proxy_config.resolver_api_url or 'Not configured',
        }
    except Exception as e:
        logger.error(f"Error loading proxy config: {e}")
        context['proxy_config'] = None

    config_service = get_config_service()
    if config_service:
        try:
            nodes = config_service.load_nodes()
            active_nodes = [n for n in nodes if n.is_active]
            reachable_nodes = [n for n in nodes if n.is_reachable]

            context['nodes'] = {
                'total': len(nodes),
                'active': len(active_nodes),
                'reachable': len(reachable_nodes),
                'list': nodes,
            }
        except Exception as e:
            logger.error(f"Error loading nodes: {e}")
            context['nodes'] = None
    else:
        context['nodes'] = None

    from django.conf import settings
    context['api_config'] = {
        'url': getattr(settings, 'LAMINATE_API_URL', 'Not configured'),
        'proxy_key_configured': bool(getattr(settings, 'PROXY_KEY', None)),
        'version': getattr(settings, 'PROXY_VERSION', 'Unknown'),
    }

    return context


@staff_member_required
def dashboard_view(request):
    """Custom dashboard view with metrics."""
    context = get_dashboard_context(request)
    return render(request, 'admin/dashboard.html', context)
