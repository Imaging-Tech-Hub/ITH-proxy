"""
Utils Module - Shared Utilities

Organized by category:
- config/: Configuration data structures (NodeConfig)
- storage/: Data persistence helpers (InstanceMetadataHandler)
- security/: Encryption and secure fields
- logging/: Logging configuration, formatters, and filters
"""
from .logging import setup_logging, get_logger

__all__ = [
    'setup_logging',
    'get_logger',
]
