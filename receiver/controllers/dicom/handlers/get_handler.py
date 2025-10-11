"""
C-GET Handler for DICOM operations.
Handles C-GET requests to retrieve DICOM studies via same connection (no NAT issues).
"""
from typing import Any, Optional, TYPE_CHECKING

from receiver.controllers.base import HandlerBase, DICOMStatus
from receiver.controllers.dicom.services import DICOMDownloadService, DICOMDatasetService

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi import PHIResolver
    from receiver.services.query import APIQueryService


class GetHandler(HandlerBase):
    """
    Handler for DICOM C-GET operations.
    Retrieves DICOM files and sends them back on the same connection.

    Advantages over C-MOVE:
    - No NAT/firewall issues (uses same connection)
    - No port forwarding required
    - Simpler network setup
    """

    def __init__(
        self,
        storage_manager: 'StorageManager',
        resolver: 'PHIResolver',
        api_query_service: Optional['APIQueryService'] = None
    ):
        """
        Initialize C-GET handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver for de-anonymization
            api_query_service: APIQueryService for downloading from API
        """
        super().__init__('get')
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.api_query_service = api_query_service
        self.dataset_service = DICOMDatasetService()
        self.download_service: Optional[DICOMDownloadService] = None

    def handle_get(self, event: Any):
        """
        Handle C-GET request.

        For C-GET, pynetdicom expects us to:
        1. Yield the number of sub-operations
        2. Yield datasets with status codes
        3. Return on the same connection (no new association)

        Args:
            event: pynetdicom C-GET event

        Yields:
            Dataset count, datasets with status codes
        """
        try:
            calling_info = self.extract_calling_info(event)
            self.log_operation_start("C-GET", calling_info)

            allowed, reason = self.check_access(event, "C-GET")
            if not allowed:
                yield DICOMStatus.ACCESS_DENIED
                return

            request = event.request
            identifier = self.decode_identifier(request.Identifier)
            query_level = self.get_query_level(identifier)
            study_uid = self.extract_uid(identifier, 'StudyInstanceUID')

            if not study_uid and query_level == 'STUDY':
                self.logger.error("No StudyInstanceUID provided for STUDY level C-GET")
                yield DICOMStatus.IDENTIFIER_DOES_NOT_MATCH_SOP_CLASS
                return

            self.log_query_parameters(identifier)

            for cx in event.assoc.accepted_contexts:
                cx._as_scu = True
            self.logger.debug(f"Configured {len(event.assoc.accepted_contexts)} contexts as SCU")

            storage_contexts = self.log_association_contexts(event)
            transfer_syntax = self.get_transfer_syntax(event)

            datasets = self._find_datasets(identifier, query_level, study_uid, transfer_syntax)

            if not datasets:
                self.logger.warning("No matching files found for C-GET request")
                yield DICOMStatus.OUT_OF_RESOURCES_SUB_OPERATIONS
                return

            total_datasets = len(datasets)
            self.logger.info(f"Found {total_datasets} datasets to retrieve")

            yield total_datasets

            sent_count = 0
            failed_count = 0

            for result in self._send_datasets(event, datasets, total_datasets, storage_contexts):
                if isinstance(result, tuple) and len(result) == 2:
                    status, dataset = result
                    sent_count += 1
                    yield result
                elif isinstance(result, int):
                    yield result
                    return
                else:
                    self.logger.warning(f"Unexpected result type from _send_datasets: {type(result)}")
                    yield result

            failed_count = total_datasets - sent_count

            if failed_count == 0:
                self.logger.info(f" C-GET completed successfully: {sent_count}/{total_datasets} datasets sent")
            elif sent_count > 0:
                self.logger.warning(f" C-GET completed with warnings: {sent_count}/{total_datasets} datasets sent, {failed_count} failed")
            else:
                self.logger.error(f" C-GET failed: no datasets could be sent")

            self.logger.info("C-GET generator completed")

        except Exception as e:
            self.logger.error(f"Error in C-GET handler: {e}", exc_info=True)
            yield DICOMStatus.OUT_OF_RESOURCES_SUB_OPERATIONS

    def _find_datasets(
        self,
        identifier: Any,
        query_level: str,
        study_uid: Optional[str],
        transfer_syntax: str
    ) -> list:
        """
        Find datasets matching the query.
        Always downloads from API to get the latest/processed version.

        Args:
            identifier: Query identifier
            query_level: Query level (STUDY, SERIES, IMAGE)
            study_uid: Study Instance UID
            transfer_syntax: Preferred transfer syntax

        Returns:
            List of DICOM datasets
        """
        if not self.api_query_service:
            self.logger.error("No API access configured - cannot perform C-GET")
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

        self.logger.info("Downloading from ITH API...")

        if query_level == 'STUDY' and study_uid:
            datasets = self.download_service.download_study(
                study_uid=study_uid,
                transfer_syntax=transfer_syntax,
                prepare_dataset_func=self.dataset_service.prepare_dataset
            )
        elif query_level == 'SERIES':
            series_uid = self.extract_uid(identifier, 'SeriesInstanceUID')
            if study_uid and series_uid:
                datasets = self.download_service.download_series(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    transfer_syntax=transfer_syntax,
                    prepare_dataset_func=self.dataset_service.prepare_dataset
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
                    transfer_syntax=transfer_syntax,
                    prepare_dataset_func=self.dataset_service.prepare_dataset
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

    def _send_datasets(
        self,
        event: Any,
        datasets: list,
        total_datasets: int,
        storage_contexts: list
    ):
        """
        Send datasets to the requesting client.

        Args:
            event: pynetdicom event
            datasets: List of datasets to send
            total_datasets: Total number of datasets
            storage_contexts: List of storage context UIDs

        Yields:
            Tuples of (status, dataset) or status codes
        """
        for idx, dataset in enumerate(datasets, 1):
            if event.is_cancelled:
                self.logger.warning(f"C-GET cancelled by client after {idx-1} datasets")
                yield DICOMStatus.CANCEL
                return

            try:
                if idx == 1:
                    self._log_first_instance(dataset, event, storage_contexts)

                if idx % 10 == 0 or idx == total_datasets:
                    progress = int(100 * idx / total_datasets)
                    self.logger.info(f"Progress: {idx}/{total_datasets} datasets sent ({progress}%)")
                else:
                    self.logger.debug(f"Sending dataset {idx}/{total_datasets}")

                self.logger.debug(f"Patient: {getattr(dataset, 'PatientName', 'Unknown')}")
                self.logger.debug(f"Study: {getattr(dataset, 'StudyInstanceUID', 'Unknown')}")
                self.logger.debug(f"SOP Class: {getattr(dataset, 'SOPClassUID', 'Unknown')}")

                yield DICOMStatus.PENDING, dataset

            except Exception as e:
                self.logger.error(f"Error processing dataset {idx}: {e}", exc_info=True)

    def _log_first_instance(self, dataset: Any, event: Any, storage_contexts: list) -> None:
        """
        Log details about the first instance for verification.

        Args:
            dataset: First DICOM dataset
            event: pynetdicom event
            storage_contexts: List of storage context UIDs
        """
        sop_class = getattr(dataset, 'SOPClassUID', 'Unknown')
        self.logger.info(f"First instance SOP Class: {sop_class}")

        has_matching_context = False
        for cx in event.assoc.accepted_contexts:
            if cx.abstract_syntax == sop_class:
                has_matching_context = True
                self.logger.info(f"Found matching context for SOP Class {sop_class}")
                break

        if not has_matching_context:
            self.logger.error(f"NO MATCHING CONTEXT for SOP Class {sop_class}!")
            self.logger.error(f"Available storage contexts: {storage_contexts}")

    def handle(self, event: Any):
        """Main handler method (delegates to handle_get for C-GET operations)."""
        return self.handle_get(event)
