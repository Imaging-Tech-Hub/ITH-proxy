"""
Scan Dispatch Handler.

Handles scan.dispatch events from backend:
1. Check if requested nodes are managed by this proxy
2. Download scan from ITH API
3. Send DICOM files to target PACS nodes
"""
from typing import Dict, Any, List
from pathlib import Path
import asyncio
from asgiref.sync import sync_to_async
from ..base import BaseEventHandler
from receiver.commands.api.scan_commands import DownloadScanCommand
from receiver.commands.dicom.send_commands import SendDICOMToMultipleNodesCommand
from receiver.utils.config import NodeConfig
from .shared import (
    get_matching_nodes,
    get_api_client,
    extract_archive,
    resolve_phi_in_directory,
    send_dispatch_status,
    download_with_progress
)


class ScanDispatchHandler(BaseEventHandler):
    """Handle scan.dispatch events."""

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle scan dispatch event.

        Payload:
        {
          "entity_id": "scan_jkl012",
          "payload": {
            "subject_id": "subj_ghi789",
            "session_id": "sess_def456",
            "nodes": ["node_3"],
            "scan_number": 3,
            "modality": "MR",
            "priority": "urgent"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        correlation_id = event.get('correlation_id')

        subject_id = payload.get('subject_id')
        session_id = payload.get('session_id')
        requested_nodes = payload.get('nodes', [])
        scan_number = payload.get('scan_number')

        self.logger.info(
            f"Handling scan dispatch: {entity_id} (Scan #{scan_number}) to nodes {requested_nodes}"
        )

        try:
            matching_nodes = await get_matching_nodes(requested_nodes)

            if not matching_nodes:
                self.logger.info(f"No matching nodes for scan dispatch {entity_id}")
                return

            asyncio.create_task(
                self._download_and_dispatch(
                    entity_id, subject_id, session_id, matching_nodes, correlation_id
                )
            )

        except Exception as e:
            self.logger.error(f"Error handling scan dispatch {entity_id}: {e}", exc_info=True)

    async def _download_and_dispatch(
        self,
        scan_id: str,
        subject_id: str,
        session_id: str,
        nodes: List[NodeConfig],
        correlation_id: str
    ):
        """Download scan and send to nodes."""
        try:
            await self._send_status(scan_id, "downloading", correlation_id, progress=0)

            api_client = get_api_client(self.consumer.proxy_key, self.get_workspace_id())

            async def download_progress(progress: int):
                """Send download progress updates to keep WebSocket alive."""
                await self._send_status(
                    scan_id,
                    "downloading",
                    correlation_id,
                    progress=progress
                )

            def do_download(progress_callback=None):
                return api_client.download_scan(
                    scan_id=scan_id,
                    subject_id=subject_id,
                    session_id=session_id,
                    output_path=Path(f"/tmp/downloads/scan_{scan_id}"),
                    progress_callback=progress_callback
                )

            download_path = await download_with_progress(
                download_func=do_download,
                progress_callback=download_progress,
                logger=self.logger,
                entity_type="scan",
                entity_id=scan_id
            )

            extract_path = download_path.parent / f"{download_path.stem}_extracted"
            await extract_archive(download_path, extract_path)

            self.logger.info(f"Resolving PHI for scan {scan_id}...")

            async def phi_progress_callback(progress: int):
                """Send progress updates to keep WebSocket alive."""
                await self._send_status(
                    scan_id,
                    "processing",
                    correlation_id,
                    progress=progress
                )

            await resolve_phi_in_directory(
                extract_path,
                self.logger,
                subject_id,
                progress_callback=phi_progress_callback
            )

            send_cmd = SendDICOMToMultipleNodesCommand(
                nodes=nodes,
                directory=extract_path
            )

            send_result = await sync_to_async(send_cmd.execute)()

            if send_result.success:
                await self._send_status(
                    scan_id,
                    "completed",
                    correlation_id,
                    files_sent=send_result.metadata.get('total_files_sent', 0)
                )
            else:
                await self._send_status(
                    scan_id, "failed", correlation_id, error=send_result.error
                )

        except Exception as e:
            self.logger.error(f"Error in scan download/dispatch: {e}", exc_info=True)
            await self._send_status(scan_id, "failed", correlation_id, error=str(e))

    async def _send_status(
        self,
        scan_id: str,
        status: str,
        correlation_id: str,
        files_sent: int = 0,
        progress: int = 0,
        error: str = None
    ):
        """Send dispatch status update."""
        await send_dispatch_status(
            self.send_response,
            scan_id,
            "scan",
            status,
            correlation_id,
            self.get_workspace_id(),
            files_sent=files_sent,
            progress=progress,
            error=error
        )
