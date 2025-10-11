"""
Base handler class for DICOM operations.

Provides common functionality for all DICOM handlers:
- Access control integration
- Logging setup
- Association context management
- Status code helpers
- Query parameter extraction
"""
import logging
from typing import Any, Optional, Tuple
from abc import ABC, abstractmethod
from io import BytesIO

from pydicom import dcmread
from pydicom.uid import ImplicitVRLittleEndian

from .dicom_constants import DICOMStatus


class HandlerBase(ABC):
    """
    Base class for all DICOM handlers (C-STORE, C-FIND, C-MOVE, C-GET).

    Provides:
    - Access control checking
    - Logging infrastructure
    - Common query parameter extraction
    - Association context utilities
    - Status code helpers
    """

    def __init__(self, handler_name: str):
        """
        Initialize base handler.

        Args:
            handler_name: Name for logging (e.g., 'store', 'find', 'get')
        """
        self.handler_name = handler_name
        self.logger = logging.getLogger(f'receiver.handlers.{handler_name}')

    def check_access(
        self,
        event: Any,
        operation_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the calling AE is allowed to perform the operation.

        Args:
            event: pynetdicom event
            operation_type: Type of operation (e.g., "C-STORE", "C-GET", "C-FIND")

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        try:
            from receiver.services.config import (
                extract_calling_ae_title,
                extract_requester_address,
                get_access_control_service
            )

            calling_ae = extract_calling_ae_title(event)
            requester_ip = extract_requester_address(event)

            access_control = get_access_control_service()

            if not access_control:
                return True, "No access control configured"

            if operation_type in ["C-STORE"]:
                allowed, reason = access_control.can_accept_store(calling_ae, requester_ip)
            elif operation_type in ["C-FIND"]:
                allowed, reason = access_control.can_accept_query(calling_ae, requester_ip)
            elif operation_type in ["C-MOVE", "C-GET"]:
                allowed, reason = access_control.can_accept_retrieve(calling_ae, requester_ip, operation_type)
            else:
                allowed, reason = True, f"Unknown operation type: {operation_type}"

            if allowed:
                self.logger.debug(f"{operation_type} access granted to {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")
            else:
                self.logger.warning(f"{operation_type} REJECTED from {calling_ae} ({requester_ip or 'unknown IP'}): {reason}")

            return allowed, reason

        except Exception as e:
            self.logger.error(f"Error checking access: {e}", exc_info=True)
            return False, f"Access control error: {str(e)}"

    def extract_calling_info(self, event: Any) -> dict:
        """
        Extract calling AE information from event.

        Args:
            event: pynetdicom event

        Returns:
            Dict with calling_ae and requester_ip
        """
        try:
            from receiver.services.config import (
                extract_calling_ae_title,
                extract_requester_address
            )

            return {
                'calling_ae': extract_calling_ae_title(event),
                'requester_ip': extract_requester_address(event)
            }
        except Exception as e:
            self.logger.warning(f"Error extracting calling info: {e}")
            return {
                'calling_ae': 'UNKNOWN',
                'requester_ip': None
            }

    def decode_identifier(self, identifier: Any) -> Any:
        """
        Decode identifier if it's a BytesIO object.

        Args:
            identifier: Query identifier (BytesIO or Dataset)

        Returns:
            Decoded Dataset
        """
        if isinstance(identifier, BytesIO):
            self.logger.debug("Identifier is BytesIO, decoding to Dataset...")
            identifier.seek(0)
            identifier = dcmread(identifier, force=True)

        return identifier

    def extract_uid(self, identifier: Any, uid_type: str) -> Optional[str]:
        """
        Extract a UID from identifier.

        Args:
            identifier: DICOM identifier Dataset
            uid_type: Type of UID to extract (e.g., 'StudyInstanceUID', 'SeriesInstanceUID')

        Returns:
            UID string or None
        """
        try:
            for elem in identifier:
                if elem.keyword == uid_type:
                    if elem.value:
                        uid = str(elem.value).strip()
                        self.logger.debug(f"Extracted {uid_type}: {uid}")
                        return uid
                    else:
                        self.logger.warning(f"{uid_type} element exists but value is empty")
                        return None

            self.logger.warning(f"No {uid_type} element found in identifier")
            return None

        except Exception as e:
            self.logger.error(f"Error extracting {uid_type}: {e}", exc_info=True)
            return None

    def get_query_level(self, identifier: Any, default: str = 'STUDY') -> str:
        """
        Get query/retrieve level from identifier.

        Args:
            identifier: DICOM identifier Dataset
            default: Default level if not specified

        Returns:
            Query level string (PATIENT, STUDY, SERIES, IMAGE)
        """
        query_level = getattr(identifier, 'QueryRetrieveLevel', default)
        self.logger.debug(f"Query Level: {query_level}")
        return query_level

    def log_query_parameters(self, identifier: Any, max_value_length: int = 100) -> None:
        """
        Log query parameters from identifier.

        Args:
            identifier: DICOM identifier Dataset
            max_value_length: Maximum length of value to display
        """
        self.logger.debug("Query Parameters:")
        self.logger.debug(f"Identifier type: {type(identifier)}")

        try:
            for elem in identifier:
                if elem.value is not None:
                    if isinstance(elem.value, (str, int, float)):
                        value_str = str(elem.value)
                        display_value = value_str[:max_value_length] + "..." if len(value_str) > max_value_length else value_str
                    else:
                        display_value = f"<{type(elem.value).__name__}>"
                    self.logger.debug(f"  {elem.keyword}: {display_value}")
        except Exception as e:
            self.logger.warning(f"Error logging query parameters: {e}")

    def configure_association_contexts(self, event: Any) -> None:
        """
        Configure association contexts for sending data back.
        Sets all accepted contexts as SCU for C-GET/C-MOVE responses.

        Args:
            event: pynetdicom event
        """
        try:
            for cx in event.assoc.accepted_contexts:
                cx._as_scu = True
            self.logger.debug(f"Configured {len(event.assoc.accepted_contexts)} contexts as SCU")
        except Exception as e:
            self.logger.warning(f"Error configuring association contexts: {e}")

    def get_transfer_syntax(self, event: Any) -> str:
        """
        Determine preferred transfer syntax from association.

        Args:
            event: pynetdicom event

        Returns:
            Transfer syntax UID
        """
        try:
            for cx in event.assoc.accepted_contexts:
                if cx.abstract_syntax.startswith('1.2.840.10008.5.1.4'):
                    if cx.transfer_syntax:
                        syntax = cx.transfer_syntax[0]
                        self.logger.debug(f"Using transfer syntax: {syntax}")
                        return syntax
        except Exception as e:
            self.logger.warning(f"Error getting transfer syntax: {e}")

        self.logger.debug(f"Using default transfer syntax: {ImplicitVRLittleEndian}")
        return ImplicitVRLittleEndian

    def log_association_contexts(self, event: Any) -> list:
        """
        Log association contexts and return storage contexts.

        Args:
            event: pynetdicom event

        Returns:
            List of storage context UIDs
        """
        storage_contexts = []

        try:
            self.logger.info(f"Association has {len(event.assoc.accepted_contexts)} accepted contexts:")

            for cx in event.assoc.accepted_contexts:
                self.logger.info(f"  Context {cx.context_id}: {cx.abstract_syntax} (SCU:{cx.as_scu}, SCP:{cx.as_scp})")

                if not cx.abstract_syntax.startswith('1.2.840.10008.5.1.4.1.2.'):
                    storage_contexts.append(cx.abstract_syntax)

            if storage_contexts:
                self.logger.info(f"Found {len(storage_contexts)} storage contexts for C-STORE sub-operations")
            else:
                self.logger.warning("NO STORAGE CONTEXTS found - client may not be able to receive images!")

        except Exception as e:
            self.logger.error(f"Error logging association contexts: {e}", exc_info=True)

        return storage_contexts

    def log_operation_start(self, operation: str, calling_info: dict) -> None:
        """
        Log the start of a DICOM operation.

        Args:
            operation: Operation name (e.g., "C-GET", "C-MOVE")
            calling_info: Dict with calling_ae and requester_ip
        """
        self.logger.info("=" * 60)
        self.logger.info(f"{operation} REQUEST RECEIVED")
        self.logger.info(f"From: {calling_info.get('calling_ae', 'UNKNOWN')}")
        if calling_info.get('requester_ip'):
            self.logger.info(f"IP: {calling_info['requester_ip']}")

    def log_operation_complete(self, operation: str, success: bool, details: str = "") -> None:
        """
        Log the completion of a DICOM operation.

        Args:
            operation: Operation name
            success: Whether operation succeeded
            details: Additional details to log
        """
        status = "COMPLETED" if success else "FAILED"
        self.logger.info(f"{operation} {status}")
        if details:
            self.logger.info(details)
        self.logger.info("=" * 60)

    def get_status_for_results(
        self,
        total: int,
        succeeded: int,
        failed: int
    ) -> int:
        """
        Determine appropriate DICOM status code based on results.

        Args:
            total: Total number of operations
            succeeded: Number of successful operations
            failed: Number of failed operations

        Returns:
            DICOM status code
        """
        if failed == 0:
            return DICOMStatus.SUCCESS
        elif succeeded > failed:
            return DICOMStatus.SUB_OPERATIONS_COMPLETE_WITH_FAILURES
        else:
            return DICOMStatus.OUT_OF_RESOURCES_SUB_OPERATIONS

    @abstractmethod
    def handle(self, event: Any):
        """
        Main handler method to be implemented by subclasses.

        Args:
            event: pynetdicom event

        Yields/Returns:
            Handler-specific results
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement handle()")
