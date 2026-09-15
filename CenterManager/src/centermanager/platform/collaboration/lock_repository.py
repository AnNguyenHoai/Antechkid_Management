from abc import ABC, abstractmethod
from typing import Dict, Any

class LockRepository(ABC):
    @abstractmethod
    def get_lock(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_lock(self, data: Dict[str, Any]) -> None:
        pass