# -*- coding: utf-8 -*-
"""Business Module Integration."""

from .business_module import BusinessModule, BusinessModuleLifecycle
from .workspace_registration import WorkspaceRegistration
from .guard import WriteGuard, ReadGuard, PermissionGuard
from .module_registry import BusinessModuleRegistry   # <-- THÊM

__all__ = [
    "BusinessModule",
    "BusinessModuleLifecycle",
    "WorkspaceRegistration",
    "WriteGuard",
    "ReadGuard",
    "PermissionGuard",
    "BusinessModuleRegistry",   # <-- THÊM
]