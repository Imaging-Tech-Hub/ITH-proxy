"""
Access Control Service for DICOM operations.
Enforces mode-based access control (public/private) and node permissions.
"""
import logging
from typing import Optional, Tuple, Any
from receiver.utils.config import NodeConfig

logger = logging.getLogger(__name__)


def extract_calling_ae_title(event: Any) -> str:
    """
    Safely extract calling AE title from DICOM event.

    Args:
        event: pynetdicom event object

    Returns:
        str: Calling AE title or "UNKNOWN" if extraction fails
    """
    try:
        if hasattr(event, 'assoc') and hasattr(event.assoc, 'requestor'):
            ae_title = event.assoc.requestor.ae_title
            if ae_title:
                if isinstance(ae_title, bytes):
                    return ae_title.decode('utf-8').strip()
                return str(ae_title).strip()
    except Exception as e:
        logger.warning(f"Could not extract calling AE title: {e}")

    return "UNKNOWN"


def extract_requester_address(event: Any) -> Optional[str]:
    """
    Extract requester IP address from DICOM event.

    Args:
        event: pynetdicom event object

    Returns:
        str: IP address or None if extraction fails
    """
    try:
        if hasattr(event, 'assoc') and hasattr(event.assoc, 'requestor'):
            if hasattr(event.assoc.requestor, 'address'):
                address = event.assoc.requestor.address
                if address:
                    return str(address)

            if hasattr(event.assoc, 'remote') and hasattr(event.assoc.remote, 'address'):
                remote_addr = event.assoc.remote.address
                if remote_addr:
                    if isinstance(remote_addr, tuple) and len(remote_addr) >= 1:
                        return str(remote_addr[0])
                    return str(remote_addr)
    except Exception as e:
        logger.debug(f"Could not extract requester address: {e}")

    return None


