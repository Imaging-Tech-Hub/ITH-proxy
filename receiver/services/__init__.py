"""
Services Module - Business Logic Layer

Clean, focused services organized by domain:
- api/: HTTP client for ITH backend communication
- config/: Configuration and access control management
- query/: DICOM query operations
- upload/: Study upload operations
- coordination/: Locking and DICOM SCU operations

Services provide reusable business logic consumed by:
- Controllers (DICOM SCP handlers)
- Commands (DICOM SCU operations)
- WebSocket handlers (Event processing)
"""

__all__ = []
