"""
Signals package.
Registers all signal handlers for the receiver app.
"""
import logging
import signal
import sys

logger = logging.getLogger(__name__)

# Import signal modules to register handlers
from . import proxy_config_signals

__all__ = [
    'proxy_config_signals',
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

        # Shutdown services
        from receiver.apps import ReceiverConfig
        ReceiverConfig.shutdown_websocket_client()
        ReceiverConfig.shutdown_dicom_server()

        logger.info("Shutdown complete")
        sys.exit(0)

    # Register handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logger.info("Shutdown handlers registered")
