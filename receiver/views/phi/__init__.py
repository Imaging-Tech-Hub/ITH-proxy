"""
PHI Views - Protected Health Information API

WARNING: PROTECTED ENDPOINTS - Require Authentication
These endpoints return Protected Health Information (PHI) and must be secured.

Endpoints:
- combined.py: All-in-one PHI endpoint (returns all three levels at once)
- patient.py: Patient-level PHI endpoint (demographics)
- study.py: Study-level PHI endpoint (institution, physicians, dates)
- series.py: Series-level PHI endpoint (acquisition dates, device info)
- batch.py: Batch PHI endpoints (multiple items in one request)
"""
from .combined import PHIMetadataAPIView
from .patient import PatientPHIMetadataView
from .study import StudyPHIMetadataView
from .series import SeriesPHIMetadataView
from .batch import PatientPHIBatchView, StudyPHIBatchView, SeriesPHIBatchView

__all__ = [
    'PHIMetadataAPIView',
    'PatientPHIMetadataView',
    'StudyPHIMetadataView',
    'SeriesPHIMetadataView',
    'PatientPHIBatchView',
    'StudyPHIBatchView',
    'SeriesPHIBatchView',
]
