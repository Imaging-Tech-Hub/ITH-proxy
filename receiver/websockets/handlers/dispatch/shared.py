"""
Shared utilities for dispatch handlers.

Common functionality used by subject/session/scan dispatch handlers:
- Node matching
- API client creation
- Archive extraction
- Status reporting
- PHI resolution
"""
from typing import List
from pathlib import Path
from receiver.services.api import IthAPIClient
from receiver.utils.config import NodeConfig


async def get_matching_nodes(requested_node_ids: List[str]) -> List[NodeConfig]:
    """
    Get nodes managed by this proxy that match requested nodes.

    Args:
        requested_node_ids: List of node IDs requested by backend

    Returns:
        List of matching NodeConfig objects
    """
    from receiver.services.config import get_config_service
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _load():
        config_service = get_config_service()
        if config_service:
            return config_service.get_active_nodes()
        return []

    managed_nodes = await _load()
    managed_node_ids = {node.node_id for node in managed_nodes}
    requested_node_ids_set = set(requested_node_ids)

    matching_ids = managed_node_ids & requested_node_ids_set

    return [node for node in managed_nodes if node.node_id in matching_ids]


def get_api_client(proxy_key: str, workspace_id: str) -> IthAPIClient:
    """
    Get configured API client.

    Args:
        proxy_key: Proxy authentication key
        workspace_id: Workspace ID

    Returns:
        Configured IthAPIClient instance
    """
    from django.conf import settings

    return IthAPIClient(
        base_url=settings.ITH_URL,
        proxy_key=proxy_key,
        workspace_id=workspace_id
    )


async def extract_archive(archive_path: Path, extract_path: Path):
    """
    Extract downloaded archive.

    Args:
        archive_path: Path to ZIP archive
        extract_path: Directory to extract to
    """
    import zipfile
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _extract():
        extract_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

    await _extract()


async def download_with_progress(
    download_func,
    progress_callback,
    logger,
    entity_type: str,
    entity_id: str
):
    """
    Execute download with progress reporting to keep WebSocket alive.

    This wrapper calls download_func with a progress callback that:
    1. Tracks bytes downloaded
    2. Reports progress periodically to avoid blocking
    3. Keeps WebSocket connection alive

    Args:
        download_func: Function that accepts progress_callback parameter
        progress_callback: Async function to call with progress updates
        logger: Logger instance
        entity_type: "scan", "session", or "subject" for logging
        entity_id: Entity identifier for logging

    Returns:
        Result from download_func
    """
    from asgiref.sync import sync_to_async
    import asyncio
    import time

    last_report_time = time.time()
    last_bytes = 0
    report_interval = 5.0
    
    def sync_progress_callback(bytes_downloaded, total_bytes):
        """Synchronous callback called by requests library."""
        nonlocal last_report_time, last_bytes
        current_time = time.time()

        if (current_time - last_report_time >= report_interval or
            bytes_downloaded - last_bytes >= 5_000_000 or
            bytes_downloaded == total_bytes):

            if total_bytes > 0:
                progress = int((bytes_downloaded / total_bytes) * 100)
            else:
                progress = 0

            mb_downloaded = bytes_downloaded / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024) if total_bytes > 0 else 0

            logger.info(
                f"Download progress for {entity_type} {entity_id}: "
                f"{progress}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)"
            )

            sync_progress_callback.last_progress = progress
            sync_progress_callback.last_bytes = bytes_downloaded
            sync_progress_callback.last_total = total_bytes

            last_report_time = current_time
            last_bytes = bytes_downloaded

    sync_progress_callback.last_progress = 0
    sync_progress_callback.last_bytes = 0
    sync_progress_callback.last_total = 0

    async def send_progress_updates():
        """Background task to send WebSocket updates."""
        while not send_progress_updates.done:
            await asyncio.sleep(5)

            if hasattr(sync_progress_callback, 'last_progress'):
                await progress_callback(sync_progress_callback.last_progress)

    send_progress_updates.done = False

    progress_task = asyncio.create_task(send_progress_updates())

    try:
        result = await sync_to_async(
            download_func,
            thread_sensitive=False
        )(progress_callback=sync_progress_callback)

        await progress_callback(100)

        return result

    finally:
        send_progress_updates.done = True
        await asyncio.sleep(0.1)
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass


