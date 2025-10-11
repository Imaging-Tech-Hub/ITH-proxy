"""
Command Pattern Implementation for ITH API and DICOM Operations.

Refactored structure:
- base/: Core command pattern components
- dicom/: DICOM-related commands (send, verify)
- api/: ITH API commands (subjects, sessions, scans, archives)

This module provides command classes that follow the Command Pattern,
allowing operations to be encapsulated, queued, and composed.
"""
# Base components
from .base import Command, CommandResult

# DICOM commands
from .dicom import (
    SendDICOMToNodeCommand,
    SendDICOMToMultipleNodesCommand,
    VerifyNodeConnectionCommand,
)

# API commands
from .api import (
    ListSubjectsCommand,
    GetSubjectCommand,
    DownloadSubjectCommand,
    ListSessionsCommand,
    GetSessionCommand,
    DownloadSessionCommand,
    ListScansCommand,
    GetScanCommand,
    DownloadScanCommand,
    CreateArchiveCommand,
    GetArchiveStatusCommand,
    DownloadArchiveCommand,
)

__all__ = [
    # Base
    'Command',
    'CommandResult',

    # DICOM Commands
    'SendDICOMToNodeCommand',
    'SendDICOMToMultipleNodesCommand',
    'VerifyNodeConnectionCommand',

    # Subject Commands
    'ListSubjectsCommand',
    'GetSubjectCommand',
    'DownloadSubjectCommand',

    # Session Commands
    'ListSessionsCommand',
    'GetSessionCommand',
    'DownloadSessionCommand',

    # Scan Commands
    'ListScansCommand',
    'GetScanCommand',
    'DownloadScanCommand',

    # Archive Commands
    'CreateArchiveCommand',
    'GetArchiveStatusCommand',
    'DownloadArchiveCommand',
]
