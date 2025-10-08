"""
Logging configuration module.
Centralized logging setup for the entire application.
"""
import logging
import logging.config
import os
from pathlib import Path
from django.conf import settings
from .formatters import ColoredFormatter, DetailedFormatter, JSONFormatter, CompactFormatter, SafeFormatter
from .filters import (
    LevelRangeFilter,
    ModuleFilter,
    DicomOperationFilter,
    SensitiveDataFilter,
    ThrottleFilter
)


def get_log_level():
    """Get log level from settings."""
    level_name = getattr(settings, 'DICOM_LOG_LEVEL', 'INFO')
    return getattr(logging, level_name.upper(), logging.INFO)


def get_logging_config():
    """
    Get logging configuration dictionary.

    Returns:
        dict: Logging configuration
    """
    log_level = get_log_level()
    log_dir = Path(getattr(settings, 'DICOM_LOG_DIR', settings.BASE_DIR / 'storage' / 'logs'))
    debug_mode = getattr(settings, 'DEBUG', True)

    log_dir.mkdir(parents=True, exist_ok=True)

    main_log = log_dir / 'main.log'
    error_log = log_dir / 'error.log'
    dicom_log = log_dir / 'dicom.log'
    api_log = log_dir / 'api.log'
    django_log = log_dir / 'django.log'
    websocket_log = log_dir / 'websocket.log'
    events_log = log_dir / 'events.log'

    config = {
        'version': 1,
        'disable_existing_loggers': False,

        'formatters': {
            'colored': {
                '()': ColoredFormatter,
                'format': '%(levelname)s [%(name)s] %(message)s'
            },
            'detailed': {
                '()': DetailedFormatter,
                'format': '%(timestamp)s [%(levelname)s] %(module_path)s:%(lineno)d - %(message)s'
            },
            'json': {
                '()': JSONFormatter,
            },
            'compact': {
                '()': CompactFormatter,
            },
            'standard': {
                '()': SafeFormatter,
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },

        'filters': {
            'sensitive_data': {
                '()': SensitiveDataFilter,
            },
            'dicom_operations': {
                '()': DicomOperationFilter,
            },
            'throttle': {
                '()': ThrottleFilter,
                'rate_limit': 100,
                'time_window': 60,
            },
        },

        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'colored',
                'filters': ['sensitive_data'],
                'stream': 'ext://sys.stdout',
            },
            'main_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.DEBUG,
                'formatter': 'detailed',
                'filters': ['sensitive_data'],
                'filename': str(main_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'error_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.ERROR,
                'formatter': 'detailed',
                'filters': ['sensitive_data'],
                'filename': str(error_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'dicom_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'standard',
                'filters': ['dicom_operations', 'sensitive_data'],
                'filename': str(dicom_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'api_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'detailed',
                'filters': ['sensitive_data'],
                'filename': str(api_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'django_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'standard',
                'filename': str(django_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'websocket_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'detailed',
                'filters': ['sensitive_data'],
                'filename': str(websocket_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
            'events_file': {
                'class': 'logging.handlers.TimedRotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'detailed',
                'filters': ['sensitive_data'],
                'filename': str(events_log),
                'when': 'midnight',
                'interval': 1,
                'backupCount': 10,
                'encoding': 'utf-8',
            },
        },

        'loggers': {
            'receiver.handlers.store': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.handlers.find': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.handlers.get': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.handlers.move': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.query': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.dicom_scp': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.dicom_scu': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'receiver.study_monitor': {
                'level': log_level,
                'handlers': ['console', 'dicom_file', 'error_file'] if debug_mode else ['dicom_file', 'error_file'],
                'propagate': False,
            },
            'pynetdicom': {
                'level': logging.WARNING,
                'handlers': ['dicom_file'],
                'propagate': False,
            },

            'receiver.views': {
                'level': log_level,
                'handlers': ['console', 'api_file', 'error_file'] if debug_mode else ['api_file', 'error_file'],
                'propagate': False,
            },
            'receiver.auth': {
                'level': log_level,
                'handlers': ['console', 'api_file', 'error_file'] if debug_mode else ['api_file', 'error_file'],
                'propagate': False,
            },
            'receiver.guard': {
                'level': log_level,
                'handlers': ['console', 'api_file', 'error_file'] if debug_mode else ['api_file', 'error_file'],
                'propagate': False,
            },
            'receiver.ith_client': {
                'level': log_level,
                'handlers': ['console', 'api_file', 'error_file'] if debug_mode else ['api_file', 'error_file'],
                'propagate': False,
            },

            'receiver.services.event_handlers.proxy_config_changed_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.proxy_nodes_changed_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.proxy_status_changed_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.session_dispatch_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.session_deleted_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.subject_dispatch_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.subject_deleted_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.scan_dispatch_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.scan_deleted_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.event_handlers.new_scan_available_handler': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },

            'receiver.services.proxy_websocket_client': {
                'level': log_level,
                'handlers': ['console', 'websocket_file', 'error_file'] if debug_mode else ['websocket_file', 'error_file'],
                'propagate': False,
            },
            'receiver.websockets.consumer': {
                'level': log_level,
                'handlers': ['console', 'websocket_file', 'error_file'] if debug_mode else ['websocket_file', 'error_file'],
                'propagate': False,
            },

            'receiver.websockets.events': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },

            'receiver.websockets.handlers': {
                'level': log_level,
                'handlers': ['console', 'events_file', 'error_file'] if debug_mode else ['events_file', 'error_file'],
                'propagate': False,
            },

            'receiver.websockets': {
                'level': log_level,
                'handlers': ['console', 'websocket_file', 'error_file'] if debug_mode else ['websocket_file', 'error_file'],
                'propagate': False,
            },

            'receiver.commands': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },

            'receiver.services.api_query_service': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.proxy_config_service': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.access_control_service': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },
            'receiver.services.study_uploader': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },

            'django': {
                'level': logging.INFO,
                'handlers': ['console', 'django_file'] if debug_mode else ['django_file'],
                'propagate': False,
            },
            'django.request': {
                'level': logging.WARNING,
                'handlers': ['console', 'django_file', 'error_file'] if debug_mode else ['django_file', 'error_file'],
                'propagate': False,
            },
            'django.server': {
                'level': logging.INFO,
                'handlers': ['console', 'django_file'] if debug_mode else ['django_file'],
                'propagate': False,
            },

            'receiver': {
                'level': log_level,
                'handlers': ['console', 'main_file', 'error_file'] if debug_mode else ['main_file', 'error_file'],
                'propagate': False,
            },
        },

        'root': {
            'level': log_level,
            'handlers': ['console', 'main_file'] if debug_mode else ['main_file'],
        },
    }

    return config


def setup_logging():
    """Setup logging for the entire application."""
    config = get_logging_config()
    logging.config.dictConfig(config)

    logger = logging.getLogger('receiver')
    log_dir = Path(getattr(settings, 'DICOM_LOG_DIR', settings.BASE_DIR / 'storage' / 'logs'))
    debug_mode = getattr(settings, 'DEBUG', True)

    logger.info("=" * 60)
    logger.info("Logging system initialized")
    logger.info(f"Log level: {get_log_level()}")
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"Console logging: {'Enabled' if debug_mode else 'Disabled (DEBUG=False)'}")
    logger.info(f"Log rotation: Daily at midnight, 10 backups")
    logger.info("=" * 60)


def get_logger(name):
    """
    Get a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)


def get_compact_logger(name):
    """Get a logger with compact formatting."""
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(CompactFormatter())
    logger.addHandler(handler)
    return logger


def get_json_logger(name):
    """Get a logger with JSON formatting."""
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger
