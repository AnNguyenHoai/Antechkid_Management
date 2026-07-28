# -*- coding: utf-8 -*-
"""
Tests for student UI helpers.
"""
from datetime import date
import pytest

from centermanager.ui.students.helpers import (
    calculate_age,
    format_date_for_display,
    format_age_for_display,
)

def test_calculate_age_birthday_occurred():
    dob = date(2015, 6, 15)
    ref = date(2026, 7, 27)
    assert calculate_age(dob, ref) == 11

def test_calculate_age_birthday_not_yet():
    dob = date(2015, 8, 20)
    ref = date(2026, 7, 27)
    assert calculate_age(dob, ref) == 10

def test_calculate_age_birthday_today():
    dob = date(2015, 7, 27)
    ref = date(2026, 7, 27)
    assert calculate_age(dob, ref) == 11

def test_calculate_age_none():
    assert calculate_age(None) is None

def test_format_date_for_display():
    d = date(2026, 7, 27)
    assert format_date_for_display(d) == "27/07/2026"
    assert format_date_for_display(None) == ""

def test_format_age_for_display():
    assert format_age_for_display(10) == "10"
    assert format_age_for_display(None) == "-"