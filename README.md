# ITH DICOM Proxy

A Django-based DICOM proxy service that enables secure medical imaging workflows with PHI anonymization and de-anonymization capabilities. This proxy acts as an intermediary between DICOM modalities and the ITH platform.

The proxy receives medical images from DICOM-enabled devices (CT scanners, MRI machines, etc.), processes them securely, and integrates with the ITH backend for storage and analysis.

## Key Features

- **DICOM Protocol Support**: Full support for C-ECHO, C-STORE, C-FIND, C-GET, and C-MOVE operations
- **PHI Protection**: Automatic anonymization of Protected Health Information (PHI) with reversible de-anonymization for authorized users
- **Backend Integration**: Real-time communication with ITH backend via REST API and WebSocket
- **Flexible Configuration**: Dynamic configuration through backend API or local database
- **Node Management**: Support for dispatching studies to multiple PACS nodes
- **Study Tracking**: Complete tracking of DICOM studies, series, and instances with status management

## Quick Start

### Docker Setup (Recommended)

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd proxy
   cp .env.example .env
   ```

2. **Edit `.env` with your settings:**
   ```bash
   ITH_URL=https://your-backend-url.com
   ITH_TOKEN=your-authentication-token
   DICOM_AE_TITLE=YOUR_AE_TITLE
   ```

3. **Start the proxy:**
   ```bash
   docker-compose up -d
   ```

The proxy will be available at:
- HTTP API: `http://localhost:8080`
- DICOM SCP: `localhost:11112`

### Native Python Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Initialize and start:**
   ```bash
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8080
   ```

## Environment Variables

Configure the proxy through the `.env` file. Key variables:

