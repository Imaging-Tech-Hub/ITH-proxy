"""
C-FIND Handler for DICOM query operations.
Coordinates queries across different levels (PATIENT, STUDY, SERIES, IMAGE).
"""
from typing import Any, Dict, Generator, Tuple, Optional, TYPE_CHECKING

from pydicom import Dataset

from receiver.controllers.base import HandlerBase, DICOMStatus

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi import PHIResolver


class FindHandler(HandlerBase):
    """Handler for C-FIND operations - responds to DICOM queries."""

    def __init__(
        self,
        storage_manager: 'StorageManager',
        resolver: 'PHIResolver',
        query_handlers: Dict[str, Any]
    ) -> None:
        """
        Initialize the find handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver instance
            query_handlers: Dict of query handlers for each level
        """
        super().__init__('find')
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
        calling_info = self.extract_calling_info(event)

        allowed, reason = self.check_access(event, "C-FIND")
        if not allowed:
            yield DICOMStatus.ACCESS_DENIED, None
            return

        self.log_operation_start("C-FIND", calling_info)

        query_ds = event.identifier
        query_level = self.get_query_level(query_ds)

        self._log_query_tags(query_ds)

        try:
            handler = self.query_handlers.get(query_level)
            if handler:
                yield from handler.find(query_ds)
            else:
                self.logger.warning(f"Unsupported query level: {query_level}")
                yield DICOMStatus.UNABLE_TO_PROCESS, None

        except Exception as e:
            self.logger.error(f"Error processing C-FIND request: {e}", exc_info=True)
            yield DICOMStatus.UNABLE_TO_PROCESS, None

    def _log_query_tags(self, query_ds: Dataset) -> None:
        """
        Log query tags and values.

        Args:
            query_ds: Query dataset
        """
        self.logger.info("Query Parameters:")
        for tag in query_ds:
            if hasattr(query_ds, tag.keyword) and tag.keyword:
                value = getattr(query_ds, tag.keyword, '')
                if value:
                    self.logger.info(f"  {tag.keyword}: {value}")
                else:
                    self.logger.info(f"  {tag.keyword}: <empty> (requesting this field)")

    def handle(self, event: Any):
        """Main handler method (delegates to handle_find for C-FIND operations)."""
        return self.handle_find(event)
