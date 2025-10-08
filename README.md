# ITH DICOM Proxy

A Django-based DICOM proxy service that enables secure medical imaging workflows with PHI anonymization and de-anonymization capabilities. This proxy acts as an intermediary between DICOM modalities and the ITH platform.

## Overview

The ITH DICOM Proxy is a standalone service that receives medical images from DICOM-enabled devices (CT scanners, MRI machines, etc.), processes them securely, and integrates with the ITH backend for storage and analysis.

## Key Features

- **DICOM Protocol Support**: Full support for C-ECHO, C-STORE, C-FIND, C-GET, and C-MOVE operations
- **PHI Protection**: Automatic anonymization of Protected Health Information (PHI) with reversible de-anonymization for authorized users
- **Backend Integration**: Real-time communication with ITH backend via REST API and WebSocket
- **Flexible Configuration**: Dynamic configuration through backend API or local database
- **Node Management**: Support for dispatching studies to multiple PACS nodes
- **Study Tracking**: Complete tracking of DICOM studies, series, and instances with status management

## Installation

### Prerequisites

**Option 1: Docker (Recommended)**
- Docker Engine 20.10+
- Docker Compose 2.0+

**Option 2: Native Python**
- Python 3.11+
- pip package manager

### Option 1: Docker Setup (Recommended)

#### Option 1A: SQLite (Default - Simplest)

1. Clone the repository and navigate to the project directory

2. Copy the environment configuration:
```bash
cp .env.example .env
```

3. Edit `.env` and configure:
   - `ITH_URL`: URL of your ITH backend (use `http://host.docker.internal:8000` for local backend)
   - `ITH_TOKEN`: Authentication key from ITH dashboard
   - `DICOM_PORT`: Port for DICOM service (default: 11112)
   - `DICOM_AE_TITLE`: AE title for this proxy (default: DICOMRCV)

4. Build and start the container:
```bash
docker-compose up -d
```

The database will be stored in `./storage/database/db.sqlite3` and persisted on the host.

#### Option 1B: PostgreSQL (Production)

1. Clone the repository and navigate to the project directory

2. Copy the environment configuration:
```bash
cp .env.example .env
```

3. Edit `.env` and configure:
   - `ITH_URL`: URL of your ITH backend
   - `ITH_TOKEN`: Authentication key from ITH dashboard
   - `POSTGRES_USER`: PostgreSQL username (default: postgres)
   - `POSTGRES_PASSWORD`: PostgreSQL password (default: postgres)
   - `POSTGRES_DB`: Database name (default: ith_proxy)

4. Build and start with PostgreSQL:
```bash
docker-compose -f docker-compose.postgres.yml up -d
```

This will start both the proxy and a PostgreSQL database container.

#### Common Docker Commands

**View logs:**
```bash
# All logs
docker-compose logs -f

# Only proxy logs
docker-compose logs -f proxy

# Only database logs (PostgreSQL)
docker-compose -f docker-compose.postgres.yml logs -f db
```

**Stop containers:**
```bash
# SQLite setup
docker-compose down

# PostgreSQL setup
docker-compose -f docker-compose.postgres.yml down
```

**Reset everything (WARNING: deletes all data):**
```bash
# SQLite setup
docker-compose down -v
rm -rf storage/

# PostgreSQL setup
docker-compose -f docker-compose.postgres.yml down -v
rm -rf storage/
```

### Option 2: Native Python Setup

1. Clone the repository and navigate to the project directory

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the environment configuration:
```bash
cp .env.example .env
```

4. Edit `.env` and configure:
   - `ITH_URL`: URL of your ITH backend
   - `ITH_TOKEN`: Authentication key from ITH dashboard
   - `DICOM_PORT`: Port for DICOM service (default: 11112)
   - `DICOM_AE_TITLE`: AE title for this proxy (default: DICOMRCV)

5. Initialize the database:
```bash
python manage.py migrate
```

6. Start the proxy service:
```bash
python manage.py runserver 0.0.0.0:8080
```

## Configuration

The proxy can be configured through:

1. **Environment Variables** (`.env` file): Initial defaults for DICOM settings, backend URL, and authentication
2. **Backend API**: Dynamic configuration fetched from ITH backend on startup
3. **Local Database**: Configuration changes are persisted locally and can be updated via API

### Environment Variables

See `.env.example` for all available configuration options:

- **Django Settings**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- **DICOM Settings**: `DICOM_AE_TITLE`, `DICOM_PORT`, `DICOM_STORAGE_DIR`
- **ITH Integration**: `ITH_URL`, `ITH_TOKEN`
- **Features**: `DICOM_AUTO_START`, `DICOM_ANONYMIZE_PATIENTS`

## Usage

### Connecting DICOM Devices

Configure your DICOM modality (scanner, workstation) to send images to:
- **Host**: IP address of the proxy server
- **Port**: As configured in `DICOM_PORT` (default: 11112)
- **AE Title**: As configured in `DICOM_AE_TITLE` (default: DICOMRCV)

### Testing the Connection

