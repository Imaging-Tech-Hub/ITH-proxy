"""
WebSocket Event Handlers.

Each handler processes a specific event type from the backend.
Handlers are organized by category:
- system/: System-level handlers (ping/pong, connection management)
- dispatch/: Subject/session/scan dispatch events
- config/: Proxy configuration update events
- deletion/: Entity deletion events
"""
from .base import BaseEventHandler
from .system import PingHandler
from .deletion import SessionDeletedHandler, ScanDeletedHandler, SubjectDeletedHandler
from .dispatch import (
    SubjectDispatchHandler,
    SessionDispatchHandler,
    ScanDispatchHandler,
    NewScanAvailableHandler
)
from .config import (
    ProxyNodesChangedHandler,
    ProxyConfigChangedHandler,
    ProxyStatusChangedHandler
)

__all__ = [
    # Base
    'BaseEventHandler',

    # System Handlers
    'PingHandler',

    # Deletion Handlers
    'SessionDeletedHandler',
    'ScanDeletedHandler',
    'SubjectDeletedHandler',

    # Dispatch Handlers
    'SubjectDispatchHandler',
    'SessionDispatchHandler',
    'ScanDispatchHandler',
    'NewScanAvailableHandler',

    # Config Handlers
    'ProxyNodesChangedHandler',
    'ProxyConfigChangedHandler',
    'ProxyStatusChangedHandler',
]
