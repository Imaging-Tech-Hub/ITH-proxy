"""
Proxy Configuration Service.
Loads proxy configuration from ITH API and manages node configurations in-memory.
"""
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from receiver.utils.node_config import NodeConfig

if TYPE_CHECKING:
    from receiver.services.ith_api_client import IthAPIClient

logger = logging.getLogger(__name__)


class ProxyConfigService:
    """
    Service for loading and managing proxy configuration in-memory.

    Uses IthAPIClient to fetch configuration from:
    GET /api/v1/proxy/configuration

    Manages:
    - Proxy DICOM settings
    - PACS node configurations (in-memory)
    - Feature flags
    - Health status
    """

    def __init__(self, api_client: 'IthAPIClient'):
        """
        Initialize proxy config service.

        Args:
            api_client: IthAPIClient instance (injected via DI)
        """
        self.api_client = api_client

        self._nodes: List[NodeConfig] = []
        self._proxy_config: Optional[Dict[str, Any]] = None
        self._full_config: Optional[Dict[str, Any]] = None

    def fetch_configuration(self) -> Optional[Dict[str, Any]]:
        """
        Fetch complete proxy configuration from API using IthAPIClient.

        Returns:
            Configuration dictionary or None if failed
        """
        try:
            logger.info("Fetching proxy configuration from API")
            config_data = self.api_client.get_proxy_configuration()

            if config_data:
                workspace_id = config_data.get('workspace_id')
                if workspace_id:
                    self.api_client.workspace_id = workspace_id
                    logger.info(f"Workspace ID set to: {workspace_id}")

                logger.info(f"Successfully fetched configuration for proxy: {config_data.get('name')}")
            else:
                logger.error("Failed to fetch proxy configuration")

            return config_data

        except Exception as e:
            logger.error(f"Error fetching configuration: {e}", exc_info=True)
            return None

    def save_configuration(self, config_data: Dict[str, Any]) -> None:
        """
        Save configuration to in-memory storage.

        Args:
            config_data: Configuration data from API
        """
        try:
            self._full_config = config_data

            nodes_data = config_data.get('nodes', [])
            self._parse_and_store_nodes(nodes_data)

            proxy_config = config_data.get('config', {})

            port = proxy_config.get('port', 11112)
            if not isinstance(port, int) or port < 1 or port > 65535:
                logger.warning(f"Invalid port value {port}, using default 11112")
                port = 11112

            ae_title = str(proxy_config.get('ae_title', 'DICOMRCV'))
            if len(ae_title) > 16:
                logger.warning(f"AE title '{ae_title}' exceeds 16 characters, truncating")
                ae_title = ae_title[:16]
            if not ae_title.strip():
                logger.warning("Empty AE title, using default 'DICOMRCV'")
                ae_title = 'DICOMRCV'

            self._proxy_config = {
                'proxy_id': config_data.get('id'),
                'workspace_id': config_data.get('workspace_id'),
                'name': config_data.get('name'),
                'description': config_data.get('description'),
                'ip_address': proxy_config.get('ip_address'),
                'port': port,
                'ae_title': ae_title,
                'mode': proxy_config.get('mode'),
                'enable_phi_anonymization': proxy_config.get('enable_phi_anonymization', False),
                'flairstar_auto_dispatch_result': proxy_config.get('flairstar_auto_dispatch_result', True),
                'resolver_information_url': proxy_config.get('resolver_information_url', ''),
                'is_active': config_data.get('is_active', True),
                'metadata': config_data.get('metadata', {})
            }

            logger.info(f"Saved configuration to memory: {len(self._nodes)} nodes")

        except Exception as e:
            logger.error(f"Error saving configuration: {e}", exc_info=True)

    def _parse_and_store_nodes(self, nodes_data: List[Dict[str, Any]]) -> None:
        """Parse nodes from API response and store in memory."""
        self._nodes = []

        for node in nodes_data:
            if 'ip' in node and 'ip_address' not in node:
                node['ip_address'] = node['ip']

            required_fields = ['id', 'ae_title', 'ip_address', 'port']
            missing_fields = [field for field in required_fields if field not in node]

            if missing_fields:
                node_name = node.get('name', 'Unknown')
                logger.warning(f"Skipping node '{node_name}' - Missing required fields: {', '.join(missing_fields)}")
                logger.debug(f"Available fields: {', '.join(node.keys())}")
                continue

            node_port = node['port']
            if not isinstance(node_port, int) or node_port < 1 or node_port > 65535:
                logger.warning(f"Node '{node.get('name')}' has invalid port {node_port}, skipping")
                continue

            node_ae_title = str(node['ae_title'])
            if len(node_ae_title) > 16:
                logger.warning(f"Node '{node.get('name')}' AE title exceeds 16 characters, truncating")
                node_ae_title = node_ae_title[:16]
            if not node_ae_title.strip():
                logger.warning(f"Node '{node.get('name')}' has empty AE title, skipping")
                continue

            node_host = str(node['ip_address']).strip()
            if not node_host:
                logger.warning(f"Node '{node.get('name')}' has empty IP address, skipping")
                continue

            node_config = NodeConfig(
                node_id=node['id'],
                name=node['name'],
                description=node.get('description', ''),
                ae_title=node_ae_title,
                host=node_host,
                port=node_port,
                storage_path='',
                is_active=node['is_active'],
                connection_timeout=30,
                max_pdu_size=16384,
                retry_count=3,
                retry_delay=5,
                permission=node.get('permission', 'READ_WRITE'),
                is_reachable=node.get('is_reachable', False),
                metadata=node.get('metadata', {})
            )
            self._nodes.append(node_config)

        logger.info(f"Parsed {len(self._nodes)} nodes from API")

    def load_nodes(self) -> List[NodeConfig]:
        """
        Load nodes from in-memory storage.

        Returns:
            List of NodeConfig objects
        """
        return self._nodes.copy()

    def load_proxy_config(self) -> Optional[Dict[str, Any]]:
        """
        Load proxy configuration from in-memory storage.

        Returns:
            Proxy configuration dictionary or None
        """
        return self._proxy_config.copy() if self._proxy_config else None

    def get_active_nodes(self) -> List[NodeConfig]:
        """
        Get only active nodes.

        Returns:
            List of active NodeConfig objects
        """
        active_nodes = [node for node in self._nodes if node.is_active]
        return active_nodes

    def get_node_by_id(self, node_id: str) -> Optional[NodeConfig]:
        """
        Get specific node by ID.

        Args:
            node_id: Node ID

        Returns:
            NodeConfig or None if not found
        """
        for node in self._nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_nodes_by_ids(self, node_ids: List[str]) -> List[NodeConfig]:
        """
        Get multiple nodes by their IDs.

        Args:
            node_ids: List of node IDs

        Returns:
            List of matching NodeConfig objects
        """
        node_id_set = set(node_ids)
        matching_nodes = [node for node in self._nodes if node.node_id in node_id_set]
        return matching_nodes

    def fetch_and_save(self) -> bool:
        """
        Fetch configuration from API and save to in-memory storage.

        Returns:
            True if successful, False otherwise
        """
        config_data = self.fetch_configuration()

        if not config_data:
            return False

        self.save_configuration(config_data)
        return True

    def get_proxy_id(self) -> Optional[str]:
        """Get proxy ID from configuration."""
        return self._proxy_config.get('proxy_id') if self._proxy_config else None

    def get_workspace_id(self) -> Optional[str]:
        """Get workspace ID from configuration."""
        return self._proxy_config.get('workspace_id') if self._proxy_config else None

    def is_phi_anonymization_enabled(self) -> bool:
        """Check if PHI anonymization is enabled."""
        return self._proxy_config.get('enable_phi_anonymization', False) if self._proxy_config else False

    def is_auto_dispatch_enabled(self) -> bool:
        """Check if auto-dispatch to FlairStar is enabled."""
        return True

    def apply_to_proxy_model(self, config_data: Dict[str, Any]) -> bool:
        """
        Apply loaded configuration to the ProxyConfiguration model.

        Args:
            config_data: Configuration data from API

        Returns:
            bool: True if successful, False otherwise
        """
        from receiver.models import ProxyConfiguration

        try:
            proxy_config = ProxyConfiguration.get_instance()
            api_config = config_data.get('config', {})

            proxy_config.port = api_config.get('port', proxy_config.port)
            proxy_config.ae_title = api_config.get('ae_title', proxy_config.ae_title)

            resolver_url = api_config.get('resolver_information_url')
            proxy_config.resolver_api_url = resolver_url if resolver_url is not None else ''

            proxy_config.save()

            logger.info(f"Applied configuration to ProxyConfiguration model: {proxy_config.dicom_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply configuration to model: {e}", exc_info=True)
            return False

    def load_and_apply_configuration(self) -> bool:
        """
        Complete flow: Fetch configuration and save locally (in-memory).

        Returns:
            bool: True if successful
        """
        config_data = self.fetch_configuration()
        if not config_data:
            logger.warning("Could not fetch configuration from API")
            return False

        self.save_configuration(config_data)

        logger.info("Configuration loaded successfully (stored in-memory)")
        return True


def get_config_service() -> Optional[ProxyConfigService]:
    """
    Get config service instance from DI container.

    Returns:
        ProxyConfigService instance or None
    """
    from receiver.containers import container

    try:
        return container.proxy_config_service()
    except Exception as e:
        logger.warning(f"Could not get config service from container: {e}")
        return None
