from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.database.seed import _create_admin_user
from centermanager.models.role import Role
from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _admin_role(session):
    role = Role(name="admin", display_name="Administrator", description="test", is_system=True)
    session.add(role)
    session.flush()
    return role


def test_new_default_admin_requires_password_change():
    session = _session()
    role = _admin_role(session)

    _create_admin_user(session, role)

    admin = session.query(User).filter(User.username == "admin").one()
    assert admin.force_password_change is True


def test_seed_preserves_existing_admin_completed_password_change():
    session = _session()
    role = _admin_role(session)
    admin = User(
        username="admin",
        password_hash="already-changed",
        full_name="Administrator",
        role_id=role.id,
        is_active=True,
        force_password_change=False,
        login_attempts=0,
    )
    session.add(admin)
    session.flush()

    _create_admin_user(session, role)

    assert admin.force_password_change is False
    assert admin.password_hash == "already-changed"


def test_seed_preserves_existing_admin_pending_password_change():
    session = _session()
    role = _admin_role(session)
    admin = User(
        username="admin",
        password_hash="bootstrap-hash",
        full_name="Administrator",
        role_id=role.id,
        is_active=True,
        force_password_change=True,
        login_attempts=0,
    )
    session.add(admin)
    session.flush()

    _create_admin_user(session, role)

    assert admin.force_password_change is True
    assert admin.password_hash == "bootstrap-hash"


def test_successful_password_change_clears_force_flag(monkeypatch):
    session = _session()
    role = _admin_role(session)
    admin = User(
        username="admin",
        password_hash="old-hash",
        full_name="Administrator",
        role_id=role.id,
        is_active=True,
        force_password_change=True,
        login_attempts=0,
    )
    session.add(admin)
    session.commit()

    monkeypatch.setattr("centermanager.services.permission_service.verify_password", lambda plain, hashed: plain == "old-password")
    monkeypatch.setattr("centermanager.services.permission_service.hash_password", lambda plain: "new-hash")

    service = PermissionService(session)
    ok, message = service.change_password(admin, "old-password", "new-password")

    assert ok is True, message
    assert admin.password_hash == "new-hash"
    assert admin.force_password_change is False

    _create_admin_user(session, role)
    assert admin.force_password_change is False
