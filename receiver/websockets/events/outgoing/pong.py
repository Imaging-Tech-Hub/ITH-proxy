"""
Pong Event - Response to ping.
"""
from dataclasses import dataclass
from ..base import WebSocketEvent


@dataclass
class PongEvent(WebSocketEvent):
    """
    Pong response to ping event.
    Sent in response to incoming ping to confirm connection is alive.
    """
    event_type: str = "pong"
    workspace_id: str = ""

    def __post_init__(self):
        self.entity_type = None
        self.entity_id = None
        self.payload = {}
