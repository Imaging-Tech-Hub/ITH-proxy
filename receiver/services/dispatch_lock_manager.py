"""
Dispatch Lock Manager - Prevents duplicate concurrent dispatch operations.
Thread-safe singleton that tracks active dispatch operations to prevent
downloading and sending the same data multiple times to the same node.
"""
import logging
import threading
from typing import Optional, Set, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DispatchLockManager:
    """
    Thread-safe manager for tracking active dispatch operations.
    Prevents duplicate concurrent dispatches to the same node for the same data.

    Usage:
        lock_manager = DispatchLockManager()

        # Method 1: Manual acquire/release
        if lock_manager.acquire_lock(node_id='node_1', entity_type='scan', entity_id='scan_123'):
            try:
                # Download and dispatch
                pass
            finally:
                lock_manager.release_lock(node_id='node_1', entity_type='scan', entity_id='scan_123')
        else:
            logger.info("Dispatch already in progress, skipping")

        # Method 2: Context manager (auto-cleanup)
        with lock_manager.lock(node_id='node_1', entity_type='scan', entity_id='scan_123') as acquired:
            if acquired:
                # Download and dispatch
                pass
            else:
                logger.info("Dispatch already in progress, skipping")
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize lock manager."""
        if self._initialized:
            return

        self._initialized = True
        self._active_locks: Set[Tuple[str, str, str]] = set()
        self._locks_lock = threading.Lock()

        logger.info("DispatchLockManager initialized")

    def _make_key(self, node_id: str, entity_type: str, entity_id: str) -> Tuple[str, str, str]:
        """
        Create lock key from dispatch parameters.

        Args:
            node_id: Target node ID
            entity_type: Type of entity (scan, session, subject)
            entity_id: Entity ID

        Returns:
            Tuple key for tracking
        """
        return (str(node_id), str(entity_type).lower(), str(entity_id))

    def acquire_lock(self, node_id: str, entity_type: str, entity_id: str) -> bool:
        """
        Attempt to acquire lock for dispatch operation.

        Args:
            node_id: Target node ID
            entity_type: Type of entity (scan, session, subject)
            entity_id: Entity ID

        Returns:
            True if lock acquired, False if already locked
        """
        key = self._make_key(node_id, entity_type, entity_id)

        with self._locks_lock:
            if key in self._active_locks:
                logger.warning(
                    f"🔒 Dispatch already in progress: "
                    f"node={node_id}, {entity_type}={entity_id}"
                )
                return False

            self._active_locks.add(key)
            logger.debug(
                f"🔓 Lock acquired: node={node_id}, {entity_type}={entity_id} "
                f"(active locks: {len(self._active_locks)})"
            )
            return True

    def release_lock(self, node_id: str, entity_type: str, entity_id: str) -> None:
        """
        Release lock for dispatch operation.

        Args:
            node_id: Target node ID
            entity_type: Type of entity (scan, session, subject)
            entity_id: Entity ID
        """
        key = self._make_key(node_id, entity_type, entity_id)

        with self._locks_lock:
            if key in self._active_locks:
                self._active_locks.remove(key)
                logger.debug(
                    f"🔓 Lock released: node={node_id}, {entity_type}={entity_id} "
                    f"(active locks: {len(self._active_locks)})"
                )
            else:
                logger.warning(
                    f"⚠️  Attempted to release non-existent lock: "
                    f"node={node_id}, {entity_type}={entity_id}"
                )

    def is_locked(self, node_id: str, entity_type: str, entity_id: str) -> bool:
        """
        Check if dispatch operation is currently locked.

        Args:
            node_id: Target node ID
            entity_type: Type of entity (scan, session, subject)
            entity_id: Entity ID

        Returns:
            True if locked, False otherwise
        """
        key = self._make_key(node_id, entity_type, entity_id)

        with self._locks_lock:
            return key in self._active_locks

    @contextmanager
    def lock(self, node_id: str, entity_type: str, entity_id: str):
        """
        Context manager for automatic lock acquisition and release.

        Args:
            node_id: Target node ID
            entity_type: Type of entity (scan, session, subject)
            entity_id: Entity ID

        Yields:
            bool: True if lock acquired, False if already locked

        Example:
            with lock_manager.lock('node_1', 'scan', 'scan_123') as acquired:
                if acquired:
                    # Do dispatch work
                    pass
        """
        acquired = self.acquire_lock(node_id, entity_type, entity_id)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_lock(node_id, entity_type, entity_id)

    def get_active_locks_count(self) -> int:
        """
        Get count of currently active locks.

        Returns:
            Number of active dispatch operations
        """
        with self._locks_lock:
            return len(self._active_locks)

    def get_active_locks(self) -> list:
        """
        Get list of currently active locks (for monitoring/debugging).

        Returns:
            List of (node_id, entity_type, entity_id) tuples
        """
        with self._locks_lock:
            return list(self._active_locks)

    def clear_all_locks(self) -> int:
        """
        Clear all locks (use with caution, mainly for testing/recovery).

        Returns:
            Number of locks cleared
        """
        with self._locks_lock:
            count = len(self._active_locks)
            self._active_locks.clear()
            logger.warning(f"🗑️  Cleared all dispatch locks ({count} locks removed)")
            return count


_lock_manager_instance: Optional[DispatchLockManager] = None


def get_dispatch_lock_manager() -> DispatchLockManager:
    """
    Get the singleton DispatchLockManager instance.

    Returns:
        DispatchLockManager instance
    """
    global _lock_manager_instance
    if _lock_manager_instance is None:
        _lock_manager_instance = DispatchLockManager()
    return _lock_manager_instance
