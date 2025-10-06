"""
WebSocket system for real-time proxy communication.
"""
from .events import (
    # Base
    WebSocketEvent,

    # Incoming Events
    PingEvent,
    SessionDeletedEvent,
    ScanDeletedEvent,
    SubjectDispatchEvent,
    SessionDispatchEvent,
    ScanDispatchEvent,
    ProxyNodesChangedEvent,
    ProxyConfigChangedEvent,
    ProxyStatusChangedEvent,

    # Outgoing Events
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
