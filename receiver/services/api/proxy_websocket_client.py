"""
Proxy WebSocket Client.
Connects to ITH API WebSocket for real-time communication.

Based on THIRD_PARTY_PROXY_FLOW.md specification.
"""
import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ProxyWebSocketClient:
    """
    WebSocket client for proxy-to-backend communication.

    Implements the third-party proxy flow:
    1. Connect with proxy_key authentication
    2. Send config_update and health_update messages
    3. Receive ping and event notifications
    """

    def __init__(
        self,
        api_url: str,
        proxy_key: str,
        health_interval: int = 10,
        reconnect_delay: int = 5
    ):
        """
        Initialize WebSocket client.

        Args:
            api_url: Base API URL (e.g., http://localhost:8000)
            proxy_key: Proxy authentication key
            health_interval: Seconds between health updates (default: 10)
            reconnect_delay: Seconds to wait before reconnecting (default: 5)
        """
        ws_base = api_url.replace('https://', 'wss://').replace('http://', 'ws://')

        self.api_url = api_url
        self.proxy_key = proxy_key
        self.health_interval = health_interval
        self.reconnect_delay = reconnect_delay

        self.ws_url = f"{ws_base}/api/v1/proxy/ws?proxy_key={proxy_key}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.workspace_id: Optional[str] = None
        self.proxy_id: Optional[str] = None

        self.event_handlers: Dict[str, Callable] = {}

    def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register handler for specific event type.

        Args:
            event_type: Event type (e.g., 'scan.deleted')
            handler: Async function to handle the event
        """
        self.event_handlers[event_type] = handler
        logger.info(f"Registered event handler for: {event_type}")

    async def connect(self) -> bool:
        """
        Connect to WebSocket and authenticate.

        Returns:
            bool: True if connected successfully
        """
        try:
            logger.info(f"Connecting to WebSocket: {self.ws_url.split('?')[0]}")

            if not self.ws_url or not self.ws_url.startswith(('ws://', 'wss://')):
                logger.error(f"Invalid WebSocket URL: {self.ws_url}")
                return False

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=120,
                ping_timeout=300
            )

            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("WebSocket connection timeout - no response from server")
                if self.websocket:
                    await self.websocket.close()
                return False

            logger.debug(f"Raw WebSocket message received: {message}")

            try:
                data = json.loads(message)
                logger.info(f"WebSocket first message: {data}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in connection response: {e}")
                logger.error(f"   Raw message: {message}")
                if self.websocket:
                    await self.websocket.close()
                return False

            message_type = data.get('type')
            event_type = data.get('event_type')

            if message_type == 'connected':
                self.workspace_id = data.get('workspace_id')
                self.proxy_id = data.get('proxy_id')

                if not self.workspace_id or not self.proxy_id:
                    logger.error(f"Missing workspace_id or proxy_id in connection response")
                    if self.websocket:
                        await self.websocket.close()
                    return False

                from receiver.containers import container
                api_client = container.ith_api_client()
                api_client.set_workspace_id(self.workspace_id)

                logger.info(f"WebSocket connected - Workspace: {self.workspace_id}, Proxy: {self.proxy_id}")
                return True

            elif event_type:
                logger.info(f"Received event '{event_type}' - connection already established")

                self.workspace_id = data.get('workspace_id')
                self.proxy_id = data.get('entity_id')

                if not self.workspace_id or not self.proxy_id:
                    logger.error(f"Missing workspace_id or entity_id in event message")
                    if self.websocket:
                        await self.websocket.close()
                    return False

                from receiver.containers import container
                api_client = container.ith_api_client()
                api_client.set_workspace_id(self.workspace_id)

                logger.info(f"WebSocket connected via event - Workspace: {self.workspace_id}, Proxy: {self.proxy_id}")

                asyncio.create_task(self._handle_event(event_type, data))

                return True

            else:
                logger.error(f"Unexpected message format")
                logger.error(f"   Message type: '{message_type}'")
                logger.error(f"   Event type: '{event_type}'")
                logger.error(f"   Full data: {data}")
                if self.websocket:
                    await self.websocket.close()
                return False

        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"WebSocket connection rejected with status {e.status_code}")
            if e.status_code == 401:
                logger.error("Authentication failed - check proxy_key")
            elif e.status_code == 403:
                logger.error("Access forbidden - proxy may be disabled")
            return False
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}", exc_info=True)
            return False

    async def send_config_update(
        self,
        ip_address: str,
        port: int,
        ae_title: str,
        api_url: str = "",
        proxy_version: str = "1.0.0"
    ) -> bool:
        """
        Send configuration update to backend.

        Args:
            ip_address: Proxy IP address
            port: DICOM port
            ae_title: DICOM AE title
            api_url: Proxy API base URL (e.g., http://192.168.1.100:8080/api)
            proxy_version: Proxy software version

        Returns:
            bool: True if acknowledged successfully
        """
        if not self.websocket:
            logger.warning("Cannot send config_update - not connected")
            return False

        try:
            message = {
                "type": "config_update",
                "ip_address": ip_address,
                "port": port,
                "ae_title": ae_title,
                "api_url": api_url,
                "proxy_version": proxy_version
            }

            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent config_update: {message}")

            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            data = json.loads(response)

            if data.get('type') == 'config_update_response':
                if data.get('status') == 'success':
                    logger.info(f" Config update acknowledged: {data.get('fields_updated', [])}")
                    return True
                else:
                    logger.error(f" Config update failed: {data.get('error')}")
                    return False

        except asyncio.TimeoutError:
            logger.error("Config update response timeout")
            return False
        except websockets.exceptions.ConnectionClosed:
            logger.error(f"Connection closed while sending config_update")
            raise
        except Exception as e:
            logger.error(f"Error sending config_update: {e}", exc_info=True)
            return False

    async def send_health_update(
        self,
        proxy_status: str = "online",
        proxy_version: Optional[str] = None,
        nodes: Optional[list] = None
    ) -> bool:
        """
        Send health status update to backend.

        Args:
            proxy_status: Proxy status (online, offline, error)
            proxy_version: Proxy software version
            nodes: List of node health statuses

        Returns:
            bool: True if acknowledged successfully

        Raises:
            ConnectionClosedError: If WebSocket connection is closed
        """
        if not self.websocket:
            return False

        try:
            if proxy_version is None:
                from django.conf import settings
                proxy_version = getattr(settings, 'PROXY_VERSION', '1.0.0')

            message = {
                "type": "health_update",
                "proxy_status": proxy_status,
                "proxy_version": proxy_version
            }

            if nodes:
                message["nodes"] = nodes

            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent health_update: {proxy_status}")

            return True

        except websockets.exceptions.ConnectionClosed:
            logger.error(f"Connection closed while sending health_update")
            raise
        except Exception as e:
            logger.error(f"Error sending health_update: {e}", exc_info=True)
            return False

    async def _periodic_health_updates(self):
        """Send health updates periodically."""
        while self.running and self.websocket:
            try:
                logger.debug("Checking node health status...")

                try:
                    nodes = await asyncio.wait_for(
                        self._get_node_health_status(),
                        timeout=20.0
                    )
                    logger.debug(f"Node health check returned {len(nodes)} nodes: {nodes}")
                except asyncio.TimeoutError:
                    logger.warning("Node health check timed out, sending update without node status")
                    nodes = []

                await self.send_health_update(
                    proxy_status="online",
                    nodes=nodes
                )

                await asyncio.sleep(self.health_interval)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Health update stopped - connection closed: {e}")
                break
            except Exception as e:
                logger.error(f"Error in health update loop: {e}", exc_info=True)
                await asyncio.sleep(self.health_interval)

    def _check_node_health_sync(self) -> list:
        """
        Synchronous function to check node health.
        Used by _get_node_health_status via sync_to_async.

        Returns:
            List of node health statuses
        """
        try:
            from receiver.services.config import get_config_service
            from receiver.commands.dicom.verify_commands import VerifyNodeConnectionCommand

            logger.debug("Getting config service for node health check...")
            config_service = get_config_service()
            if not config_service:
                logger.warning("Config service not available for node health check")
                return []

            logger.debug("Loading nodes from config service...")
            nodes = config_service.load_nodes()
            logger.info(f"Found {len(nodes)} total nodes to check")
            node_statuses = []

            for node in nodes:
                if not node.is_active:
                    logger.info(f"Skipping inactive node: {node.name} (is_active={node.is_active})")
                    continue

                logger.info(f" Verifying node: {node.name} at {node.host}:{node.port}")
                try:
                    verify_cmd = VerifyNodeConnectionCommand(node)
                    result = verify_cmd.execute()
                    is_reachable = result.data.get('is_online', False)
                    logger.info(f"{'' if is_reachable else ''} Node {node.name}: {'reachable' if is_reachable else 'unreachable'}")

                    node.is_reachable = is_reachable
                except Exception as e:
                    logger.warning(f" Node {node.name} verification failed: {e}")
                    is_reachable = False
                    node.is_reachable = False

                node_statuses.append({
                    "node_id": node.node_id,
                    "is_reachable": is_reachable
                })

            logger.info(f"Node health check complete: {len(node_statuses)} active nodes checked")
            return node_statuses

        except Exception as e:
            logger.error(f"Error getting node health: {e}", exc_info=True)
            return []

    async def _get_node_health_status(self) -> list:
        """
        Get health status of all managed PACS nodes using C-ECHO.

        Returns:
            List of node health statuses
        """
        from asgiref.sync import sync_to_async

        return await sync_to_async(self._check_node_health_sync, thread_sensitive=False)()

    async def _handle_incoming_messages(self):
        """Handle incoming messages from backend."""
        while self.running and self.websocket:
            try:
                message = await self.websocket.recv()

                if not message:
                    logger.warning("Received empty message from server")
                    continue

                try:
                    data = json.loads(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in message: {e}")
                    logger.debug(f"Raw message: {message[:200]}")
                    continue

                if not isinstance(data, dict):
                    logger.error(f"Message data is not a dictionary: {type(data)}")
                    continue

                message_type = data.get('type')
                event_type = data.get('event_type')

                if not event_type and 'payload' in data:
                    nested_payload = data.get('payload', {})
                    event_type = nested_payload.get('event_type')
                    if event_type:
                        logger.debug(f"Event type found in nested payload: {event_type}")
                        data = {
                            'event_type': event_type,
                            'workspace_id': nested_payload.get('workspace_id', data.get('workspace_id')),
                            'timestamp': nested_payload.get('timestamp', data.get('timestamp')),
                            'correlation_id': nested_payload.get('correlation_id'),
                            'entity_type': nested_payload.get('entity_type'),
                            'entity_id': nested_payload.get('entity_id'),
                            'payload': nested_payload.get('payload', {})
                        }

                if message_type == 'ping':
                    logger.debug("Received ping from server")

                elif message_type == 'health_update_response':
                    if data.get('status') == 'success':
                        logger.debug("Health update acknowledged")
                    else:
                        logger.warning(f"Health update error: {data.get('error')}")

                elif message_type == 'config_update_response':
                    if data.get('status') == 'success':
                        logger.debug(f"Config update acknowledged: {data.get('fields_updated')}")
                    else:
                        logger.warning(f"Config update error: {data.get('error')}")

                elif event_type:
                    logger.info(f"Received event: {event_type}")
                    await self._handle_event(event_type, data)

                else:
                    logger.debug(f"Received unhandled message type: {message_type}")
                    logger.debug(f"Message data: {json.dumps(data)[:500]}")

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                break
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket error in message handler: {e}", exc_info=True)
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_event(self, event_type: str, data: Dict[str, Any]):
        """
        Handle event notification from backend.

        Args:
            event_type: Event type (e.g., 'scan.deleted')
            data: Event data
        """
        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                logger.debug(f"Handling event '{event_type}' with registered handler")
                await handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
        else:
            logger.warning(f"No handler registered for event: '{event_type}'")
            logger.warning(f"Available handlers: {', '.join(self.event_handlers.keys())}")
            logger.debug(f"Event data: {data}")

    async def start(self):
        """Start WebSocket client with automatic reconnection."""
        self.running = True

        while self.running:
            try:
                connected = await self.connect()
                if not connected:
                    logger.warning(f"Failed to connect, retrying in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue

                await self._send_initial_config()

                health_task = asyncio.create_task(self._periodic_health_updates())
                message_task = asyncio.create_task(self._handle_incoming_messages())

                await asyncio.gather(health_task, message_task, return_exceptions=True)

                logger.warning("WebSocket tasks ended, reconnecting...")

            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
            finally:
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except Exception:
                        pass
                    self.websocket = None

            await asyncio.sleep(self.reconnect_delay)

    def _get_host_ip_address(self) -> str:
        """
        Get the host IP address, handling Docker container scenarios.

        Detection strategies (in order):
        1. Check PROXY_HOST_IP environment variable (manual override)
        2. Detect Docker environment and get host gateway IP
        3. Find non-loopback network interface IP
        4. Resolve hostname to IP
        5. Fallback to localhost

        Returns:
            str: Best available IP address for DICOM connectivity
        """
        import socket
        import os

        env_ip = os.getenv('PROXY_HOST_IP', '').strip()
        if env_ip:
            logger.info(f"Using PROXY_HOST_IP from environment: {env_ip}")
            return env_ip

        is_docker = os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')

        if is_docker:
            logger.info("Detected Docker environment")

            try:
                host_gateway = socket.gethostbyname('host.docker.internal')
                logger.info(f"Found Docker host gateway: {host_gateway}")
                return host_gateway
            except (socket.gaierror, OSError):
                logger.debug("host.docker.internal not available")

            try:
                with open('/proc/net/route', 'r') as f:
                    for line in f:
                        fields = line.strip().split()
                        if fields[1] == '00000000':
                            gateway_hex = fields[2]
                            gateway_ip = '.'.join([
                                str(int(gateway_hex[i:i+2], 16))
                                for i in range(6, -1, -2)
                            ])
                            logger.info(f"Found Docker host via default gateway: {gateway_ip}")
                            return gateway_ip
            except (FileNotFoundError, IndexError, ValueError) as e:
                logger.debug(f"Could not read route table: {e}")

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            try:
                s.connect(('8.8.8.8', 80))
                ip_address = s.getsockname()[0]
                s.close()

                if not ip_address.startswith('172.17.'):
                    logger.info(f"Found primary network interface IP: {ip_address}")
                    return ip_address
                else:
                    logger.debug(f"Skipping Docker internal IP: {ip_address}")
            except (socket.error, socket.timeout):
                s.close()
        except Exception as e:
            logger.debug(f"Could not detect network interface IP: {e}")

        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
            if not ip_address.startswith('172.17.') and ip_address != '127.0.0.1':
                logger.info(f"Resolved hostname {hostname} to: {ip_address}")
                return ip_address
        except (socket.gaierror, OSError) as e:
            logger.debug(f"Could not resolve hostname {hostname}: {e}")

        logger.warning("Could not detect host IP, using localhost (DICOM devices must be on same machine)")
        return '127.0.0.1'

    def _construct_api_url(self, ip_address: str) -> str:
        """
        Construct the public API URL for this proxy.

        Args:
            ip_address: The IP address where proxy is accessible

        Returns:
            Full API base URL (e.g., http://192.168.1.100:8080/api)
        """
        from django.conf import settings

        explicit_url = getattr(settings, 'PROXY_API_URL', '').strip()
        if explicit_url:
            if not explicit_url.endswith('/api') and not explicit_url.endswith('/api/'):
                explicit_url = explicit_url.rstrip('/') + '/api'
            logger.info(f"Using explicit PROXY_API_URL: {explicit_url}")
            return explicit_url

        api_port = getattr(settings, 'API_PORT', 8080)
        api_url = f"http://{ip_address}:{api_port}/api"
        logger.info(f"Auto-constructed API URL: {api_url}")
        return api_url

    async def _send_initial_config(self):
        """
        Send initial configuration update after connection.

        Raises:
            ConnectionClosedError: If connection closes during config send
        """
        try:
            from django.conf import settings

            ip_address = self._get_host_ip_address()
            proxy_version = getattr(settings, 'PROXY_VERSION', '1.0.0')

            api_url = self._construct_api_url(ip_address)

            logger.info(f"Sending config update:")
            logger.info(f"  DICOM: {ip_address}:{settings.DICOM_PORT} (AE: {settings.DICOM_AE_TITLE})")
            logger.info(f"  API: {api_url}")

            await self.send_config_update(
                ip_address=ip_address,
                port=settings.DICOM_PORT,
                ae_title=settings.DICOM_AE_TITLE,
                api_url=api_url,
                proxy_version=proxy_version
            )

        except websockets.exceptions.ConnectionClosed:
            logger.error(f"Connection closed while sending initial config")
            raise
        except Exception as e:
            logger.error(f"Error sending initial config: {e}", exc_info=True)

    async def stop(self):
        """Stop WebSocket client gracefully."""
        self.running = False

        if self.websocket:
            await self.send_health_update(proxy_status="offline")

            await self.websocket.close()
            logger.info("WebSocket client stopped")


def get_websocket_client() -> Optional[ProxyWebSocketClient]:
    """
    Get WebSocket client instance with event handlers registered.

    Returns:
        ProxyWebSocketClient or None if not configured
    """
    from django.conf import settings
    from receiver.websockets.handlers import (
        SessionDispatchHandler,
        ScanDispatchHandler,
        SubjectDispatchHandler,
        NewScanAvailableHandler,
        ProxyConfigChangedHandler,
        ProxyNodesChangedHandler,
        ProxyStatusChangedHandler,
        SessionDeletedHandler,
        ScanDeletedHandler,
    )

    api_url = getattr(settings, 'ITH_URL', None)
    proxy_key = getattr(settings, 'ITH_TOKEN', None)

    if not api_url or not proxy_key:
        logger.warning("WebSocket client not configured (missing ITH_URL or ITH_TOKEN)")
        return None

    logger.info(f"WebSocket client configured with API URL: {api_url}")
    client = ProxyWebSocketClient(
        api_url=api_url,
        proxy_key=proxy_key
    )

    class MockConsumer:
        """Mock consumer for standalone websocket client."""
        def __init__(self, ws_client):
            self.ws_client = ws_client
            self.proxy_key = proxy_key

        @property
        def workspace_id(self):
            return self.ws_client.workspace_id

        @property
        def proxy_id(self):
            return self.ws_client.proxy_id

        async def send_event(self, event: Dict[str, Any]):
            """Send event through websocket."""
            await self.ws_client.websocket.send(json.dumps(event))

    mock_consumer = MockConsumer(client)

    client.register_event_handler('session.dispatch', SessionDispatchHandler(mock_consumer).handle)
    client.register_event_handler('scan.dispatch', ScanDispatchHandler(mock_consumer).handle)
    client.register_event_handler('subject.dispatch', SubjectDispatchHandler(mock_consumer).handle)
    client.register_event_handler('scan.new_scan_available', NewScanAvailableHandler(mock_consumer).handle)

    client.register_event_handler('proxy.config_changed', ProxyConfigChangedHandler(mock_consumer).handle)
    client.register_event_handler('proxy.nodes_changed', ProxyNodesChangedHandler(mock_consumer).handle)
    client.register_event_handler('proxy.status_changed', ProxyStatusChangedHandler(mock_consumer).handle)

    client.register_event_handler('session.deleted', SessionDeletedHandler(mock_consumer).handle)
    client.register_event_handler('scan.deleted', ScanDeletedHandler(mock_consumer).handle)

    logger.info(" Registered 9 event handlers: dispatch, config, deletion, new_scan")

    return client
