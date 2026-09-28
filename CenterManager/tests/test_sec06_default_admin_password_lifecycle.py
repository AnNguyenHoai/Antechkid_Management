from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager.database.seed import _create_admin_user
from centermanager.models.role import Role
from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _admin_role(session):
    role = Role(name="admin", display_name="Administrator", description="test", is_system=True)
    session.add(role)
    session.flush()
    return role


def test_new_default_admin_requires_password_change():
    factory = _session_factory()
    with factory() as session:
        role = _admin_role(session)
        _create_admin_user(session, role)
        admin = session.query(User).filter(User.username == "admin").one()
        assert admin.force_password_change is True


def test_seed_preserves_existing_admin_completed_password_change():
    factory = _session_factory()
    with factory() as session:
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
    factory = _session_factory()
    with factory() as session:
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


def test_successful_password_change_clears_force_flag():
    from centermanager.security.password import hash_password, verify_password

    factory = _session_factory()
    with factory() as session:
        role = _admin_role(session)
        admin = User(
            username="admin",
            password_hash=hash_password("old-password"),
            full_name="Administrator",
            role_id=role.id,
            is_active=True,
            force_password_change=True,
            login_attempts=0,
        )
        session.add(admin)
        session.commit()
        admin_id = admin.id

    service = PermissionService(factory)
    updated = service.change_password(admin_id, "old-password", "new-password")

    assert updated.force_password_change is False
    password_valid, _ = verify_password("new-password", updated.password_hash)
    assert password_valid is True

    with factory() as session:
        role = session.query(Role).filter(Role.name == "admin").one()
        _create_admin_user(session, role)
        admin = session.query(User).filter(User.id == admin_id).one()
        assert admin.force_password_change is False
