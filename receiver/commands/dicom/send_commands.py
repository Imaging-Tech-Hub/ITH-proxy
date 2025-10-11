"""
DICOM send commands - refactored for better separation of concerns.
"""
import concurrent.futures
from pathlib import Path
from typing import List, Optional

from receiver.commands.base import Command, CommandResult
from receiver.commands.base.validators import RequiredFieldValidator, PathExistsValidator
from receiver.utils.config import NodeConfig
from .services import DICOMSendService, SendOptions


class SendDICOMToNodeCommand(Command):
    """
    Send DICOM files to a single PACS node.

    Refactored version with:
    - Clearer separation of concerns (service layer handles business logic)
    - Better validation using validator utilities
    - Simplified async handling

    Example:
        node = NodeConfig(node_id="n1", name="PACS", ae_title="PACS", host="10.0.1.100", port=11112)
        cmd = SendDICOMToNodeCommand(node, directory=Path("/scans"))
        result = cmd.execute()
        if result:
            print(f"Sent {result.data['files_sent']} files")
    """

    def __init__(
        self,
        node: NodeConfig,
        files: Optional[List[Path]] = None,
        directory: Optional[Path] = None,
        options: Optional[SendOptions] = None,
        async_mode: bool = False
    ):
        """
        Initialize command.

        Args:
            node: Target PACS node
            files: List of DICOM files to send
            directory: Directory containing DICOM files
            options: Send configuration options
            async_mode: Run in background thread
        """
        super().__init__()
        self.node = node
        self.files = files
        self.directory = Path(directory) if directory else None
        self.options = options or SendOptions()
        self.async_mode = async_mode
        self.service = DICOMSendService(self.options)

    def validate(self) -> bool:
        """Validate command parameters."""
        # Check node is active
        if not self.node.is_active:
            self.logger.error(f"Node {self.node.name} is not active")
            return False

        # Validate files XOR directory
        if (self.files and self.directory) or (not self.files and not self.directory):
            self.logger.error("Provide either files or directory, not both or neither")
            return False

        # Validate directory exists
        if self.directory:
            validator = PathExistsValidator("directory", must_be_dir=True)
            is_valid, error = validator.validate(self.directory)
            if not is_valid:
                self.logger.error(error)
                return False

        return True

    def _send_sync(self):
        """Execute synchronous send operation."""
        return self.service.send_to_node(
            self.node,
            files=self.files,
            directory=self.directory
        )

    def execute(self) -> CommandResult:
        """Execute DICOM send command."""
        if not self.validate():
            return CommandResult(success=False, error="Validation failed")

        try:
            if self.async_mode:
                # Run in background thread
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(self._send_sync)

                self.logger.info(f"Started async DICOM send to {self.node.name}")

                return CommandResult(
                    success=True,
                    data={'future': future, 'async': True},
                    metadata={'node': self.node.name}
                )
            else:
                # Run synchronously
                self.logger.info(f"Sending DICOM files to {self.node.name}")
                send_result = self._send_sync()

                return CommandResult(
                    success=send_result.success,
                    data={
                        'files_sent': send_result.files_sent,
                        'files_failed': send_result.files_failed,
                        'total_files': send_result.total_files
                    },
                    error=send_result.error if not send_result.success else None,
                    metadata={'node': self.node.name}
                )

        except Exception as e:
            self.logger.error(f"Failed to send DICOM to {self.node.name}: {e}")
            return CommandResult(success=False, error=str(e))


class SendDICOMToMultipleNodesCommand(Command):
    """
    Send DICOM files to multiple PACS nodes in parallel.

    Example:
        nodes = [node1, node2, node3]
        cmd = SendDICOMToMultipleNodesCommand(nodes, directory=Path("/scans"))
        result = cmd.execute()
        for node_result in result.data['results']:
            print(f"{node_result['node']}: {node_result['files_sent']} files")
    """

    def __init__(
        self,
        nodes: List[NodeConfig],
        files: Optional[List[Path]] = None,
        directory: Optional[Path] = None,
        options: Optional[SendOptions] = None,
        max_workers: int = 5
    ):
        """
        Initialize command.

        Args:
            nodes: List of target PACS nodes
            files: List of DICOM files to send
            directory: Directory containing DICOM files
            options: Send configuration options
            max_workers: Maximum number of parallel sends
        """
        super().__init__()
        self.nodes = nodes
        self.files = files
        self.directory = Path(directory) if directory else None
        self.options = options or SendOptions()
        self.max_workers = max_workers

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.nodes:
            self.logger.error("No nodes provided")
            return False

        if (self.files and self.directory) or (not self.files and not self.directory):
            self.logger.error("Provide either files or directory, not both or neither")
            return False

        if self.directory:
            validator = PathExistsValidator("directory", must_be_dir=True)
            is_valid, error = validator.validate(self.directory)
            if not is_valid:
                self.logger.error(error)
                return False

        return True

    def _send_to_node(self, node: NodeConfig) -> dict:
        """Send to single node (worker function)."""
        self.logger.info(f"Sending to node: {node.name}")

        cmd = SendDICOMToNodeCommand(
            node=node,
            files=self.files,
            directory=self.directory,
            options=self.options,
            async_mode=False
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
            return CommandResult(success=False, error="Validation failed")

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
            return CommandResult(success=False, error=str(e))
