"""
Scan Dispatch Event Handler.
Handles scan.dispatch events from ITH backend.
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


class ScanDispatchHandler:
    """
    Handles scan.dispatch events.
    Downloads scan from API and sends to specified PACS nodes.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle scan.dispatch event.

        Event structure:
        {
          "event_type": "scan.dispatch",
          "workspace_id": "ws_abc123",
          "entity_type": "scan",
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
            node_ids = payload.get('nodes', [])
            scan_number = payload.get('scan_number', 'Unknown')
            modality = payload.get('modality', 'Unknown')
            priority = payload.get('priority', 'normal')

            logger.info("=" * 60)
            logger.info(f" SCAN DISPATCH EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Scan: {scan_id} (#{scan_number}, {modality})")
            logger.info(f"Session: {session_id}")
            logger.info(f"Subject: {subject_id}")
            logger.info(f"Target Nodes: {', '.join(node_ids)}")
            logger.info(f"Priority: {priority}")
            logger.info("=" * 60)

            if not all([workspace_id, scan_id, subject_id, session_id, node_ids]):
                logger.error(" Missing required fields in scan.dispatch event")
                return False

            matching_nodes = await self._get_matching_nodes(node_ids)

            if not matching_nodes:
                logger.info(f"ℹ️  No nodes from {node_ids} are managed by this proxy, skipping")
                return True

            logger.info(f" Found {len(matching_nodes)} matching nodes managed by this proxy")

            scan_path = await self._download_scan(
                workspace_id, scan_id, subject_id, session_id
            )

            if not scan_path:
                logger.error(" Failed to download scan from API")
                return False

            dicom_dir = await self._extract_scan(scan_path)

            if not dicom_dir:
                logger.error(" Failed to extract scan archive")
                return False

            resolved_dir = await self._resolve_dicom_files(dicom_dir)

            if not resolved_dir:
                logger.error(" Failed to resolve PHI in DICOM files")
                return False

            scan_label = f"Scan #{scan_number or 'Unknown'} ({modality or 'Unknown'})"

            patient_info = await self._get_patient_info(subject_id, session_id)

            logger.info(f"\n📤 Preparing to send scan:")
            logger.info(f"   Scan: {scan_label}")
            logger.info(f"   Patient: {patient_info.get('patient_name', 'Unknown')} (ID: {patient_info.get('patient_id', 'Unknown')})")
            logger.info(f"   Study: {patient_info.get('study_description', 'Unknown')}")
            logger.info(f"   StudyInstanceUID: {patient_info.get('study_instance_uid', 'Unknown')}")
            logger.info(f"\n📍 Target Nodes:")
            for node in matching_nodes:
                logger.info(f"   - {node.name} @ {node.host}:{node.port} (AE: {node.ae_title})")

            success = await self._send_to_nodes(matching_nodes, resolved_dir, scan_label, patient_info)

            await self._cleanup(scan_path, dicom_dir)

            if success:
                logger.info(f" Scan dispatch completed successfully")
                return True
            else:
                logger.error(f" Scan dispatch failed")
                return False

        except Exception as e:
            logger.error(f" Error handling scan.dispatch event: {e}", exc_info=True)
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
                            logger.warning(f"⚠️  Node {node.name} ({node.node_id}) is inactive, skipping")
                            continue

                        if not node.is_reachable:
                            logger.warning(f"⚠️  Node {node.name} ({node.node_id}) is not reachable, skipping")
                            continue

                        if node.permission.upper() not in ['WRITE_ONLY', 'READ_WRITE']:
                            logger.warning(f"⚠️  Node {node.name} ({node.node_id}) does not have WRITE permission (permission: {node.permission}), skipping")
                            continue

                        logger.info(f"✅ Matched node: {node.name} ({node.node_id}) - Permission: {node.permission}")
                        matching.append(node)

                return matching

            return await sync_to_async(_get_nodes)()

        except Exception as e:
            logger.error(f"Error getting matching nodes: {e}", exc_info=True)
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

                temp_dir = Path(tempfile.gettempdir()) / "scan_dispatch"
                temp_dir.mkdir(parents=True, exist_ok=True)
                zip_path = temp_dir / f"{scan_id}.zip"

                logger.info(f" Downloading scan from API...")
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

    async def _get_patient_info(self, subject_id: str, session_id: str) -> Dict[str, str]:
        """
        Get patient and study information from API.

        Args:
            subject_id: Subject ID
            session_id: Session ID

        Returns:
            Dict with patient info
        """
        try:
            from receiver.containers import container

            api_client = container.ith_api_client()

            subject_response = await sync_to_async(api_client.get_subject)(subject_id)
            subject_data = subject_response.get('subject', {})

            session_response = await sync_to_async(api_client.get_session)(session_id)
            session_data = session_response.get('session', {})

            from receiver.controllers.phi_resolver import PHIResolver
            resolver = PHIResolver()

            anonymous_name = subject_data.get('label', '')
            anonymous_id = anonymous_name if anonymous_name else subject_data.get('subject_identifier', '')

            original = await sync_to_async(resolver.resolve_patient)(
                anonymous_name=anonymous_name,
                anonymous_id=anonymous_id
            )

            if original:
                patient_name = original['original_name']
                patient_id = original['original_id']
            else:
                patient_name = anonymous_name
                patient_id = anonymous_id

            return {
                'patient_name': patient_name,
                'patient_id': patient_id,
                'study_description': session_data.get('description') or session_data.get('label', ''),
                'study_instance_uid': session_data.get('study_instance_uid', ''),
            }

        except Exception as e:
            logger.warning(f"Could not fetch patient info: {e}")
            return {
                'patient_name': 'Unknown',
                'patient_id': 'Unknown',
                'study_description': 'Unknown',
                'study_instance_uid': 'Unknown',
            }

    async def _send_to_nodes(
        self,
        nodes: list,
        dicom_dir: Path,
        scan_label: str,
        patient_info: Dict[str, str]
    ) -> bool:
        """
        Send DICOM files to all specified nodes.

        Args:
            nodes: List of NodeConfig objects
            dicom_dir: Directory containing DICOM files
            scan_label: Scan label for logging
            patient_info: Patient and study information

        Returns:
            bool: True if at least one node succeeded
        """
        try:
            from receiver.commands.dicom_send_commands import SendDICOMToMultipleNodesCommand

            def _send():
                logger.info(f"\n🚀 Sending DICOM to nodes:")
                logger.info(f"   Scan: {scan_label}")
                logger.info(f"   Patient: {patient_info['patient_name']} (ID: {patient_info['patient_id']})")
                logger.info(f"   Study: {patient_info['study_description']}")
                logger.info(f"   Targets: {len(nodes)} node(s)")

                cmd = SendDICOMToMultipleNodesCommand(
                    nodes=nodes,
                    directory=dicom_dir,
                    recursive=True,
                    ae_title='DICOM_PROXY'
                )

                result = cmd.execute()

                if result.success:
                    logger.info(f"\n✅ Send completed:")
                    logger.info(f"   Successful nodes: {result.metadata.get('successful_nodes', 0)}/{len(nodes)}")
                    logger.info(f"   Files sent: {result.metadata.get('total_files_sent', 0)}")
                    logger.info(f"   Files failed: {result.metadata.get('total_files_failed', 0)}")
                    return True
                else:
                    logger.error(f"\n❌ Send failed: {result.error}")
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