async def resolve_phi_in_directory(dicom_dir: Path, logger, subject_id: str = None, progress_callback=None) -> int:
    """
    Resolve PHI in all DICOM files in a directory.
    Uses local database for PHI resolution.
    Processes files in batches to avoid blocking event loop for too long.

    Args:
        dicom_dir: Directory containing DICOM files
        logger: Logger instance for logging
        subject_id: Optional subject ID for logging
        progress_callback: Optional async function to call with progress updates

    Returns:
        Number of files with PHI resolved
    """
    from asgiref.sync import sync_to_async
    from pydicom import dcmread
    import asyncio

    def _resolve_batch(files_batch):
        """Resolve PHI for a batch of files."""
        from receiver.containers import container

        resolver = container.phi_resolver()
        resolved_count = 0
        first_patient_info = None

        for dcm_file in files_batch:
            try:
                ds = dcmread(str(dcm_file))
                ds = resolver.resolve_dataset(ds)
                ds.save_as(str(dcm_file))
                resolved_count += 1

                if resolved_count == 1:
                    patient_name = getattr(ds, 'PatientName', 'Unknown')
                    patient_id = getattr(ds, 'PatientID', 'Unknown')
                    first_patient_info = (patient_name, patient_id)

            except Exception as e:
                logger.warning(f"Failed to resolve PHI for {dcm_file.name}: {e}")

        return resolved_count, first_patient_info

    # Get all DICOM files
    dcm_files = list(dicom_dir.rglob('*.dcm'))

    if not dcm_files:
        logger.warning(f"No DICOM files found in {dicom_dir}")
        return 0

    total_files = len(dcm_files)
    logger.info(f"Resolving PHI for {total_files} DICOM files...")

    batch_size = 50
    total_resolved = 0
    first_patient_logged = False

    for i in range(0, total_files, batch_size):
        batch = dcm_files[i:i + batch_size]

        resolved_count, patient_info = await sync_to_async(
            _resolve_batch, thread_sensitive=False
        )(batch)

        total_resolved += resolved_count

        if patient_info and not first_patient_logged:
            logger.info(f"Resolved to: {patient_info[0]} ({patient_info[1]})")
            first_patient_logged = True

        progress = int((i + len(batch)) / total_files * 100)
        logger.debug(f"PHI resolution progress: {i + len(batch)}/{total_files} ({progress}%)")

        if progress_callback:
            await progress_callback(progress)

        await asyncio.sleep(0)

    logger.info(f"Resolved PHI for {total_resolved}/{total_files} files")
    return total_resolved


async def send_dispatch_status(
    send_func,
    entity_id: str,
    entity_type: str,
    status: str,
    correlation_id: str,
    workspace_id: str,
    progress: int = 0,
    files_sent: int = 0,
    files_total: int = 0,
    error: str = None
):
    """
    Send dispatch status update to backend.

    Args:
        send_func: Async function to send message (from handler)
        entity_id: Entity ID (subject/session/scan ID)
        entity_type: Type of entity ("subject"/"session"/"scan")
        status: Status ("downloading"/"completed"/"failed")
        correlation_id: Correlation ID from original event
        workspace_id: Workspace ID
        progress: Progress percentage (0-100)
        files_sent: Number of files sent
        files_total: Total number of files
        error: Error message if failed
    """
    from datetime import datetime

    status_event = {
        "event_type": "dispatch.status",
        "workspace_id": workspace_id,
        "timestamp": datetime.now().isoformat() + 'Z',
        "correlation_id": correlation_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": {
            "status": status,
            "progress": progress,
            "files_sent": files_sent,
            "files_total": files_total
        }
    }

    if error:
        status_event["payload"]["error"] = error

    await send_func(status_event)


async def get_active_dispatchable_nodes() -> List[NodeConfig]:
    """
    Get all active, reachable nodes with read/write permissions.

    Returns nodes that are:
    - Active (is_active=True)
    - Reachable (is_reachable=True)
    - Have permission (read or read_write)

    Returns:
        List of NodeConfig objects ready for dispatch
    """
    from receiver.services.config import get_config_service
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _load():
        config_service = get_config_service()
        if config_service:
            return config_service.get_active_nodes()
        return []

    all_nodes = await _load()

    dispatchable_nodes = [
        node for node in all_nodes
        if node.is_active
        and node.is_reachable
        and node.permission
        and node.permission.lower() in ('read', 'read_write')
    ]

    return dispatchable_nodes
