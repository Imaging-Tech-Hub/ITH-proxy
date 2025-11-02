"""
Signals Module - System Signal Handlers

Handles system-level signals for graceful shutdown and lifecycle management.
Also includes Django model signals for cache invalidation.
"""
from .shutdown_handler import register_shutdown_handlers
from . import cache_invalidation  # noqa: F401

__all__ = [
    'register_shutdown_handlers',
]
