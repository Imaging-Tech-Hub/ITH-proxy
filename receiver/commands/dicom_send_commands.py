"""
DICOM Send commands for dispatching files to PACS nodes.
Nodes are loaded from configuration (not database).
"""
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any
from .base import Command, CommandResult
from receiver.utils.node_config import NodeConfig
from receiver.services.dicom_scu import DICOMServiceUser, DICOMSendResult


class SendDICOMToNodeCommand(Command):
    """
    Send DICOM files to a single PACS node.
    Runs in background thread if async_mode=True.

    Usage:
        # Create node config
        node = NodeConfig(
            node_id="node_1",
            name="Main PACS",
            ae_title="MAIN_PACS",
            host="10.0.1.100",
            port=11112
        )

        # Synchronous
        cmd = SendDICOMToNodeCommand(node, files=[Path("file1.dcm"), Path("file2.dcm")])
        result = cmd.execute()

        # Asynchronous (returns immediately, operation runs in background)
        cmd = SendDICOMToNodeCommand(node, directory=Path("/scans"), async_mode=True)
        result = cmd.execute()  # Returns immediately with future
        if result:
            future = result.data['future']
            send_result = future.result()  # Wait for completion
    """

    def __init__(
        self,
        node: NodeConfig,
        files: Optional[List[Path]] = None,
        directory: Optional[Path] = None,
        recursive: bool = True,
        async_mode: bool = False,
        ae_title: str = 'DICOM_PROXY'
    ):
        """
        Initialize command.

        Args:
            node: Target PACS node configuration
            files: List of DICOM files to send (either files or directory)
            directory: Directory containing DICOM files (either files or directory)
            recursive: Recursively scan directory
            async_mode: Run in background thread
            ae_title: AE Title for SCU
        """
        super().__init__()
        self.node = node
        self.files = files
        self.directory = Path(directory) if directory else None
        self.recursive = recursive
        self.async_mode = async_mode
        self.ae_title = ae_title
        self.scu = DICOMServiceUser(
            ae_title=ae_title,
            max_pdu_size=node.max_pdu_size,
            connection_timeout=node.connection_timeout
        )

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.node.is_active:
            self.logger.error(f"Node {self.node.name} is not active")
            return False

        if not self.files and not self.directory:
            self.logger.error("Either files or directory must be provided")
            return False

        if self.files and self.directory:
            self.logger.error("Provide either files or directory, not both")
            return False

        if self.directory and not self.directory.exists():
            self.logger.error(f"Directory does not exist: {self.directory}")
            return False

        return True

    def _send_sync(self) -> DICOMSendResult:
        """Synchronous send operation."""
        if self.files:
            return self.scu.send_files(
                self.files,
                self.node.host,
                self.node.port,
                self.node.ae_title,
                retry_count=self.node.retry_count,
                retry_delay=self.node.retry_delay
            )
        else:
            return self.scu.send_directory(
                self.directory,
                self.node.host,
                self.node.port,
                self.node.ae_title,
                recursive=self.recursive,
                retry_count=self.node.retry_count,
                retry_delay=self.node.retry_delay
            )

    def execute(self) -> CommandResult:
        """Execute DICOM send command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            if self.async_mode:
                # Run in background thread
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(self._send_sync)

                self.logger.info(f"Started async DICOM send to {self.node.name}")

                return CommandResult(
                    success=True,
                    data={'future': future},
                    metadata={
                        'node': self.node.name,
                        'async': True
                    }
                )
            else:
                # Run synchronously
                self.logger.info(f"Sending DICOM files to {self.node.name}")
                send_result = self._send_sync()

                if send_result.success:
                    return CommandResult(
                        success=True,
                        data={
                            'files_sent': send_result.files_sent,
                            'files_failed': send_result.files_failed,
                            'total_files': send_result.total_files
                        },
                        metadata={
                            'node': self.node.name,
                            'async': False
                        }
                    )
                else:
                    return CommandResult(
                        success=False,
                        data={
                            'files_sent': send_result.files_sent,
                            'files_failed': send_result.files_failed,
                            'total_files': send_result.total_files
                        },
                        error=send_result.error
                    )

        except Exception as e:
            self.logger.error(f"Failed to send DICOM to {self.node.name}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class SendDICOMToMultipleNodesCommand(Command):
    """
    Send DICOM files to multiple PACS nodes in parallel.
    Each node send operation runs in its own background thread.

    Usage:
        nodes = [
            NodeConfig(node_id="node_1", name="Main PACS", ae_title="MAIN", host="10.0.1.100", port=11112),
            NodeConfig(node_id="node_2", name="Backup PACS", ae_title="BACKUP", host="10.0.1.101", port=11112),
        ]

        cmd = SendDICOMToMultipleNodesCommand(
            nodes=nodes,
            directory=Path("/scans/patient001")
        )
        result = cmd.execute()
        if result:
            for node_result in result.data['results']:
                logger.info(f"{node_result['node']}: {node_result['status']}")
    """

    def __init__(
        self,
        nodes: List[NodeConfig],
        files: Optional[List[Path]] = None,
        directory: Optional[Path] = None,
        recursive: bool = True,
        max_workers: int = 5,
        ae_title: str = 'DICOM_PROXY'
    ):
        """
        Initialize command.

        Args:
            nodes: List of target PACS node configurations
            files: List of DICOM files to send (either files or directory)
            directory: Directory containing DICOM files (either files or directory)
            recursive: Recursively scan directory
            max_workers: Maximum number of parallel sends
            ae_title: AE Title for SCU
        """
        super().__init__()
        self.nodes = nodes
        self.files = files
        self.directory = Path(directory) if directory else None
        self.recursive = recursive
        self.max_workers = max_workers
        self.ae_title = ae_title

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.nodes:
            self.logger.error("No nodes provided")
            return False

        if not self.files and not self.directory:
            self.logger.error("Either files or directory must be provided")
            return False

        if self.files and self.directory:
            self.logger.error("Provide either files or directory, not both")
            return False

        if self.directory and not self.directory.exists():
            self.logger.error(f"Directory does not exist: {self.directory}")
            return False

        return True

    def _send_to_node(self, node: NodeConfig) -> Dict[str, Any]:
        """Send to single node (worker function)."""
        self.logger.info(f"Sending to node: {node.name}")

        cmd = SendDICOMToNodeCommand(
            node=node,
            files=self.files,
            directory=self.directory,
            recursive=self.recursive,
            async_mode=False,
            ae_title=self.ae_title
        )

        result = cmd.execute()

        return {
            'node_id': node.node_id,
            'node': node.name,
            'success': result.success,
            'files_sent': result.data.get('files_sent', 0) if result.data else 0,
            'files_failed': result.data.get('files_failed', 0) if result.data else 0,
            'error': result.error
        }

    def execute(self) -> CommandResult:
        """Execute multi-node DICOM send command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            active_nodes = [n for n in self.nodes if n.is_active]

            if not active_nodes:
                self.logger.warning("No active nodes found")
                return CommandResult(
                    success=True,
                    data={'results': []},
                    metadata={'total_nodes': 0, 'active_nodes': 0}
                )

            self.logger.info(f"Sending DICOM files to {len(active_nodes)} nodes in parallel")

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self._send_to_node, node): node for node in active_nodes}

                results = []
                for future in concurrent.futures.as_completed(futures):
                    node = futures[future]
                    try:
                        node_result = future.result()
                        results.append(node_result)
                        status = "SUCCESS" if node_result['success'] else "FAILED"
                        self.logger.info(f"{status}: {node.name}: {node_result['files_sent']} files sent")
                    except Exception as e:
                        self.logger.error(f"FAILED: {node.name}: {e}")
                        results.append({
                            'node_id': node.node_id,
                            'node': node.name,
                            'success': False,
                            'files_sent': 0,
                            'files_failed': 0,
                            'error': str(e)
                        })

            total_success = sum(1 for r in results if r['success'])
            total_files_sent = sum(r['files_sent'] for r in results)
            total_files_failed = sum(r['files_failed'] for r in results)

            self.logger.info(f"Completed: {total_success}/{len(results)} nodes successful, "
                           f"{total_files_sent} files sent, {total_files_failed} files failed")

            return CommandResult(
                success=total_success > 0,
                data={'results': results},
                metadata={
                    'total_nodes': len(active_nodes),
                    'successful_nodes': total_success,
                    'total_files_sent': total_files_sent,
                    'total_files_failed': total_files_failed
                }
            )

        except Exception as e:
            self.logger.error(f"Failed to send DICOM to multiple nodes: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class VerifyNodeConnectionCommand(Command):
    """
    Verify connection to PACS node using C-ECHO.

    Usage:
        node = NodeConfig(
            node_id="node_1",
            name="Main PACS",
            ae_title="MAIN_PACS",
            host="10.0.1.100",
            port=11112
        )

        cmd = VerifyNodeConnectionCommand(node)
        result = cmd.execute()
        if result:
            logger.info(f"Node {node.name} is online")
    """

    def __init__(self, node: NodeConfig, ae_title: str = 'DICOM_PROXY'):
        """
        Initialize command.

        Args:
            node: PACS node configuration to verify
            ae_title: AE Title for SCU
        """
        super().__init__()
        self.node = node
        self.ae_title = ae_title
        self.scu = DICOMServiceUser(
            ae_title=ae_title,
            max_pdu_size=node.max_pdu_size,
            connection_timeout=node.connection_timeout,
            verification_only=True
        )

    def execute(self) -> CommandResult:
        """Execute verify connection command."""
        try:
            self.logger.info(f"Verifying connection to {self.node.name}")

            is_online = self.scu.verify_connection(
                self.node.host,
                self.node.port,
                self.node.ae_title
            )

            if is_online:
                return CommandResult(
                    success=True,
                    data={'is_online': True},
                    metadata={'node': self.node.name}
                )
            else:
                return CommandResult(
                    success=False,
                    data={'is_online': False},
                    error=f"Node {self.node.name} is offline"
                )

        except Exception as e:
            self.logger.error(f"Failed to verify connection to {self.node.name}: {e}")
            return CommandResult(
                success=False,
                data={'is_online': False},
                error=str(e)
            )
