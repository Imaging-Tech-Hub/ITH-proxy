"""
C-MOVE Handler for DICOM operations.
Handles C-MOVE requests to send DICOM studies to configured PACS nodes.
"""
from typing import Any, Optional, TYPE_CHECKING

from receiver.controllers.base import HandlerBase, DICOMStatus
from receiver.controllers.dicom.services import DICOMDownloadService, DICOMDatasetService

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi import PHIResolver
    from receiver.services.config import ProxyConfigService
    from receiver.services.query import APIQueryService


class MoveHandler(HandlerBase):
    """
    Handler for DICOM C-MOVE operations.
    Sends DICOM files to destination AE (configured PACS nodes).
    """

    def __init__(
        self,
        storage_manager: 'StorageManager',
        resolver: 'PHIResolver',
        config_service: 'ProxyConfigService',
        api_query_service: Optional['APIQueryService'] = None
    ):
        """
        Initialize C-MOVE handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver for de-anonymization
            config_service: ProxyConfigService for node configuration
            api_query_service: APIQueryService for downloading from API
        """
        super().__init__('move')
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.config_service = config_service
        self.api_query_service = api_query_service
        self.dataset_service = DICOMDatasetService()
        self.download_service: Optional[DICOMDownloadService] = None

    def handle_move(self, event: Any):
        """
        Handle C-MOVE request.

        For C-MOVE, pynetdicom expects us to:
        1. Return the destination address (IP, port)
        2. Yield the number of sub-operations
        3. Yield datasets to be moved
        4. pynetdicom handles the actual C-STORE operations

        Args:
            event: pynetdicom C-MOVE event

        Yields:
            Destination address, dataset count, datasets, or status codes
        """
        try:
            calling_info = self.extract_calling_info(event)

            allowed, reason = self.check_access(event, "C-MOVE")
            if not allowed:
                yield DICOMStatus.ACCESS_DENIED
                return

            request = event.request
            move_destination = self._get_move_destination(request)

            allowed, reason = self._check_destination_access(move_destination)
            if not allowed:
                self.logger.warning(f"C-MOVE to {move_destination} REJECTED: {reason}")
                yield DICOMStatus.MOVE_DESTINATION_UNKNOWN
                return

            self.log_operation_start("C-MOVE", calling_info)
            self.logger.info(f"Move Destination AE: {move_destination}")

            identifier = self.decode_identifier(request.Identifier)
            query_level = self.get_query_level(identifier)
            study_uid = self.extract_uid(identifier, 'StudyInstanceUID')

            if not study_uid and query_level == 'STUDY':
                self.logger.error("No StudyInstanceUID provided for STUDY level C-MOVE")
                yield DICOMStatus.IDENTIFIER_DOES_NOT_MATCH_SOP_CLASS
                return

            self.log_query_parameters(identifier)

            destination_ip, destination_port = self._get_destination_address(move_destination)
            if not destination_ip:
                self.logger.error(f"No configuration found for destination AE: {move_destination}")
                yield DICOMStatus.MOVE_DESTINATION_UNKNOWN
                return

            self.logger.info(f"Destination: {destination_ip}:{destination_port}")

            datasets = self._find_datasets(identifier, query_level, study_uid)

            if not datasets:
                self.logger.warning("No matching files found for C-MOVE request")
                yield DICOMStatus.OUT_OF_RESOURCES_SUB_OPERATIONS
                return

            total_datasets = len(datasets)
            self.logger.info(f"Found {total_datasets} datasets to move")
            self.logger.info(f"Initiating C-MOVE to {move_destination}")

            yield (destination_ip, destination_port)

            yield total_datasets

            sent_count, failed_count = self._send_datasets(event, datasets, total_datasets)

            final_status = self.get_status_for_results(total_datasets, sent_count, failed_count)
            self.logger.info(f"C-MOVE completed: {sent_count}/{total_datasets} sent, {failed_count} failed")
            yield final_status

            self.log_operation_complete("C-MOVE", failed_count == 0,
                                       f"{sent_count}/{total_datasets} datasets sent")

        except Exception as e:
            self.logger.error(f"Error in C-MOVE handler: {e}", exc_info=True)
            yield DICOMStatus.OUT_OF_RESOURCES_SUB_OPERATIONS

    def _get_move_destination(self, request: Any) -> str:
        """
        Extract move destination AE title from request.

        Args:
            request: C-MOVE request

        Returns:
            Move destination AE title
        """
        if hasattr(request.MoveDestination, 'decode'):
            return request.MoveDestination.decode('utf-8').strip()
        else:
            return str(request.MoveDestination).strip()

    def _check_destination_access(self, ae_title: str) -> tuple:
        """
        Check if C-MOVE to destination is allowed.

        Args:
            ae_title: Destination AE title

        Returns:
            Tuple of (allowed, reason)
        """
        try:
            from receiver.services.config import get_access_control_service

            access_control = get_access_control_service()
            if not access_control:
                return True, "No access control configured"

            allowed, reason = access_control.can_send_to_node(ae_title)
            if allowed:
                self.logger.debug(f"C-MOVE to {ae_title} allowed: {reason}")
            return allowed, reason

        except Exception as e:
            self.logger.error(f"Error checking destination access: {e}", exc_info=True)
            return False, f"Access control error: {str(e)}"

    def _get_destination_address(self, ae_title: str) -> tuple:
        """
        Get destination address for AE title from configured nodes.
        Only returns active and reachable nodes.

        Args:
            ae_title: Destination AE title

        Returns:
            Tuple of (ip, port) or (None, None)
        """
        try:
            nodes = self.config_service.get_all_nodes()

            for node in nodes:
                if node.ae_title.upper().strip() == ae_title.upper().strip():
                    if not node.is_active:
                        self.logger.warning(f"Node {node.name} ({ae_title}) is inactive")
                        continue

                    if not node.is_reachable:
                        self.logger.warning(f"Node {node.name} ({ae_title}) is not reachable")
                        continue

                    self.logger.info(f"Found node: {node.name} ({ae_title})")
                    self.logger.info(f"Address: {node.host}:{node.port}")
                    self.logger.info(f"Permission: {node.permission}")
                    return (node.host, node.port)

            self.logger.warning(f"No active/reachable node found for AE title: {ae_title}")
            return (None, None)

        except Exception as e:
            self.logger.error(f"Error getting destination address: {e}", exc_info=True)
            return (None, None)

    def _find_datasets(
        self,
        identifier: Any,
        query_level: str,
        study_uid: Optional[str]
    ) -> list:
        """
        Find datasets matching the query.
        Always downloads from API to get the latest/processed version.

        Args:
            identifier: Query identifier
            query_level: Query level (STUDY, SERIES, IMAGE)
            study_uid: Study Instance UID

        Returns:
            List of DICOM datasets
        """
        if not self.api_query_service:
            self.logger.error("No API access configured - cannot perform C-MOVE")
            return []

        if not self.download_service:
            from receiver.containers import container
            from receiver.services.coordination import get_dispatch_lock_manager

            api_client = container.ith_api_client()
            lock_manager = get_dispatch_lock_manager()

            self.download_service = DICOMDownloadService(
                api_client=api_client,
                resolver=self.resolver,
                lock_manager=lock_manager
            )

        self.logger.info("Downloading from ITH API (latest version)...")


        def no_op_prepare(ds, ts):
            pass

        if query_level == 'STUDY' and study_uid:
            datasets = self.download_service.download_study(
                study_uid=study_uid,
                transfer_syntax='',
                prepare_dataset_func=no_op_prepare
            )
        elif query_level == 'SERIES':
            series_uid = self.extract_uid(identifier, 'SeriesInstanceUID')
            if study_uid and series_uid:
                datasets = self.download_service.download_series(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    transfer_syntax='',
                    prepare_dataset_func=no_op_prepare
                )
            else:
                self.logger.error("Missing UIDs for SERIES level query")
                datasets = []
        elif query_level == 'IMAGE':
            series_uid = self.extract_uid(identifier, 'SeriesInstanceUID')
            sop_uid = self.extract_uid(identifier, 'SOPInstanceUID')
            if study_uid and series_uid and sop_uid:
                datasets = self.download_service.download_image(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    sop_uid=sop_uid,
                    transfer_syntax='',
                    prepare_dataset_func=no_op_prepare
                )
            else:
                self.logger.error("Missing UIDs for IMAGE level query")
                datasets = []
        else:
            self.logger.warning(f"Unsupported query level: {query_level}")
            datasets = []

        if datasets:
            self.logger.info(f"Downloaded {len(datasets)} datasets from API")
        else:
            self.logger.warning("No data found in API")

        return datasets

    def _send_datasets(self, event: Any, datasets: list, total_datasets: int) -> tuple:
        """
        Send datasets with PHI resolved.

        Args:
            event: pynetdicom event
            datasets: List of datasets to send
            total_datasets: Total number of datasets

        Returns:
            Tuple of (sent_count, failed_count)
        """
        sent_count = 0
        failed_count = 0

        for dataset in datasets:
            if event.is_cancelled:
                self.logger.warning(f"C-MOVE cancelled by client after {sent_count} datasets")
                yield DICOMStatus.CANCEL
                return sent_count, failed_count

            try:
                dataset = self.resolver.resolve_dataset(dataset)

                sent_count += 1
                self.logger.info(f"Sending dataset {sent_count}/{total_datasets}")
                self.logger.debug(f"Patient: {getattr(dataset, 'PatientName', 'Unknown')}")
                self.logger.debug(f"Study: {getattr(dataset, 'StudyInstanceUID', 'Unknown')}")

                yield DICOMStatus.PENDING, dataset

            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error processing dataset: {e}", exc_info=True)
                yield DICOMStatus.SUB_OPERATIONS_COMPLETE_WITH_FAILURES

        return sent_count, failed_count

    def handle(self, event: Any):
        """Main handler method (delegates to handle_move for C-MOVE operations)."""
        return self.handle_move(event)
