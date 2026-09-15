import uuid
from datetime import datetime
from typing import Optional

class EditSessionManager:
    def __init__(self):
        self._session_id: Optional[str] = None
        self._owner: Optional[str] = None
        self._started_at: Optional[datetime] = None
        self._state: str = "IDLE"

    def start_session(self, owner: str) -> str:
        self._session_id = str(uuid.uuid4())
        self._owner = owner
        self._started_at = datetime.now()
        self._state = "ACTIVE"
        return self._session_id

    def end_session(self) -> None:
        self._session_id = None
        self._owner = None
        self._started_at = None
        self._state = "IDLE"

    def get_session_id(self) -> Optional[str]:
        return self._session_id

    def get_owner(self) -> Optional[str]:
        return self._owner

    def is_active(self) -> bool:
        return self._state == "ACTIVE"