"""
WebSocket Event Handlers.
Each handler processes a specific event type from the backend.
"""
from .base import BaseEventHandler
from .ping_handler import PingHandler
from .deletion_handlers import SessionDeletedHandler, ScanDeletedHandler
from .dispatch_handlers import (
    SubjectDispatchHandler,
    SessionDispatchHandler,
    ScanDispatchHandler
)
from .config_handlers import (
    ProxyNodesChangedHandler,
    ProxyConfigChangedHandler,
    ProxyStatusChangedHandler
)

__all__ = [
    # Base
    'BaseEventHandler',

    # Ping
    'PingHandler',

    # Deletion Handlers
    'SessionDeletedHandler',
    'ScanDeletedHandler',

    # Dispatch Handlers
    'SubjectDispatchHandler',
    'SessionDispatchHandler',
    'ScanDispatchHandler',

    # Config Handlers
    'ProxyNodesChangedHandler',
    'ProxyConfigChangedHandler',
    'ProxyStatusChangedHandler',
]
