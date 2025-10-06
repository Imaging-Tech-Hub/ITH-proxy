"""
Management command to set the proxy key in the database.
"""
from django.core.management.base import BaseCommand
from receiver.models import ProxyConfiguration


class Command(BaseCommand):
    help = 'Set the proxy key in the database configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            'proxy_key',
            type=str,
            help='The proxy key to set (will be encrypted automatically)'
        )

    def handle(self, *args, **options):
        proxy_key = options['proxy_key']

        if not proxy_key:
            self.stdout.write(self.style.ERROR('Proxy key cannot be empty'))
            return

        try:
            config = ProxyConfiguration.get_instance()
            config.proxy_key = proxy_key
            config.save()

            self.stdout.write(self.style.SUCCESS(
                f'✅ Proxy key has been set and encrypted successfully'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'Configuration: {config.ae_title}@{config.ip_address}:{config.port}'
            ))
            self.stdout.write(self.style.SUCCESS(
                'The key is now stored encrypted in the database.'
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to set proxy key: {e}'))
