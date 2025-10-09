"""
New Scan Available Event Handler.
Handles scan.new_scan_available events from ITH backend (e.g., FlairStar analysis completion).
"""
import asyncio
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any
from asgiref.sync import sync_to_async
from pydicom import dcmread

logger = logging.getLogger(__name__)


class NewScanAvailableHandler:
    """
    Handles scan.new_scan_available events.
    Triggered when new scans are ready (e.g., FlairStar analysis completed).
    Downloads and dispatches to configured nodes.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle scan.new_scan_available event.

        Event structure:
        {
          "event_type": "scan.new_scan_available",
          "workspace_id": "ws_abc123",
          "entity_type": "scan",
          "entity_id": "scan_jkl012",
          "payload": {
            "subject_id": "subj_ghi789",
            "session_id": "sess_def456",
            "scan_type": "FlairStar",
            "scan_modality": "Derived",
            "source": "flairstar_analysis",
            "action": "pull_and_dispatch",
            "priority": "normal",
            "metadata": {}
          }
        }

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            scan_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})

            subject_id = payload.get('subject_id')
            session_id = payload.get('session_id')
            scan_type = payload.get('scan_type', 'Unknown')
            scan_modality = payload.get('scan_modality', 'Unknown')
            source = payload.get('source', 'unknown')
            priority = payload.get('priority', 'normal')
            metadata = payload.get('metadata', {})

            logger.info("=" * 60)
            logger.info(f"🆕 NEW SCAN AVAILABLE EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Scan: {scan_id}")
            logger.info(f"Type: {scan_type} ({scan_modality})")
            logger.info(f"Source: {source}")
            logger.info(f"Session: {session_id}")
            logger.info(f"Subject: {subject_id}")
            logger.info(f"Priority: {priority}")
            logger.info("=" * 60)

            if not all([workspace_id, scan_id, subject_id, session_id]):
                logger.error(" Missing required fields in scan.new_scan_available event")
                return False

            # Get target nodes for dispatch
            target_nodes = await self._get_dispatch_nodes()
            if not target_nodes:
                logger.info(f"ℹ️  No nodes configured for dispatch, skipping")
                return True

            logger.info(f" Dispatching to {len(target_nodes)} nodes")

            scan_path = await self._download_scan(workspace_id, scan_id, subject_id, session_id)

            if not scan_path:
                logger.error(" Failed to download new scan from API")
                return False

            dicom_dir = await self._extract_scan(scan_path)

            if not dicom_dir:
                logger.error(" Failed to extract scan archive")
                return False

            resolved_dir = await self._resolve_dicom_files(dicom_dir)

            if not resolved_dir:
                logger.error(" Failed to resolve PHI in DICOM files")
                return False

            scan_label = f"{scan_type} ({scan_modality})"
            success = await self._send_to_nodes(target_nodes, resolved_dir, scan_label)

            await self._cleanup(scan_path, dicom_dir)

            if success:
                logger.info(f" New scan auto-dispatch completed successfully")
                return True
            else:
                logger.error(f" New scan auto-dispatch failed")
                return False

        except Exception as e:
            logger.error(f" Error handling scan.new_scan_available event: {e}", exc_info=True)
            return False

    async def _get_dispatch_nodes(self) -> list:
        """
        Get nodes configured for auto-dispatch.

        Returns:
            List of active and reachable NodeConfig objects
        """
        try:
            from receiver.services.proxy_config_service import get_config_service

            def _get_nodes():
                config_service = get_config_service()
                if not config_service:
                    return []

                all_nodes = config_service.load_nodes()
                active_nodes = []

                for node in all_nodes:
                    if not node.is_active:
                        logger.debug(f"Node {node.name} is inactive, skipping")
                        continue

                    if not node.is_reachable:
                        logger.debug(f"Node {node.name} is not reachable, skipping")
                        continue

                    logger.info(f" Auto-dispatch target: {node.name} ({node.node_id})")
                    active_nodes.append(node)

                return active_nodes

            return await sync_to_async(_get_nodes)()

        except Exception as e:
            logger.error(f"Error getting auto-dispatch nodes: {e}", exc_info=True)
            return []

    async def _download_scan(
        self,
        workspace_id: str,
        scan_id: str,
        subject_id: str,
        session_id: str
    ) -> Path:
        """
        Download scan from ITH API.

        Args:
            workspace_id: Workspace ID
            scan_id: Scan ID
            subject_id: Subject ID
            session_id: Session ID

        Returns:
            Path to downloaded ZIP file, or None if failed
        """
        try:
            from receiver.containers import container

            def _download():
                api_client = container.ith_api_client()
                api_client.workspace_id = workspace_id

                temp_dir = Path(tempfile.gettempdir()) / "new_scan_available"
                temp_dir.mkdir(parents=True, exist_ok=True)
                zip_path = temp_dir / f"{scan_id}.zip"

                logger.info(f" Downloading new scan from API...")
                api_client.download_scan(
                    scan_id=scan_id,
                    subject_id=subject_id,
                    session_id=session_id,
                    output_path=zip_path
                )

                logger.info(f" Downloaded scan to {zip_path}")
                return zip_path

            return await sync_to_async(_download)()

        except Exception as e:
            logger.error(f"Error downloading scan: {e}", exc_info=True)
            return None

    async def _extract_scan(self, zip_path: Path) -> Path:
        """
        Extract scan ZIP archive.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Path to extracted directory, or None if failed
        """
        try:
            def _extract():
                extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)

                logger.info(f" Extracting scan archive...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                dcm_files = list(extract_dir.rglob('*.dcm'))
                logger.info(f" Extracted {len(dcm_files)} DICOM files")

                return extract_dir

            return await sync_to_async(_extract)()

        except Exception as e:
            logger.error(f"Error extracting scan: {e}", exc_info=True)
            return None

    async def _resolve_dicom_files(self, dicom_dir: Path) -> Path:
        """
        Resolve PHI in all DICOM files (de-anonymize).

        Args:
            dicom_dir: Directory containing anonymized DICOM files

        Returns:
            Path to directory with resolved files, or None if failed
        """
        try:
            def _resolve():
                from receiver.controllers.phi_resolver import PHIResolver
                resolver = PHIResolver()

                dcm_files = list(dicom_dir.rglob('*.dcm'))
                logger.info(f"🔍 Resolving PHI for {len(dcm_files)} DICOM files...")

                resolved_count = 0
                for dcm_file in dcm_files:
                    try:
                        ds = dcmread(str(dcm_file))

                        ds = resolver.resolve_dataset(ds)

                        ds.save_as(str(dcm_file))
                        resolved_count += 1

                    except Exception as e:
                        logger.warning(f"Failed to resolve {dcm_file.name}: {e}")

                logger.info(f"✅ Resolved PHI for {resolved_count}/{len(dcm_files)} files")
                return dicom_dir

            return await sync_to_async(_resolve)()

        except Exception as e:
            logger.error(f"Error resolving DICOM files: {e}", exc_info=True)
            return None

    async def _send_to_nodes(
        self,
        nodes: list,
        dicom_dir: Path,
        scan_label: str
    ) -> bool:
        """
        Send DICOM files to all specified nodes.

        Args:
            nodes: List of NodeConfig objects
            dicom_dir: Directory containing DICOM files
            scan_label: Scan label for logging

        Returns:
            bool: True if at least one node succeeded
        """
        try:
            from receiver.commands.dicom_send_commands import SendDICOMToMultipleNodesCommand

            def _send():
                logger.info(f" Auto-dispatching {scan_label} to {len(nodes)} nodes...")

                cmd = SendDICOMToMultipleNodesCommand(
                    nodes=nodes,
                    directory=dicom_dir,
                    recursive=True,
                    ae_title='DICOM_PROXY'
                )

                result = cmd.execute()

                if result.success:
                    logger.info(f" Successfully sent to {result.metadata.get('successful_nodes', 0)} nodes")
                    logger.info(f"Files sent: {result.metadata.get('total_files_sent', 0)}")
                    logger.info(f"Files failed: {result.metadata.get('total_files_failed', 0)}")
                    return True
                else:
                    logger.error(f" Failed to send to nodes: {result.error}")
                    return False

            return await sync_to_async(_send)()

        except Exception as e:
            logger.error(f"Error sending to nodes: {e}", exc_info=True)
            return False

    async def _cleanup(self, zip_path: Path, extract_dir: Path) -> None:
        """
        Cleanup temporary files.

        Args:
            zip_path: Path to ZIP file
            extract_dir: Path to extracted directory
        """
        try:
            import shutil

            def _do_cleanup():
                if zip_path and zip_path.exists():
                    zip_path.unlink()
                    logger.debug(f"🗑️  Deleted {zip_path}")

                if extract_dir and extract_dir.exists():
                    shutil.rmtree(extract_dir)
                    logger.debug(f"🗑️  Deleted {extract_dir}")

            await sync_to_async(_do_cleanup)()

        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {e}")
