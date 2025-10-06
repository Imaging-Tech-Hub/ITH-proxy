"""
Custom logging handlers for specialized output.
"""
import logging
from pathlib import Path
from datetime import datetime


class StudyCompletionHandler(logging.Handler):
    """Handler that writes study completion events to a separate file."""

    def __init__(self, filename='study_completions.log'):
        super().__init__()
        self.filename = filename
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        if 'study completed' in record.getMessage().lower():
            with open(self.filename, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {record.getMessage()}\n")


class ErrorNotificationHandler(logging.Handler):
    """Handler that can send notifications for critical errors."""

    def __init__(self, notification_func=None):
        super().__init__(level=logging.ERROR)
        self.notification_func = notification_func or self._default_notification

    def _default_notification(self, record):
        """Default notification - just print to stderr."""
        import sys
        print(f"🚨 CRITICAL ERROR: {record.getMessage()}", file=sys.stderr)

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                self.notification_func(record)
            except Exception:
                self.handleError(record)


class MetricsHandler(logging.Handler):
    """Handler that tracks logging metrics."""

    def __init__(self):
        super().__init__()
        self.metrics = {
            'total': 0,
            'by_level': {},
            'by_module': {},
            'errors': [],
        }

    def emit(self, record):
        self.metrics['total'] += 1

        level = record.levelname
        self.metrics['by_level'][level] = self.metrics['by_level'].get(level, 0) + 1

        module = record.name
        self.metrics['by_module'][module] = self.metrics['by_module'].get(module, 0) + 1

        if record.levelno >= logging.ERROR:
            self.metrics['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'module': module,
                'message': record.getMessage(),
            })

    def get_metrics(self):
        """Get current metrics."""
        return self.metrics.copy()

    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = {
            'total': 0,
            'by_level': {},
            'by_module': {},
            'errors': [],
        }
