"""
WebSocket Event Handlers.
Handles events received from ITH backend via WebSocket.
"""
# Dispatch handlers
from .session_dispatch_handler import SessionDispatchHandler
from .scan_dispatch_handler import ScanDispatchHandler
from .subject_dispatch_handler import SubjectDispatchHandler
from .new_scan_available_handler import NewScanAvailableHandler

# Proxy configuration handlers
from .proxy_config_changed_handler import ProxyConfigChangedHandler
from .proxy_nodes_changed_handler import ProxyNodesChangedHandler
from .proxy_status_changed_handler import ProxyStatusChangedHandler

# Deletion handlers
from .session_deleted_handler import SessionDeletedHandler
from .scan_deleted_handler import ScanDeletedHandler
from .subject_deleted_handler import SubjectDeletedHandler

__all__ = [
    # Dispatch
    'SessionDispatchHandler',
    'ScanDispatchHandler',
    'SubjectDispatchHandler',
    'NewScanAvailableHandler',
    # Config
    'ProxyConfigChangedHandler',
    'ProxyNodesChangedHandler',
    'ProxyStatusChangedHandler',
    # Deletion
    'SessionDeletedHandler',
    'ScanDeletedHandler',
    'SubjectDeletedHandler',
]
