"""Real SQLCipher + isolated local Git. No deployed DB or remote lock access."""
import base64
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, text, update

from tests.test_e1b2a_post_publish_consistency import reporting, workspace, remote_rows  # noqa: F401
from tests.test_e1b1_durable_write_recovery import KEY, connect, git
from centermanager.core.current_user import CurrentUserContext, get_current_user
from centermanager.database.engine import acquire_runtime_dbapi_connection, release_runtime_dbapi_connection
from centermanager.database.mutation_authority import gate_for, MutationAuthorityError, system_mutation_permit
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.write_transaction import WriteTransactionState
from centermanager.platform.write_recovery import RecoveryRequired


def raw(w):
    return acquire_runtime_dbapi_connection(lambda: connect(w.journal.database), owner='mutation-authority-test')


def assert_original(w):
    with w.factory() as db:
        assert db.get(Student, 1).full_name == 'Synthetic One'


def replace_remote_owner(w, *, expired=False):
    old = w.provider.remote_lock_status()
    record = dict(old, owner='successor', username='successor', session_id='successor-session',
                  lease_expires_at=(datetime.now() + timedelta(seconds=-1 if expired else 60)).isoformat())
    oid = w.provider._create_lock_commit_plumbing(record, old['oid'])
    assert w.provider._push_lock_branch(oid, old['oid'])
    assert w.cm._get_remote_lock_status()['session_id'] == 'successor-session'


def test_authorized_write_student_service_and_permission_floor(reporting):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    student = StudentService(w.factory).create_student('Authorized Student')
    assert student.id > 2
    StudentService(w.factory).update_student(1, full_name='Authorized update')
    actor = SimpleNamespace(id=1, role=SimpleNamespace(name='reception'), is_active=True,
                            permissions={'student.view'})
    with CurrentUserContext(actor), pytest.raises(MutationAuthorityError, match='capability'):
        StudentService(w.factory).update_student(1, full_name='Unauthorized')
    with w.factory() as db:
        assert db.get(Student, 1).full_name == 'Authorized update'


@pytest.mark.parametrize('state', [WriteTransactionState.IDLE, WriteTransactionState.WAITING])
@pytest.mark.parametrize('boundary', ['service', 'orm', 'dbapi', 'bulk-update', 'bulk-delete'])
def test_read_waiting_deny_all_shared_boundaries(reporting, state, boundary):
    w = reporting
    w.tx._state = state
    with pytest.raises(MutationAuthorityError):
        if boundary == 'service':
            StudentService(w.factory).update_student(1, full_name='Denied')
        elif boundary == 'dbapi':
            connection = raw(w)
            try:
                connection.execute('UPDATE students SET full_name=? WHERE id=1', ('Denied',))
            finally:
                release_runtime_dbapi_connection(connection)
        else:
            with w.factory() as db:
                if boundary == 'orm':
                    db.get(Student, 1).full_name = 'Denied'
                elif boundary == 'bulk-update':
                    db.execute(update(Student).where(Student.id == 1).values(full_name='Denied'))
                else:
                    db.execute(delete(Student).where(Student.id == 2))
                db.commit()
    assert_original(w)


def test_lost_remote_authority_before_orm_commit_preserves_intent(reporting):
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        db.get(Student, 1).full_name = 'SECRET UNCOMMITTED VALUE'
        db.flush()
        replace_remote_owner(w)
        with pytest.raises(MutationAuthorityError):
            db.commit()
        db.rollback()
    assert_original(w)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    document = w.journal.inspect()
    assert document['status'] == 'OPEN' and document['mutation_authority_lost']
    w.journal.verify_capture(document['last_capture'])
    with pytest.raises(RecoveryRequired):
        w.journal.assert_replaceable()
    receipts = list((w.journal.root / 'mutation-intents').glob('*.enc'))
    assert receipts
    decoded = []
    for receipt in receipts:
        assert b'SECRET' not in receipt.read_bytes()
        for line in receipt.read_bytes().splitlines():
            value = base64.b64decode(line)
            decoded.append(json.loads(AESGCM(KEY).decrypt(value[:12], value[12:], b'CenterManager mutation intent v1')))
    assert any('SECRET UNCOMMITTED VALUE' in str(row) for row in decoded)


