"""
C-FIND Handler for DICOM query operations.
Coordinates queries across different levels (PATIENT, STUDY, SERIES, IMAGE).
"""
import logging
from typing import Any, Dict, Generator, Tuple, Optional, TYPE_CHECKING
from pydicom import Dataset

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi_resolver import PHIResolver

logger = logging.getLogger('receiver.handlers.find')


class FindHandler:
    """Handler for C-FIND operations - responds to DICOM queries."""

    def __init__(self, storage_manager: 'StorageManager', resolver: 'PHIResolver', query_handlers: Dict[str, Any]) -> None:
        """
        Initialize the find handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver instance
            query_handlers: Dict of query handlers for each level
        """
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.query_handlers = query_handlers

    def handle_find(self, event: Any) -> Generator[Tuple[int, Optional[Dataset]], None, None]:
        """
        Handle incoming C-FIND request.

        Args:
            event: pynetdicom event object

        Yields:
            tuple: (status_code, response_dataset)
        """
        from receiver.services.access_control_service import extract_calling_ae_title, extract_requester_address, get_access_control_service
        calling_ae = extract_calling_ae_title(event)
        requester_ip = extract_requester_address(event)

        access_control = get_access_control_service()

        if access_control:
            allowed, reason = access_control.can_accept_query(calling_ae, requester_ip)
            if not allowed:
                logger.warning(f"C-FIND REJECTED from {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")
                yield 0xC001, None
                return
            logger.debug(f"C-FIND access granted to {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")

        logger.info("=" * 60)
        logger.info(" RECEIVED C-FIND REQUEST")
        logger.info(f"From: {calling_ae}")
        logger.info("=" * 60)

        query_ds = event.identifier

        query_level = getattr(query_ds, 'QueryRetrieveLevel', 'STUDY')
        logger.info(f" Query Level: {query_level}")

        logger.info(" Query Parameters:")
        for tag in query_ds:
            if hasattr(query_ds, tag.keyword) and tag.keyword:
                value = getattr(query_ds, tag.keyword, '')
                if value:
                    logger.info(f"{tag.keyword}: {value}")
                else:
                    logger.info(f"{tag.keyword}: <empty> (requesting this field)")

        try:
            handler = self.query_handlers.get(query_level)
            if handler:
                yield from handler.find(query_ds)
            else:
                logger.warning(f" Unsupported query level: {query_level}")
                yield 0xC000, None

        except Exception as e:
            logger.error(f" Error processing C-FIND request: {e}", exc_info=True)
            yield 0xC000, None
