from abc import ABC, abstractmethod
from typing import Dict, Any

class MetadataRepository(ABC):
    @abstractmethod
    def load_lock(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_lock(self, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load_version(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_version(self, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load_deployment(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_deployment(self, data: Dict[str, Any]) -> None:
        pass