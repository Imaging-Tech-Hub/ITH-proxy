# WebSocket Events Structure

## Directory Organization

```
events/
├── base.py                          # Base WebSocketEvent class
├── incoming/                        # Incoming events (from ITH backend)
│   ├── ping.py                      # Keep-alive ping
│   ├── session_deleted.py           # Session deletion notification
│   ├── scan_deleted.py              # Scan deletion notification
│   ├── subject_dispatch.py          # Subject download dispatch
│   ├── session_dispatch.py          # Session download dispatch
│   ├── scan_dispatch.py             # Scan download dispatch
│   ├── proxy_nodes_changed.py       # Node configuration update
│   ├── proxy_config_changed.py      # Proxy configuration update
│   └── proxy_status_changed.py      # Proxy status update
└── outgoing/                        # Outgoing events (to ITH backend)
    ├── pong.py                      # Pong response
    ├── dispatch_status.py           # Dispatch operation status
    └── proxy_heartbeat.py           # Proxy health status
```

## Incoming Events (events/incoming/)

Events received from the ITH backend that the proxy must handle.

### Ping Event
- **Type**: `ping`
- **Purpose**: Keep-alive message
- **Action**: Respond with pong

### Deletion Events
- **session.deleted**: Remove session from local PACS
- **scan.deleted**: Remove scan from local PACS

### Dispatch Events
- **subject.dispatch**: Download subject to specified nodes
- **session.dispatch**: Download session to specified nodes
- **scan.dispatch**: Download scan to specified nodes

### Configuration Events
- **proxy.nodes_changed**: Update node configuration
- **proxy.config_changed**: Update proxy settings
- **proxy.status_changed**: Change proxy operational status

## Outgoing Events (events/outgoing/)

Events sent from the proxy to the ITH backend.

### Pong Event
- **Type**: `pong`
- **Purpose**: Response to ping, confirms connection alive

### Dispatch Status Event
- **Type**: `dispatch.status`
- **Purpose**: Inform backend about dispatch progress
- **Payload**: node_id, status, progress, files_sent, files_total, error

### Proxy Heartbeat Event
- **Type**: `proxy.heartbeat`
- **Purpose**: Periodic health status update
- **Payload**: status, nodes_online, nodes_total, active_dispatches, disk_usage_gb, version

## Base Event Structure

All events inherit from `WebSocketEvent` with these fields:

```python
@dataclass
class WebSocketEvent:
    event_type: str                    # Event type identifier
    workspace_id: str                  # Workspace ID
    timestamp: str                     # ISO 8601 timestamp
    correlation_id: str                # Correlation ID for tracking
    entity_type: Optional[str]         # Entity type (subject/session/scan/proxy)
    entity_id: Optional[str]           # Entity ID
    payload: Dict[str, Any]            # Event-specific data
```

## Usage Example

### Creating Events

```python
# Incoming event (would be received from backend)
from receiver.websockets.events.incoming import SessionDispatchEvent

event = SessionDispatchEvent.create(
    workspace_id="ws_123",
    session_id="sess_456",
    subject_id="subj_789",
    nodes=["node_1", "node_2"],
    session_label="MRI-2025-001",
    priority="high"
)

# Outgoing event (sent to backend)
from receiver.websockets.events.outgoing import DispatchStatusEvent

status = DispatchStatusEvent.create(
    workspace_id="ws_123",
    entity_type="session",
    entity_id="sess_456",
    node_id="node_1",
    status="completed",
    files_sent=150,
    files_total=150,
    progress=100
)
```

### Serializing Events

```python
# Convert to dictionary for JSON
event_dict = event.to_dict()

# Send via WebSocket
await websocket.send(json.dumps(event_dict))
```
