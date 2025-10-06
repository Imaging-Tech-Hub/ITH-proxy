# WebSocket System for Proxy Real-time Communication

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Laminate Backend                            │
│                                                                 │
│  Sends events:                                                  │
│  - ping (keep-alive)                                            │
│  - *.deleted (session/scan deletions)                           │
│  - *.dispatch (download requests)                               │
│  - proxy.* (configuration updates)                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ WebSocket (wss://)
                       │ ws://host/proxy/ws?proxy_key=pk_xxx
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ProxyConsumer                                │
│                (consumer.py)                                    │
│                                                                 │
│  - Authenticates proxy via proxy_key                            │
│  - One connection per proxy (disconnects old)                   │
│  - Routes events to handlers                                    │
│  - Sends heartbeat every 30s                                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ Routes to handlers
                       │
        ┌──────────────┼──────────────┬──────────────┐
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐
│  Ping    │  │  Deletion    │  │ Dispatch  │  │  Config  │
│ Handler  │  │  Handlers    │  │ Handlers  │  │ Handlers │
└──────────┘  └──────────────┘  └───────────┘  └──────────┘
     │             │                  │              │
     │             │                  │              │
     ▼             ▼                  ▼              ▼
  Respond    Delete from DB    Download & Send   Update Config
  with Pong                     to PACS Nodes     Files
```

## Directory Structure

```
websockets/
├── consumer.py                      # Main WebSocket consumer
├── events/                          # Event definitions
│   ├── base.py                      # Base event class
│   ├── in/                          # Incoming events (from backend)
│   │   ├── ping.py
│   │   ├── session_deleted.py
│   │   ├── scan_deleted.py
│   │   ├── subject_dispatch.py
│   │   ├── session_dispatch.py
│   │   ├── scan_dispatch.py
│   │   ├── proxy_nodes_changed.py
│   │   ├── proxy_config_changed.py
│   │   └── proxy_status_changed.py
│   └── out/                         # Outgoing events (to backend)
│       ├── pong.py
│       ├── dispatch_status.py
│       └── proxy_heartbeat.py
└── handlers/                        # Event handlers
    ├── base.py                      # Base handler class
    ├── ping_handler.py              # Ping/pong handler
    ├── deletion_handlers.py         # Session/scan deletion
    ├── dispatch_handlers.py         # Download dispatches
    └── config_handlers.py           # Configuration updates
```

## Event Flow

### Example: Dispatch Event Flow

1. **Backend sends dispatch event:**
   ```json
   {
     "event_type": "session.dispatch",
     "workspace_id": "ws_123",
     "entity_id": "sess_456",
     "correlation_id": "corr_abc",
     "payload": {
       "subject_id": "subj_789",
       "nodes": ["node_1", "node_2"],
       "session_label": "MRI-2025-001",
       "priority": "high"
     }
   }
   ```

2. **ProxyConsumer receives and routes to SessionDispatchHandler**

3. **SessionDispatchHandler logic:**
   ```python
   async def handle(event):
       # 1. Check if nodes are managed by this proxy
       matching_nodes = get_matching_nodes(event.payload.nodes)

       if not matching_nodes:
           return  # Not for this proxy

       # 2. Download session from API in background
       asyncio.create_task(download_and_dispatch())
   ```

4. **Download and dispatch (background task):**
   ```python
   async def download_and_dispatch():
       # Send initial status
       send_status("downloading")

       # Download from Laminate API
       result = DownloadSessionCommand(...).execute()

       # Extract files
       extract_archive(result.file_path)

       # Send to PACS nodes
       SendDICOMToMultipleNodesCommand(
           nodes=matching_nodes,
           directory=extracted_path
       ).execute()

       # Send completion status
       send_status("completed", files_sent=150)
   ```

5. **Proxy sends status updates to backend:**
   ```json
   {
     "event_type": "dispatch.status",
     "correlation_id": "corr_abc",
     "entity_type": "session",
     "entity_id": "sess_456",
     "payload": {
       "status": "completed",
       "files_sent": 150,
       "files_total": 150,
       "progress": 100
     }
   }
   ```

## Handler Responsibilities

### Ping Handler (`ping_handler.py`)
- **Receives:** `ping` events
- **Action:** Responds with `pong`
- **Purpose:** Keep connection alive

### Deletion Handlers (`deletion_handlers.py`)

#### SessionDeletedHandler
- **Receives:** `session.deleted` events
- **Actions:**
  1. Find session by `study_instance_uid`
  2. Delete session from database (cascades to scans)
  3. Clean up patient mapping if orphaned
  4. Remove storage files

#### ScanDeletedHandler
- **Receives:** `scan.deleted` events
- **Actions:**
  1. Find scan by `study_instance_uid` + `scan_number`
  2. Delete scan from database
  3. Remove storage files

### Dispatch Handlers (`dispatch_handlers.py`)

All dispatch handlers follow similar pattern:
1. Check if requested nodes are managed by this proxy
2. Download entity from Laminate REST API
3. Extract downloaded archive
4. Send DICOM files to target PACS nodes
5. Report progress to backend

#### SubjectDispatchHandler
- **Receives:** `subject.dispatch`
- **Downloads:** Entire subject (all sessions/scans)
- **Uses:** `DownloadSubjectCommand` + `SendDICOMToMultipleNodesCommand`

#### SessionDispatchHandler
- **Receives:** `session.dispatch`
- **Downloads:** Single session (all scans)
- **Uses:** `DownloadSessionCommand` + `SendDICOMToMultipleNodesCommand`

#### ScanDispatchHandler
- **Receives:** `scan.dispatch`
- **Downloads:** Single scan
- **Uses:** `DownloadScanCommand` + `SendDICOMToMultipleNodesCommand`

### Config Handlers (`config_handlers.py`)

#### ProxyNodesChangedHandler
- **Receives:** `proxy.nodes_changed`
- **Actions:**
  1. Parse node configurations from payload
  2. Save to `~/.laminate-proxy/nodes.json`
  3. Handle actions: `added`, `removed`, `updated`, `replaced`

#### ProxyConfigChangedHandler
- **Receives:** `proxy.config_changed`
- **Actions:**
  1. Apply configuration changes
  2. Save to `~/.laminate-proxy/proxy.json`
  3. Log changes

#### ProxyStatusChangedHandler
- **Receives:** `proxy.status_changed`
- **Actions:**
  1. Update proxy status
  2. Pause operations if `is_active: false`
  3. Resume operations if `is_active: true`

## Connection Management

### Authentication
- Proxy key passed as query parameter: `?proxy_key=pk_xxx`
- Validated on connect
- Rejected if invalid (close code 4003)

### One Connection Per Proxy
- Tracked in `ProxyConsumer.active_connections` dict
- Key: `proxy_key`
- Value: Consumer instance
- Old connection auto-disconnected when new connection with same key

### Heartbeat
- Consumer sends ping every 30 seconds
- Backend responds with pong (or vice versa)
- Maintains connection alive through firewalls/load balancers

## Usage Example

### Testing with wscat
```bash
# Install wscat
npm install -g wscat

# Connect to proxy WebSocket
wscat -c "ws://localhost:8000/proxy/ws?proxy_key=pk_test123"

# You'll receive ping messages every 30s
# Send test dispatch event:
{
  "event_type": "session.dispatch",
  "workspace_id": "ws_123",
  "entity_id": "sess_456",
  "payload": {
    "subject_id": "subj_789",
    "nodes": ["node_1"],
    "session_label": "Test",
    "priority": "normal"
  }
}
```

## Configuration Files

### Node Configuration (`~/.laminate-proxy/nodes.json`)
```json
{
  "nodes": [
    {
      "node_id": "node_1",
      "name": "Main PACS",
      "ae_title": "MAIN_PACS",
      "host": "10.0.1.100",
      "port": 11112,
      "storage_path": "/data/dicom/main",
      "is_active": true
    }
  ]
}
```

### Proxy Status (`~/.laminate-proxy/status.json`)
```json
{
  "status": "active",
  "is_active": true,
  "reason": "",
  "updated_at": "2025-10-04T10:30:00.000Z"
}
```

## Error Handling

All handlers implement error handling:
- Log errors with full stack trace
- Send error status to backend for dispatch operations
- Don't disconnect on handler errors
- Use idempotent operations (safe to receive same event twice)

## Next Steps

1. **Install Django Channels:**
   ```bash
   pip install channels channels-redis
   ```

2. **Configure ASGI application:**
   - Update `asgi.py` with Channels routing
   - Add WebSocket URL routing

3. **Install Redis:**
   - Required for Channels layer (pub/sub)
   - Can use in-memory for development

4. **Implement node configuration loading:**
   - Add method to load managed nodes from config
   - Used by dispatch handlers to filter nodes

5. **Add authentication:**
   - Implement real `authenticate_proxy()` method
   - Query database or external API to validate proxy_key
