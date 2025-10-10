"""
Signals package.
Registers all signal handlers for the receiver app.
"""
import logging
import signal
import sys

logger = logging.getLogger(__name__)

__all__ = [
    'register_shutdown_handlers',
]


def register_shutdown_handlers():
    """
    Register signal handlers for graceful shutdown.
    Handles SIGTERM and SIGINT signals.
    """
    def shutdown_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received shutdown signal: {signum}")

        try:
            # Shutdown services
            from receiver.apps import ReceiverConfig
            ReceiverConfig.shutdown_websocket_client()
            ReceiverConfig.shutdown_dicom_server()

            logger.info("Shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            # Let Django handle the exit gracefully instead of forcing sys.exit()
            # This prevents thread join issues during shutdown
            pass

    # Register handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logger.info("Shutdown handlers registered")
