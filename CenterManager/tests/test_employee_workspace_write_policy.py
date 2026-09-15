from types import SimpleNamespace

from centermanager.ui.employee_workspace.employee_workspace_write_policy import (
    EmployeeWorkspaceWritePolicy,
)


def capabilities(**overrides):
    values = {
        "employee_update_self": False,
        "employee_update_all": False,
        "schedule_manage": False,
        "attendance_create_self": False,
        "attendance_manage": False,
        "registration_self": False,
        "registration_manage": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_write_lock_never_grants_missing_capabilities():
    policy = EmployeeWorkspaceWritePolicy.resolve(capabilities(), True)

    assert policy.employee_profile_self is False
    assert policy.employee_profile_all is False
    assert policy.schedule_manage is False
    assert policy.working_time_create_self is False
    assert policy.working_time_manage is False
    assert policy.registration_self is False
    assert policy.registration_manage is False


def test_write_lock_gates_each_explicit_capability_independently():
    policy = EmployeeWorkspaceWritePolicy.resolve(
        capabilities(
            employee_update_self=True,
            employee_update_all=False,
            schedule_manage=True,
            attendance_create_self=True,
            attendance_manage=False,
            registration_self=True,
            registration_manage=False,
        ),
        True,
    )

    assert policy.employee_profile_self is True
    assert policy.employee_profile_all is False
    assert policy.schedule_manage is True
    assert policy.working_time_create_self is True
    assert policy.working_time_manage is False
    assert policy.registration_self is True
    assert policy.registration_manage is False


def test_releasing_write_lock_disables_all_mutations():
    policy = EmployeeWorkspaceWritePolicy.resolve(
        capabilities(
            employee_update_self=True,
            employee_update_all=True,
            schedule_manage=True,
            attendance_create_self=True,
            attendance_manage=True,
            registration_self=True,
            registration_manage=True,
        ),
        False,
    )

    assert all(not value for value in policy.__dict__.values())
