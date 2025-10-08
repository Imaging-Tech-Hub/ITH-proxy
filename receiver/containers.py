"""
Dependency Injection Container
Centralized configuration for all service dependencies.
"""
from dependency_injector import containers, providers
from django.conf import settings


class Container(containers.DeclarativeContainer):
    """
    Main DI Container for the receiver application.
    Manages all service dependencies and their life cycles.
    """

    config = providers.Configuration()

    phi_anonymizer = providers.Singleton(
        'receiver.controllers.phi_anonymizer.PHIAnonymizer'
    )

    phi_resolver = providers.Singleton(
        'receiver.controllers.phi_resolver.PHIResolver'
    )

    storage_manager = providers.Singleton(
        'receiver.controllers.storage_manager.StorageManager',
        storage_dir=config.storage_dir
    )

    study_monitor = providers.Singleton(
        'receiver.controllers.dicom.study_monitor.StudyMonitor',
        timeout=config.study_timeout
    )

    ith_api_client = providers.Singleton(
        'receiver.services.ith_api_client.IthAPIClient',
        base_url=config.ith_url,
        proxy_key=config.ith_token
    )

    proxy_config_service = providers.Singleton(
        'receiver.services.proxy_config_service.ProxyConfigService',
        api_client=ith_api_client
    )

    api_query_service = providers.Singleton(
        'receiver.services.api_query_service.APIQueryService',
        api_client=ith_api_client,
        resolver=phi_resolver
    )

    patient_query_handler = providers.Singleton(
        'receiver.controllers.dicom.query_handlers.PatientQueryHandler',
        storage_manager=storage_manager,
        resolver=phi_resolver,
        api_query_service=api_query_service
    )

    study_query_handler = providers.Singleton(
        'receiver.controllers.dicom.query_handlers.StudyQueryHandler',
        storage_manager=storage_manager,
        resolver=phi_resolver,
        api_query_service=api_query_service
    )

    series_query_handler = providers.Singleton(
        'receiver.controllers.dicom.query_handlers.SeriesQueryHandler',
        storage_manager=storage_manager,
        resolver=phi_resolver,
        api_query_service=api_query_service
    )

    image_query_handler = providers.Singleton(
        'receiver.controllers.dicom.query_handlers.ImageQueryHandler',
        storage_manager=storage_manager,
        resolver=phi_resolver,
        api_query_service=api_query_service
    )

    query_handlers = providers.Dict(
        PATIENT=patient_query_handler,
        STUDY=study_query_handler,
        SERIES=series_query_handler,
        IMAGE=image_query_handler
    )

    dicom_service_provider = providers.Singleton(
        'receiver.controllers.dicom.dicom_scp.DicomServiceProvider',
        storage_manager=storage_manager,
        study_monitor=study_monitor,
        anonymizer=phi_anonymizer,
        resolver=phi_resolver,
        query_handlers=query_handlers,
        port=config.port,
        ae_title=config.ae_title,
        bind_address=config.bind_address
    )


def setup_container() -> Container:
    """
    Setup and configure the DI container with Django settings.

    Returns:
        Configured Container instance
    """
    container = Container()

    container.config.ae_title.from_value(settings.DICOM_AE_TITLE)
    container.config.port.from_value(settings.DICOM_PORT)
    container.config.bind_address.from_value(settings.DICOM_BIND_ADDRESS)
    container.config.storage_dir.from_value(settings.DICOM_STORAGE_DIR)
    container.config.study_timeout.from_value(settings.DICOM_STUDY_TIMEOUT)

    container.config.ith_url.from_value(
        getattr(settings, 'ITH_URL', 'http://localhost:8000')
    )
    container.config.ith_token.from_value(
        getattr(settings, 'ITH_TOKEN', '')
    )
    container.config.proxy_config_dir.from_value(
        getattr(settings, 'PROXY_CONFIG_DIR', None)
    )

    return container


container = setup_container()
