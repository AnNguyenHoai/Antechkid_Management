# -*- coding: utf-8 -*-
"""Versioned SEC-02 IPC contract.

No operation in this protocol is allowed to return the raw SQLCipher workspace key.
The eventual Windows service owns key unsealing and protected file access; callers
request operations/results only.
"""
from __future__ import annotations

from enum import Enum

PROTOCOL_VERSION = 1
SERVICE_NAME = "AnTechKidsData"
SERVICE_SID = rf"NT SERVICE\{SERVICE_NAME}"
SERVICE_PIPE_NAME = r"\\.\pipe\AnTechKidsData.v1"


class ProtectedDataOperation(str, Enum):
    HEALTH = "health"
    VALIDATE_DATABASE = "validate_database"
    CREATE_BACKUP = "create_backup"


# Destructive operations such as restore/reset/rekey are intentionally excluded
# from protocol v1. SEC-04 must add an authenticated admin authorization envelope
# before those operations can cross the service boundary.
READ_ONLY_OR_SAFE_OPERATIONS = frozenset(ProtectedDataOperation)
