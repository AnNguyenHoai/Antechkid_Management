from typing import Optional
from .identity_provider import IdentityProvider
from centermanager.core.current_user import get_current_user

class DefaultIdentityProvider(IdentityProvider):
    def current_user(self) -> Optional[object]:
        return get_current_user()

    def current_user_id(self) -> Optional[str]:
        user = self.current_user()
        return user.username if user else None

    def current_role(self) -> Optional[str]:
        user = self.current_user()
        return user.role.name if user and user.role else None