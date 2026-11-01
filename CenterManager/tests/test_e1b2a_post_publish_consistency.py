"""Synthetic SQLCipher/Git reporting lifecycle, preserving E1B-1 boundaries."""
from datetime import date
from functools import wraps
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from reportlab.pdfgen import canvas

from tests.test_e1b1_durable_write_recovery import workspace, KEY, connect, git  # noqa: F401
from centermanager.database.base import Base
from centermanager.database.engine import create_engine_for_path
from centermanager.database.artifact_security import materialize_runtime_database_to_repository
from centermanager.models.student import Student
from centermanager.models.class_ import Class
from centermanager.models.session import Session as LessonSession
from centermanager.models.attendance import Attendance
from centermanager.models.enrollment import Enrollment
from centermanager.services.student_service import StudentService
from centermanager.services.report_service import ReportService, ReportPreparationError
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.heartbeat import HeartbeatManager
from centermanager.platform.business.guard import WriteGuard
from centermanager.events.event_bus import EventBus


@pytest.fixture
def reporting(workspace, monkeypatch):
    w = workspace
    engine = create_engine_for_path(w.journal.database, encrypted=True, encryption_key=KEY,
                                    runtime_guarded=True, allow_create=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([Student(id=1, student_code='SYN001', full_name='Synthetic One'),
                    Student(id=2, student_code='SYN002', full_name='Synthetic Two'),
                    Class(id=1, name='Synthetic Class', planned_sessions=2)])
        db.commit()
        db.add(LessonSession(id=1, class_id=1, session_number=1, title='Synthetic Lesson', scheduled_date=date.today()))
        db.add(Enrollment(id=1, student_id=1, class_id=1, start_date=date.today(), status='ACTIVE'))
        db.commit()
        db.add(Attendance(id=1, session_id=1, student_id=1, status='Absent'))
        db.commit()
    materialize_runtime_database_to_repository()
    git(w.journal.repository, 'add', '.')
    git(w.journal.repository, 'commit', '-m', 'synthetic reporting schema and fixtures')
    git(w.journal.repository, 'push', 'origin', 'main')
    w.base = git(w.journal.repository, 'rev-parse', 'HEAD')
    monkeypatch.setattr(HeartbeatManager, 'start', lambda self: None)
    cm = CollaborationManager(runtime_root=w.paths.runtime_root, event_bus=EventBus(), sync_provider=w.provider)
    cm.initialize('synthetic', 'synthetic', 'admin')
    tx = WriteTransactionManager(cm)
    students = StudentService(factory)
    service = ReportService(students, None, None, None, None, None, None, factory,
                            write_guard=WriteGuard(cm))
    rendered = []
    class Renderer:
        def generate(self, student_id, output_path):
            with factory() as db:
                student = db.get(Student, student_id)
                statuses = [a.status for a in db.query(Attendance).filter_by(student_id=student_id)]
                enrollments = [e.status for e in db.query(Enrollment).filter_by(student_id=student_id)]
                text = f'{student.full_name}|{statuses}|enrollments={enrollments}'
            rendered.append((student_id, text))
            pdf = canvas.Canvas(str(output_path))
            pdf.drawString(50, 700, text)
            pdf.save()
            return output_path
    service._generator = Renderer()
    accepted = {'value': False}
    post_accept_writes = []
    @event.listens_for(engine, 'before_cursor_execute')
    def track_authoritative_writes(conn, cursor, statement, parameters, context, executemany):
        if accepted['value'] and statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP')):
            post_accept_writes.append(statement)
    class Sync:
        def execute_write_handoff_sync(self):
            return True  # Fixture materialized and committed this exact accepted base.
        def get_last_write_handoff_main_commit(self):
            return w.provider.get_local_main_commit()
        def publish_only(self, message, user, expected_main_commit, repository_already_materialized=False):
            assert repository_already_materialized
            result = w.provider.publish_only(message, user, expected_main_commit)
            accepted['value'] = result
            return result
    tx.set_sync_service(Sync())
    tx.set_report_callbacks(service.prepare_for_publication, service.verify_publication_reports)
    w.tx, w.cm, w.reports, w.factory, w.rendered = tx, cm, service, factory, rendered
    w.accepted, w.post_accept_writes = accepted, post_accept_writes
    yield w
    cm.shutdown()
    engine.dispose()


def mutate(w, kind='student'):
    with w.factory() as db:
        if kind == 'student':
            db.get(Student, 1).full_name = 'UPDATED SYNTHETIC'
        elif kind == 'attendance':
            db.get(Attendance, 1).status = 'Present'
        elif kind == 'enrollment':
            db.get(Enrollment, 1).status = 'WITHDRAWN'
        db.commit()
    w.tx.mark_student_dirty(1)


def remote_rows(w, sql):
    db = connect(w.journal.repository / 'database' / 'center.db', readonly=True)
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


@pytest.mark.parametrize('kind', ['student', 'attendance', 'enrollment'])
def test_modified_aggregate_finish_publishes_report_metadata_once_and_restarts_clean(reporting, kind):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    mutate(w, kind)
    assert w.tx.finish_editing(), w.tx.last_finish_error
    assert w.tx.state == WriteTransactionState.IDLE
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert remote_rows(w, 'SELECT student_id, report_type FROM reports') == [(1, 'latest')]
    assert len(w.rendered) == 1
    if kind == 'student':
        assert 'UPDATED SYNTHETIC' in w.rendered[0][1]
    if kind == 'attendance':
        assert 'Present' in w.rendered[0][1]
    if kind == 'enrollment':
        assert 'WITHDRAWN' in w.rendered[0][1]
    assert not w.post_accept_writes
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert StartupSynchronization(w.provider).run()
    assert w.reports.get_student_reports(1)[0].file_path.endswith('StudentProfile.pdf')
    w.journal.assert_replaceable()


def test_multiple_dirty_students_deduplicated_before_one_publication(reporting):
    w = reporting
    assert w.tx.start_editing()
    for sid in (2, 1, 2, 1):
        w.tx.mark_student_dirty(sid)
    assert w.tx.finish_editing()
    assert [sid for sid, text in w.rendered] == [1, 2]
    assert remote_rows(w, 'SELECT student_id FROM reports ORDER BY student_id') == [(1,), (2,)]
    assert not w.post_accept_writes


def test_readonly_regeneration_and_daily_export_leave_sqlcipher_and_clean_receipt_intact(reporting):
    from centermanager.services.auto_report_service import AutoReportService
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    assert w.tx.finish_editing()
    before_db = w.journal.database.read_bytes()
    count = len(remote_rows(w, 'SELECT id FROM reports'))
    pdf = w.reports.generate_student_report(1)
    local = w.reports.get_student_reports(1)[0]
    assert local.id == -1 and w.reports.get_report_file_path(-1) == pdf
    assert w.journal.database.read_bytes() == before_db
    daily = AutoReportService(StudentService(w.factory), w.reports)
    daily.run_daily_check()
    assert daily._state_file.exists()
    assert w.journal.database.read_bytes() == before_db
    assert len(remote_rows(w, 'SELECT id FROM reports')) == count
    assert not w.post_accept_writes
    assert w.journal.inspect()['status'] == 'CLEAN'
    w.journal.assert_replaceable()


def test_generation_failure_before_publish_keeps_open_journal_and_can_retry(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    before = w.provider.observe_remote_main_commit()
    original = w.reports._generator.generate
    def fail(*args):
        raise OSError('synthetic report disk failure')
    monkeypatch.setattr(w.reports._generator, 'generate', fail)
    assert not w.tx.finish_editing()
    assert 'MAIN was not published' in w.tx.last_finish_error
    assert w.tx.state == WriteTransactionState.EDITING
    assert w.journal.inspect()['status'] == 'OPEN'
    assert w.provider.observe_remote_main_commit() == before
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert not StartupSynchronization(w.provider).run()
    monkeypatch.setattr(w.reports._generator, 'generate', original)
    assert w.tx.finish_editing(), w.tx.last_finish_error
    assert w.journal.inspect()['status'] == 'CLEAN'


def test_report_file_failure_after_core_publish_is_distinct_and_does_not_dirty_db(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.tx._sync_service.publish_only
    @wraps(original)
    def accepted_then_file_lost(**kwargs):
        result = original(**kwargs)
        w.reports._default_report_path(1).unlink()
        return result
    monkeypatch.setattr(w.tx._sync_service, 'publish_only', accepted_then_file_lost)
    assert w.tx.finish_editing()
    assert w.tx.state == WriteTransactionState.IDLE
    assert 'Core data was published' in w.tx.report_warning
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert not w.post_accept_writes
    # READ-mode regeneration restores delivery without a second SQL/Git push.
    w.reports.generate_student_report(1)
    w.journal.assert_replaceable()
    assert not w.post_accept_writes


@pytest.mark.parametrize('outcome', ['rejected', 'lost-ack'])
def test_unaccepted_or_unknown_publish_keeps_report_metadata_and_artifacts_protected(reporting, monkeypatch, outcome):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.tx._sync_service.publish_only
    @wraps(original)
    def publish(**kwargs):
        if outcome == 'lost-ack':
            original(**kwargs)
        else:
            return False
        raise RuntimeError('synthetic unknown publication response')
    monkeypatch.setattr(w.tx._sync_service, 'publish_only', publish)
    assert not w.tx.finish_editing()
    assert w.journal.inspect()['status'] == 'PUBLISHING'
    assert w.accepted['value'] == (outcome == 'lost-ack')
    assert w.reports._default_report_path(1).exists()
    from centermanager.platform.write_recovery import RecoveryRequired
    with pytest.raises(RecoveryRequired):
        w.reports.generate_student_report(1)  # Cannot overwrite pending artifacts.
    with pytest.raises(RecoveryRequired):
        w.journal.assert_replaceable()


def test_active_sqlcipher_wal_during_reports_is_included_in_publication(reporting):
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        from sqlalchemy import text
        db.execute(text('PRAGMA journal_mode=WAL'))
        db.execute(text('PRAGMA wal_autocheckpoint=0'))
        db.get(Student, 1).full_name = 'WAL SYNTHETIC'
        db.commit()
    w.tx.mark_student_dirty(1)
    assert w.tx.finish_editing()
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('WAL SYNTHETIC',)]
    assert remote_rows(w, 'SELECT student_id FROM reports') == [(1,)]
    assert w.journal.inspect()['status'] == 'CLEAN'


def test_derived_update_cannot_hide_unrelated_unaccepted_file_change(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    assert w.tx.finish_editing()
    old = w.reports._generator.generate
    def render_and_mutate_attachment(*args):
        result = old(*args)
        w.paths.attachment_dir.joinpath('unaccepted.txt').write_text('synthetic unsaved attachment')
        return result
    monkeypatch.setattr(w.reports._generator, 'generate', render_and_mutate_attachment)
    from centermanager.platform.write_recovery import RecoveryRequired
    with pytest.raises(RecoveryRequired):
        w.reports.generate_student_report(1)
    with pytest.raises(RecoveryRequired):
        w.journal.assert_replaceable()
    assert w.paths.attachment_dir.joinpath('unaccepted.txt').exists()


@pytest.mark.parametrize('failure', ['metadata', 'file-install'])
def test_pre_publish_persistence_failure_restores_previous_report_pair_and_keeps_recovery(reporting, monkeypatch, failure):
    w = reporting
    assert w.tx.start_editing()
    pdf = w.reports.generate_student_report(1)
    receipt = pdf.with_suffix('.report.json')
    previous = (pdf.read_bytes(), receipt.read_bytes())
    capture = w.journal.inspect()['last_capture']
    mutate(w)
    if failure == 'metadata':
        @event.listens_for(w.factory.kw['bind'], 'before_cursor_execute')
        def fail_metadata(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('INSERT INTO REPORTS'):
                raise OSError('synthetic metadata persistence failure')
    else:
        import centermanager.platform.write_recovery as recovery
        original = recovery._install
        def fail_receipt(source, destination):
            if Path(destination) == receipt:
                raise OSError(28, 'synthetic insufficient disk space')
            return original(source, destination)
        monkeypatch.setattr(recovery, '_install', fail_receipt)
    assert not w.tx.finish_editing()
    assert w.tx.state == WriteTransactionState.EDITING
    assert w.provider.observe_remote_main_commit() == w.base
    assert (pdf.read_bytes(), receipt.read_bytes()) == previous
    assert w.journal.inspect()['status'] == 'OPEN'
    assert Path(capture).exists()
    w.journal.verify_capture(capture)
    assert remote_rows(w, 'SELECT student_id FROM reports') == []


def test_receipt_failure_after_verified_publish_is_report_warning_without_sql_or_recovery_loss(reporting, monkeypatch):
    import centermanager.platform.write_recovery as recovery
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = recovery._json
    def fail_receipt(path, document):
        if Path(path).suffix == '.json' and Path(path).name.endswith('.report.json'):
            raise OSError('synthetic local receipt write failure')
        return original(path, document)
    monkeypatch.setattr(recovery, '_json', fail_receipt)
    assert w.tx.finish_editing()
    assert w.accepted['value']
    assert w.tx.report_warning
    assert not w.post_accept_writes
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert w.reports.get_report_file_path(-1) is None
    assert Path(w.journal.inspect()['last_capture']).exists()
    w.journal.assert_replaceable()


def test_report_preparation_does_not_extend_finishing_deadline(reporting, monkeypatch):
    from datetime import datetime, timedelta
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.reports._generator.generate
    def slow_renderer(*args):
        result = original(*args)
        w.tx._finishing_deadline = datetime.now() - timedelta(seconds=1)
        return result
    monkeypatch.setattr(w.reports._generator, 'generate', slow_renderer)
    assert not w.tx.finish_editing()
    assert w.tx.state == WriteTransactionState.FINISHING_STALE
    assert w.provider.observe_remote_main_commit() == w.base
    assert w.journal.inspect()['status'] == 'OPEN'
    assert 'Nothing was published' in w.tx.last_finish_error


def test_true_post_publish_sql_mutation_still_preserves_recovery(reporting):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    def unexpected_authoritative_side_effect():
        with w.factory() as db:
            db.get(Student, 1).full_name = 'UNACCEPTED CALLBACK'
            db.commit()
    assert w.tx.finish_editing(on_publish_success=unexpected_authoritative_side_effect)
    assert w.tx.state == WriteTransactionState.RECOVERY_REQUIRED
    assert w.journal.inspect()['status'] == 'POST_PUBLISH_PENDING'
    capture = Path(w.journal.inspect()['last_capture'])
    w.journal.verify_capture(capture)
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('UPDATED SYNTHETIC',)]
    from centermanager.platform.write_recovery import RecoveryRequired
    for _ in range(2):
        with pytest.raises(RecoveryRequired):
            w.reports.generate_student_report(1)
        assert capture.exists()
        w.journal.verify_capture(capture)


def test_new_accepted_main_invalidates_old_local_report_receipt(reporting):
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    assert w.tx.finish_editing()
    assert w.reports.get_report_file_path(-1)
    git(w.journal.repository, 'commit', '--allow-empty', '-m', 'synthetic next accepted MAIN')
    git(w.journal.repository, 'push', 'origin', 'main')
    # Simulate an accepted no-DB-change synchronization, keeping the old PDF.
    assert StartupSynchronization(w.provider).run()
    assert w.reports.get_report_file_path(-1) is None
    legacy = remote_rows(w, 'SELECT id FROM reports')[0][0]
    assert w.reports.get_report_file_path(legacy) is None
    w.reports.generate_student_report(1)
    assert w.reports.get_report_file_path(-1)
    w.journal.assert_replaceable()
