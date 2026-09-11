from abc import ABC, abstractmethod
from typing import Optional

class IdentityProvider(ABC):
    @abstractmethod
    def current_user(self) -> Optional[object]:
        pass

    @abstractmethod
    def current_user_id(self) -> Optional[str]:
        pass

    @abstractmethod
    def current_role(self) -> Optional[str]:
        pass