"""
Subject Dispatch Event Handler.
Handles subject.dispatch events from ITH backend.
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


class SubjectDispatchHandler:
    """
    Handles subject.dispatch events.
    Downloads subject (patient with all sessions) from API and sends to specified PACS nodes.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle subject.dispatch event.

        Event structure:
        {
          "event_type": "subject.dispatch",
          "workspace_id": "ws_abc123",
          "entity_type": "subject",
          "entity_id": "subj_ghi789",
          "payload": {
            "nodes": ["node_1", "node_2"],
            "subject_identifier": "PATIENT-001",
            "priority": "high"
          }
        }

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            subject_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})

            node_ids = payload.get('nodes', [])
            subject_identifier = payload.get('subject_identifier', 'Unknown')
            priority = payload.get('priority', 'normal')

            logger.info("=" * 60)
            logger.info(f" SUBJECT DISPATCH EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Subject: {subject_id} ({subject_identifier})")
            logger.info(f"Target Nodes: {', '.join(node_ids)}")
            logger.info(f"Priority: {priority}")
            logger.info("=" * 60)

            if not workspace_id or not subject_id or not node_ids:
                logger.error(" Missing required fields in subject.dispatch event")
                return False

            matching_nodes = await self._get_matching_nodes(node_ids)

            if not matching_nodes:
                logger.info(f"ℹ️  No nodes from {node_ids} are managed by this proxy, skipping")
                return True  # Not an error, just not for us

            logger.info(f" Found {len(matching_nodes)} matching nodes managed by this proxy")

            subject_path = await self._download_subject(workspace_id, subject_id)

            if not subject_path:
                logger.error(" Failed to download subject from API")
                return False

            dicom_dir = await self._extract_subject(subject_path)

            if not dicom_dir:
                logger.error(" Failed to extract subject archive")
                return False

            resolved_dir = await self._resolve_dicom_files(dicom_dir, subject_id=subject_id)

            if not resolved_dir:
                logger.error(" Failed to resolve PHI in DICOM files")
                return False

            success = await self._send_to_nodes(matching_nodes, resolved_dir, subject_identifier)

            await self._cleanup(subject_path, dicom_dir)

            if success:
                logger.info(f" Subject dispatch completed successfully")
                return True
            else:
                logger.error(f" Subject dispatch failed")
                return False

        except Exception as e:
            logger.error(f" Error handling subject.dispatch event: {e}", exc_info=True)
            return False

    async def _get_matching_nodes(self, node_ids: list) -> list:
        """
        Get nodes managed by this proxy that match the requested node IDs.

        Args:
            node_ids: List of node IDs from event

        Returns:
            List of matching NodeConfig objects
        """
        try:
            from receiver.services.proxy_config_service import get_config_service

            def _get_nodes():
                config_service = get_config_service()
                if not config_service:
                    return []

                all_nodes = config_service.load_nodes()
                matching = []

                for node in all_nodes:
                    if node.node_id in node_ids:
                        if not node.is_active:
                            logger.warning(f"Node {node.name} ({node.node_id}) is inactive, skipping")
                            continue

                        if not node.is_reachable:
                            logger.warning(f"Node {node.name} ({node.node_id}) is not reachable, skipping")
                            continue

                        logger.info(f" Matched node: {node.name} ({node.node_id})")
                        matching.append(node)

                return matching

            return await sync_to_async(_get_nodes)()

        except Exception as e:
            logger.error(f"Error getting matching nodes: {e}", exc_info=True)
            return []

    async def _download_subject(
        self,
        workspace_id: str,
        subject_id: str
    ) -> Path:
        """
        Download subject from ITH API.

        Args:
            workspace_id: Workspace ID
            subject_id: Subject ID

        Returns:
            Path to downloaded ZIP file, or None if failed
        """
        try:
            from receiver.containers import container

            def _download():
                api_client = container.ith_api_client()
                api_client.workspace_id = workspace_id

                temp_dir = Path(tempfile.gettempdir()) / "subject_dispatch"
                temp_dir.mkdir(parents=True, exist_ok=True)
                zip_path = temp_dir / f"{subject_id}.zip"

                logger.info(f" Downloading subject (all sessions) from API...")
                api_client.download_subject(
                    subject_id=subject_id,
                    output_path=zip_path
                )

                logger.info(f" Downloaded subject to {zip_path}")
                return zip_path

            return await sync_to_async(_download)()

        except Exception as e:
            logger.error(f"Error downloading subject: {e}", exc_info=True)
            return None

    async def _extract_subject(self, zip_path: Path) -> Path:
        """
        Extract subject ZIP archive.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Path to extracted directory, or None if failed
        """
        try:
            def _extract():
                extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)

                logger.info(f" Extracting subject archive...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                dcm_files = list(extract_dir.rglob('*.dcm'))
                logger.info(f" Extracted {len(dcm_files)} DICOM files from all sessions")

                return extract_dir

            return await sync_to_async(_extract)()

        except Exception as e:
            logger.error(f"Error extracting subject: {e}", exc_info=True)
            return None

    async def _resolve_dicom_files(self, dicom_dir: Path, subject_id: str = None) -> Path:
        """
        Resolve PHI in all DICOM files (de-anonymize).
        Uses API to get PHI for files from backend.

        Args:
            dicom_dir: Directory containing anonymized DICOM files
            subject_id: Backend subject ID for API resolution

        Returns:
            Path to directory with resolved files, or None if failed
        """
        try:
            def _resolve():
                from receiver.containers import container

                resolver = container.phi_resolver()

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
        subject_identifier: str
    ) -> bool:
        """
        Send DICOM files to all specified nodes with duplicate dispatch prevention.

        Args:
            nodes: List of NodeConfig objects
            dicom_dir: Directory containing DICOM files
            subject_identifier: Subject identifier for logging

        Returns:
            bool: True if at least one node succeeded
        """
        try:
            from receiver.commands.dicom_send_commands import SendDICOMToMultipleNodesCommand
            from receiver.services.dispatch_lock_manager import get_dispatch_lock_manager

            def _send():
                lock_manager = get_dispatch_lock_manager()

                study_uids = set()
                dcm_files = list(dicom_dir.rglob('*.dcm'))
                for dcm_file in dcm_files[:10]:
                    try:
                        ds = dcmread(str(dcm_file))
                        study_uid = getattr(ds, 'StudyInstanceUID', None)
                        if study_uid:
                            study_uids.add(study_uid)
                    except Exception:
                        pass

                if not study_uids:
                    study_uids = {'unknown'}

                nodes_to_send = []
                skipped_nodes = []

                for node in nodes:
                    can_send = True
                    acquired_locks = []

                    for study_uid in study_uids:
                        if lock_manager.acquire_lock(node.node_id, 'subject', study_uid):
                            acquired_locks.append(study_uid)
                        else:
                            can_send = False
                            logger.warning(
                                f"🔒 Skipping {node.name}: dispatch already in progress for "
                                f"study {study_uid}"
                            )
                            for acquired in acquired_locks:
                                lock_manager.release_lock(node.node_id, 'subject', acquired)
                            break

                    if can_send:
                        nodes_to_send.append((node, list(study_uids)))
                    else:
                        skipped_nodes.append(node)

                if not nodes_to_send:
                    logger.warning("⚠️  All nodes are already processing this dispatch, skipping")
                    return False

                if skipped_nodes:
                    logger.info(
                        f"Skipped {len(skipped_nodes)} node(s) due to in-progress dispatch, "
                        f"sending to {len(nodes_to_send)} node(s)"
                    )

                try:
                    logger.info(f" Sending subject '{subject_identifier}' to {len(nodes_to_send)} nodes...")
                    logger.info(f"Studies: {', '.join(study_uids)}")

                    cmd = SendDICOMToMultipleNodesCommand(
                        nodes=[n[0] for n in nodes_to_send],
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

                finally:
                    for node, study_uids_for_node in nodes_to_send:
                        for study_uid in study_uids_for_node:
                            lock_manager.release_lock(node.node_id, 'subject', study_uid)

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
