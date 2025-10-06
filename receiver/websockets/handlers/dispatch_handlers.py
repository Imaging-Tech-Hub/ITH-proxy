"""
Dispatch Event Handlers.
Handle subject/session/scan dispatch events from backend.

These handlers:
1. Check if requested nodes are managed by this proxy
2. Download the entity from Laminate API
3. Send DICOM files to target PACS nodes
4. Report progress back to backend
"""
from typing import Dict, Any, List, Set
from pathlib import Path
import asyncio
from .base import BaseEventHandler
from receiver.commands.subject_commands import DownloadSubjectCommand
from receiver.commands.session_commands import DownloadSessionCommand
from receiver.commands.scan_commands import DownloadScanCommand
from receiver.commands.dicom_send_commands import SendDICOMToMultipleNodesCommand
from receiver.services.laminate_api_client import LaminateAPIClient
from receiver.utils.node_config import NodeConfig


class SubjectDispatchHandler(BaseEventHandler):
    """
    Handle subject.dispatch events.

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the subject using REST API
    3. Store DICOM files in the appropriate node storage
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle subject dispatch event.

        Payload:
        {
          "entity_id": "subj_ghi789",
          "payload": {
            "nodes": ["node_1", "node_2"],
            "subject_identifier": "PATIENT-001",
            "priority": "high"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        correlation_id = event.get('correlation_id')

        requested_nodes = payload.get('nodes', [])
        subject_identifier = payload.get('subject_identifier')
        priority = payload.get('priority', 'normal')

        self.logger.info(f"Handling subject dispatch: {entity_id} to nodes {requested_nodes} (priority: {priority})")

        try:
            # Check which requested nodes are managed by this proxy
            matching_nodes = await self._get_matching_nodes(requested_nodes)

            if not matching_nodes:
                self.logger.info(f"No matching nodes for subject dispatch {entity_id}")
                return

            self.logger.info(f"Dispatching subject {entity_id} to {len(matching_nodes)} nodes")

            # Run download and dispatch in background
            asyncio.create_task(
                self._download_and_dispatch_subject(
                    entity_id,
                    matching_nodes,
                    correlation_id
                )
            )

        except Exception as e:
            self.logger.error(f"Error handling subject dispatch {entity_id}: {e}", exc_info=True)

    async def _download_and_dispatch_subject(
        self,
        subject_id: str,
        nodes: List[NodeConfig],
        correlation_id: str
    ):
        """Download subject and send to nodes."""
        from asgiref.sync import sync_to_async

        try:
            # Send initial status
            await self._send_status(subject_id, "subject", "downloading", correlation_id)

            # Download subject
            workspace_id = self.get_workspace_id()
            api_client = self._get_api_client()

            download_cmd = DownloadSubjectCommand(
                client=api_client,
                subject_id=subject_id,
                output_path=Path(f"/tmp/downloads/subject_{subject_id}")
            )

            # Execute download (sync operation in thread)
            result = await sync_to_async(download_cmd.execute)()

            if not result.success:
                await self._send_status(
                    subject_id, "subject", "failed",
                    correlation_id, error=result.error
                )
                return

            download_path = Path(result.data['file_path'])

            # Extract downloaded files
            extract_path = download_path.parent / f"{download_path.stem}_extracted"
            await self._extract_archive(download_path, extract_path)

            # Send to PACS nodes
            send_cmd = SendDICOMToMultipleNodesCommand(
                nodes=nodes,
                directory=extract_path,
                recursive=True
            )

            send_result = await sync_to_async(send_cmd.execute)()

            if send_result.success:
                await self._send_status(
                    subject_id, "subject", "completed",
                    correlation_id,
                    files_sent=send_result.metadata.get('total_files_sent', 0)
                )
            else:
                await self._send_status(
                    subject_id, "subject", "failed",
                    correlation_id, error=send_result.error
                )

        except Exception as e:
            self.logger.error(f"Error in subject download/dispatch: {e}", exc_info=True)
            await self._send_status(
                subject_id, "subject", "failed",
                correlation_id, error=str(e)
            )

    async def _get_matching_nodes(self, requested_node_ids: List[str]) -> List[NodeConfig]:
        """Get nodes managed by this proxy that match requested nodes."""
        # TODO: Load node configuration for this proxy
        # This should be loaded from config file or API
        # For now, return empty list
        managed_nodes = await self._load_managed_nodes()

        managed_node_ids = {node.node_id for node in managed_nodes}
        requested_node_ids_set = set(requested_node_ids)

        matching_ids = managed_node_ids & requested_node_ids_set

        return [node for node in managed_nodes if node.node_id in matching_ids]

    async def _load_managed_nodes(self) -> List[NodeConfig]:
        """Load nodes managed by this proxy."""
        from receiver.services.proxy_config_service import get_config_service
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _load():
            config_service = get_config_service()
            if config_service:
                return config_service.get_active_nodes()
            return []

        return await _load()

    def _get_api_client(self) -> LaminateAPIClient:
        """Get configured API client."""
        from django.conf import settings

        return LaminateAPIClient(
            base_url=settings.LAMINATE_API_URL,
            proxy_key=self.consumer.proxy_key,
            workspace_id=self.get_workspace_id()
        )

    async def _extract_archive(self, archive_path: Path, extract_path: Path):
        """Extract downloaded archive."""
        import zipfile
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _extract():
            extract_path.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)

        await _extract()

    async def _send_status(
        self,
        entity_id: str,
        entity_type: str,
        status: str,
        correlation_id: str,
        progress: int = 0,
        files_sent: int = 0,
        files_total: int = 0,
        error: str = None
    ):
        """Send dispatch status update to backend."""
        from datetime import datetime

        status_event = {
            "event_type": "dispatch.status",
            "workspace_id": self.get_workspace_id(),
            "timestamp": datetime.utcnow().isoformat() + 'Z',
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

        await self.send_response(status_event)


class SessionDispatchHandler(SubjectDispatchHandler):
    """
    Handle session.dispatch events.

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the session using REST API
    """

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
        priority = payload.get('priority', 'normal')

        self.logger.info(f"Handling session dispatch: {entity_id} ({session_label}) to nodes {requested_nodes}")

        try:
            matching_nodes = await self._get_matching_nodes(requested_nodes)

            if not matching_nodes:
                self.logger.info(f"No matching nodes for session dispatch {entity_id}")
                return

            asyncio.create_task(
                self._download_and_dispatch_session(
                    entity_id,
                    subject_id,
                    matching_nodes,
                    correlation_id
                )
            )

        except Exception as e:
            self.logger.error(f"Error handling session dispatch {entity_id}: {e}", exc_info=True)

    async def _download_and_dispatch_session(
        self,
        session_id: str,
        subject_id: str,
        nodes: List[NodeConfig],
        correlation_id: str
    ):
        """Download session and send to nodes."""
        from asgiref.sync import sync_to_async

        try:
            await self._send_status(session_id, "session", "downloading", correlation_id)

            api_client = self._get_api_client()

            download_cmd = DownloadSessionCommand(
                client=api_client,
                session_id=session_id,
                subject_id=subject_id,
                output_path=Path(f"/tmp/downloads/session_{session_id}")
            )

            result = await sync_to_async(download_cmd.execute)()

            if not result.success:
                await self._send_status(
                    session_id, "session", "failed",
                    correlation_id, error=result.error
                )
                return

            download_path = Path(result.data['file_path'])
            extract_path = download_path.parent / f"{download_path.stem}_extracted"
            await self._extract_archive(download_path, extract_path)

            send_cmd = SendDICOMToMultipleNodesCommand(
                nodes=nodes,
                directory=extract_path,
                recursive=True
            )

            send_result = await sync_to_async(send_cmd.execute)()

            if send_result.success:
                await self._send_status(
                    session_id, "session", "completed",
                    correlation_id,
                    files_sent=send_result.metadata.get('total_files_sent', 0)
                )
            else:
                await self._send_status(
                    session_id, "session", "failed",
                    correlation_id, error=send_result.error
                )

        except Exception as e:
            self.logger.error(f"Error in session download/dispatch: {e}", exc_info=True)
            await self._send_status(
                session_id, "session", "failed",
                correlation_id, error=str(e)
            )


class ScanDispatchHandler(SubjectDispatchHandler):
    """
    Handle scan.dispatch events.

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the scan using REST API
    """

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
        modality = payload.get('modality')

        self.logger.info(f"Handling scan dispatch: {entity_id} (Scan #{scan_number}) to nodes {requested_nodes}")

        try:
            matching_nodes = await self._get_matching_nodes(requested_nodes)

            if not matching_nodes:
                self.logger.info(f"No matching nodes for scan dispatch {entity_id}")
                return

            asyncio.create_task(
                self._download_and_dispatch_scan(
                    entity_id,
                    subject_id,
                    session_id,
                    matching_nodes,
                    correlation_id
                )
            )

        except Exception as e:
            self.logger.error(f"Error handling scan dispatch {entity_id}: {e}", exc_info=True)

    async def _download_and_dispatch_scan(
        self,
        scan_id: str,
        subject_id: str,
        session_id: str,
        nodes: List[NodeConfig],
        correlation_id: str
    ):
        """Download scan and send to nodes."""
        from asgiref.sync import sync_to_async

        try:
            await self._send_status(scan_id, "scan", "downloading", correlation_id)

            api_client = self._get_api_client()

            download_cmd = DownloadScanCommand(
                client=api_client,
                scan_id=scan_id,
                subject_id=subject_id,
                session_id=session_id,
                output_path=Path(f"/tmp/downloads/scan_{scan_id}")
            )

            result = await sync_to_async(download_cmd.execute)()

            if not result.success:
                await self._send_status(
                    scan_id, "scan", "failed",
                    correlation_id, error=result.error
                )
                return

            download_path = Path(result.data['file_path'])
            extract_path = download_path.parent / f"{download_path.stem}_extracted"
            await self._extract_archive(download_path, extract_path)

            send_cmd = SendDICOMToMultipleNodesCommand(
                nodes=nodes,
                directory=extract_path,
                recursive=True
            )

            send_result = await sync_to_async(send_cmd.execute)()

            if send_result.success:
                await self._send_status(
                    scan_id, "scan", "completed",
                    correlation_id,
                    files_sent=send_result.metadata.get('total_files_sent', 0)
                )
            else:
                await self._send_status(
                    scan_id, "scan", "failed",
                    correlation_id, error=send_result.error
                )

        except Exception as e:
            self.logger.error(f"Error in scan download/dispatch: {e}", exc_info=True)
            await self._send_status(
                scan_id, "scan", "failed",
                correlation_id, error=str(e)
            )