### Django Settings
- `SECRET_KEY`: Django secret key (change in production)
- `DEBUG`: Enable debug mode (`True`/`False`)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### DICOM Configuration
- `DICOM_AE_TITLE`: AE title for this proxy (default: `DICOMRCV`)
- `DICOM_PORT`: DICOM service port (default: `11112`)
- `DICOM_BIND_ADDRESS`: Bind address (empty = all interfaces)
- `DICOM_STORAGE_DIR`: Storage directory for DICOM files (default: `data`)
- `DICOM_LOG_DIR`: Log directory (default: `data/logs`)
- `DICOM_STUDY_TIMEOUT`: Study completion timeout in seconds (default: `60`)
- `DICOM_MAX_PDU_SIZE`: Maximum PDU size in bytes (default: `16384`)
- `DICOM_ACSE_TIMEOUT`: Association timeout in seconds (default: `30`)
- `DICOM_DIMSE_TIMEOUT`: DIMSE message timeout (default: `60`)
- `DICOM_NETWORK_TIMEOUT`: General network timeout (default: `60`)
- `DICOM_MAX_ASSOCIATIONS`: Max concurrent associations (default: `50`)
- `DICOM_LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `DICOM_ANONYMIZE_PATIENTS`: Enable PHI anonymization (default: `True`)
- `DICOM_AUTO_START`: Auto-start DICOM server with Django (default: `True`)

### ITH Backend Integration
- `ITH_URL`: ITH backend URL (required)
- `ITH_TOKEN`: Authentication token from ITH dashboard (required)
- `PROXY_VERSION`: Proxy software version (default: `1.0.0`)

### Archive & Upload
- `ARCHIVE_DIR`: Archive directory for ZIP files (default: `data/archives`)
- `UPLOAD_MAX_RETRIES`: Max upload retry attempts (default: `3`)
- `UPLOAD_RETRY_DELAY`: Delay between retries in seconds (default: `5`)
- `CLEANUP_AFTER_UPLOAD`: Delete files after successful upload (default: `True`)

### Database Configuration
- `DATABASE_ENGINE`: Database type (`sqlite` or `postgresql`)
- `DATABASE_PATH`: SQLite database path (default: `data/database/db.sqlite3`)
- `POSTGRES_DB`: PostgreSQL database name
- `POSTGRES_USER`: PostgreSQL username
- `POSTGRES_PASSWORD`: PostgreSQL password
- `POSTGRES_HOST`: PostgreSQL host
- `POSTGRES_PORT`: PostgreSQL port

See `.env.example` for complete documentation.

## PHI Anonymization

When enabled (`DICOM_ANONYMIZE_PATIENTS=True`), the proxy automatically:

1. **Anonymizes**: Replaces patient name and ID with anonymous identifiers
2. **Encrypts**: Stores original values securely in encrypted database
3. **Forwards**: Sends anonymized studies to the backend
4. **De-anonymizes**: Allows authorized users to retrieve original PHI when needed

This ensures compliance with privacy regulations (HIPAA, GDPR) while maintaining traceability.

### Anonymization Process

- Patient Name → `ANON-{hash}`
- Patient ID → `ANON-{hash}`
- Original values encrypted with Fernet symmetric encryption
- Mapping stored in database for authorized retrieval

## DICOM Conformance

### Supported DICOM Operations

| Service Class | Operation | Role | Description |
|--------------|-----------|------|-------------|
| Verification | C-ECHO | SCP | Connectivity verification and echo requests |
| Verification | C-ECHO | SCU | Verify connectivity to remote PACS nodes |
| Storage | C-STORE | SCP | Receive and store DICOM images from modalities |
| Storage | C-STORE | SCU | Send DICOM objects to remote PACS nodes |
| Query/Retrieve | C-FIND | SCP | Query for studies, series, and instances |
| Query/Retrieve | C-GET | SCP | Retrieve DICOM objects from proxy storage |
| Query/Retrieve | C-MOVE | SCP | Move DICOM objects to specified destinations |
| Query/Retrieve | C-MOVE | SCU | Dispatch studies to configured PACS nodes |

### Supported Transfer Syntaxes

| Transfer Syntax | UID |
|----------------|-----|
| Implicit VR Little Endian | 1.2.840.10008.1.2 |
| Explicit VR Little Endian | 1.2.840.10008.1.2.1 |

**Note**: Additional transfer syntaxes supported through pynetdicom's `StoragePresentationContexts`.

### Network Configuration Defaults

| Parameter | Default Value | Environment Variable |
|-----------|--------------|---------------------|
| AE Title | DICOMRCV | DICOM_AE_TITLE |
| Port | 11112 | DICOM_PORT |
| Bind Address | 0.0.0.0 | DICOM_BIND_ADDRESS |
| Maximum PDU Size | 16384 bytes | DICOM_MAX_PDU_SIZE |
| ACSE Timeout | 30 seconds | DICOM_ACSE_TIMEOUT |
| DIMSE Timeout | 60 seconds | DICOM_DIMSE_TIMEOUT |
| Network Timeout | 60 seconds | DICOM_NETWORK_TIMEOUT |
| Maximum Associations | 50 concurrent | DICOM_MAX_ASSOCIATIONS |
| Study Timeout | 60 seconds | DICOM_STUDY_TIMEOUT |

### Supported Modalities

| Modality | DICOM Code | SOP Classes |
|----------|------------|-------------|
| Computed Tomography | CT | CT Image Storage, Enhanced CT Image Storage |
| Positron Emission Tomography | PT | PET Image Storage, Enhanced PET Image Storage |
| Magnetic Resonance | MR | MR Image Storage, Enhanced MR Image Storage, Enhanced MR Color Image Storage |

**Note**: The proxy is specifically configured for CT, PET, and MR modalities.

### Query/Retrieve Information Models

| Model | C-FIND | C-MOVE | C-GET |
|-------|--------|--------|-------|
| Study Root Query/Retrieve | ✓ | ✓ | ✓ |
| Patient Root Query/Retrieve | ✓ | ✓ | ✓ |

## Usage

### Connecting DICOM Devices

Configure your DICOM modality to send images to:
- **Host**: IP address of the proxy server
- **Port**: `11112` (or your configured `DICOM_PORT`)
- **AE Title**: `DICOMRCV` (or your configured `DICOM_AE_TITLE`)

## Docker Commands

### View Logs
```bash
docker-compose logs -f          # All logs
docker-compose logs -f proxy    # Proxy logs only
```

### Management Commands
```bash
# Run migrations
docker-compose exec proxy python manage.py migrate

# Create superuser
docker-compose exec proxy python manage.py createsuperuser

# Access Django shell
docker-compose exec proxy python manage.py shell

# Access container shell
docker-compose exec proxy /bin/bash
```

### Stop and Reset
```bash
# Stop containers
docker-compose down

# Reset everything (WARNING: deletes all data)
docker-compose down -v
rm -rf data/
```

## PostgreSQL Setup

For production deployments, use PostgreSQL:

```bash
# Start with PostgreSQL
docker-compose -f docker-compose.postgres.yml up -d

# View logs
docker-compose -f docker-compose.postgres.yml logs -f

# Stop
docker-compose -f docker-compose.postgres.yml down
```

Configure PostgreSQL settings in `.env`:
```bash
DATABASE_ENGINE=postgresql
POSTGRES_DB=ith_proxy
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

## Support

For issues and questions, please contact ITH support or refer to the documentation.

## License

Proprietary - IMAGE TECH HUB.
