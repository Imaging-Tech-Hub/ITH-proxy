"""
Django Admin Configuration for DICOM Receiver Models
"""
from django.contrib import admin
from django.contrib.auth.models import User, Group

from .patient_mapping_admin import PatientMappingAdmin
from .session_admin import SessionAdmin
from .scan_admin import ScanAdmin

# Unregister default Django admin models (User and Group)
admin.site.unregister(User)
admin.site.unregister(Group)

# Customize admin site branding
admin.site.site_header = "ITH Proxy Administration"
admin.site.site_title = "ITH Proxy"
admin.site.index_title = "DICOM PACS Proxy Management"

__all__ = [
    'PatientMappingAdmin',
    'SessionAdmin',
    'ScanAdmin',
]
