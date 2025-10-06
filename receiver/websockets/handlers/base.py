"""
Base Event Handler.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from ..consumer import ProxyConsumer

# Use websocket logger for base handler (transport/connection)
logger = logging.getLogger('receiver.websockets')


class BaseEventHandler(ABC):
    """
    Base class for all event handlers.
    Each event type has its own handler that processes the event.
    """

    def __init__(self, consumer: 'ProxyConsumer'):
        """
        Initialize handler.

        Args:
            consumer: ProxyConsumer instance that received the event
        """
        self.consumer = consumer
        # Each handler should use its own logger from the events namespace
        handler_name = self.__class__.__module__.replace('receiver.websockets.handlers', 'receiver.websockets.events')
        self.logger = logging.getLogger(handler_name)

    @abstractmethod
    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle the event.

        Args:
            event: Event dictionary received from backend
        """
        pass

    async def send_response(self, event: Dict[str, Any]) -> None:
        """
        Send response event to backend.

        Args:
            event: Event dictionary to send
        """
        await self.consumer.send_event(event)

    def get_workspace_id(self) -> str:
        """Get workspace ID from consumer."""
        return self.consumer.workspace_id

    def get_proxy_id(self) -> str:
        """Get proxy ID from consumer."""
        return self.consumer.proxy_id
