"""
Ping Event Handler.
"""
from typing import Dict, Any
from datetime import datetime
from ..base import BaseEventHandler


class PingHandler(BaseEventHandler):
    """
    Handle ping events.
    Responds with pong to keep connection alive.
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle ping event by responding with pong.

        Args:
            event: Ping event from backend
        """
        self.logger.debug(f"Received ping from backend")

        # Respond with pong
        pong_event = {
            "event_type": "pong",
            "timestamp": datetime.now().isoformat() + 'Z'
        }

        await self.send_response(pong_event)
