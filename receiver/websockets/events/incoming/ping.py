"""
Ping Event - Keep-alive message sent every 30 seconds.
"""
from dataclasses import dataclass
from ..base import WebSocketEvent


@dataclass
class PingEvent(WebSocketEvent):
    """
    Keep-alive ping event.
    Sent every 30 seconds to maintain connection.

    Payload from docs:
    {
      "type": "ping",
      "timestamp": "2025-10-04T10:30:00.000Z"
    }
    """
    event_type: str = "ping"
    workspace_id: str = ""

    def __post_init__(self):
        self.entity_type = None
        self.entity_id = None
        self.payload = {}
