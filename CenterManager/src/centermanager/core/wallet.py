from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple, Union


class Wallet(str, Enum):
    """Canonical Wallet V2 money locations."""

    CASH = "CASH"
    BANK = "BANK"


class WalletMappingError(ValueError):
    """Raised when a payment-method value cannot be mapped safely to a Wallet."""

    def __init__(self, value: Optional[str]) -> None:
        self.value = value
        super().__init__(f"Unknown wallet alias: {value!r}.")


# These are persistence/read compatibility aliases, not additional wallets.
# New writes use the canonical enum values above.
_WALLET_ALIASES = {
    Wallet.CASH: (
        Wallet.CASH.value,
        "Cash",
        "TÀI KHOẢN CÁ NHÂN",
    ),
    Wallet.BANK: (
        Wallet.BANK.value,
        "Bank",
        "Bank Transfer",
        "TÀI KHOẢN CÔNG TY",
    ),
}


def _normalized_alias(value: str) -> str:
    return value.strip().replace("_", " ").casefold()


def resolve_wallet(value: Union[str, Wallet]) -> Wallet:
    """Resolve a canonical/legacy value without guessing unknown aliases."""

    if isinstance(value, Wallet):
        return value
    if not isinstance(value, str) or not value.strip():
        raise WalletMappingError(value if isinstance(value, str) else None)

    normalized = _normalized_alias(value)
    for wallet, aliases in _WALLET_ALIASES.items():
        if normalized in {_normalized_alias(alias) for alias in aliases}:
            return wallet
    raise WalletMappingError(value)


def canonical_wallet_value(value: Union[str, Wallet]) -> str:
    """Return the canonical persistence value for a known Wallet alias."""

    return resolve_wallet(value).value


def wallet_aliases(value: Union[str, Wallet]) -> Tuple[str, ...]:
    """Return all known persisted aliases for the resolved Wallet."""

    return _WALLET_ALIASES[resolve_wallet(value)]


def is_known_wallet_alias(value: Optional[str]) -> bool:
    try:
        resolve_wallet(value)  # type: ignore[arg-type]
        return True
    except WalletMappingError:
        return False
