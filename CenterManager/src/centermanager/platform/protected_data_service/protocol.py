# -*- coding: utf-8 -*-
"""Versioned SEC-02 IPC contract.

The protected-data protocol is operation-oriented. It never exposes the raw
SQLCipher workspace key and never accepts arbitrary SQL. Domain operations that
mutate protected data must be authorized by an authenticated application session
owned by the Windows service.
"""
from __future__ import annotations

from enum import Enum

PROTOCOL_VERSION = 2
SERVICE_NAME = "AnTechKidsData"
SERVICE_SID = rf"NT SERVICE\{SERVICE_NAME}"
SERVICE_PIPE_NAME = r"\\.\pipe\AnTechKidsData.v2"


class ProtectedDataOperation(str, Enum):
    HEALTH = "health"
    VALIDATE_DATABASE = "validate_database"
    CREATE_BACKUP = "create_backup"

    # Service-owned application session lifecycle.
    AUTHENTICATE = "authenticate"
    LOGOUT = "logout"

    # First Phase-B2 vertical slice. These are domain APIs, not table/SQL APIs.
    STUDENT_LIST = "student.list"
    STUDENT_CREATE = "student.create"


UNAUTHENTICATED_OPERATIONS = frozenset({
    ProtectedDataOperation.HEALTH,
    ProtectedDataOperation.VALIDATE_DATABASE,
    ProtectedDataOperation.AUTHENTICATE,
})

SESSION_OPERATIONS = frozenset({
    ProtectedDataOperation.LOGOUT,
    ProtectedDataOperation.STUDENT_LIST,
    ProtectedDataOperation.STUDENT_CREATE,
    ProtectedDataOperation.CREATE_BACKUP,
})

# Raw SQL / raw key / destructive reset/restore/rekey remain intentionally absent.
