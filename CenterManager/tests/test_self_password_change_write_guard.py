"""Real SQLCipher/Git WRITE regressions for self-service password changes.

A staff account must not need user.update/user.manage to change its own
password. Never grant this self-service operation without the usual Git lease.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from tests.test_e1b1_durable_write_recovery import workspace  # noqa: F401
from tests.test_e1b2a_post_publish_consistency import reporting, remote_rows  # noqa: F401
from centermanager.core.current_user import CurrentUserContext
from centermanager.database.mutation_authority import (
    MutationAuthorityError, verified_self_password_change,
)
from centermanager.models.role import Role
from centermanager.models.user import User
from centermanager.security.password import hash_password, verify_password
from centermanager.services.permission_service import (
    AuthenticationError, PermissionService,
)


def _create_test_staff(w):
    # Fixture's admin WRITE authority is restricted to synthetic local Git.
    with w.factory() as db:
        role = Role(name="teacher", display_name="Teacher", is_system=True)
        db.add(role)
        db.flush()
        db.add_all([
            User(id=1, username="staff-self-test", full_name="Synthetic Staff",
                 role_id=role.id, password_hash=hash_password("initial-secret"),
                 is_active=True, force_password_change=True, login_attempts=0),
            User(id=2, username="other-staff-test", full_name="Other Staff",
                 role_id=role.id, password_hash=hash_password("other-secret"),
                 is_active=True, force_password_change=True, login_attempts=0),
        ])
        db.commit()
    return SimpleNamespace(
        id=1, username="synthetic", role=SimpleNamespace(name="teacher"),
        is_active=True, permissions=set(),
    )


def test_staff_first_password_change_publishes_with_no_user_admin_capability(reporting):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    actor = _create_test_staff(w)
    service = PermissionService(w.factory)

    with CurrentUserContext(actor):
        updated = service.change_password(1, "initial-secret", "new-secret")
        assert updated.force_password_change is False
        assert verify_password("new-secret", updated.password_hash)[0]
        # The ordinary role cannot arbitrarily change user profile fields.
        with w.factory() as db:
            with pytest.raises(MutationAuthorityError, match="capability"):
                db.execute(update(User).where(User.id == 1).values(full_name="Denied"))
            db.rollback()
        w.tx.mark_dirty()
        assert w.tx.finish_editing()

    # Remote MAIN, not just the local runtime, has the updated credential.
    rows = remote_rows(
        w, "SELECT password_hash, force_password_change FROM users WHERE id=1",
    )
    assert len(rows) == 1
    assert verify_password("new-secret", rows[0][0])[0]
    assert rows[0][1] == 0
    other = remote_rows(w, "SELECT password_hash FROM users WHERE id=2")
    assert verify_password("other-secret", other[0][0])[0]


def test_password_change_rejects_wrong_current_password_and_read_mode(reporting):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    actor = _create_test_staff(w)
    service = PermissionService(w.factory)

    with CurrentUserContext(actor):
        with pytest.raises(AuthenticationError, match="incorrect"):
            service.change_password(1, "wrong-secret", "new-secret")
        w.tx.mark_dirty()
        assert w.tx.finish_editing()

        # Without a verified WRITE owner, a valid password still cannot mutate.
        with pytest.raises(MutationAuthorityError, match="WRITE"):
            service.change_password(1, "initial-secret", "new-secret")

    original = remote_rows(w, "SELECT password_hash FROM users WHERE id=1")
    assert verify_password("initial-secret", original[0][0])[0]


def test_self_password_context_does_not_grant_unrelated_columns(reporting):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    actor = _create_test_staff(w)
    with CurrentUserContext(actor), verified_self_password_change(1):
        with w.factory() as db:
            with pytest.raises(MutationAuthorityError, match="capability"):
                db.execute(update(User).where(User.id == 1).values(email="forbidden@example.test"))
            db.rollback()
