"""
Signals Module - System Signal Handlers

Handles system-level signals for graceful shutdown and lifecycle management.
"""
from .shutdown_handler import register_shutdown_handlers

__all__ = [
    'register_shutdown_handlers',
]
