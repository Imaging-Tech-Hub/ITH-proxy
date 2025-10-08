"""
WebSocket Consumer for Proxy Real-time Communication.
Handles bidirectional communication between proxy and ITH backend.
"""
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .handlers import (
    PingHandler,
    SessionDeletedHandler,
    ScanDeletedHandler,
    SubjectDispatchHandler,
    SessionDispatchHandler,
    ScanDispatchHandler,
    NewScanAvailableHandler,
    ProxyNodesChangedHandler,
    ProxyConfigChangedHandler,
    ProxyStatusChangedHandler,
)

logger = logging.getLogger(__name__)


class ProxyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for proxy connections.

    Connection: ws://host/proxy/ws?proxy_key=pk_xxx

    Features:
    - Authentication via proxy_key query parameter
    - One connection per proxy (old connections auto-disconnect)
    - Ping/pong heartbeat every 30 seconds
    - Event routing to specialized handlers
    """

    active_connections: Dict[str, 'ProxyConsumer'] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_key: Optional[str] = None
        self.workspace_id: Optional[str] = None
        self.proxy_id: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None

        self.handlers = {
            'ping': PingHandler(self),
            'session.deleted': SessionDeletedHandler(self),
            'scan.deleted': ScanDeletedHandler(self),
            'subject.dispatch': SubjectDispatchHandler(self),
            'session.dispatch': SessionDispatchHandler(self),
            'scan.dispatch': ScanDispatchHandler(self),
            'scan.new_scan_available': NewScanAvailableHandler(self),
            'proxy.nodes_changed': ProxyNodesChangedHandler(self),
            'proxy.config_changed': ProxyConfigChangedHandler(self),
            'proxy.status_changed': ProxyStatusChangedHandler(self),
        }

    async def connect(self):
        """
        Handle WebSocket connection.

        Steps:
        1. Extract and validate proxy_key from query params
        2. Authenticate proxy
        3. Disconnect old connection if exists
        4. Accept new connection
        5. Start heartbeat
        """
        query_params = dict(
            (k, v[0]) for k, v in self.scope['query_string'].decode().split('&')
            if '=' in k
        )
        query_params = {}
        for param in self.scope['query_string'].decode().split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                query_params[key] = value

        self.proxy_key = query_params.get('proxy_key')

        if not self.proxy_key:
            logger.warning("Connection rejected: No proxy_key provided")
            await self.close(code=4001)
            return

        auth_result = await self.authenticate_proxy(self.proxy_key)

        if not auth_result['valid']:
            logger.warning(f"Connection rejected: Invalid proxy_key {self.proxy_key}")
            await self.close(code=4003)
            return

        self.workspace_id = auth_result['workspace_id']
        self.proxy_id = auth_result['proxy_id']

        if self.proxy_key in self.active_connections:
            old_consumer = self.active_connections[self.proxy_key]
            logger.info(f"Disconnecting old connection for proxy {self.proxy_key}")
            await old_consumer.close(code=4002)  # Replaced by new connection

        await self.accept()

        self.active_connections[self.proxy_key] = self

        logger.info(f"Proxy connected: {self.proxy_key} (workspace: {self.workspace_id})")

        self.heartbeat_task = asyncio.create_task(self.send_heartbeat())

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        Clean up resources and remove from active connections.
        """
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        if self.proxy_key and self.proxy_key in self.active_connections:
            if self.active_connections[self.proxy_key] == self:
                del self.active_connections[self.proxy_key]

        logger.info(f"Proxy disconnected: {self.proxy_key} (code: {close_code})")

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        Route events to appropriate handlers.
        """
        try:
            event = json.loads(text_data)
            event_type = event.get('event_type')

            if not event_type:
                logger.warning(f"Received event without event_type: {event}")
                return

            logger.debug(f"Received event: {event_type} from {self.proxy_key}")

            handler = self.handlers.get(event_type)

            if handler:
                await handler.handle(event)
            else:
                logger.warning(f"No handler for event type: {event_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)

    async def send_event(self, event: Dict[str, Any]):
        """
        Send event to proxy.

        Args:
            event: Event dictionary to send
        """
        try:
            await self.send(text_data=json.dumps(event))
            logger.debug(f"Sent event: {event.get('event_type')} to {self.proxy_key}")
        except Exception as e:
            logger.error(f"Error sending event: {e}", exc_info=True)

    async def send_heartbeat(self):
        """
        Send periodic ping messages every 30 seconds.
        Maintains connection alive.
        """
        while True:
            try:
                await asyncio.sleep(30)

                ping_event = {
                    "type": "ping",
                    "timestamp": self._get_timestamp()
                }

                await self.send_event(ping_event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}", exc_info=True)
                break

    async def authenticate_proxy(self, proxy_key: str) -> Dict[str, Any]:
        """
        Authenticate proxy using proxy_key.

        Validates proxy_key and retrieves workspace_id and proxy_id
        from the config service.

        Args:
            proxy_key: Proxy API key

        Returns:
            Dict with 'valid', 'workspace_id', 'proxy_id'
        """
        from receiver.services.proxy_config_service import get_config_service
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _authenticate():
            config_service = get_config_service()

            if not config_service:
                logger.warning("Config service not initialized")
                return {
                    'valid': False,
                    'workspace_id': None,
                    'proxy_id': None
                }

            if config_service.proxy_key != proxy_key:
                logger.warning("Proxy key mismatch")
                return {
                    'valid': False,
                    'workspace_id': None,
                    'proxy_id': None
                }

            proxy_config = config_service.load_proxy_config()

            if not proxy_config:
                logger.warning("No proxy config found")
                return {
                    'valid': False,
                    'workspace_id': None,
                    'proxy_id': None
                }

            if not proxy_config.get('is_active', False):
                logger.warning("Proxy is not active")
                return {
                    'valid': False,
                    'workspace_id': None,
                    'proxy_id': None
                }

            return {
                'valid': True,
                'workspace_id': proxy_config.get('workspace_id'),
                'proxy_id': proxy_config.get('proxy_id')
            }

        return await _authenticate()

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
