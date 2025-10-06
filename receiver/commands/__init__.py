"""
Command Pattern Implementation for Laminate API Operations.

This module provides command classes for consuming the Laminate REST API.
Commands can be composed and executed in sequence for complex workflows.
"""
from .base import Command, CommandResult
from .subject_commands import ListSubjectsCommand, GetSubjectCommand, DownloadSubjectCommand
from .session_commands import ListSessionsCommand, GetSessionCommand, DownloadSessionCommand
from .scan_commands import ListScansCommand, GetScanCommand, DownloadScanCommand
from .archive_commands import CreateArchiveCommand, GetArchiveStatusCommand, DownloadArchiveCommand

__all__ = [
    # Base
    'Command',
    'CommandResult',

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
