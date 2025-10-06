"""
DICOM SCP (Service Class Provider) Server
Main coordinator for DICOM networking and operations.
"""
import logging
import signal
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, Callable, TYPE_CHECKING
from pynetdicom import AE, evt, StoragePresentationContexts
from pynetdicom.sop_class import (
    Verification,
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelGet,
    CTImageStorage,
    EnhancedCTImageStorage,
    PositronEmissionTomographyImageStorage,
    EnhancedPETImageStorage,
    MRImageStorage,
    EnhancedMRImageStorage,
    EnhancedMRColorImageStorage,
)
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
from django.conf import settings

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi_anonymizer import PHIAnonymizer
    from receiver.controllers.phi_resolver import PHIResolver
    from .study_monitor import StudyMonitor

logger = logging.getLogger('receiver.dicom_scp')


class DicomServiceProvider:
    """
    DICOM Service Class Provider that receives and processes DICOM files.
    Coordinates all DICOM operations through modular handlers.

    Supported Modalities:
    - CT (Computed Tomography)
    - PET (Positron Emission Tomography)
    - MR (Magnetic Resonance)
    """

    SUPPORTED_SOP_CLASSES = [
        CTImageStorage,
        EnhancedCTImageStorage,

        PositronEmissionTomographyImageStorage,
        EnhancedPETImageStorage,

        MRImageStorage,
        EnhancedMRImageStorage,
        EnhancedMRColorImageStorage,
    ]

    SUPPORTED_MODALITIES = ['CT', 'PT', 'MR']

    def __init__(
        self,
        storage_manager: 'StorageManager',
        study_monitor: 'StudyMonitor',
        anonymizer: 'PHIAnonymizer',
        resolver: 'PHIResolver',
        query_handlers: Dict[str, Any],
        port: Optional[int] = None,
        ae_title: Optional[str] = None,
        bind_address: Optional[str] = None
    ) -> None:
        """
        Initialize the DICOM SCP.

        Args:
            storage_manager: StorageManager instance
            study_monitor: StudyMonitor instance
            anonymizer: PHIAnonymizer instance
            resolver: PHIResolver instance
            query_handlers: Dict of query handlers
            port: Port to listen on
            ae_title: AE title for this SCP
            bind_address: IP address to bind to
        """
        self.storage_manager = storage_manager
        self.study_monitor = study_monitor
        self.anonymizer = anonymizer
        self.resolver = resolver
        self.query_handlers = query_handlers

        self.port = port or getattr(settings, 'DICOM_PORT', 11112)
        self.ae_title = (ae_title or getattr(settings, 'DICOM_AE_TITLE', 'DICOMRCV')).encode()
        self.bind_address = bind_address or getattr(settings, 'DICOM_BIND_ADDRESS', '')

        self.is_running: bool = False
        self.server_thread: Optional[threading.Thread] = None
        self.ae: Optional[AE] = None
        self.shutdown_event: threading.Event = threading.Event()

        self._completion_lock: threading.Lock = threading.Lock()
        self._completed_studies: set = set()

        from .handlers import StoreHandler, FindHandler, MoveHandler, GetHandler
        from receiver.services.proxy_config_service import get_config_service
        from receiver.services.api_query_service import get_api_query_service

        config_service = get_config_service()

        api_query_service = get_api_query_service()

        self.store_handler = StoreHandler(storage_manager, anonymizer, config_service)
        self.find_handler = FindHandler(storage_manager, resolver, query_handlers)
        self.move_handler = MoveHandler(storage_manager, resolver, config_service, api_query_service)
        self.get_handler = GetHandler(storage_manager, resolver, api_query_service)

        self.study_monitor.register_study_complete_callback(self._study_complete_handler)

    def _study_complete_handler(self, study_uid: str) -> None:
        """
        Handle study completion: zip and upload to Laminate API.
        Thread-safe to prevent duplicate processing.

        Args:
            study_uid: Study Instance UID
        """
        with self._completion_lock:
            if study_uid in self._completed_studies:
                logger.warning(f"Study {study_uid} already being processed, skipping duplicate")
                return
            self._completed_studies.add(study_uid)

        try:
            logger.info(f" Study completed: {study_uid}")

            self.storage_manager.mark_study_complete(study_uid)

            stats = self.storage_manager.get_study_statistics(study_uid)
            if stats:
                logger.info(f"Series: {stats['series_count']}, Instances: {stats['instances_count']}")

            study = self.storage_manager.get_study(study_uid)
            if not study:
                logger.error(f"Study not found in database: {study_uid}")
                return

            from receiver.services.proxy_config_service import get_config_service
            config_service = get_config_service()

            if not config_service or not config_service.is_auto_dispatch_enabled():
                logger.info(f"Auto-dispatch disabled, skipping upload for study: {study_uid}")
                return

            self._archive_and_upload_study(study_uid, study, stats)

        finally:
            with self._completion_lock:
                self._completed_studies.discard(study_uid)

    def _archive_and_upload_study(self, study_uid: str, study, stats) -> None:
        """
        Create ZIP archive and upload study to Laminate API.

        Args:
            study_uid: Study Instance UID
            study: Study/Session database object
            stats: Study statistics dictionary
        """
        try:
            from pathlib import Path
            from receiver.utils.study_archiver import StudyArchiver
            from receiver.services.study_uploader import get_study_uploader
            from django.conf import settings

            archive_dir = getattr(settings, 'ARCHIVE_DIR', 'archives')
            archiver = StudyArchiver(archive_dir)

            study_path = Path(study.storage_path)
            if not study_path.exists():
                logger.error(f"Study path does not exist: {study_path}")
                return

            archive_name = f"{study.patient_id}_{study_uid}"

            logger.info(f"Creating archive for study: {study_uid}")
            zip_path = archiver.create_study_archive(study_path, archive_name)

            if not zip_path:
                logger.error(f"Failed to create archive for study: {study_uid}")
                return

            uploader = get_study_uploader()
            if not uploader:
                logger.error("Study uploader not available")
                archiver.cleanup_archive(zip_path)
                return

            study_info = {
                'name': study.patient_name or 'UNKNOWN',
                'patient_id': study.patient_id or 'UNKNOWN',
                'description': study.study_description or '',
                'metadata': {
                    'study_uid': study_uid,
                    'study_date': str(study.study_date) if study.study_date else None,
                    'series_count': stats.get('series_count', 0) if stats else 0,
                    'instances_count': stats.get('instances_count', 0) if stats else 0,
                }
            }

            logger.info(f"Uploading study to Laminate API: {study_uid}")
            success, response_data = uploader.upload_study(zip_path, study_info)

            if success:
                logger.info(f" Study uploaded successfully: {study_uid}")

                if uploader.cleanup_after_upload:
                    logger.info(f"Cleaning up files for study: {study_uid}")
                    archiver.cleanup_archive(zip_path)
                    archiver.cleanup_study_directory(study_path)
                    logger.info(f" Cleanup completed for study: {study_uid}")
                else:
                    archiver.cleanup_archive(zip_path)
            else:
                logger.error(f" Failed to upload study: {study_uid}")
                logger.info(f"Archive kept for manual retry: {zip_path}")

        except Exception as e:
            logger.error(f"Error archiving/uploading study {study_uid}: {e}", exc_info=True)

    def _handle_store_with_monitor(self, event: Any) -> int:
        """
        Handle C-STORE with study monitoring.

        Args:
            event: pynetdicom event

        Returns:
            int: DICOM status code
        """
        status = self.store_handler.handle_store(event)

        if status == 0x0000:
            dataset = event.dataset
            study_uid = dataset.StudyInstanceUID
            self.study_monitor.update_study_activity(study_uid)

        return status

    def _server_process(self) -> None:
        """Run the DICOM server in a separate thread."""
        try:
            self.ae = AE(ae_title=self.ae_title)

            for sop_class in self.SUPPORTED_SOP_CLASSES:
                self.ae.add_supported_context(
                    sop_class,
                    transfer_syntax=[ImplicitVRLittleEndian, ExplicitVRLittleEndian]
                )

            self.ae.add_supported_context(StudyRootQueryRetrieveInformationModelFind)
            self.ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)

            self.ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
            self.ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)

            self.ae.add_supported_context(StudyRootQueryRetrieveInformationModelGet)
            self.ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)

            self.ae.add_supported_context(Verification)

            handlers = [
                (evt.EVT_C_STORE, self._handle_store_with_monitor),
                (evt.EVT_C_FIND, self.find_handler.handle_find),
                (evt.EVT_C_MOVE, self.move_handler.handle_move),
                (evt.EVT_C_GET, self.get_handler.handle_get),
            ]

            bind_addr = self.bind_address or '0.0.0.0'
            self.ae.start_server(
                (bind_addr, self.port),
                block=False,
                evt_handlers=handlers
            )

            logger.info("=" * 60)
            logger.info(f" DICOM server running on {bind_addr}:{self.port}")
            logger.info(f" AE Title: {self.ae_title.decode()}")
            logger.info(f" C-STORE: Enabled (receive DICOM images)")
            logger.info(f" C-FIND: Enabled (query studies)")
            logger.info(f" C-MOVE: Enabled (send to PACS nodes, requires NAT/port forwarding)")
            logger.info(f" C-GET: Enabled (retrieve on same connection, firewall-friendly)")
            logger.info(f" C-ECHO: Enabled (verification)")
            logger.info(f" Supported Modalities: {', '.join(self.SUPPORTED_MODALITIES)}")
            logger.info(f" SOP Classes: {len(self.SUPPORTED_SOP_CLASSES)}")
            logger.info(f"Study timeout: {self.study_monitor.timeout}s")
            logger.info("=" * 60)

            from receiver.services.access_control_service import get_access_control_service
            access_control = get_access_control_service()
            if access_control:
                access_control.log_access_status()

            while not self.shutdown_event.is_set():
                time.sleep(0.1)

        except Exception as e:
            logger.error(f" Error in DICOM server process: {e}", exc_info=True)
        finally:
            if self.ae:
                self.ae.shutdown()
                logger.info("DICOM server has been shut down")

    def start(self) -> None:
        """Start the DICOM receiver service in non-blocking mode."""
        if self.is_running:
            logger.warning("DICOM server is already running")
            return

        logger.info(f"Starting DICOM receiver on port {self.port}")

        self.is_running = True
        self.shutdown_event.clear()

        self.server_thread = threading.Thread(target=self._server_process, daemon=True)
        self.server_thread.start()

    def stop(self) -> None:
        """Stop the DICOM receiver service."""
        if not self.is_running:
            logger.warning("DICOM server is not running")
            return

        logger.info("Stopping DICOM receiver...")
        self.shutdown_event.set()

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(5.0)

        self.is_running = False
        logger.info("DICOM receiver stopped")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle termination signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, stopping DICOM receiver")
        self.stop()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get server statistics.

        Returns:
            dict: Server statistics
        """
        return {
            'ae_title': self.ae_title.decode(),
            'port': self.port,
            'is_running': self.is_running,
            'active_studies': self.study_monitor.get_study_count(),
        }
