"""
New Scan Available Handler.

Handles scan.new_scan_available events from backend.
Triggered when new scans are ready (e.g., FlairStar analysis completed).

This handler:
1. Gets all active, reachable nodes with read/write or read_only permissions
2. Downloads the new scan from the backend
3. Resolves PHI (maps anonymized IDs back to real PHI)
4. Dispatches to all eligible PACS nodes
"""
from typing import Dict, Any, List
from pathlib import Path
import asyncio
from asgiref.sync import sync_to_async
from ..base import BaseEventHandler
from receiver.utils.config import NodeConfig
from receiver.commands.api.scan_commands import DownloadScanCommand
from receiver.commands.dicom.send_commands import SendDICOMToMultipleNodesCommand
from .shared import (
    get_active_dispatchable_nodes,
    get_api_client,
    extract_archive,
    resolve_phi_in_directory,
    send_dispatch_status,
    download_with_progress
)


class NewScanAvailableHandler(BaseEventHandler):
    """Handle scan.new_scan_available events."""

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle scan.new_scan_available event.

        Payload Example:
        {
          "entity_id": "797f5cf6-77c3-447c-b52e-55f95c6b4fc4",
          "correlation_id": "abc123-correlation-id",
          "payload": {
            "subject_id": "5078fa35-cd67-4019-a2c3-7338d8cf495e",
            "session_id": "c436d91f-0abe-4790-9870-5cd03104bb09",
            "scan_type": "FlairStar",
            "scan_modality": "Derived",
            "source": "flairstar_analysis",
            "action": "pull_and_dispatch",
            "priority": "normal",
            "metadata": {
              "analysis_id": "a1b2c3d4-analysis-id",
              "created_from_flair": true,
              "created_from_swi": false,
              "processing_duration": 123.45
            }
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        correlation_id = event.get('correlation_id')

        subject_id = payload.get('subject_id')
        session_id = payload.get('session_id')
        scan_type = payload.get('scan_type')
        scan_modality = payload.get('scan_modality')
        source = payload.get('source', 'unknown')
        action = payload.get('action', 'pull_and_dispatch')

        self.logger.info(
            f"New scan available: {entity_id} "
            f"(Type: {scan_type}, Modality: {scan_modality}, Source: {source})"
        )

        try:
            dispatchable_nodes = await get_active_dispatchable_nodes()

            if not dispatchable_nodes:
                self.logger.warning(
                    f"No active/reachable nodes available for dispatch of scan {entity_id}"
                )
                return

            node_names = [node.name for node in dispatchable_nodes]
            self.logger.info(
                f"Will dispatch to {len(dispatchable_nodes)} nodes: {', '.join(node_names)}"
            )

            if action == 'pull_and_dispatch':
                asyncio.create_task(
                    self._download_and_dispatch(
                        entity_id,
                        subject_id,
                        session_id,
                        dispatchable_nodes,
                        correlation_id,
                        scan_type
                    )
                )
            else:
                self.logger.warning(f"Unknown action '{action}' for scan {entity_id}")

        except Exception as e:
            self.logger.error(
                f"Error handling new_scan_available {entity_id}: {e}",
                exc_info=True
            )

    async def _download_and_dispatch(
        self,
        scan_id: str,
        subject_id: str,
        session_id: str,
        nodes: List[NodeConfig],
        correlation_id: str,
        scan_type: str = None
    ):
        """
        Download scan and dispatch to all nodes.

        Args:
            scan_id: Scan entity ID
            subject_id: Subject ID
            session_id: Session ID
            nodes: List of target nodes
            correlation_id: Correlation ID for tracking
            scan_type: Type of scan (e.g., "FlairStar")
        """
        try:
            await self._send_status(scan_id, "downloading", correlation_id)

            api_client = get_api_client(
                self.consumer.proxy_key,
                self.get_workspace_id()
            )

            async def download_progress(progress: int):
                """Send download progress updates to keep WebSocket alive."""
                await self._send_status(scan_id, "downloading", correlation_id)

            def do_download(progress_callback=None):
                return api_client.download_scan(
                    scan_id=scan_id,
                    subject_id=subject_id,
                    session_id=session_id,
                    output_path=Path(f"/tmp/downloads/new_scan_{scan_id}"),
                    progress_callback=progress_callback
                )

            self.logger.info(f"Downloading scan {scan_id} from backend...")

            download_path = await download_with_progress(
                download_func=do_download,
                progress_callback=download_progress,
                logger=self.logger,
                entity_type="scan",
                entity_id=scan_id
            )

            extract_path = download_path.parent / f"{download_path.stem}_extracted"

            self.logger.info(f"Extracting archive to {extract_path}...")
            await extract_archive(download_path, extract_path)

            self.logger.info(f"Resolving PHI for scan {scan_id}...")
            resolved_count = await resolve_phi_in_directory(
                extract_path,
                self.logger,
                subject_id
            )

            if resolved_count == 0:
                self.logger.warning(
                    f"No DICOM files found or PHI resolution failed for {scan_id}"
                )

            self.logger.info(
                f"Dispatching scan {scan_id} to {len(nodes)} nodes..."
            )

            send_cmd = SendDICOMToMultipleNodesCommand(
                nodes=nodes,
                directory=extract_path
            )

            send_result = await sync_to_async(send_cmd.execute)()

            if send_result.success:
                total_files = send_result.metadata.get('total_files_sent', 0)
                self.logger.info(
                    f"Successfully dispatched scan {scan_id}: {total_files} files sent"
                )
                await self._send_status(
                    scan_id,
                    "completed",
                    correlation_id,
                    files_sent=total_files
                )
            else:
                error_msg = f"Dispatch failed: {send_result.error}"
                self.logger.error(error_msg)
                await self._send_status(
                    scan_id, "failed", correlation_id, error=error_msg
                )

            try:
                import shutil
                if download_path.exists():
                    download_path.unlink()
                if extract_path.exists():
                    shutil.rmtree(extract_path)
                self.logger.info(f"Cleaned up temporary files for {scan_id}")
            except Exception as cleanup_error:
                self.logger.warning(f"Failed to cleanup temp files: {cleanup_error}")

        except Exception as e:
            error_msg = f"Error in download/dispatch: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            await self._send_status(scan_id, "failed", correlation_id, error=error_msg)

    async def _send_status(
        self,
        scan_id: str,
        status: str,
        correlation_id: str,
        files_sent: int = 0,
        error: str = None
    ):
        """
        Send dispatch status update to backend.

        Args:
            scan_id: Scan entity ID
            status: Status ("downloading"/"completed"/"failed")
            correlation_id: Correlation ID from original event
            files_sent: Number of files successfully sent
            error: Error message if failed
        """
        await send_dispatch_status(
            self.send_response,
            scan_id,
            "scan",
            status,
            correlation_id,
            self.get_workspace_id(),
            files_sent=files_sent,
            error=error
        )
