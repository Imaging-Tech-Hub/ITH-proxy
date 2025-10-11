"""
PHI Views - Protected Health Information API

WARNING: PROTECTED ENDPOINTS - Require Authentication
These endpoints return Protected Health Information (PHI) and must be secured.
"""
from .phi_metadata_view import PHIMetadataAPIView

__all__ = [
    'PHIMetadataAPIView',
]
