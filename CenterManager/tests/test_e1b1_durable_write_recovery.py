"""E1B-1: synthetic SQLCipher + isolated real Git; no production resources."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from centermanager.core.paths import get_paths
from centermanager.database.encryption import DatabaseKeyStore, apply_sqlcipher_key, load_sqlcipher_driver
from centermanager.database.artifact_identity import next_identity_document, write_identity_document, identity_manifest_path
from centermanager.platform.write_recovery import WriteRecoveryJournal, RecoveryRequired
from centermanager.platform.synchronization import GitSynchronizationProvider

KEY = bytes(range(32))  # Public synthetic key; never a real workspace key.


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def connect(path, readonly=False):
    connection = load_sqlcipher_driver().connect(path.resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True)
    apply_sqlcipher_key(connection, KEY)
    return connection


def values(path):
    connection = connect(path, readonly=True)
    try:
        return [r[0] for r in connection.execute('SELECT value FROM recovery_items ORDER BY id')]
    finally:
        connection.close()


@pytest.fixture
def workspace(temp_runtime, tmp_path, monkeypatch):
    monkeypatch.setenv('ANTECHKIDS_FORCE_DATABASE_ENCRYPTION', '1')
    monkeypatch.setattr(DatabaseKeyStore, 'load', lambda self: KEY)
    paths = get_paths()
    paths.ensure_directories()
    paths.config_dir.mkdir(exist_ok=True)
    DatabaseKeyStore().bundle_path.write_text('SYNTHETIC-PROTECTED-REFERENCE', encoding='utf-8')
    database = paths.database_dir / 'center.db'
    connection = load_sqlcipher_driver().connect(str(database))
    apply_sqlcipher_key(connection, KEY)
    connection.execute('CREATE TABLE recovery_items(id INTEGER PRIMARY KEY, value TEXT)')
    connection.execute("INSERT INTO recovery_items(value) VALUES ('BASE')")
    connection.commit()
    connection.close()
    repository = paths.runtime_root / 'repository'
    (repository / 'database').mkdir(parents=True)
    repo_db = repository / 'database' / 'center.db'
    shutil.copy2(database, repo_db)
    write_identity_document(identity_manifest_path(repo_db), next_identity_document(repo_db, KEY, repo_db))
    (repository / 'manifest.json').write_text('{"runtime_version": 1}', encoding='utf-8')
    git(repository, 'init', '-b', 'main')
    git(repository, 'config', 'user.name', 'Synthetic Recovery')
    git(repository, 'config', 'user.email', 'synthetic@example.invalid')
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'synthetic base')
    remote = tmp_path / 'synthetic.git'
    remote.mkdir()
    git(remote, 'init', '--bare')
    git(repository, 'remote', 'add', 'origin', str(remote))
    git(repository, 'push', '-u', 'origin', 'main')
    provider = GitSynchronizationProvider(repo_path=repository, repository_url=str(remote), branch='main', allow_local_file_remote=True)
    assert provider.connect()
    journal = WriteRecoveryJournal()
    base = git(repository, 'rev-parse', 'HEAD')
    yield SimpleNamespace(journal=journal, provider=provider, paths=paths, base=base, remote=remote)
    from centermanager.database import session
    session.quiesce_runtime_db()
    from centermanager.database.engine import end_runtime_db_maintenance
    end_runtime_db_maintenance()


def begin(w):
    w.journal.begin('synthetic-session', w.base, {'session_id': 'synthetic-session', 'oid': 'observed-authority', 'lease_revision': 2})


def mutate(w):
    connection = connect(w.journal.database)
    try:
        connection.execute("INSERT INTO recovery_items(value) VALUES ('LOCAL_UNACCEPTED')")
        connection.commit()
    finally:
        connection.close()


def test_durable_base_ciphertext_key_reference_and_no_epoch(workspace):
    w = workspace
    begin(w)
    document = w.journal.inspect()
    assert document['status'] == 'OPEN' and document['ownership_epoch'] is None
    assert document['base_main_oid'] == w.base
    capture = Path(document['last_capture'])
    assert w.journal.verify_capture(capture)['key_reference'] == str(DatabaseKeyStore().bundle_path)
    assert values(capture / 'center.db') == ['BASE']
    assert not (capture / 'center.db').read_bytes().startswith(b'SQLite format 3')
    assert 'BASE' not in w.journal.journal.read_text()
    assert not w.journal.root.is_relative_to(w.journal.runtime)


@pytest.mark.parametrize('failure', ['journal', 'snapshot', 'disk'])
def test_preparation_failure_never_allows_writes_or_replaces_db(workspace, monkeypatch, failure):
    import centermanager.platform.write_recovery as module
    from centermanager.database import wal_safety
    before = workspace.journal.database.read_bytes()
    def fail(*a, **k):
        raise OSError('synthetic disk full or checkpoint failure')
    if failure == 'journal':
        monkeypatch.setattr(module, '_json', fail)
    else:
        monkeypatch.setattr(wal_safety, '_checkpoint_runtime_database', fail)
    with pytest.raises(OSError):
        begin(workspace)
    assert workspace.journal.database.read_bytes() == before
    if failure != 'journal':
        assert workspace.journal.inspect()['status'] == 'PREPARING'
        with pytest.raises(RecoveryRequired):
            workspace.journal.assert_replaceable()


def test_active_wal_repeated_captures_never_lose_commits(workspace):
    begin(workspace)
    j = workspace.journal
    from centermanager.database.engine import acquire_runtime_dbapi_connection
    # Model an already-committed legacy writer, registered only for native
    # quiesce/close ordering. E1B-2B separately denies new READ DML at acquisition.
    # Windows must see this handle drain before the recovery checkpoint.
    from centermanager.database.engine import _register_runtime_dbapi_connection
    writer = connect(j.database)
    _register_runtime_dbapi_connection(writer, owner='legacy-wal-recovery-fixture')
    try:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute("INSERT INTO recovery_items(value) VALUES ('WAL_ONLY')")
        writer.commit()
        assert j.database.with_name('center.db-wal').stat().st_size > 0
        first, second = j.preserve('first-attempt'), j.preserve('second-attempt')
        for capture in (first, second):
            j.verify_capture(capture)
            assert values(capture / 'center.db') == ['BASE', 'WAL_ONLY']
        assert first != second
        assert values(j.database) == ['BASE', 'WAL_ONLY']
    finally:
        writer.close()


@pytest.mark.parametrize('path', ['startup', 'runtime', 'reset', 'pull', 'restore', 'cancel-rollback', 'clone'])
def test_dirty_journal_blocks_destructive_boundary(workspace, path):
    w = workspace
    begin(w)
    mutate(w)
    before = w.journal.database.read_bytes()
    (w.journal.repository / 'unpublished.txt').write_text('synthetic unpublished artifact')
    if path == 'startup':
        from centermanager.platform.sync.startup_sync import StartupSynchronization
        startup = StartupSynchronization(w.provider)
        assert not startup.run() and 'protected' in startup.recovery_error
    elif path == 'runtime':
        from centermanager.platform.sync.write_handoff_runtime_sync_service import RuntimeSyncService
        assert not RuntimeSyncService._apply_runtime_update(SimpleNamespace())
    elif path == 'restore':
        from centermanager.platform.backup.backup_service import BackupService
        from centermanager.platform.backup.restore_authorization import issue_restore_authorization
        authorization = issue_restore_authorization(actor=SimpleNamespace(id=1, username='synthetic', is_admin=True), reason='synthetic test', confirmation='RESTORE synthetic')
        result = BackupService().restore_backup(Path('synthetic'), authorization=authorization)
        assert not result.success and 'protected' in result.error
    elif path == 'cancel-rollback':
        from centermanager.services.write_transaction import WriteTransactionManager
        with pytest.raises(RecoveryRequired):
            WriteTransactionManager(SimpleNamespace())._restore_snapshot()
    elif path == 'clone':
        with pytest.raises(RecoveryRequired):
            w.provider.clone()
    else:
        assert not getattr(w.provider, 'reset_to_remote' if path == 'reset' else 'pull')()
    assert w.journal.database.read_bytes() == before
    assert (w.journal.repository / 'unpublished.txt').exists()


def test_cancel_retains_data_even_without_dirty_flag(workspace):
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    begin(workspace)
    mutate(workspace)
    transaction = WriteTransactionManager(SimpleNamespace(is_writing=lambda: True, release_write=lambda: True))
    transaction._state = WriteTransactionState.EDITING
    transaction._recovery_journal = workspace.journal
    assert not transaction.has_changes
    assert transaction.cancel_editing(force=True)
    assert transaction.state == WriteTransactionState.RECOVERY_REQUIRED
    document = workspace.journal.inspect()
    assert document['status'] == 'CANCELLED' and document['release'] == 'VERIFIED'
    assert values(Path(document['last_capture']) / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
    assert values(workspace.journal.database) == ['BASE', 'LOCAL_UNACCEPTED']


@pytest.mark.parametrize('remote', [None, 'different-accepted-commit'])
def test_unknown_or_different_publish_ack_never_clean(workspace, remote):
    begin(workspace)
    workspace.journal.update(status='PUBLISHING')
    provider = SimpleNamespace(get_local_main_commit=lambda: workspace.base, observe_remote_main_commit=lambda: remote)
    with pytest.raises(RecoveryRequired):
        workspace.journal.published(provider)
    assert workspace.journal.inspect()['status'] == 'PUBLISHING'
    with pytest.raises(RecoveryRequired):
        workspace.journal.assert_replaceable()


def test_verified_clean_publish_allows_startup_retains_captures(workspace):
    begin(workspace)
    workspace.journal.update(status='PUBLISHING')
    workspace.journal.published(workspace.provider)
    workspace.journal.released()
    assert workspace.journal.inspect()['status'] == 'CLEAN'
    workspace.journal.assert_replaceable()
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert StartupSynchronization(workspace.provider).run()
    assert len(list((workspace.journal.root / 'captures').iterdir())) == 2


def test_post_materialization_mutation_cannot_be_marked_published(workspace):
    begin(workspace)
    mutate(workspace)
    workspace.journal.update(status='PUBLISHING')
    with pytest.raises(RecoveryRequired):
        workspace.journal.published(workspace.provider)
    with pytest.raises(RecoveryRequired):
        workspace.journal.assert_replaceable()


def test_legacy_dirty_blocks_clean_may_start(workspace):
    workspace.journal.assert_replaceable(legacy=True)
    mutate(workspace)
    with pytest.raises(RecoveryRequired, match='Legacy'):
        workspace.journal.assert_replaceable(legacy=True)
    assert workspace.journal.inspect() is None


def test_explicit_reconciliation_keeps_unaccepted_git_commit_and_db(workspace):
    w = workspace
    begin(w)
    mutate(w)
    (w.journal.repository / 'unpublished.txt').write_text('synthetic local work', encoding='utf-8')
    git(w.journal.repository, 'add', '.')
    git(w.journal.repository, 'commit', '-m', 'synthetic unaccepted commit')
    unaccepted = git(w.journal.repository, 'rev-parse', 'HEAD')
    w.journal.reconcile(base_oid=w.base, accepted_main=w.base, observe_main=w.provider.observe_remote_main_commit)
    capture = Path(w.journal.inspect()['last_capture'])
    assert git(capture / 'repository', 'rev-parse', 'HEAD') == unaccepted
    assert values(capture / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
    assert w.provider.reset_to_remote()
    w.journal.assert_replaceable()
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert StartupSynchronization(w.provider).run()
    assert values(w.journal.database) == ['BASE']
    assert values(capture / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
    w.journal.verify_capture(capture)


def test_unknown_reconciliation_does_not_change_journal(workspace):
    begin(workspace)
    before = workspace.journal.journal.read_bytes()
    with pytest.raises(RecoveryRequired):
        workspace.journal.reconcile(base_oid=workspace.base, accepted_main=workspace.base, observe_main=lambda: None)
    assert workspace.journal.journal.read_bytes() == before


def test_readonly_inspection_does_not_load_key_or_mutate(workspace, monkeypatch):
    begin(workspace)
    before = workspace.journal.fingerprint()
    def fail(self):
        raise AssertionError('key must not be loaded')
    monkeypatch.setattr(DatabaseKeyStore, 'load', fail)
    assert workspace.journal.inspect()['status'] == 'OPEN'
    assert workspace.journal.fingerprint() == before


@pytest.mark.parametrize('stage', ['before-journal', 'after-journal', 'after-db-commit', 'during-publish', 'lost-publish-ack'])
def test_real_process_kill_and_restart(workspace, stage):
    script = r'''
import os, sys, subprocess
from pathlib import Path
from centermanager.core import paths as p
p._paths = p.Paths()
p._paths._runtime_root = Path(sys.argv[1])
os.environ['ANTECHKIDS_FORCE_DATABASE_ENCRYPTION'] = '1'
from centermanager.database.encryption import DatabaseKeyStore, apply_sqlcipher_key, load_sqlcipher_driver
DatabaseKeyStore.load = lambda self: bytes(range(32))
from centermanager.platform.write_recovery import WriteRecoveryJournal
j = WriteRecoveryJournal()
stage, base = sys.argv[2:]
if stage != 'before-journal':
    j.begin('killed-session', base, {'session_id': 'killed-session'})
if stage in {'after-db-commit', 'during-publish', 'lost-publish-ack'}:
    c = load_sqlcipher_driver().connect(str(j.database))
    apply_sqlcipher_key(c, bytes(range(32)))
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA wal_autocheckpoint=0')
    c.execute("INSERT INTO recovery_items(value) VALUES ('KILLED_COMMIT')")
    c.commit()
if stage in {'during-publish', 'lost-publish-ack'}:
    c.close()
    from centermanager.database.artifact_security import materialize_runtime_database_to_repository
    materialize_runtime_database_to_repository()
    j.preserve('before-push')
    j.update(status='PUBLISHING')
    def git(*args):
        subprocess.run(['git', *args], cwd=j.repository, check=True, capture_output=True)
    git('add', '.')
    git('commit', '-m', 'synthetic killed publication')
    if stage == 'lost-publish-ack':
        git('push', 'origin', 'main')
print('READY', flush=True)
sys.stdin.read()
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    child = subprocess.Popen([sys.executable, '-c', script, str(workspace.paths.runtime_root), stage, workspace.base],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, env=env)
    try:
        line = child.stdout.readline()
        if line != 'READY\n':
            _, stderr = child.communicate(timeout=15)
            pytest.fail('Synthetic child failed before kill: ' + stderr)
        child.kill()
        child.communicate(timeout=15)
        assert child.returncode != 0
        if stage == 'before-journal':
            assert workspace.journal.inspect() is None
            workspace.journal.assert_replaceable(legacy=True)
        else:
            with pytest.raises(RecoveryRequired):
                workspace.journal.assert_replaceable()
            assert workspace.journal.inspect()['publication'] == 'UNVERIFIED'
            if stage in {'after-db-commit', 'during-publish', 'lost-publish-ack'}:
                assert values(workspace.journal.database) == ['BASE', 'KILLED_COMMIT']
                capture = workspace.journal.preserve('after-kill')
                assert values(capture / 'center.db') == ['BASE', 'KILLED_COMMIT']
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=15)


def test_restart_with_changed_remote_owner_remains_protected(workspace):
    from datetime import datetime, timedelta
    begin(workspace)
    mutate(workspace)
    record = {'locked': True, 'owner': 'successor', 'session_id': 'different-session',
              'lease_revision': 1, 'lease_expires_at': (datetime.now() + timedelta(seconds=60)).isoformat()}
    commit = workspace.provider._create_lock_commit_plumbing(record, None)
    assert workspace.provider._push_lock_branch(commit, None)
    assert workspace.provider.remote_lock_status()['session_id'] == 'different-session'
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert not StartupSynchronization(workspace.provider).run()
    assert values(workspace.journal.database) == ['BASE', 'LOCAL_UNACCEPTED']
    assert workspace.provider.remote_lock_status()['session_id'] == 'different-session'


@pytest.mark.parametrize('queued', [False, True])
def test_transaction_prepares_journal_before_editing_and_blocks_on_failure(workspace, monkeypatch, queued):
    from unittest.mock import Mock
    from centermanager.platform.collaboration import WriteRequestInfo, WriteRequestResult
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    collab = Mock()
    collab._sync_provider = workspace.provider
    collab.get_session_id.return_value = 'synthetic-session'
    collab.get_lock_generation.return_value = 1
    collab.request_write.return_value = WriteRequestInfo(WriteRequestResult.GRANTED)
    tx = WriteTransactionManager(collab)
    monkeypatch.setattr(tx, '_verify_first_writer_consistency', lambda: True)
    monkeypatch.setattr(tx, '_get_handoff_main_commit', lambda: workspace.base)
    observed = []
    def fail(self, *a, **k):
        observed.append(tx.is_editing)
        raise OSError('synthetic insufficient space')
    monkeypatch.setattr(WriteRecoveryJournal, 'begin', fail)
    if queued:
        tx._state = WriteTransactionState.GRANTING
        tx.on_write_granted()
    else:
        assert not tx.start_editing()
    assert observed == [False]
    assert not tx.is_editing
    assert tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert 'recovery protection failed' in tx.last_start_error
    collab.release_write.assert_called_once()


def test_manifest_tampering_cannot_authorize_reconciliation(workspace):
    import json
    begin(workspace)
    capture = Path(workspace.journal.inspect()['last_capture'])
    manifest = capture / 'manifest.json'
    document = json.loads(manifest.read_text())
    document['reason'] = 'forged'
    manifest.write_text(json.dumps(document))
    with pytest.raises(RecoveryRequired, match='authentication'):
        workspace.journal.verify_capture(capture)


def test_failed_cancel_preservation_retains_original_and_blocks(workspace, monkeypatch):
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    from unittest.mock import Mock
    begin(workspace)
    mutate(workspace)
    collab = Mock()
    tx = WriteTransactionManager(collab)
    tx._state = WriteTransactionState.EDITING
    tx._recovery_journal = workspace.journal
    def fail(*a):
        raise OSError('disk full')
    monkeypatch.setattr(workspace.journal, 'preserve', fail)
    assert not tx.cancel_editing(force=True)
    assert tx.state == WriteTransactionState.RECOVERY_REQUIRED
    collab.release_write.assert_not_called()
    assert values(workspace.journal.database) == ['BASE', 'LOCAL_UNACCEPTED']


def test_release_alone_cannot_mark_unpublished_session_clean(workspace):
    begin(workspace)
    workspace.journal.released()
    assert workspace.journal.inspect()['status'] == 'OPEN'
    assert workspace.journal.inspect()['publication'] == 'UNVERIFIED'
    with pytest.raises(RecoveryRequired):
        workspace.journal.assert_replaceable()


@pytest.mark.parametrize('callback_mutates', [False, True])
def test_real_transaction_sqlcipher_publish_release_and_second_session(workspace, monkeypatch, callback_mutates):
    from centermanager.events.event_bus import EventBus
    from centermanager.platform.collaboration import CollaborationManager
    from centermanager.platform.collaboration.heartbeat import HeartbeatManager
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    monkeypatch.setattr(HeartbeatManager, 'start', lambda self: None)
    collab = CollaborationManager(runtime_root=workspace.paths.runtime_root, event_bus=EventBus(), sync_provider=workspace.provider)
    collab.initialize('synthetic', 'synthetic', 'admin')
    tx = WriteTransactionManager(collab)
    class Sync:
        def execute_write_handoff_sync(self):
            return True  # Exact base already materialized by this fixture.
        def get_last_write_handoff_main_commit(self):
            return workspace.provider.get_local_main_commit()
        def publish_only(self, message, user, expected_main_commit, repository_already_materialized=False):
            assert repository_already_materialized
            return workspace.provider.publish_only(message, user, expected_main_commit)
    tx.set_sync_service(Sync())
    try:
        assert tx.start_editing(), tx.last_start_error
        assert workspace.journal.inspect()['status'] == 'OPEN'
        mutate(workspace)
        tx.mark_dirty()
        assert tx.finish_editing(on_publish_success=(lambda: mutate(workspace)) if callback_mutates else None)
        if callback_mutates:
            assert tx.state == WriteTransactionState.RECOVERY_REQUIRED
            document = workspace.journal.inspect()
            assert document['status'] == 'POST_PUBLISH_PENDING'
            assert document['release'] == 'VERIFIED'
            assert values(Path(document['last_capture']) / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED', 'LOCAL_UNACCEPTED']
            assert values(workspace.journal.repository / 'database' / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
            return
        assert tx.state == WriteTransactionState.IDLE
        assert workspace.journal.inspect()['status'] == 'CLEAN'
        workspace.journal.assert_replaceable()
        assert values(workspace.journal.repository / 'database' / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
        assert tx.start_editing(), tx.last_start_error
        assert workspace.journal.inspect()['status'] == 'OPEN'
        assert len(list((workspace.journal.root / 'history').iterdir())) == 1
    finally:
        collab.shutdown()


def test_cancel_release_failure_remains_blocked(workspace):
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    begin(workspace)
    tx = WriteTransactionManager(SimpleNamespace(is_writing=lambda: True, release_write=lambda: False))
    tx._state = WriteTransactionState.EDITING
    tx._recovery_journal = workspace.journal
    assert not tx.cancel_editing(force=True)
    assert not tx.is_editing
    assert tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert workspace.journal.inspect()['release'] == 'UNVERIFIED'


def test_duplicate_start_does_not_reclassify_active_journal(workspace):
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    begin(workspace)
    tx = WriteTransactionManager(SimpleNamespace())
    tx._state = WriteTransactionState.EDITING
    assert not tx.start_editing()
    assert tx.state == WriteTransactionState.EDITING
    assert workspace.journal.inspect()['status'] == 'OPEN'


def test_mutation_after_snapshot_prevents_reconciliation_receipt(workspace, monkeypatch):
    from centermanager.database import session
    begin(workspace)
    original = session.refresh_runtime_db
    def write_on_resume():
        original()
        mutate(workspace)
    monkeypatch.setattr(session, 'refresh_runtime_db', write_on_resume)
    with pytest.raises(RecoveryRequired, match='changed after'):
        workspace.journal.reconcile(base_oid=workspace.base, accepted_main=workspace.base,
                                    observe_main=workspace.provider.observe_remote_main_commit)
    assert workspace.journal.inspect()['status'] == 'OPEN'
    assert values(workspace.journal.database) == ['BASE', 'LOCAL_UNACCEPTED']


def test_post_publish_callback_commit_is_preserved_never_clean(workspace):
    begin(workspace)
    workspace.journal.update(status='PUBLISHING')
    workspace.journal.published(workspace.provider)
    # Reproduce ReportService's existing post-success metadata commit boundary.
    mutate(workspace)
    assert workspace.journal.preserve_post_publish_changes()
    workspace.journal.released()
    document = workspace.journal.inspect()
    assert document['status'] == 'POST_PUBLISH_PENDING'
    assert document['publication'] == 'VERIFIED' and document['release'] == 'VERIFIED'
    assert values(Path(document['last_capture']) / 'center.db') == ['BASE', 'LOCAL_UNACCEPTED']
    assert values(workspace.journal.repository / 'database' / 'center.db') == ['BASE']
    with pytest.raises(RecoveryRequired):
        workspace.journal.assert_replaceable()


def test_recovery_state_projects_readonly_actionable_ui():
    from unittest.mock import Mock
    from centermanager.ui.main_window import MainWindow
    from centermanager.services.write_transaction import WriteTransactionState
    status = Mock()
    view = SimpleNamespace(
        _transaction=SimpleNamespace(state=WriteTransactionState.RECOVERY_REQUIRED,
                                     is_editing=False, last_start_error='Preservation failed; free disk space and inspect recovery.'),
        start_edit_btn=Mock(), finish_edit_btn=Mock(), cancel_btn=Mock(),
        app_top_bar=Mock(), statusBar=lambda: status,
        _update_write_actions=Mock(), _editing_idle_timer=Mock())
    MainWindow._update_write_buttons(view)
    view._update_write_actions.assert_called_once_with(False)
    view.start_edit_btn.setVisible.assert_called_once_with(False)
    view.finish_edit_btn.setVisible.assert_called_once_with(False)
    status.showMessage.assert_called_once_with(view._transaction.last_start_error)
    view._editing_idle_timer.stop.assert_called_once()