@pytest.mark.parametrize('failure', ['unknown', 'exception', 'renew-denied'])
def test_uncertain_renewal_latches_recovery_and_cannot_reopen_on_reconnect(reporting, monkeypatch, failure):
    w = reporting
    assert w.tx.start_editing()
    if failure == 'unknown':
        monkeypatch.setattr(w.provider, 'remote_lock_status', lambda: {'state': 'UNKNOWN', 'error': 'offline'})
    elif failure == 'exception':
        def fail():
            raise OSError('offline')
        monkeypatch.setattr(w.provider, 'remote_lock_status', fail)
    else:
        monkeypatch.setattr(w.provider, 'renew_lock', lambda *a: False)
    assert not w.cm.renew_remote_lease(force=True)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    with pytest.raises(MutationAuthorityError):
        StudentService(w.factory).update_student(1, full_name='Denied')
    monkeypatch.undo()
    assert not w.tx.recover_stale_editing()
    assert not w.tx.start_editing()
    assert_original(w)


def test_old_raw_session_cannot_execute_cached_sql_after_new_owner(reporting):
    w = reporting
    assert w.tx.start_editing()
    connection = raw(w)
    try:
        statement = 'UPDATE students SET full_name=? WHERE id=1'
        connection.execute(statement, ('First admitted',))
        connection.commit()
        replace_remote_owner(w)
        with pytest.raises(MutationAuthorityError):
            connection.execute(statement, ('Stale cached statement',))
        assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    finally:
        release_runtime_dbapi_connection(connection)
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('Synthetic One',)]


def test_authorized_bulk_cte_executemany_and_sql_commit(reporting):
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        db.execute(update(Student).where(Student.id == 1).values(full_name='Bulk UPDATE'))
        db.execute(delete(Student).where(Student.id == 2))
        db.commit()
    connection = raw(w)
    try:
        connection.executemany('UPDATE students SET full_name=? WHERE id=?', [('Batch', 1)])
        connection.execute('COMMIT')
        connection.execute("WITH chosen AS (SELECT 1) UPDATE students SET full_name='CTE' WHERE id IN chosen")
        connection.commit()
        assert connection.execute('SELECT full_name FROM students').fetchall() == [('CTE',)]
    finally:
        release_runtime_dbapi_connection(connection)


def test_sql_commit_and_savepoint_release_cannot_bypass_loss(reporting):
    w = reporting
    assert w.tx.start_editing()
    connection = raw(w)
    try:
        connection.execute('SAVEPOINT test_scope')
        connection.execute("UPDATE students SET full_name='Pending' WHERE id=1")
        replace_remote_owner(w)
        for sql in ('RELEASE test_scope', 'COMMIT'):
            with pytest.raises(MutationAuthorityError):
                connection.execute(sql)
        connection.rollback()
    finally:
        release_runtime_dbapi_connection(connection)
    assert_original(w)


def test_background_callback_after_finish_denied_reports_remain_readonly(reporting):
    w = reporting
    assert w.tx.start_editing()
    StudentService(w.factory).update_student(1, full_name='Published')
    w.tx.mark_student_dirty(1)
    rejected = []
    def late():
        with pytest.raises(MutationAuthorityError):
            StudentService(w.factory).update_student(1, full_name='Late callback')
        rejected.append(True)
    assert w.tx.finish_editing(on_publish_success=late)
    assert rejected and w.rendered
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('Published',)]
    w.reports.generate_student_report(1)
    w.journal.assert_replaceable()


