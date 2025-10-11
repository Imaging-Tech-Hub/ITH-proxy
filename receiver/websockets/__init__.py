"""
WebSocket Module - Real-time Communication Layer

Handles bidirectional WebSocket communication with ITH backend:
- consumer.py: Django Channels WebSocket consumer
- handlers/: Event handlers for different event types

Event handlers process incoming events and trigger appropriate actions
using commands and services.
"""

# Note: Import handlers from subdirectory directly
# Example: from receiver.websockets.handlers import SessionDispatchHandler

__all__ = []
