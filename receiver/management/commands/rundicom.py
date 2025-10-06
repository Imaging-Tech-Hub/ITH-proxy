"""
Django management command to run the DICOM receiver service.
Usage: python manage.py rundicom
"""
from django.core.management.base import BaseCommand
from receiver.containers import container
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Start the DICOM receiver service (SCP server)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=int,
            default=None,
            help='Port to listen on (overrides settings)',
        )
        parser.add_argument(
            '--ae-title',
            type=str,
            default=None,
            help='AE Title for the DICOM server (overrides settings)',
        )
        parser.add_argument(
            '--bind',
            type=str,
            default=None,
            help='IP address to bind to (overrides settings)',
        )

    def handle(self, *args, **options):
        """Start the DICOM receiver service."""
        self.stdout.write(self.style.SUCCESS('Starting DICOM receiver service...'))

        dicom_scp = container.dicom_service_provider()

        if options['port']:
            dicom_scp.port = options['port']
        if options['ae_title']:
            dicom_scp.ae_title = options['ae_title'].encode()
        if options['bind']:
            dicom_scp.bind_address = options['bind']

        try:
            dicom_scp.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutting down DICOM receiver...'))
            dicom_scp.stop()
            self.stdout.write(self.style.SUCCESS('DICOM receiver stopped'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running DICOM receiver: {e}'))
            raise
