# -*- coding: utf-8 -*-
"""
Database seeder - creates default roles, permissions, and admin user.
"""
import logging
from typing import List

from sqlalchemy.orm import Session

from centermanager.models.role import Role, RoleDefinitions
from centermanager.models.permission import Permission, PermissionDefinitions
from centermanager.models.user import User
from centermanager.models.role_permission import RolePermission

logger = logging.getLogger(__name__)


# src/centermanager/database/seed.py
def seed_roles_and_permissions(session: Session) -> None:
    # Create permissions
    permissions = _create_permissions(session)
    permission_map = {p.name: p for p in permissions}

    # Admin: full access
    admin_role = _create_role(
        session,
        name=RoleDefinitions.ADMIN,
        display_name="Administrator",
        description="Full system access",
        is_system=True,
        permission_names=list(permission_map.keys())
    )

    # Teacher
    teacher_role = _create_role(
        session,
        name=RoleDefinitions.TEACHER,
        display_name="Teacher",
        description="Teaching functions only",
        is_system=True,
        permission_names=[
            PermissionDefinitions.STUDENT_VIEW,
            PermissionDefinitions.STUDENT_CREATE,
            PermissionDefinitions.STUDENT_UPDATE,
            PermissionDefinitions.TEACHER_VIEW,
            PermissionDefinitions.CLASS_VIEW,
            PermissionDefinitions.CLASS_CREATE,
            PermissionDefinitions.CLASS_UPDATE,
            PermissionDefinitions.REPORT_VIEW,
            PermissionDefinitions.LESSON_VIEW,
            PermissionDefinitions.LESSON_CREATE,
            PermissionDefinitions.LESSON_UPDATE,
            PermissionDefinitions.LESSON_CANCEL,
            PermissionDefinitions.ATTENDANCE_VIEW,
            PermissionDefinitions.ATTENDANCE_CREATE,
            PermissionDefinitions.ATTENDANCE_UPDATE,
        ]
    )

    # Reception
    reception_role = _create_role(
        session,
        name=RoleDefinitions.RECEPTION,
        display_name="Reception",
        description="Student management only (no finance)",
        is_system=True,
        permission_names=[
            PermissionDefinitions.STUDENT_VIEW,
            PermissionDefinitions.STUDENT_CREATE,
            PermissionDefinitions.STUDENT_UPDATE,
            PermissionDefinitions.TEACHER_VIEW,
            PermissionDefinitions.CLASS_VIEW,
            PermissionDefinitions.ATTENDANCE_VIEW,
        ]
    )

    # Finance
    finance_role = _create_role(
        session,
        name=RoleDefinitions.FINANCE,
        display_name="Finance",
        description="Finance operations only",
        is_system=True,
        permission_names=[
            PermissionDefinitions.FINANCE_VIEW,
            PermissionDefinitions.FINANCE_INCOME_CREATE,
            PermissionDefinitions.FINANCE_INCOME_UPDATE,
            PermissionDefinitions.FINANCE_INCOME_DELETE,
            PermissionDefinitions.FINANCE_EXPENSE_CREATE,
            PermissionDefinitions.FINANCE_EXPENSE_UPDATE,
            PermissionDefinitions.FINANCE_EXPENSE_DELETE,
            PermissionDefinitions.REPORT_VIEW,
        ]
    )

    # ---- Thêm role MANAGER ----
    # Manager: tất cả quyền trừ setting.update và user.manage (tức là không vào Admin/Settings)
    manager_permissions = [
        p.name for p in permissions
        if p.name not in [
            PermissionDefinitions.SETTING_UPDATE,
            PermissionDefinitions.USER_MANAGE,
            PermissionDefinitions.USER_VIEW,
            PermissionDefinitions.USER_CREATE,
            PermissionDefinitions.USER_UPDATE,
            PermissionDefinitions.USER_DELETE,
            PermissionDefinitions.USER_RESET_PASSWORD,
        ]
    ]
    manager_role = _create_role(
        session,
        name=RoleDefinitions.MANAGER,
        display_name="Manager",
        description="Full access except settings and user management",
        is_system=True,
        permission_names=manager_permissions
    )

    # Admin user
    _create_admin_user(session, admin_role)
    session.commit()


def _create_permissions(session: Session) -> List[Permission]:
    """Create all system permissions."""
    created = []
    for perm_name in PermissionDefinitions.all_permissions():
        existing = session.query(Permission).filter(Permission.name == perm_name).first()
        if existing:
            created.append(existing)
            continue

        category = PermissionDefinitions.get_category(perm_name)
        permission = Permission(
            name=perm_name,
            description=f"{perm_name} permission",
            category=category,
        )
        session.add(permission)
        created.append(permission)

    session.flush()
    return created


def _create_role(
    session: Session,
    name: str,
    display_name: str,
    description: str,
    is_system: bool,
    permission_names: List[str],
) -> Role:
    """Create a role with the given permissions."""
    existing = session.query(Role).filter(Role.name == name).first()
    if existing:
        # Update permissions for existing role
        existing.display_name = display_name
        existing.description = description
        existing.is_system = is_system
        # Clear existing permissions
        existing.permissions.clear()
        # Add new permissions
        for perm_name in permission_names:
            perm = session.query(Permission).filter(Permission.name == perm_name).first()
            if perm:
                existing.permissions.append(perm)
        session.flush()
        return existing

    role = Role(
        name=name,
        display_name=display_name,
        description=description,
        is_system=is_system,
    )
    session.add(role)
    session.flush()

    # Add permissions
    for perm_name in permission_names:
        perm = session.query(Permission).filter(Permission.name == perm_name).first()
        if perm:
            role.permissions.append(perm)

    session.flush()
    return role


# src/centermanager/database/seed.py (sửa _create_admin_user)
def _create_admin_user(session: Session, admin_role: Role) -> None:
    existing = session.query(User).filter(User.username == "admin").first()
    if existing:
        if existing.role_id != admin_role.id:
            existing.role_id = admin_role.id
            existing.force_password_change = False
            existing.login_attempts = 0
            existing.locked_until = None
            session.flush()
        return

    import hashlib
    password_hash = hashlib.sha256("admin123".encode()).hexdigest()

    admin = User(
        username="admin",
        password_hash=password_hash,
        full_name="System Administrator",
        email="admin@centermanager.local",
        role_id=admin_role.id,
        is_active=True,
        force_password_change=False,
        login_attempts=0,
    )
    session.add(admin)
    session.flush()
    logger.info("Default admin user created: username='admin', password='admin123'")