Use DICOM testing tools to verify connectivity:

```bash
# Test connection (C-ECHO)
echoscu <proxy-ip> 11112 -aet TESTAE -aec DICOMRCV

# Send test image (C-STORE)
storescu <proxy-ip> 11112 -aet TESTAE -aec DICOMRCV test.dcm
```

### API Endpoints

The proxy provides REST API endpoints:

- `GET /api/health/` - Health check (public)
- `GET /api/status/` - Detailed status (requires authentication)
- `POST /api/phi-metadata/` - Retrieve PHI metadata for a study (requires authentication)

Authentication requires a valid JWT token from the ITH backend in the Authorization header.

## PHI Anonymization

When enabled, the proxy automatically:
1. Replaces patient name and ID with anonymous identifiers
2. Stores the original values securely in encrypted database
3. Forwards anonymized studies to the backend
4. Allows authorized users to retrieve original PHI when needed

This ensures compliance with privacy regulations while maintaining traceability.

## Node Management

The proxy can dispatch DICOM studies to configured PACS nodes using C-MOVE operations. Nodes are configured through the ITH backend and automatically synchronized with the proxy.

## WebSocket Communication

The proxy maintains a persistent WebSocket connection with the backend for:
- Real-time configuration updates
- Study completion notifications
- Health status monitoring
- Command and control operations

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

**Note**: Additional transfer syntaxes supported through pynetdicom's `StoragePresentationContexts` for C-STORE operations.

### Network Configuration

| Parameter | Default Value | Configurable | Environment Variable |
|-----------|--------------|--------------|---------------------|
| AE Title | DICOMRCV | Yes | DICOM_AE_TITLE |
| Port | 11112 | Yes | DICOM_PORT |
| Bind Address | 0.0.0.0 | Yes | DICOM_BIND_ADDRESS |
| Maximum PDU Size | 16384 bytes | Yes | DICOM_MAX_PDU_SIZE |
| ACSE Timeout | 30 seconds | Yes | DICOM_ACSE_TIMEOUT |
| Maximum Associations | 50 concurrent | Yes | DICOM_MAX_ASSOCIATIONS |
| Study Timeout | 60 seconds | Yes | DICOM_STUDY_TIMEOUT |

### Supported Modalities and SOP Classes

| Modality | DICOM Code | SOP Classes |
|----------|------------|-------------|
| Computed Tomography | CT | CT Image Storage, Enhanced CT Image Storage |
| Positron Emission Tomography | PT | PET Image Storage, Enhanced PET Image Storage |
| Magnetic Resonance | MR | MR Image Storage, Enhanced MR Image Storage, Enhanced MR Color Image Storage |

**Note**: The proxy is specifically configured for CT, PET, and MR modalities. Other modalities are not currently supported.

### Query/Retrieve Information Models

| Model | C-FIND | C-MOVE | C-GET |
|-------|--------|--------|-------|
| Study Root Query/Retrieve | ✓ | ✓ | ✓ |
| Patient Root Query/Retrieve | ✓ | ✓ | ✓ |

## Storage

DICOM files are stored locally in the configured `DICOM_STORAGE_DIR`:
```
storage/
├── studies/
│   ├── <study-uid>/
│   │   ├── <series-uid>/
│   │   │   └── <instance-uid>.dcm
└── logs/
    └── main.log
```

## Security

- JWT-based authentication for API endpoints
- PHI encryption at rest using Fernet symmetric encryption
- Secure WebSocket communication with backend
- Audit logging for PHI access

## Development

### Docker Development

**Build and run in development mode:**
```bash
docker-compose up --build
```

**Execute commands inside container:**
```bash
# Run migrations
docker-compose exec proxy python manage.py migrate

# Create superuser
docker-compose exec proxy python manage.py createsuperuser

# Run tests
docker-compose exec proxy python manage.py test receiver

# Access Django shell
docker-compose exec proxy python manage.py shell

# Access container shell
docker-compose exec proxy /bin/bash
```

**View specific log files:**
```bash
# DICOM operations log
docker-compose exec proxy tail -f /app/storage/logs/dicom.log

# API requests log
docker-compose exec proxy tail -f /app/storage/logs/api.log

# Error log
docker-compose exec proxy tail -f /app/storage/logs/error.log
```

**Rebuild container after code changes:**
```bash
docker-compose down
docker-compose up --build -d
```

### Native Python Development

**Running Tests:**
```bash
python manage.py test receiver
```

**Database Migrations:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Development Server:**
```bash
python manage.py runserver 0.0.0.0:8080
```

## Troubleshooting

### DICOM Connection Issues

- Verify firewall rules allow incoming connections on DICOM port
- Check AE title configuration matches on both modality and proxy
- Review logs in `storage/logs/` for connection errors

### Backend Integration Issues

- Verify `ITH_URL` is accessible from the proxy
- Check `ITH_TOKEN` is valid and not expired
- Review WebSocket connection status in logs

## Support

For issues and questions, please contact ITH support or refer to the documentation.

## License

Proprietary - IMAGE TECH HUB.
