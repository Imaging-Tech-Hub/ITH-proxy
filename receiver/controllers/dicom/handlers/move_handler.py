"""
C-MOVE Handler for DICOM operations.
Handles C-MOVE requests to send DICOM studies to configured PACS nodes.
"""
import logging
from pathlib import Path
from io import BytesIO
from typing import Any, List, Optional, TYPE_CHECKING
from pydicom import dcmread

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi_resolver import PHIResolver
    from receiver.services.proxy_config_service import ProxyConfigService
    from receiver.services.api_query_service import APIQueryService

logger = logging.getLogger('receiver.handlers.move')


class MoveHandler:
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
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.config_service = config_service
        self.api_query_service = api_query_service

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
            from receiver.services.access_control_service import extract_calling_ae_title, get_access_control_service
            calling_ae = extract_calling_ae_title(event)

            access_control = get_access_control_service()

            if access_control:
                allowed, reason = access_control.can_accept_retrieve(calling_ae, "C-MOVE")
                if not allowed:
                    logger.warning(f"C-MOVE REJECTED from {calling_ae}: {reason}")
                    yield 0xC001
                    return
                logger.debug(f"C-MOVE access granted to {calling_ae}: {reason}")

            request = event.request

            if hasattr(request.MoveDestination, 'decode'):
                move_destination = request.MoveDestination.decode('utf-8').strip()
            else:
                move_destination = str(request.MoveDestination).strip()

            if access_control:
                allowed, reason = access_control.can_send_to_node(move_destination)
                if not allowed:
                    logger.warning(f"C-MOVE to {move_destination} REJECTED: {reason}")
                    yield 0xA801
                    return
                logger.debug(f"C-MOVE to {move_destination} allowed: {reason}")

            logger.info("=" * 60)
            logger.info(" C-MOVE REQUEST RECEIVED")
            logger.info(f" From: {calling_ae}")
            logger.info(f" Move Destination AE: {move_destination}")

            identifier = request.Identifier
            query_level = getattr(identifier, 'QueryRetrieveLevel', 'STUDY')
            logger.info(f" Query Level: {query_level}")

            self._log_query_parameters(identifier)

            study_uid = self._extract_study_uid(identifier)
            if not study_uid and query_level == 'STUDY':
                logger.error(" No StudyInstanceUID provided for STUDY level C-MOVE")
                yield 0xA900 
                return

            destination_ip, destination_port = self._get_destination_address(move_destination)
            if not destination_ip:
                logger.error(f" No configuration found for destination AE: {move_destination}")
                yield 0xA801
                return

            logger.info(f" Destination: {destination_ip}:{destination_port}")

            datasets = self._find_datasets(identifier, query_level, study_uid)

            if not datasets:
                logger.warning(" No matching files found for C-MOVE request")
                yield 0xA701 
                return

            total_datasets = len(datasets)
            logger.info(f" Found {total_datasets} datasets to move")
            logger.info(f" Initiating C-MOVE to {move_destination}")

            yield (destination_ip, destination_port)

            yield total_datasets

            sent_count = 0
            for dataset in datasets:
                try:
                    dataset = self.resolver.resolve_dataset(dataset)

                    sent_count += 1
                    logger.info(f" Sending dataset {sent_count}/{total_datasets}")
                    logger.info(f"Patient: {getattr(dataset, 'PatientName', 'Unknown')}")
                    logger.info(f"Study: {getattr(dataset, 'StudyInstanceUID', 'Unknown')}")

                    yield 0xFF00, dataset

                except Exception as e:
                    logger.error(f" Error processing dataset: {e}", exc_info=True)
                    yield 0xB000 

            logger.info(f" C-MOVE completed: {sent_count}/{total_datasets} datasets sent")
            logger.info("=" * 60)
            yield 0x0000 

        except Exception as e:
            logger.error(f" Error in C-MOVE handler: {e}", exc_info=True)
            yield 0xA701 

    def _log_query_parameters(self, identifier: Any) -> None:
        """Log query parameters from identifier."""
        logger.info(" Query Parameters:")
        for elem in identifier:
            if elem.value is not None:
                if isinstance(elem.value, (str, int, float)):
                    value_str = str(elem.value)
                    display_value = value_str[:100] + "..." if len(value_str) > 100 else value_str
                else:
                    display_value = f"<{type(elem.value).__name__}>"
                logger.info(f"{elem.keyword}: {display_value}")

    def _extract_study_uid(self, identifier: Any) -> Optional[str]:
        """Extract StudyInstanceUID from identifier."""
        for elem in identifier:
            if elem.keyword == 'StudyInstanceUID' and elem.value:
                return str(elem.value).strip()
        return None

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
                        logger.warning(f"Node {node.name} ({ae_title}) is inactive")
                        continue

                    if not node.is_reachable:
                        logger.warning(f"Node {node.name} ({ae_title}) is not reachable")
                        continue

                    logger.info(f" Found node: {node.name} ({ae_title})")
                    logger.info(f"Address: {node.host}:{node.port}")
                    logger.info(f"Permission: {node.permission}")
                    return (node.host, node.port)

            logger.warning(f" No active/reachable node found for AE title: {ae_title}")
            return (None, None)

        except Exception as e:
            logger.error(f"Error getting destination address: {e}", exc_info=True)
            return (None, None)

    def _find_datasets(
        self,
        identifier: Any,
        query_level: str,
        study_uid: Optional[str]
    ) -> List[Any]:
        """
        Find datasets matching the query.
        Always downloads from API to get the latest/processed version.
        Local files are cleaned up after upload, and API has the authoritative data.

        Args:
            identifier: Query identifier
            query_level: Query level (STUDY, SERIES, IMAGE)
            study_uid: Study Instance UID

        Returns:
            List of DICOM datasets
        """
        datasets = []

        if self.api_query_service:
            logger.info(" Downloading from Laminate API (latest version)...")
            api_datasets = self._download_from_api(query_level, study_uid, identifier)

            if api_datasets:
                logger.info(f" Downloaded {len(api_datasets)} datasets from API")
                return api_datasets
            else:
                logger.warning(f"No data found in API")
        else:
            logger.error(" No API access configured - cannot perform C-MOVE")

        return datasets

    def _download_from_api(
        self,
        query_level: str,
        study_uid: Optional[str],
        identifier: Any
    ) -> List[Any]:
        """
        Download datasets from Laminate API.

        Args:
            query_level: Query level
            study_uid: Study Instance UID
            identifier: Query identifier

        Returns:
            List of DICOM datasets
        """
        datasets = []

        try:
 
            if query_level == 'STUDY' and study_uid:
                from receiver.containers import container
                api_client = container.laminate_api_client()

                sessions_response = api_client.list_sessions()
                sessions = sessions_response.get('sessions', [])

                for session in sessions:
                    metadata = session.get('metadata', {})
                    if metadata.get('study_instance_uid') == study_uid:
                        session_id = session.get('id')
                        subject_id = session.get('subject_id')

                        if session_id and subject_id:
                            import tempfile
                            with tempfile.TemporaryDirectory() as temp_dir:
                                temp_path = Path(temp_dir) / f"{session_id}.zip"

                                logger.info(f" Downloading session {session_id} from API...")
                                api_client.download_session(
                                    session_id=session_id,
                                    subject_id=subject_id,
                                    output_path=temp_path
                                )

                                import zipfile
                                extract_dir = Path(temp_dir) / "extracted"
                                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                                    zip_ref.extractall(extract_dir)

                                for dcm_file in extract_dir.rglob('*.dcm'):
                                    try:
                                        ds = dcmread(str(dcm_file))
                                        datasets.append(ds)
                                    except Exception as e:
                                        logger.warning(f"Error reading {dcm_file}: {e}")

                        break

        except Exception as e:
            logger.error(f"Error downloading from API: {e}", exc_info=True)

        return datasets
