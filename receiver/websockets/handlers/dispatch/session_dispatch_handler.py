"""
Session Dispatch Handler.

Handles session.dispatch events from backend:
1. Check if requested nodes are managed by this proxy
2. Download session from ITH API
3. Send DICOM files to target PACS nodes
"""
from typing import Dict, Any, List
from pathlib import Path
import asyncio
from asgiref.sync import sync_to_async
from ..base import BaseEventHandler
from receiver.commands.api.session_commands import DownloadSessionCommand
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


class SessionDispatchHandler(BaseEventHandler):
    """Handle session.dispatch events."""

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle session dispatch event.

        Payload:
        {
          "entity_id": "sess_def456",
          "payload": {
            "subject_id": "subj_ghi789",
            "nodes": ["node_1"],
            "session_label": "MRI-2025-001",
            "priority": "normal"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        correlation_id = event.get('correlation_id')

        subject_id = payload.get('subject_id')
        requested_nodes = payload.get('nodes', [])
        session_label = payload.get('session_label')

        self.logger.info(
            f"Handling session dispatch: {entity_id} ({session_label}) to nodes {requested_nodes}"
        )

        try:
            matching_nodes = await get_matching_nodes(requested_nodes)

            if not matching_nodes:
                self.logger.info(f"No matching nodes for session dispatch {entity_id}")
                return

            asyncio.create_task(
                self._download_and_dispatch(entity_id, subject_id, matching_nodes, correlation_id)
            )

        except Exception as e:
            self.logger.error(f"Error handling session dispatch {entity_id}: {e}", exc_info=True)

    async def _download_and_dispatch(
        self,
        session_id: str,
        subject_id: str,
        nodes: List[NodeConfig],
        correlation_id: str
    ):
        """Download session and send to nodes."""
        try:
            await self._send_status(session_id, "downloading", correlation_id, progress=0)

            api_client = get_api_client(self.consumer.proxy_key, self.get_workspace_id())

            async def download_progress(progress: int):
                """Send download progress updates to keep WebSocket alive."""
                await self._send_status(
                    session_id,
                    "downloading",
                    correlation_id,
                    progress=progress
                )

            def do_download(progress_callback=None):
                return api_client.download_session(
                    session_id=session_id,
                    subject_id=subject_id,
                    output_path=Path(f"/tmp/downloads/session_{session_id}"),
                    progress_callback=progress_callback
                )

            download_path = await download_with_progress(
                download_func=do_download,
                progress_callback=download_progress,
                logger=self.logger,
                entity_type="session",
                entity_id=session_id
            )

            extract_path = download_path.parent / f"{download_path.stem}_extracted"
            await extract_archive(download_path, extract_path)

            self.logger.info(f"Resolving PHI for session {session_id}...")

            async def phi_progress_callback(progress: int):
                """Send progress updates to keep WebSocket alive."""
                await self._send_status(
                    session_id,
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
                    session_id,
                    "completed",
                    correlation_id,
                    files_sent=send_result.metadata.get('total_files_sent', 0)
                )
            else:
                await self._send_status(
                    session_id, "failed", correlation_id, error=send_result.error
                )

        except Exception as e:
            self.logger.error(f"Error in session download/dispatch: {e}", exc_info=True)
            await self._send_status(session_id, "failed", correlation_id, error=str(e))

    async def _send_status(
        self,
        session_id: str,
        status: str,
        correlation_id: str,
        files_sent: int = 0,
        progress: int = 0,
        error: str = None
    ):
        """Send dispatch status update."""
        await send_dispatch_status(
            self.send_response,
            session_id,
            "session",
            status,
            correlation_id,
            self.get_workspace_id(),
            files_sent=files_sent,
            progress=progress,
            error=error
        )
