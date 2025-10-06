"""
Base WebSocket Event class.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class WebSocketEvent:
    """
    Base class for all WebSocket events.
    All events share common fields: event_type, workspace_id, timestamp, correlation_id, entity_type, entity_id, payload
    """
    event_type: str = ""
    workspace_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> Dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()
