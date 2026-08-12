from enum import Enum, auto
from typing import Callable, List, Tuple

class RuntimeState(Enum):
    BOOTSTRAP = auto()
    SYNCHRONIZING = auto()
    READY = auto()
    WRITE = auto()
    PUBLISHING = auto()
    RECOVERING = auto()
    OFFLINE = auto()
    ERROR = auto()

class RuntimeStateMachine:
    def __init__(self):
        self._state = RuntimeState.BOOTSTRAP
        self._listeners: List[Callable[[RuntimeState, RuntimeState], None]] = []

    @property
    def state(self) -> RuntimeState:
        return self._state

    def transition_to(self, new_state: RuntimeState) -> bool:
        old = self._state
        # Simple validation: cannot transition from ERROR to anything except RECOVERING? 
        # We'll keep it permissive.
        self._state = new_state
        for listener in self._listeners:
            try:
                listener(old, new_state)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Listener error")
        return True

    def add_listener(self, callback: Callable[[RuntimeState, RuntimeState], None]):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[RuntimeState, RuntimeState], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)