"""
Custom logging filters for fine-grained control.
"""
import logging
import re


class LevelRangeFilter(logging.Filter):
    """Filter messages within a specific level range."""

    def __init__(self, min_level=logging.DEBUG, max_level=logging.CRITICAL):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record):
        return self.min_level <= record.levelno <= self.max_level


class ModuleFilter(logging.Filter):
    """Filter messages by module name pattern."""

    def __init__(self, include_patterns=None, exclude_patterns=None):
        super().__init__()
        self.include_patterns = [re.compile(p) for p in (include_patterns or [])]
        self.exclude_patterns = [re.compile(p) for p in (exclude_patterns or [])]

    def filter(self, record):
        module_name = record.name

        for pattern in self.exclude_patterns:
            if pattern.search(module_name):
                return False

        if self.include_patterns:
            for pattern in self.include_patterns:
                if pattern.search(module_name):
                    return True
            return False

        return True


class DicomOperationFilter(logging.Filter):
    """Filter DICOM operation messages."""

    OPERATIONS = ['C-STORE', 'C-FIND', 'C-GET', 'C-MOVE', 'C-ECHO']

    def __init__(self, operations=None):
        super().__init__()
        self.operations = operations or self.OPERATIONS

    def filter(self, record):
        message = record.getMessage()
        return any(op in message for op in self.operations)


class SensitiveDataFilter(logging.Filter):
    """Filter or redact sensitive data from logs."""

    SENSITIVE_PATTERNS = [
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE), 'password=***'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE), 'token=***'),
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '***-**-****'),
    ]

    def filter(self, record):
        message = record.getMessage()

        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)

        record.msg = message
        return True


class ThrottleFilter(logging.Filter):
    """Throttle repeated log messages."""

    def __init__(self, rate_limit=10, time_window=60):
        super().__init__()
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.message_counts = {}
        self.last_reset = {}

    def filter(self, record):
        import time

        message_key = f"{record.name}:{record.levelno}:{record.getMessage()}"
        current_time = time.time()

        if message_key in self.last_reset:
            if current_time - self.last_reset[message_key] > self.time_window:
                self.message_counts[message_key] = 0
                self.last_reset[message_key] = current_time
        else:
            self.message_counts[message_key] = 0
            self.last_reset[message_key] = current_time

        self.message_counts[message_key] += 1

        if self.message_counts[message_key] <= self.rate_limit:
            return True
        elif self.message_counts[message_key] == self.rate_limit + 1:
            record.msg = f"{record.getMessage()} (throttled - max {self.rate_limit} in {self.time_window}s)"
            return True

        return False
