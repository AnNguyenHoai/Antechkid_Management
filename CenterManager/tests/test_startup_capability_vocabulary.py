"""Regression coverage for startup capability vocabulary integrity."""

from centermanager.core.capabilities import Capability
from centermanager.models.permission import PermissionDefinitions


def test_work_registration_self_alias_is_canonical():
    assert PermissionDefinitions.WORK_REGISTRATION_SELF == Capability.WORK_REGISTRATION_SELF.value


def test_all_workspace_registration_capabilities_are_registered():
    assert Capability.WORK_REGISTRATION_SELF.value in Capability.values()
    assert Capability.WORK_REGISTRATION_VIEW_ALL.value in Capability.values()
    assert Capability.WORK_REGISTRATION_MANAGE.value in Capability.values()
