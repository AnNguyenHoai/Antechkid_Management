# -*- coding: utf-8 -*-
"""
UI helpers for student display.
"""
from datetime import date
from typing import Optional


def calculate_age(birth_date: Optional[date], reference_date: Optional[date] = None) -> Optional[int]:
    """
    Calculate age from birth_date.
    If reference_date is None, use today's date.
    Returns None if birth_date is None.
    """
    if birth_date is None:
        return None
    today = reference_date if reference_date is not None else date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def format_date_for_display(dt: Optional[date]) -> str:
    """Format date as dd/mm/yyyy or empty string if None."""
    if dt is None:
        return ""
    return dt.strftime("%d/%m/%Y")


def format_status(status: Optional[str]) -> str:
    """Return status or empty string if None."""
    return status or ""


def format_age_for_display(age: Optional[int]) -> str:
    """Return age as string or '-' if None."""
    if age is None:
        return "-"
    return str(age)