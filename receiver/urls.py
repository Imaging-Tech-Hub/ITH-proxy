"""
Receiver app URL configuration
"""
from django.urls import path
from receiver.views import (
    PHIMetadataAPIView,
    PatientPHIMetadataView,
    StudyPHIMetadataView,
    SeriesPHIMetadataView,
    PatientPHIBatchView,
    StudyPHIBatchView,
    SeriesPHIBatchView,
    PublicHealthCheckView,
    AuthenticatedStatusView,
)

app_name = 'receiver'

urlpatterns = [
    # Legacy PHI endpoint (returns all three levels at once)
    path('api/phi-metadata/', PHIMetadataAPIView.as_view(), name='get_phi_metadata'),

    # Three-level PHI endpoints (single item)
    path('api/phi-metadata/patient/', PatientPHIMetadataView.as_view(), name='get_patient_phi'),
    path('api/phi-metadata/study/', StudyPHIMetadataView.as_view(), name='get_study_phi'),
    path('api/phi-metadata/series/', SeriesPHIMetadataView.as_view(), name='get_series_phi'),

    # Batch PHI endpoints (multiple items)
    path('api/phi-metadata/patient/batch/', PatientPHIBatchView.as_view(), name='get_patient_phi_batch'),
    path('api/phi-metadata/study/batch/', StudyPHIBatchView.as_view(), name='get_study_phi_batch'),
    path('api/phi-metadata/series/batch/', SeriesPHIBatchView.as_view(), name='get_series_phi_batch'),

    # Health check endpoints
    path('api/health/', PublicHealthCheckView.as_view(), name='health_check'),
    path('api/status/', AuthenticatedStatusView.as_view(), name='status'),
]
