"""
WebSocket Events Package.

Organized into:
- base: Base event class
- incoming/: Events received from ITH backend (incoming)
- outgoing/: Events sent to ITH backend (outgoing)
"""
from .base import WebSocketEvent

# Import incoming events
from .incoming import (
    PingEvent,
    SessionDeletedEvent,
    ScanDeletedEvent,
    SubjectDispatchEvent,
    SessionDispatchEvent,
    ScanDispatchEvent,
    ProxyNodesChangedEvent,
    ProxyConfigChangedEvent,
    ProxyStatusChangedEvent,
)

# Import outgoing events
from .outgoing import (
    PongEvent,
    DispatchStatusEvent,
    ProxyHeartbeatEvent,
)

__all__ = [
    # Base
    'WebSocketEvent',

    # Incoming Events (from backend)
    'PingEvent',
    'SessionDeletedEvent',
    'ScanDeletedEvent',
    'SubjectDispatchEvent',
    'SessionDispatchEvent',
    'ScanDispatchEvent',
    'ProxyNodesChangedEvent',
    'ProxyConfigChangedEvent',
    'ProxyStatusChangedEvent',

    # Outgoing Events (to backend)
    'PongEvent',
    'DispatchStatusEvent',
    'ProxyHeartbeatEvent',
]