class AccessControlService:
    """
    Service for validating DICOM access based on proxy mode and node permissions.

    Modes:
    - PUBLIC: Accept operations from any node, no permission checks
    - PRIVATE: Only accept operations from configured nodes, enforce permissions

    Node Permissions (private mode only):
    - read: Can query and retrieve (C-FIND, C-GET, C-MOVE from proxy)
    - write: Can store (C-STORE to proxy)
    - read_write: Can do both
    """

    def __init__(self, config_service):
        """
        Initialize access control service.

        Args:
            config_service: ProxyConfigService instance
        """
        self.config_service = config_service

    def get_mode(self) -> str:
        """
        Get current proxy mode.

        Returns:
            str: 'public' or 'private', defaults to 'public' if not set
        """
        proxy_config = self.config_service.load_proxy_config()
        if proxy_config:
            mode = proxy_config.get('mode', 'public')
            return mode.lower() if mode else 'public'
        return 'public'

    def is_public_mode(self) -> bool:
        """Check if proxy is in public mode."""
        return self.get_mode() == 'public'

    def is_private_mode(self) -> bool:
        """Check if proxy is in private mode."""
        return self.get_mode() == 'private'

    def find_node_by_ae_title(self, ae_title: str, requester_ip: Optional[str] = None) -> Optional[NodeConfig]:
        """
        Find a configured node by its AE title and optionally by IP address.
        Case-insensitive comparison with whitespace trimming.

        Args:
            ae_title: DICOM AE Title of the node
            requester_ip: Optional IP address of the requester for additional validation

        Returns:
            NodeConfig if found, None otherwise
        """
        if not ae_title:
            return None

        normalized_ae = ae_title.strip().upper()

        nodes = self.config_service.load_nodes()
        matched_nodes = []

        for node in nodes:
            node_ae_normalized = node.ae_title.strip().upper() if node.ae_title else ""
            if node_ae_normalized == normalized_ae:
                matched_nodes.append(node)

        if not matched_nodes:
            return None

        if len(matched_nodes) == 1:
            return matched_nodes[0]

        if requester_ip and len(matched_nodes) > 1:
            logger.info(f"Multiple nodes found with AE title '{ae_title}', matching by IP: {requester_ip}")
            for node in matched_nodes:
                if node.host == requester_ip:
                    logger.info(f"Matched node by IP: {node.name} ({node.host})")
                    return node
            logger.warning(f"No node matched by IP {requester_ip}, using first match")

        return matched_nodes[0]

    def can_accept_store(self, calling_ae_title: str, requester_ip: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if proxy can accept C-STORE from a calling AE.

        Args:
            calling_ae_title: AE title of the calling node
            requester_ip: Optional IP address of the requester

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        mode = self.get_mode()

        if mode == 'public':
            logger.debug(f"C-STORE allowed in public mode from {calling_ae_title} ({requester_ip or 'unknown IP'})")
            return True, "Public mode - all nodes allowed"

        node = self.find_node_by_ae_title(calling_ae_title, requester_ip)

        if not node:
            logger.warning(f"C-STORE rejected: Unknown node '{calling_ae_title}' ({requester_ip or 'unknown IP'}) in private mode")
            return False, f"Node '{calling_ae_title}' not configured"

        if not node.is_active:
            logger.warning(f"C-STORE rejected: Node '{calling_ae_title}' is inactive")
            return False, f"Node '{calling_ae_title}' is inactive"

        permission = node.permission.lower() if node.permission else "none"
        if permission in ['write', 'read_write']:
            logger.debug(f"C-STORE allowed from {calling_ae_title} @ {node.host} (permission: {permission})")
            return True, f"Node has {permission} permission"
        else:
            logger.warning(f"C-STORE rejected: Node '{calling_ae_title}' has {permission} permission (needs write or read_write)")
            return False, f"Node has {permission} permission (needs write or read_write)"

    def can_accept_query(self, calling_ae_title: str, requester_ip: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if proxy can accept C-FIND from a calling AE.

        Args:
            calling_ae_title: AE title of the calling node
            requester_ip: Optional IP address of the requester

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        mode = self.get_mode()

        if mode == 'public':
            logger.info(f"C-FIND allowed in PUBLIC mode from {calling_ae_title} ({requester_ip or 'unknown IP'}) (permissions not enforced)")
            return True, "Public mode - all nodes allowed"

        node = self.find_node_by_ae_title(calling_ae_title, requester_ip)

        if not node:
            logger.warning(f"C-FIND rejected: Unknown node '{calling_ae_title}' ({requester_ip or 'unknown IP'}) in private mode")
            return False, f"Node '{calling_ae_title}' not configured"

        if not node.is_active:
            logger.warning(f"C-FIND rejected: Node '{calling_ae_title}' is inactive")
            return False, f"Node '{calling_ae_title}' is inactive"

        permission = node.permission.lower() if node.permission else "none"
        if permission in ['read', 'read_write']:
            logger.info(f"C-FIND allowed in PRIVATE mode from {calling_ae_title} @ {node.host} (permission: {permission})")
            return True, f"Node has {permission} permission"
        else:
            logger.warning(f"C-FIND REJECTED in PRIVATE mode: Node '{calling_ae_title}' has {permission} permission (needs read or read_write)")
            return False, f"Node has {permission} permission (needs read or read_write)"

    def can_accept_retrieve(self, calling_ae_title: str, requester_ip: Optional[str] = None, operation: str = "C-GET") -> Tuple[bool, str]:
        """
        Check if proxy can accept C-GET or C-MOVE from a calling AE.

        Args:
            calling_ae_title: AE title of the calling node
            requester_ip: Optional IP address of the requester
            operation: Operation type (C-GET or C-MOVE)

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        mode = self.get_mode()

        if mode == 'public':
            logger.debug(f"{operation} allowed in public mode from {calling_ae_title} ({requester_ip or 'unknown IP'})")
            return True, "Public mode - all nodes allowed"

        node = self.find_node_by_ae_title(calling_ae_title, requester_ip)

        if not node:
            logger.warning(f"{operation} rejected: Unknown node '{calling_ae_title}' ({requester_ip or 'unknown IP'}) in private mode")
            return False, f"Node '{calling_ae_title}' not configured"

        if not node.is_active:
            logger.warning(f"{operation} rejected: Node '{calling_ae_title}' is inactive")
            return False, f"Node '{calling_ae_title}' is inactive"

        permission = node.permission.lower() if node.permission else "none"
        if permission in ['read', 'read_write']:
            logger.debug(f"{operation} allowed from {calling_ae_title} @ {node.host} (permission: {permission})")
            return True, f"Node has {permission} permission"
        else:
            logger.warning(f"{operation} rejected: Node '{calling_ae_title}' has {permission} permission (needs read or read_write)")
            return False, f"Node has {permission} permission (needs read or read_write)"

    def can_send_to_node(self, destination_ae_title: str) -> Tuple[bool, str]:
        """
        Check if proxy can send data to a destination node (C-MOVE destination or dispatch).

        Args:
            destination_ae_title: AE title of the destination node

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        mode = self.get_mode()

        if mode == 'public':
            logger.debug(f"Send allowed in public mode to {destination_ae_title}")
            return True, "Public mode - all destinations allowed"

        node = self.find_node_by_ae_title(destination_ae_title)

        if not node:
            logger.warning(f"Send rejected: Unknown destination '{destination_ae_title}' in private mode")
            return False, f"Destination '{destination_ae_title}' not configured"

        if not node.is_active:
            logger.warning(f"Send rejected: Destination '{destination_ae_title}' is inactive")
            return False, f"Destination '{destination_ae_title}' is inactive"

        logger.debug(f"Send allowed to configured node {destination_ae_title}")
        return True, f"Destination is configured and active"

    def log_access_status(self):
        """Log current access control status."""
        mode = self.get_mode()
        nodes = self.config_service.load_nodes()
        active_nodes = [n for n in nodes if n.is_active]

        logger.info("=" * 60)
        logger.info(f"ACCESS CONTROL STATUS")
        logger.info(f"Mode: {mode.upper()}")

        if mode == 'public':
            logger.info("Public mode - accepting DICOM from any node")
        else:
            logger.info(f"Private mode - only accepting from {len(active_nodes)} configured nodes")
            for node in active_nodes:
                logger.info(f"  - {node.ae_title} @ {node.host}:{node.port} ({node.permission})")

        logger.info("=" * 60)


_access_control_service = None


def get_access_control_service():
    """
    Get singleton instance of AccessControlService.

    Returns:
        AccessControlService instance or None if config service not available
    """
    global _access_control_service

    if _access_control_service is not None:
        return _access_control_service

    try:
        from .proxy_config_service import get_config_service

        config_service = get_config_service()
        if not config_service:
            logger.error("Config service not available, access control disabled")
            return None

        _access_control_service = AccessControlService(config_service)
        return _access_control_service

    except Exception as e:
        logger.error(f"Error creating access control service: {e}", exc_info=True)
        return None
