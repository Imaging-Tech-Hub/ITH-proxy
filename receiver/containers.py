"""
Dependency Injection Container

Centralized configuration for all service dependencies using dependency-injector.
Manages singleton instances and dependency wiring for the entire application.

Design:
- Services are singletons (one instance per application)
- Dependencies injected via constructor
- Lazy initialization (created on first use)
- Thread-safe singleton management
"""
from dependency_injector import containers, providers
from django.conf import settings


class Container(containers.DeclarativeContainer):
    """
    Main DI Container for the receiver application.

    Manages lifecycle and dependencies for:
    - Services (API clients, config, query, upload, coordination)
    - Controllers (PHI, storage, DICOM)
    - Query handlers
    """

    # Configuration providers
    config = providers.Configuration()

    # ============================================================================
    # PHI Services (controllers/phi/)
    # ============================================================================

    phi_anonymizer = providers.Singleton(
        'receiver.controllers.phi.PHIAnonymizer'
    )

    phi_resolver = providers.Singleton(
        'receiver.controllers.phi.PHIResolver'
    )

    # ============================================================================
    # API Services (services/api/)
    # ============================================================================

    ith_api_client = providers.Singleton(
        'receiver.services.api.IthAPIClient',
        base_url=config.ith_url,
        proxy_key=config.ith_token
    )

    # ============================================================================
    # Config Services (services/config/)
    # ============================================================================

    proxy_config_service = providers.Singleton(
        'receiver.services.config.ProxyConfigService',
        api_client=ith_api_client
    )

    # ============================================================================
    # Query Services (services/query/)
    # ============================================================================

    api_query_service = providers.Singleton(
        'receiver.services.query.APIQueryService',
        api_client=ith_api_client,
        resolver=phi_resolver
    )

    # ============================================================================
    # Coordination Services (services/coordination/)
    # ============================================================================

    dispatch_lock_manager = providers.Singleton(
        'receiver.services.coordination.DispatchLockManager'
    )

    # ============================================================================
    # Storage Controller (controllers/)
    # ============================================================================

    storage_manager = providers.Singleton(
        'receiver.controllers.StorageManager',
        storage_dir=config.storage_dir
    )

    # ============================================================================
    # DICOM Controller (controllers/dicom/)
    # ============================================================================

    study_monitor = providers.Singleton(
        'receiver.controllers.dicom.StudyMonitor',
        timeout=config.study_timeout
    )

    # ============================================================================
    # Query Handlers (controllers/dicom/query_handlers/)
    # ============================================================================

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

    # Query handlers dictionary for C-FIND
    query_handlers = providers.Dict(
        PATIENT=patient_query_handler,
        STUDY=study_query_handler,
        SERIES=series_query_handler,
        IMAGE=image_query_handler
    )

    # ============================================================================
    # DICOM Service Provider (controllers/dicom/)
    # ============================================================================

    dicom_service_provider = providers.Singleton(
        'receiver.controllers.dicom.DicomServiceProvider',
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

    Loads configuration from Django settings and initializes the container.
    Called once during application startup (in apps.py).

    Returns:
        Configured Container instance with all settings loaded
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
