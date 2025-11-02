"""
Views Module - REST API Endpoints

Organized by domain:
- health/: Health check and status endpoints
- phi/: Protected Health Information (PHI) endpoints
"""
from .health import PublicHealthCheckView, AuthenticatedStatusView
from .phi import (
    PHIMetadataAPIView,
    PatientPHIMetadataView,
    StudyPHIMetadataView,
    SeriesPHIMetadataView,
    PatientPHIBatchView,
    StudyPHIBatchView,
    SeriesPHIBatchView,
)

__all__ = [
    # Health Views
    'PublicHealthCheckView',
    'AuthenticatedStatusView',

    # PHI Views
    'PHIMetadataAPIView',
    'PatientPHIMetadataView',
    'StudyPHIMetadataView',
    'SeriesPHIMetadataView',
    'PatientPHIBatchView',
    'StudyPHIBatchView',
    'SeriesPHIBatchView',
]
