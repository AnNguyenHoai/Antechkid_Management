"""Local admission against the existing collaboration lease and recovery ledger.

This is a consumer of remote observations, never a lock/ownership authority.
No network operation or DB checkpoint is allowed in this module's critical path.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import threading
import time
import uuid


class MutationAuthorityError(RuntimeError):
    """The local operation has no valid persistence permit."""


@dataclass(frozen=True)
class MutationPermit:
    repository_id: str
    session_id: str
    incarnation: str
    category: str
    permissions: tuple[str, ...]
    actor_id: str


_local = threading.local()
_gates: dict[Path, "MutationAuthorityGate"] = {}
_registry_lock = threading.RLock()


@contextmanager
def verified_self_password_change(user_id):
    """Used only after PermissionService verifies the current credential."""
    previous = getattr(_local, 'password_user_id', None)
    _local.password_user_id = str(user_id)
    try:
        yield
    finally:
        _local.password_user_id = previous


@contextmanager
def verified_employee_identity_repair(user_id):
    """Existing authenticated self-link repair, after service proves no link."""
    previous = getattr(_local, 'employee_user_id', None)
    _local.employee_user_id = str(user_id)
    try:
        yield
    finally:
        _local.employee_user_id = previous


@contextmanager
def runtime_install_permit():
    """Preserve the pre-swap recovery proof for the bundled schema barrier."""
    from centermanager.platform.write_recovery import require_replaceable
    gate = gate_for()
    with gate.lock:
        if not gate.closed:
            raise MutationAuthorityError('Runtime replacement cannot race an active local editor')
        require_replaceable()
        previous = getattr(_local, 'install_path', None)
        _local.install_path = runtime_path()
        try:
            yield
        finally:
            _local.install_path = previous


def runtime_path() -> Path:
    from centermanager.database.engine import get_database_path
    return get_database_path().resolve()


def gate_for(path=None) -> "MutationAuthorityGate":
    path = Path(path).resolve() if path is not None else runtime_path()
    with _registry_lock:
        return _gates.setdefault(path, MutationAuthorityGate(path))


def is_runtime_path(path) -> bool:
    return Path(path).resolve() == runtime_path()


class MutationAuthorityGate:
    def __init__(self, database: Path):
        self.database = database
        self.lock = threading.RLock()
        self.transaction = None
        self.incarnation = uuid.uuid4().hex
        self.deadline = 0.0
        self.session_id = ""
        self.repository_id = ""
        self.repository_config_hash = ""
        self.closed = True
        self.lost = False
        self.finishing_thread = None

    def bind(self, transaction):
        with self.lock:
            if self.transaction is not None and not self.closed:
                raise MutationAuthorityError("A local mutation session is already bound")
            self.transaction = transaction
            transaction._mutation_gate = self
            transaction._collab_manager._mutation_gate = self

    def _config_hash(self):
        # Local file read only; do not execute Git under a DB lock.
        config = self.transaction._recovery_journal.repository / ".git" / "config"
        return hashlib.sha256(config.read_bytes()).hexdigest()

    def open(self):
        """Explicit entry only, after journal preparation and remote validation."""
        with self.lock:
            tx = self.transaction
            journal = tx._recovery_journal
            if journal is None:
                raise MutationAuthorityError("Durable WRITE recovery is required")
            document = journal.inspect()
            if not document or document['status'] != 'OPEN' or document.get('mutation_authority_lost'):
                raise MutationAuthorityError("Recovery is pending; editing cannot resume")
            self.session_id = tx._collab_manager.get_session_id()
            if document['session_id'] != self.session_id:
                raise MutationAuthorityError("Recovery session mismatch")
            self.repository_id = document['repository_id']
            if self.repository_id != journal._repository_id():
                raise MutationAuthorityError("Repository identity mismatch")
            self.repository_config_hash = self._config_hash()
            self.incarnation = uuid.uuid4().hex
            self.lost = False
            self.closed = False
            self.deadline = 0.0
        # The existing manager supplies the observation; no second lock source.
        if not tx._collab_manager.validate_write_authority(tx._collab_manager.get_session()).get('valid'):
            self.invalidate("WRITE could not be verified at mutation admission")
        with self.lock:
            if self.lost or self.deadline <= time.monotonic():
                self.invalidate("No current remote lease observation")
                raise MutationAuthorityError("No current remote lease observation")

    def observe(self, observation, started):
        with self.lock:
            if self.closed or self.lost:
                return
            cm = self.transaction._collab_manager
            try:
                remaining = (datetime.fromisoformat(observation['lease_expires_at']) - datetime.now()).total_seconds()
                valid = (observation.get('state') == 'ACTIVE' and observation.get('verified') is True
                         and observation.get('session_id') == self.session_id
                         and observation.get('owner') == cm.get_session().username
                         and bool(observation.get('oid')) and remaining > 0)
            except (KeyError, TypeError, ValueError, AttributeError):
                valid = False
            if not valid:
                self.invalidate("Remote WRITE is lost, expired or unverified")
                return
            # The unchanged 60-second lease is the maximum validity boundary.
            # Use request START, so network latency cannot extend the lease.
            self.deadline = min(started + cm._lock_timeout, time.monotonic() + remaining)

    def invalidate(self, reason):
        with self.lock:
            if self.closed or self.lost:
                return
            self.lost = True
            self.deadline = 0.0
            tx = self.transaction
            from centermanager.services.write_transaction import WriteTransactionState
            tx._state = WriteTransactionState.RECOVERY_REQUIRED
            tx._is_editing = False
            tx._stale_editing_reason = reason
            tx._last_start_error = reason + ". Local work is preserved; inspect recovery before synchronizing."
            # Do not acquire the collaboration mutex here (renewal owns it).
            # This flag only stops renewal; it never releases remote ownership.
            tx._collab_manager._lease_renewal_suspended = True
            if tx._recovery_journal is not None:
                tx._recovery_journal.update(mutation_authority_lost=True, mutation_failure=reason)

    def close(self):
        with self.lock:
            self.closed = True
            self.deadline = 0.0
            self.finishing_thread = None

    def require(self, category, permissions=(), expected=None):
        """Called under lock by statement and commit boundaries."""
        maintenance = getattr(_local, 'maintenance', None)
        if maintenance is not None:
            path, token, kinds, kind = maintenance
            if path != self.database or category not in kinds:
                raise MutationAuthorityError("Maintenance permit does not cover this operation")
            permit = MutationPermit('system', token, token, category, (), 'system')
            if expected is not None and expected.incarnation != token:
                raise MutationAuthorityError("Transaction belongs to another maintenance permit")
            return permit
        tx = self.transaction
        if self.closed or self.lost or tx is None:
            raise MutationAuthorityError("Active verified WRITE is required")
        cm = tx._collab_manager
        if self.database != runtime_path():
            self.invalidate("Runtime repository identity changed")
            raise MutationAuthorityError("Runtime repository identity changed")
        state = tx.state.name
        allowed = (state == 'EDITING' and self.finishing_thread in (None, threading.get_ident())) or (state == 'FINISHING' and self.finishing_thread == threading.get_ident())
        if (not allowed or not cm.is_writing() or cm._lease_renewal_suspended
                or cm.get_session_id() != self.session_id):
            self.invalidate("Local WRITE session is suspended or no longer editing")
            raise MutationAuthorityError("Local WRITE session is suspended or no longer editing")
        if time.monotonic() >= self.deadline:
            self.invalidate("Verified WRITE observation has expired")
            raise MutationAuthorityError("Verified WRITE observation has expired")
        try:
            document = tx._recovery_journal.inspect()
            valid = (document['status'] == 'OPEN' and not document.get('mutation_authority_lost')
                     and document['session_id'] == self.session_id
                     and document['repository_id'] == self.repository_id
                     and Path(document['database']).resolve() == self.database
                     and self._config_hash() == self.repository_config_hash)
        except Exception:
            valid = False
        if not valid:
            self.invalidate("Recovery journal or repository identity changed")
            raise MutationAuthorityError("Recovery journal or repository identity changed")
        if category != 'business':
            raise MutationAuthorityError("System operation requires an explicit maintenance permit")
        from centermanager.core.current_user import get_current_user
        from centermanager.services.authorization_service import AuthorizationService
        actor = get_current_user()
        if actor is None or str(actor.id) != str(cm.get_session().user_id):
            raise MutationAuthorityError("Mutation actor does not match the WRITE session")
        self_password = (permissions == ('self_password_change',)
                         and getattr(_local, 'password_user_id', None) == str(actor.id)
                         and bool(getattr(actor, 'is_active', True)))
        self_employee = (permissions == ('self_employee_link',)
                         and getattr(_local, 'employee_user_id', None) == str(actor.id)
                         and getattr(getattr(actor, 'role', None), 'name', None) not in (None, 'admin')
                         and bool(getattr(actor, 'is_active', True)))
        from centermanager.services.employee_capability_policy import EmployeeCapabilityPolicy
        def allows(permission):
            if permission.startswith(('employee.', 'schedule.', 'working_time.', 'work_registration.')):
                return EmployeeCapabilityPolicy.has(actor, permission)
            return AuthorizationService.allows(actor, permission)
        if not self_password and not self_employee:
            if not permissions or not any(allows(permission) for permission in permissions):
                raise MutationAuthorityError("Required business capability is missing")
        permit = MutationPermit(self.repository_id, self.session_id, self.incarnation,
                                category, tuple(permissions), str(actor.id))
        if expected is not None and (expected.incarnation != permit.incarnation or expected.actor_id != permit.actor_id):
            raise MutationAuthorityError("Stale transaction cannot be committed by a new session")
        return permit


@contextmanager
def system_mutation_permit(kind, *, path=None):
    """Thread-scoped system work; never grants ordinary business DML.

    This boundary has fixed categories, no caller-provided table/SQL allowlist.
    Callers retain their existing bootstrap/restore authorization and journal
    proofs. Migration executes only the bundled, previously approved chain.
    """
    path = Path(path).resolve() if path is not None else runtime_path()
    gate = gate_for(path)
    from centermanager.platform.write_recovery import WriteRecoveryJournal
    from centermanager.database.engine import runtime_db_maintenance_active
    kinds = {'checkpoint': {'checkpoint'}, 'initialize': {'pragma'},
             'migration': {'schema', 'business', 'pragma'},
             'bootstrap': {'business'}}
    if kind not in kinds:
        raise MutationAuthorityError("Unknown system mutation category")
    with gate.lock:
        if kind == 'checkpoint':
            if not runtime_db_maintenance_active():
                raise MutationAuthorityError("Checkpoint requires the runtime maintenance fence")
        else:
            installed = (kind == 'migration' and getattr(_local, 'install_path', None) == path
                         and runtime_db_maintenance_active())
            if gate.transaction is not None and not installed:
                raise MutationAuthorityError("Startup maintenance cannot run after collaboration is bound")
            if is_runtime_path(path) and not installed:
                WriteRecoveryJournal().assert_replaceable()
        previous = getattr(_local, 'maintenance', None)
        _local.maintenance = (path, uuid.uuid4().hex, kinds[kind], kind)
        try:
            yield
        finally:
            _local.maintenance = previous


def authentication_activity_policy(session):
    """Expose engine persistence policy without service-owned DB mechanics."""
    engine = session.get_bind()
    return (bool(getattr(engine, '_cm_mutation_protected', False)),
            getattr(engine, '_cm_login_key', None))
