"""
Custom logging formatters for different output styles.
"""
import logging
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """Colored console formatter with icons."""

    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }

    ICONS = {
        'DEBUG': '',
        'INFO': '',
        'WARNING': '',
        'ERROR': '',
        'CRITICAL': '',
    }

    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        levelname_orig = record.levelname

        if levelname_orig in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname_orig]}{self.BOLD}{self.ICONS[levelname_orig]} "
                f"{levelname_orig}{self.RESET}"
            )

        try:
            result = super().format(record)
        except (TypeError, ValueError) as e:
            result = f"{record.levelname} [{record.name}] {record.msg}"
        finally:
            record.levelname = levelname_orig

        return result


class DetailedFormatter(logging.Formatter):
    """Detailed formatter with all metadata."""

    def format(self, record):
        record.timestamp = datetime.now().isoformat()
        record.module_path = f"{record.module}.{record.funcName}"

        try:
            return super().format(record)
        except (TypeError, ValueError) as e:
            return f"{record.timestamp} [{record.levelname}] {record.module_path}:{record.lineno} - {record.msg}"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        import json

        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            message = str(record.msg)

        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': message,
        }

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra

        return json.dumps(log_data)


class CompactFormatter(logging.Formatter):
    """Compact formatter for minimal output."""

    ICONS = {
        'DEBUG': '',
        'INFO': '',
        'WARNING': '',
        'ERROR': '',
        'CRITICAL': '',
    }

    def format(self, record):
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            message = str(record.msg)

        icon = self.ICONS.get(record.levelname, '')
        if icon:
            return f"{icon} [{record.module}] {message}"
        return f"[{record.module}] {message}"


class SafeFormatter(logging.Formatter):
    """Safe formatter that handles malformed log records."""

    def format(self, record):
        try:
            return super().format(record)
        except (TypeError, ValueError):
            return f"{self.formatTime(record)} [{record.levelname}] {record.name}: {record.msg}"