def test_observation_expiry_blocks_commit_without_network_or_input_activity(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    gate = gate_for()
    with w.factory() as db:
        db.get(Student, 1).full_name = 'Uncommitted'
        db.flush()
        gate.deadline = 0
        monkeypatch.setattr(w.provider, 'remote_lock_status', lambda: pytest.fail('Network called inside commit'))
        with pytest.raises(MutationAuthorityError, match='expired'):
            db.commit()
        db.rollback()
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert_original(w)
    monkeypatch.undo()


def test_slow_ui_is_not_revocation_while_worker_renews(reporting):
    w = reporting
    assert w.tx.start_editing()
    # No user input/heartbeat APIs are involved in persistence authorization.
    assert w.cm.renew_remote_lease(force=True)
    StudentService(w.factory).update_student(1, full_name='No keyboard needed')
    assert w.tx.state == WriteTransactionState.EDITING


def test_multithread_flush_loss_commit_race(reporting):
    w = reporting
    assert w.tx.start_editing()
    actor = get_current_user()
    flushed, proceed = threading.Event(), threading.Event()
    results = []
    def writer():
        try:
            with CurrentUserContext(actor), w.factory() as db:
                db.get(Student, 1).full_name = 'Thread pending'
                db.flush()
                flushed.set()
                assert proceed.wait(10)
                with pytest.raises(MutationAuthorityError):
                    db.commit()
                db.rollback()
                results.append('denied')
        except BaseException as exc:
            results.append(exc)
            flushed.set()
    worker = threading.Thread(target=writer)
    worker.start()
    try:
        assert flushed.wait(10)
        replace_remote_owner(w)
    finally:
        proceed.set()
        worker.join(10)
    assert not worker.is_alive() and results == ['denied']
    assert_original(w)


def test_maintenance_is_scoped_not_a_business_bypass(reporting):
    w = reporting
    connection = raw(w)
    try:
        with pytest.raises(MutationAuthorityError):
            connection.execute('CREATE TABLE unauthorized(id INTEGER)')
        with pytest.raises(MutationAuthorityError):
            with system_mutation_permit('checkpoint'):
                pass
        with pytest.raises(MutationAuthorityError):
            with system_mutation_permit('migration'):
                connection.execute('CREATE TABLE synthetic_migration(id INTEGER)')
        with pytest.raises(MutationAuthorityError):
            connection.execute('DELETE FROM students')
    finally:
        release_runtime_dbapi_connection(connection)


def test_pending_journal_blocks_migration_restore_and_preserves_wal(reporting):
    w = reporting
    assert w.tx.start_editing()
    external = connect(w.journal.database)
    external.execute('PRAGMA journal_mode=WAL')
    external.execute('PRAGMA wal_autocheckpoint=0')
    external.close()
    # A managed read handle keeps WAL live and is drained by the real Windows
    # maintenance proof before preservation. No untracked native handle remains.
    keeper = raw(w)
    keeper.execute('SELECT count(*) FROM students').fetchone()
    try:
        StudentService(w.factory).update_student(1, full_name='Committed WAL')
        wal = Path(str(w.journal.database) + '-wal')
        assert wal.exists() and wal.stat().st_size > 0
        with w.factory() as db:
            db.get(Student, 1).full_name = 'Pending WAL'
            db.flush()
            replace_remote_owner(w)
            with pytest.raises(MutationAuthorityError):
                db.commit()
            db.rollback()
        with pytest.raises((MutationAuthorityError, RecoveryRequired)):
            with system_mutation_permit('migration'):
                pass
        from centermanager.platform.backup.backup_service import BackupService
        from centermanager.platform.backup.restore_authorization import issue_restore_authorization
        authorization = issue_restore_authorization(actor=SimpleNamespace(id=1, username='synthetic', is_admin=True),
                                                   reason='test', confirmation='RESTORE test')
        assert not BackupService().restore_backup(Path('unused'), authorization=authorization).success
        assert w.journal.inspect()['status'] == 'OPEN'
        assert wal.exists()
        capture = w.journal.preserve('denied-commit-recovery')
        snapshot = connect(capture / 'center.db', readonly=True)
        try:
            assert snapshot.execute('SELECT full_name FROM students WHERE id=1').fetchone() == ('Committed WAL',)
        finally:
            snapshot.close()
    finally:
        release_runtime_dbapi_connection(keeper)


def test_finance_service_runs_under_same_gate(reporting):
    from centermanager.services.income_service import IncomeService
    w = reporting
    service = IncomeService(w.factory, None, None, None, None)
    assert w.tx.start_editing()
    from centermanager.models.finance_period import FinancePeriod
    with w.factory() as db:
        db.add(FinancePeriod(duration_months=1, effective_from=date.today().replace(day=1)))
        db.commit()
    item = service.create_income(amount=100, income_type='Other', payment_method='Cash', payment_date=date.today())
    assert item.id
    assert w.tx.finish_editing()
    with pytest.raises(MutationAuthorityError):
        service.create_income(amount=50, income_type='Other', payment_method='Cash', payment_date=date.today())


@pytest.mark.parametrize('sql', ['ATTACH DATABASE ":memory:" AS bypass', 'PRAGMA writable_schema=ON',
                                 'PRAGMA foreign_keys=OFF', 'CREATE TABLE bypass(id INTEGER)',
                                 'PRAGMA rekey="bad"'])
def test_ordinary_write_cannot_create_system_bypass(reporting, sql):
    w = reporting
    assert w.tx.start_editing()
    connection = raw(w)
    try:
        with pytest.raises(MutationAuthorityError):
            connection.execute(sql)
    finally:
        release_runtime_dbapi_connection(connection)


def test_existing_bundled_migrations_and_narrow_bootstrap(workspace, monkeypatch):
    from alembic.config import Config
    from centermanager.database import migration
    from centermanager.database.engine import create_production_engine
    from centermanager.database.seed import seed_roles_and_permissions
    from sqlalchemy.orm import sessionmaker
    root = Path(__file__).resolve().parents[1]
    def config(path):
        value = Config(str(root / 'alembic.ini'))
        value.set_main_option('script_location', str(root / 'migrations'))
        return value
    monkeypatch.setattr(migration, 'get_alembic_config', config)
    migration.upgrade_database_to_head()
    engine = create_production_engine()
    try:
        with system_mutation_permit('bootstrap'), sessionmaker(bind=engine)() as db:
            seed_roles_and_permissions(db)
        with system_mutation_permit('bootstrap'), engine.begin() as db:
            with pytest.raises(MutationAuthorityError, match='initial account'):
                db.exec_driver_sql("INSERT INTO students(student_code, full_name) VALUES ('BAD', 'Bad bootstrap')")
        with engine.connect() as db:
            assert db.exec_driver_sql('SELECT count(*) FROM users').scalar_one() == 1
    finally:
        engine.dispose()


def test_read_backup_is_a_snapshot_not_a_runtime_mutation(reporting):
    from centermanager.platform.backup.backup_service import BackupService
    w = reporting
    before = w.journal.database.read_bytes()
    result = BackupService().create_backup('readonly-synthetic')
    assert result.success, result.error
    assert w.journal.database.read_bytes() == before
    assert w.journal.inspect() is None
    assert_original(w)


@pytest.mark.parametrize('expired', [False, True])
def test_reconnect_with_revoked_or_expired_session_cannot_reuse_work(reporting, expired):
    w = reporting
    assert w.tx.start_editing()
    StudentService(w.factory).update_student(1, full_name='Unaccepted work')
    replace_remote_owner(w, expired=expired)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert not w.tx.finish_editing()
    assert not w.tx.recover_stale_editing()
    assert not w.tx.start_editing()
    assert w.provider.observe_remote_main_commit() == w.base
    assert w.journal.inspect()['status'] == 'OPEN'


def test_runtime_login_has_no_sql_writes_and_preserves_lockout(reporting):
    from centermanager.models.role import Role
    from centermanager.models.user import User
    from centermanager.security.password import hash_password
    from centermanager.services.permission_service import PermissionService, AuthenticationError
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        role = Role(name='admin', display_name='Synthetic Admin', is_system=True)
        db.add(role)
        db.flush()
        db.add(User(id=1, username='login-test', full_name='Login Test',
                    password_hash=hash_password('synthetic-valid-password'),
                    role_id=role.id, is_active=True, force_password_change=False, login_attempts=0))
        db.commit()
    assert w.tx.finish_editing()
    service = PermissionService(w.factory)
    assert service.authenticate_user('login-test', 'synthetic-valid-password').id == 1
    before = w.journal.database.read_bytes()
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            service.authenticate_user('login-test', 'wrong-password')
    with pytest.raises(AuthenticationError, match='locked'):
        service.authenticate_user('login-test', 'synthetic-valid-password')
    assert w.journal.database.read_bytes() == before
    with w.factory() as db:
        user = db.get(User, 1)
        assert user.login_attempts == 0 and user.last_login is None
    assert w.journal.inspect()['status'] == 'CLEAN'
    w.journal.assert_replaceable()


def test_protected_service_alternate_engine_has_no_unbound_writer(reporting, tmp_path):
    from centermanager.database.engine import create_engine_for_path
    from sqlalchemy.orm import sessionmaker
    import shutil
    destination = tmp_path / 'service-owned.db'
    shutil.copy2(reporting.journal.database, destination)
    engine = create_engine_for_path(destination, encrypted=True, encryption_key=KEY, mutation_guarded=True)
    try:
        with sessionmaker(bind=engine)() as db:
            assert db.get(Student, 1)
            db.get(Student, 1).full_name = 'No application session token can grant WRITE'
            with pytest.raises(MutationAuthorityError):
                db.commit()
            db.rollback()
    finally:
        engine.dispose()


def test_loss_during_finish_save_cannot_be_overwritten_by_local_saved(reporting):
    w = reporting
    assert w.tx.start_editing()
    def save():
        StudentService(w.factory).update_student(1, full_name='Saved but unaccepted')
        replace_remote_owner(w)
        return True
    assert not w.tx.finish_editing(save_callback=save)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert w.provider.observe_remote_main_commit() == w.base
    assert w.journal.inspect()['status'] == 'OPEN'


def test_intent_disk_failure_aborts_statement_and_retains_recovery(reporting, monkeypatch):
    from centermanager.database.guarded_dbapi import GuardedConnection
    w = reporting
    assert w.tx.start_editing()
    def full_disk(*args):
        raise OSError('synthetic full disk')
    monkeypatch.setattr(GuardedConnection, '_record', full_disk)
    with pytest.raises(MutationAuthorityError):
        StudentService(w.factory).update_student(1, full_name='Cannot persist intent')
    assert_original(w)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert w.journal.inspect()['status'] == 'OPEN'
    assert w.journal.inspect()['mutation_authority_lost']


def test_delete_only_finance_permission_preserves_logical_void_workflow(reporting):
    from centermanager.models.finance_period import FinancePeriod
    from centermanager.services.income_service import IncomeService
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        db.add(FinancePeriod(duration_months=1, effective_from=date.today().replace(day=1)))
        db.commit()
    service = IncomeService(w.factory, None, None, None, None)
    item = service.create_income(amount=100, income_type='Other', payment_method='Cash', payment_date=date.today())
    actor = SimpleNamespace(id=1, username='synthetic', full_name='Synthetic',
                            role=SimpleNamespace(name='finance'), is_active=True,
                            permissions={'finance.income.delete'})
    with CurrentUserContext(actor):
        assert service.void_income(item.id, 'Synthetic void').status == 'VOIDED'
        with w.factory() as db, pytest.raises(MutationAuthorityError):
            db.execute(update(Student).where(Student.id == 1).values(full_name='Unrelated edit'))


def test_existing_employee_self_link_repair_still_requires_write(reporting):
    from centermanager.models.role import Role
    from centermanager.models.user import User
    from centermanager.services.employee_service import EmployeeService
    from centermanager.services.permission_service import PermissionService
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        role = Role(name='teacher', display_name='Teacher', is_system=True)
        db.add(role)
        db.flush()
        db.add(User(id=1, username='synthetic', full_name='Teacher self',
                    password_hash='synthetic-fixture-only', role_id=role.id,
                    is_active=True, force_password_change=False, login_attempts=0))
        db.commit()
    actor = PermissionService(w.factory).get_user(1)
    with CurrentUserContext(actor):
        repaired = EmployeeService(w.factory).get_current_employee()
        assert repaired.user_id == 1
    assert w.tx.finish_editing()


def test_loss_projection_is_queued_after_db_hook_unwinds(reporting, qapp):
    from centermanager.platform.collaboration.events import ModeChanged
    w = reporting
    assert w.tx.start_editing()
    qapp.processEvents()
    states = []
    w.cm._event_bus.register(ModeChanged, lambda event: states.append((event.mode, w.tx.state)))
    with gate_for().lock:
        gate_for().invalidate('Synthetic loss inside a DB boundary')
        assert states == []
    qapp.processEvents()
    assert states == [('READ', WriteTransactionState.RECOVERY_REQUIRED)]


def test_ui_projects_already_latched_recovery_instead_of_ignoring_lease_failure():
    from centermanager.ui.main_window import MainWindow
    projected = []
    window = SimpleNamespace(_transaction=SimpleNamespace(state=WriteTransactionState.RECOVERY_REQUIRED,
                                                         is_editing=False),
                             _update_write_buttons=lambda: projected.append(True))
    MainWindow._on_lease_renewal_failed(window, {'error': 'synthetic'})
    assert projected == [True]


def test_healthy_renewal_does_not_wait_for_long_native_statement(reporting):
    w = reporting
    assert w.tx.start_editing()
    actor = get_current_user()
    entered, release, renewed = threading.Event(), threading.Event(), threading.Event()
    results = []
    def slow_floor(value):
        entered.set()
        assert release.wait(20)
        return value
    def writer():
        connection = None
        try:
            with CurrentUserContext(actor):
                connection = raw(w)
                connection.create_function('floor', 1, slow_floor)
                connection.execute('UPDATE students SET full_name=CAST(floor(id) AS TEXT) WHERE id=1')
                # Simulate the old observation having aged out during UI/native
                # work. Fresh worker evidence must be consumed at commit.
                gate_for().deadline = 0
                connection.commit()
                results.append('committed')
        except BaseException as exc:
            results.append(exc)
        finally:
            if connection is not None:
                release_runtime_dbapi_connection(connection)
    def renew():
        try:
            assert w.cm.renew_remote_lease(force=True)
            renewed.set()
        except BaseException as exc:
            results.append(exc)
    worker = threading.Thread(target=writer)
    lease_worker = threading.Thread(target=renew)
    worker.start()
    try:
        assert entered.wait(10)
        lease_worker.start()
        assert renewed.wait(15), 'Healthy renewal blocked on the native DB mutation mutex'
        assert not release.is_set()
    finally:
        release.set()
        worker.join(20)
        if lease_worker.ident is not None:
            lease_worker.join(20)
    assert not worker.is_alive() and not lease_worker.is_alive()
    assert results == ['committed']
    assert w.tx.state == WriteTransactionState.EDITING
