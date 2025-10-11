"""
Receiver app URL configuration
"""
from django.urls import path
from receiver.views import PHIMetadataAPIView, PublicHealthCheckView, AuthenticatedStatusView

app_name = 'receiver'

urlpatterns = [
    path('api/phi-metadata/', PHIMetadataAPIView.as_view(), name='get_phi_metadata'),
    path('api/health/', PublicHealthCheckView.as_view(), name='health_check'),
    path('api/status/', AuthenticatedStatusView.as_view(), name='status'),
]
