"""
Node Configuration - represents PACS node configuration (not a database model).
Nodes are loaded from configuration files or external API.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeConfig:
    """
    Configuration for a PACS node.
    This is a simple data class, not a database model.
    """
    node_id: str
    name: str
    description: str = ""

    ae_title: str = "PACS"
    host: str = "localhost"
    port: int = 11112

    storage_path: str = ""

    is_active: bool = True
    is_reachable: bool = False

    permission: str = "READ_WRITE"

    connection_timeout: int = 30
    max_pdu_size: int = 16384

    retry_count: int = 3
    retry_delay: int = 5

    metadata: dict = None

    def __post_init__(self):
        """Initialize mutable default values."""
        if self.metadata is None:
            self.metadata = {}

    def __str__(self):
        return f"{self.name} ({self.ae_title}@{self.host}:{self.port})"

    @classmethod
    def from_dict(cls, data: dict) -> 'NodeConfig':
        """
        Create NodeConfig from dictionary.

        Args:
            data: Dictionary with node configuration

        Returns:
            NodeConfig instance
        """
        return cls(
            node_id=data.get('node_id'),
            name=data.get('name'),
            description=data.get('description', ''),
            ae_title=data.get('ae_title', 'PACS'),
            host=data.get('host', 'localhost'),
            port=data.get('port', 11112),
            storage_path=data.get('storage_path', ''),
            is_active=data.get('is_active', True),
            is_reachable=data.get('is_reachable', False),
            permission=data.get('permission', 'READ_WRITE'),
            connection_timeout=data.get('connection_timeout', 30),
            max_pdu_size=data.get('max_pdu_size', 16384),
            retry_count=data.get('retry_count', 3),
            retry_delay=data.get('retry_delay', 5),
            metadata=data.get('metadata', {})
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'node_id': self.node_id,
            'name': self.name,
            'description': self.description,
            'ae_title': self.ae_title,
            'host': self.host,
            'port': self.port,
            'storage_path': self.storage_path,
            'is_active': self.is_active,
            'is_reachable': self.is_reachable,
            'permission': self.permission,
            'connection_timeout': self.connection_timeout,
            'max_pdu_size': self.max_pdu_size,
            'retry_count': self.retry_count,
            'retry_delay': self.retry_delay,
            'metadata': self.metadata
        }
