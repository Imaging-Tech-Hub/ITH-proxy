"""
Proxy Configuration Signals.
Handles DICOM server restart when configuration changes.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from receiver.models.proxy_configuration import ProxyConfiguration

logger = logging.getLogger(__name__)

# Track old values before save
_old_proxy_key = None


@receiver(post_save, sender=ProxyConfiguration)
def handle_proxy_config_change(sender, instance, created, **kwargs):
    """
    Handle proxy configuration changes.

    When port or ae_title changes, restart the DICOM SCP server.
    When proxy_key changes, reload the DI container.
    Always notify backend via WebSocket.

    Args:
        sender: ProxyConfiguration model class
        instance: ProxyConfiguration instance that was saved
        created: True if new instance was created
        **kwargs: Additional signal arguments
    """
    if created:
        logger.info(f"Proxy configuration created: {instance.dicom_address}")
        restart_dicom_server(instance)
    else:
        dicom_changed = _dicom_config_changed(instance)
        proxy_key_changed = _proxy_key_changed(instance)

        if dicom_changed:
            logger.info(f"DICOM configuration changed: {instance.dicom_address}")
            restart_dicom_server(instance)

        if proxy_key_changed:
            logger.info(f"Proxy key changed, reloading API client configuration")
            reload_api_client(instance)

        if not dicom_changed and not proxy_key_changed:
            logger.info(f"Proxy configuration updated (non-critical fields)")

    # Always notify backend via WebSocket about config changes
    notify_backend_config_update(instance)


def _dicom_config_changed(instance: ProxyConfiguration) -> bool:
    """
    Check if DICOM-related configuration changed.

    Compares current instance with database to detect changes in:
    - port
    - ae_title

    Args:
        instance: Current ProxyConfiguration instance

    Returns:
        bool: True if DICOM config changed
    """
    try:
        # Get fresh instance from database to compare
        from django.db.models import F
        old_data = ProxyConfiguration.objects.filter(pk=instance.pk).values('port', 'ae_title').first()

        if not old_data:
            return True

        port_changed = old_data['port'] != instance.port
        ae_title_changed = old_data['ae_title'] != instance.ae_title

        return port_changed or ae_title_changed

    except Exception:
        return True


@receiver(pre_save, sender=ProxyConfiguration)
def track_proxy_key_before_save(sender, instance, **kwargs):
    """
    Track proxy_key value before save to detect changes.

    Args:
        sender: ProxyConfiguration model class
        instance: ProxyConfiguration instance about to be saved
        **kwargs: Additional signal arguments
    """
    global _old_proxy_key
    try:
        if instance.pk:
            old_instance = ProxyConfiguration.objects.get(pk=instance.pk)
            _old_proxy_key = old_instance.proxy_key
        else:
            _old_proxy_key = None
    except ProxyConfiguration.DoesNotExist:
        _old_proxy_key = None


def _proxy_key_changed(instance: ProxyConfiguration) -> bool:
    """
    Check if proxy_key changed.

    Args:
        instance: Current ProxyConfiguration instance

    Returns:
        bool: True if proxy_key changed
    """
    global _old_proxy_key
    try:
        changed = _old_proxy_key != instance.proxy_key
        return changed
    except Exception:
        return False


def reload_api_client(config: ProxyConfiguration):
    """
    Reload API client with new proxy key.

    This function updates the DI container with the new proxy key
    so that the API client uses the updated authentication.

    Args:
        config: ProxyConfiguration instance with new proxy key
    """
    from receiver.containers import container

    try:
        logger.info(f"Reloading API client with updated proxy key")

        if config.proxy_key:
            container.config.proxy_key.from_value(config.proxy_key)
            logger.info("API client configuration updated with new proxy key")
        else:
            logger.warning("Proxy key is empty, API client may not authenticate properly")

    except Exception as e:
        logger.error(f"Error reloading API client: {e}", exc_info=True)


def restart_dicom_server(config: ProxyConfiguration):
    """
    Restart DICOM SCP server with new configuration.

    This function:
    1. Stops the current DICOM server
    2. Updates the DI container configuration
    3. Restarts the DICOM server with new settings

    Args:
        config: ProxyConfiguration instance with new settings
    """
    import threading
    from receiver.containers import container

    try:
        logger.info(f"Restarting DICOM server with config: {config.dicom_address}")

        dicom_service = container.dicom_service_provider()

        if dicom_service.is_running:
            logger.info("Stopping current DICOM server...")
            dicom_service.stop()

        container.config.ae_title.from_value(config.ae_title)
        container.config.port.from_value(config.port)

        logger.info(f"Starting DICOM server on {config.ae_title}@{config.ip_address}:{config.port}")
        dicom_thread = threading.Thread(
            target=dicom_service.start,
            daemon=False
        )
        dicom_thread.start()

        logger.info("DICOM server restarted successfully")

    except Exception as e:
        logger.error(f"Error restarting DICOM server: {e}", exc_info=True)
        raise


def notify_backend_config_update(config: ProxyConfiguration):
    """
    Notify backend via WebSocket about configuration changes.

    This sends a config_update message to the backend so it can
    update its records with the latest proxy configuration.

    Args:
        config: ProxyConfiguration instance with updated settings
    """
    from asgiref.sync import async_to_sync
    from django.apps import apps

    try:
        receiver_config = apps.get_app_config('receiver')
        ws_client = receiver_config.websocket_client

        if ws_client and ws_client.websocket:
            from django.conf import settings
            proxy_version = getattr(settings, 'PROXY_VERSION', '1.0.0')

            async_to_sync(ws_client.send_config_update)(
                ip_address=config.ip_address,
                port=config.port,
                ae_title=config.ae_title,
                resolver_url=config.resolver_api_url,
                proxy_version=proxy_version
            )
            logger.info("Backend notified of configuration update via WebSocket")
        else:
            logger.debug("WebSocket client not connected, skipping backend notification")

    except Exception as e:
        logger.warning(f"Could not notify backend of config update: {e}")


def get_current_config() -> ProxyConfiguration:
    """
    Get current proxy configuration (convenience function).

    Returns:
        ProxyConfiguration: The singleton instance
    """
    return ProxyConfiguration.get_instance()
