from dataclasses import dataclass
try:
    from .event_bus import Event
except ImportError:
    class Event: pass

@dataclass
class FinanceDataChanged(Event):
    entity: str
    action: str
    entity_id: int | None = None
