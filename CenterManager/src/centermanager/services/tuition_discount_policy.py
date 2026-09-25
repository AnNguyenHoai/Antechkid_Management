"""Enrollment-level tuition discount policy.

The policy resolves a business rule into the canonical ``discount_amount``
snapshot consumed by TuitionAccrualService.  It deliberately has no knowledge
of Class persistence, Outstanding, FinancePeriod, or promotion configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional


_MONEY_QUANTUM = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class DiscountType(str, Enum):
    FIXED = "FIXED"
    PERCENT = "PERCENT"


class TuitionDiscountPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class TuitionDiscountSnapshot:
    discount_type: Optional[str]
    discount_value: Optional[Decimal]
    discount_amount: Decimal
    discount_source: Optional[str]
    discount_reason: Optional[str]
    discount_policy_version: Optional[str]


class TuitionDiscountPolicy:
    """Resolve fixed/percentage rules against a snapshotted gross contract fee."""

    VERSION = "enrollment_discount_v1"
    SOURCE_MANUAL = "MANUAL"
    APPROVED_SOURCES = frozenset({SOURCE_MANUAL})

    @classmethod
    def resolve(
        cls,
        gross_fee,
        *,
        discount_type: Optional[str] = None,
        discount_value=None,
        source: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> TuitionDiscountSnapshot:
        try:
            gross = _money(Decimal(str(gross_fee)))
        except Exception as exc:
            raise TuitionDiscountPolicyError("Gross fee must be a valid number.") from exc
        if gross < 0:
            raise TuitionDiscountPolicyError("Gross fee cannot be negative.")

        if discount_type is None and discount_value in (None, "", 0, Decimal("0")):
            return TuitionDiscountSnapshot(None, None, Decimal("0.0000"), None, None, None)
        if discount_type is None:
            raise TuitionDiscountPolicyError("Discount type is required when a discount value is provided.")

        try:
            kind = DiscountType(str(getattr(discount_type, "value", discount_type)).strip().upper())
        except ValueError as exc:
            raise TuitionDiscountPolicyError("Discount type must be FIXED or PERCENT.") from exc
        try:
            value = _money(Decimal(str(discount_value)))
        except Exception as exc:
            raise TuitionDiscountPolicyError("Discount value must be a valid number.") from exc
        if value < 0:
            raise TuitionDiscountPolicyError("Discount value cannot be negative.")

        if kind == DiscountType.PERCENT:
            if value > Decimal("100"):
                raise TuitionDiscountPolicyError("Percentage discount cannot exceed 100%.")
            amount = _money(gross * value / Decimal("100"))
        else:
            amount = value

        if amount > gross:
            raise TuitionDiscountPolicyError("Discount amount cannot exceed the agreed course fee.")

        normalized_source = (source or "").strip().upper() or None
        if normalized_source is not None and normalized_source not in cls.APPROVED_SOURCES:
            raise TuitionDiscountPolicyError(
                "Only MANUAL discount source is approved; promotion engine rules are not enabled."
            )
        normalized_reason = (reason or "").strip() or None
        return TuitionDiscountSnapshot(
            discount_type=kind.value,
            discount_value=value,
            discount_amount=amount,
            discount_source=normalized_source,
            discount_reason=normalized_reason,
            discount_policy_version=cls.VERSION,
        )
