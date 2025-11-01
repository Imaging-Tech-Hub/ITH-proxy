from django.apps import AppConfig
import os
import threading
import logging

logger = logging.getLogger(__name__)


class ReceiverConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'receiver'

    dicom_server = None
    dicom_thread = None
    websocket_client = None
    websocket_task = None

    def ready(self):
        """
        Called when Django starts.
        Auto-starts DICOM server if DICOM_AUTO_START is True.
        """
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from django.conf import settings
        from receiver.signals import register_shutdown_handlers

        # Import cache invalidation signals (they auto-register via @receiver decorator)
        import receiver.signals  # noqa: F401

        register_shutdown_handlers()

        self.load_proxy_configuration()

        auto_start = getattr(settings, 'DICOM_AUTO_START', False)

        if auto_start:
            logger.info("DICOM auto-start enabled, starting DICOM server...")
            self.start_dicom_server()

        self.start_websocket_client()

    def start_dicom_server(self):
        """Start DICOM server in background thread."""
        try:
            from receiver.containers import container

            self.dicom_server = container.dicom_service_provider()

            self.dicom_thread = threading.Thread(
                target=self.dicom_server.start,
                daemon=False
            )
            self.dicom_thread.start()

            logger.info("DICOM server started in background thread")

        except Exception as e:
            logger.error(f"Failed to start DICOM server: {e}", exc_info=True)

    def load_proxy_configuration(self):
        """Load proxy configuration from backend API."""
        try:
            from receiver.services.config import get_config_service

            config_service = get_config_service()
            if not config_service:
                logger.warning("Could not get config service - skipping configuration load")
                return

            success = config_service.load_and_apply_configuration()

            if success:
                logger.info("Proxy configuration loaded successfully from API")
            else:
                logger.warning("Could not load proxy configuration from API - using defaults")

        except Exception as e:
            logger.warning(f"Failed to load proxy configuration: {e}")

    def start_websocket_client(self):
        """Start WebSocket client for backend communication."""
        try:
            import asyncio
            from receiver.services.api import get_websocket_client

            self.websocket_client = get_websocket_client()

            if not self.websocket_client:
                logger.warning("WebSocket client not started - missing configuration")
                return

            def run_websocket():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.websocket_client.start())
                except Exception as e:
                    logger.error(f"WebSocket client error: {e}", exc_info=True)
                finally:
                    loop.close()

            import threading
            self.websocket_thread = threading.Thread(
                target=run_websocket,
                daemon=True,
                name="WebSocketClient"
            )
            self.websocket_thread.start()

            logger.info("WebSocket client started in background thread")

        except Exception as e:
            logger.error(f"Failed to start WebSocket client: {e}", exc_info=True)

    @classmethod
    def shutdown_dicom_server(cls):
        """Gracefully shutdown DICOM server."""
        if cls.dicom_server and cls.dicom_server.is_running:
            logger.info("Shutting down DICOM server gracefully...")
            cls.dicom_server.stop()

            if cls.dicom_thread and cls.dicom_thread.is_alive():
                cls.dicom_thread.join(timeout=10.0)

            logger.info("DICOM server shutdown complete")

    @classmethod
    def shutdown_websocket_client(cls):
        """Gracefully shutdown WebSocket client."""
        if cls.websocket_client:
            import asyncio
            logger.info("Shutting down WebSocket client...")

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(cls.websocket_client.stop())
                loop.close()
            except Exception as e:
                logger.error(f"Error stopping WebSocket client: {e}")

            logger.info("WebSocket client shutdown complete")
