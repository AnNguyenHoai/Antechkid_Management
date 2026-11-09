"""Explicit local UAT-only activation gate for Tuition Engine V1.

Default remains CLOSED in every normal executable. No remote state, migration
or Enrollment is changed by enabling the gate itself.
"""
from __future__ import annotations

import os


UAT_ENV_NAME = "ANTECHKIDS_TUITION_V1_UAT"


def tuition_v1_uat_enabled() -> bool:
    """Only an exact local opt-in unlocks experimental operator controls."""
    return os.environ.get(UAT_ENV_NAME, "") == "1"
