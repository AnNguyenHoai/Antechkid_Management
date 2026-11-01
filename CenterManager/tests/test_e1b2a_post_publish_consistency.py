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
from centermanager.models.report import Report
from centermanager.services.student_service import StudentService
from centermanager.services.report_service import ReportService, ReportGenerationError
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.heartbeat import HeartbeatManager
from centermanager.platform.business.guard import WriteGuard
from centermanager.events.event_bus import EventBus


@pytest.fixture
def reporting(workspace, monkeypatch, tmp_path):
    w = workspace
    seed_path = tmp_path / "reporting-seed.db"
    engine = create_engine_for_path(seed_path, encrypted=True, encryption_key=KEY)
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
        db.add(Report(id=1, student_id=1, file_path="Reports/Student/SYN001/StudentProfile.pdf",
                      report_type="legacy", generated_by="synthetic", metadata_json="{}"))
        db.add(Attendance(id=1, session_id=1, student_id=1, status='Absent'))
        db.commit()
    engine.dispose()
    import shutil
    shutil.copy2(seed_path, w.journal.database)
    engine = create_engine_for_path(w.journal.database, encrypted=True, encryption_key=KEY,
                                    runtime_guarded=True, allow_create=False)
    factory = sessionmaker(bind=engine)
    materialize_runtime_database_to_repository()
    git(w.journal.repository, 'add', '.')
    git(w.journal.repository, 'commit', '-m', 'synthetic reporting schema and fixtures')
    git(w.journal.repository, 'push', 'origin', 'main')
    w.base = git(w.journal.repository, 'rev-parse', 'HEAD')
    monkeypatch.setattr(HeartbeatManager, 'start', lambda self: None)
    cm = CollaborationManager(runtime_root=w.paths.runtime_root, event_bus=EventBus(), sync_provider=w.provider)
    cm.initialize('1', 'synthetic', 'admin')
    tx = WriteTransactionManager(cm)
    tx.enable_local_mutation_gate()
    from types import SimpleNamespace
    from centermanager.core.current_user import get_current_user, set_current_user
    from centermanager.core.capabilities import Capability
    old_actor = get_current_user()
    set_current_user(SimpleNamespace(id=1, full_name='Synthetic', username='synthetic', role=SimpleNamespace(name='admin'),
                                    is_active=True, permissions=set(Capability.values())))
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
    tx.set_report_callback(service.generate_published_reports)
    w.tx, w.cm, w.reports, w.factory, w.rendered = tx, cm, service, factory, rendered
    w.accepted, w.post_accept_writes = accepted, post_accept_writes
    yield w
    cm.shutdown()
    set_current_user(old_actor)
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
def test_modified_aggregate_finish_generates_current_report_without_post_publish_sql_and_restarts_clean(reporting, kind):
    w = reporting
    assert w.tx.start_editing(), w.tx.last_start_error
    mutate(w, kind)
    assert w.tx.finish_editing(), w.tx.last_start_error
    assert w.tx.state == WriteTransactionState.IDLE
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert remote_rows(w, 'SELECT student_id, report_type FROM reports') == [(1, 'legacy')]
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
    local = w.reports.get_student_reports(1)[0]
    assert local.id == -1 and local.report_type == 'latest'
    w.journal.assert_replaceable()


def test_multiple_dirty_students_deduplicated_after_one_verified_publication(reporting):
    w = reporting
    assert w.tx.start_editing()
    for sid in (2, 1, 2, 1):
        w.tx.mark_student_dirty(sid)
    assert w.tx.finish_editing()
    assert [sid for sid, text in w.rendered] == [1, 2]
    assert [w.reports.get_student_reports(sid)[0].id for sid in (1, 2)] == [-1, -2]
    assert remote_rows(w, 'SELECT student_id FROM reports') == [(1,)]
    assert not w.post_accept_writes


def test_readonly_regeneration_and_daily_export_leave_sqlcipher_and_clean_receipt_intact(reporting):
    from centermanager.services.auto_report_service import AutoReportService
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    assert w.tx.finish_editing()
    before_db = w.journal.database.read_bytes()
    pdf = w.reports.generate_student_report(1)
    local = w.reports.get_student_reports(1)[0]
    assert local.id == -1 and w.reports.get_report_file_path(-1) == pdf
    assert w.journal.database.read_bytes() == before_db
    daily = AutoReportService(StudentService(w.factory), w.reports)
    daily.run_daily_check()
    assert daily._state_file.exists()
    assert w.journal.database.read_bytes() == before_db
    assert remote_rows(w, 'SELECT report_type FROM reports') == [('legacy',)]
    assert not w.post_accept_writes
    assert w.journal.inspect()['status'] == 'CLEAN'
    w.journal.assert_replaceable()


def test_generation_with_changed_database_report_metadata_never_hides_or_rewrites_it(reporting):
    w = reporting
    assert w.tx.start_editing()
    with w.factory() as db:
        db.get(Report, 1).report_type = 'legitimate-metadata-change'
        db.commit()
    w.tx.mark_student_dirty(1)
    before = w.journal.database.read_bytes()
    w.reports.generate_student_report(1)
    assert w.journal.database.read_bytes() == before
    assert w.journal.inspect()['status'] == 'OPEN'
    assert w.tx.finish_editing()
    assert remote_rows(w, 'SELECT report_type FROM reports') == [('legitimate-metadata-change',)]
    assert not w.post_accept_writes
    assert w.journal.inspect()['status'] == 'CLEAN'


def test_generation_failure_before_publish_keeps_open_journal_and_business_changes(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.reports._generator.generate
    def fail(*args):
        raise OSError('synthetic report disk failure')
    monkeypatch.setattr(w.reports._generator, 'generate', fail)
    with pytest.raises(OSError):
        w.reports.generate_student_report(1)
    assert w.tx.state == WriteTransactionState.EDITING
    assert w.journal.inspect()['status'] == 'OPEN'
    assert w.provider.observe_remote_main_commit() == w.base
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    assert not StartupSynchronization(w.provider).run()
    monkeypatch.setattr(w.reports._generator, 'generate', original)
    assert w.tx.finish_editing()
    assert w.journal.inspect()['status'] == 'CLEAN'


def test_report_failure_after_core_publish_is_distinct_and_restart_is_safe(reporting, monkeypatch):
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.reports._generator.generate
    def fail(*args):
        assert w.accepted['value']  # Reports never gate an otherwise authorized core publish.
        raise OSError('synthetic report file failure')
    monkeypatch.setattr(w.reports._generator, 'generate', fail)
    assert w.tx.finish_editing()
    assert w.tx.state == WriteTransactionState.IDLE
    assert 'Core data was published' in w.tx.report_warning
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('UPDATED SYNTHETIC',)]
    assert not w.post_accept_writes
    assert StartupSynchronization(w.provider).run()
    monkeypatch.setattr(w.reports._generator, 'generate', original)
    w.reports.generate_student_report(1)
    w.journal.assert_replaceable()
    assert not w.post_accept_writes


@pytest.mark.parametrize('outcome', ['rejected', 'lost-ack'])
def test_unaccepted_or_unknown_publish_keeps_existing_artifacts_and_recovery_protected(reporting, monkeypatch, outcome):
    w = reporting
    assert w.tx.start_editing()
    pdf = w.reports.generate_student_report(1)
    previous = pdf.read_bytes()
    w.rendered.clear()
    mutate(w)
    original = w.tx._sync_service.publish_only
    @wraps(original)
    def publish(**kwargs):
        if outcome == 'lost-ack':
            original(**kwargs)
            raise RuntimeError('synthetic unknown publication response')
        return False
    monkeypatch.setattr(w.tx._sync_service, 'publish_only', publish)
    assert not w.tx.finish_editing()
    assert w.journal.inspect()['status'] == 'PUBLISHING'
    assert w.accepted['value'] == (outcome == 'lost-ack')
    assert not w.rendered  # No report success callback on rejection or unknown response.
    assert pdf.read_bytes() == previous
    from centermanager.platform.write_recovery import RecoveryRequired
    for _ in range(2):
        with pytest.raises(RecoveryRequired):
            w.reports.generate_student_report(1)
        with pytest.raises(RecoveryRequired):
            w.journal.assert_replaceable()
        assert pdf.read_bytes() == previous
        w.journal.verify_capture(w.journal.inspect()['last_capture'])


def test_active_sqlcipher_wal_during_reports_is_preserved_in_publication(reporting):
    w = reporting
    assert w.tx.start_editing()
    # Prepare WAL through an unmodified external-client simulation. Live
    # application handles cannot change persistence PRAGMAs without maintenance.
    raw = connect(w.journal.database)
    raw.execute('PRAGMA journal_mode=WAL')
    raw.execute('PRAGMA wal_autocheckpoint=0')
    raw.close()
    with w.factory() as db:
        db.get(Student, 1).full_name = 'WAL SYNTHETIC'
        db.commit()
    w.reports.generate_student_report(1)  # READ projection while WRITE/WAL is active.
    w.tx.mark_student_dirty(1)
    assert w.tx.finish_editing()
    assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('WAL SYNTHETIC',)]
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert not w.post_accept_writes


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


@pytest.mark.parametrize('failure', ['pdf-install', 'receipt-install'])
def test_pre_publish_disk_failure_restores_previous_pair_and_keeps_recovery(reporting, monkeypatch, failure):
    import centermanager.platform.write_recovery as recovery
    w = reporting
    assert w.tx.start_editing()
    pdf = w.reports.generate_student_report(1)
    receipt = pdf.with_suffix('.report.json')
    previous = (pdf.read_bytes(), receipt.read_bytes())
    capture = w.journal.inspect()['last_capture']
    mutate(w)
    original = recovery._install
    def fail_install(source, destination):
        if Path(destination) == (pdf if failure == 'pdf-install' else receipt):
            raise OSError(28, 'synthetic insufficient disk space')
        return original(source, destination)
    monkeypatch.setattr(recovery, '_install', fail_install)
    with pytest.raises(OSError):
        w.reports.generate_student_report(1)
    assert w.tx.state == WriteTransactionState.EDITING
    assert w.provider.observe_remote_main_commit() == w.base
    assert (pdf.read_bytes(), receipt.read_bytes()) == previous
    assert w.journal.inspect()['status'] == 'OPEN'
    w.journal.verify_capture(capture)


def test_receipt_failure_after_verified_publish_is_report_warning_without_sql_or_recovery_loss(reporting, monkeypatch):
    import centermanager.platform.write_recovery as recovery
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = recovery._install
    def fail_receipt(source, destination):
        if Path(destination).name.endswith('.report.json'):
            raise OSError('synthetic local receipt write failure')
        return original(source, destination)
    monkeypatch.setattr(recovery, '_install', fail_receipt)
    assert w.tx.finish_editing()
    assert w.accepted['value'] and w.tx.report_warning
    assert not w.post_accept_writes
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert w.reports.get_report_file_path(-1) is None
    w.journal.verify_capture(w.journal.inspect()['last_capture'])
    w.journal.assert_replaceable()


def test_render_runs_only_after_verification_without_extending_deadline(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    original = w.reports._generator.generate
    deadlines = []
    def render(*args):
        assert w.accepted['value']
        assert w.tx.state == WriteTransactionState.PUBLISHED
        assert w.journal.inspect()['status'] == 'PUBLISHED'
        deadline = w.tx._finishing_deadline
        result = original(*args)
        assert w.tx._finishing_deadline == deadline
        deadlines.append(deadline)
        return result
    monkeypatch.setattr(w.reports._generator, 'generate', render)
    assert w.tx.finish_editing()
    assert len(deadlines) == 1 and deadlines[0] is not None


def test_true_post_publish_sql_mutation_still_preserves_recovery(reporting):
    w = reporting
    assert w.tx.start_editing()
    mutate(w)
    def unexpected_authoritative_side_effect():
        # Unmodified/third-party writer outside the application gate remains an
        # E1C blocker; E1B-1 must still detect and preserve its actual mutation.
        raw = connect(w.journal.database)
        try:
            raw.execute("UPDATE students SET full_name='UNACCEPTED CALLBACK' WHERE id=1")
            raw.commit()
        finally:
            raw.close()
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
    assert StartupSynchronization(w.provider).run()
    assert w.reports.get_report_file_path(-1) is None
    assert w.reports.get_report_file_path(1) is None
    w.reports.generate_student_report(1)
    assert w.reports.get_report_file_path(-1)
    w.journal.assert_replaceable()


@pytest.mark.parametrize('role', ['admin', 'reception'])
def test_production_renderer_respects_permissions_without_blocking_core_publish(reporting, role):
    from types import SimpleNamespace
    from centermanager.services.parent_service import ParentService
    from centermanager.services.attendance_service import AttendanceService
    from centermanager.services.session_service import SessionService
    from centermanager.services.student_note_service import StudentNoteService
    from centermanager.services.outstanding_service import OutstandingService
    from centermanager.services.income_service import IncomeService
    from centermanager.export.pdf.student_report_generator import StudentReportGenerator
    from centermanager.core.current_user import CurrentUserContext
    from centermanager.core.capabilities import Capability
    w = reporting
    w.reports._generator = StudentReportGenerator(
        w.reports._student_service, ParentService(w.factory),
        AttendanceService(w.factory, None, None), SessionService(w.factory),
        StudentNoteService(w.factory), OutstandingService(w.factory),
        IncomeService(w.factory, None, None, None, None))
    permissions = {c.value for c in Capability} if role == 'admin' else {'student.view', 'student.update'}
    principal = SimpleNamespace(id=1, role=SimpleNamespace(name=role), is_active=True,
                                permissions=permissions, full_name='Synthetic Renderer')
    with CurrentUserContext(principal):
        assert w.tx.start_editing(), w.tx.last_start_error
        mutate(w)
        assert w.tx.finish_editing()
        assert w.journal.inspect()['status'] == 'CLEAN'
        assert remote_rows(w, 'SELECT full_name FROM students WHERE id=1') == [('UPDATED SYNTHETIC',)]
        if role == 'admin':
            assert not w.tx.report_warning
            assert w.reports.get_report_file_path(-1).read_bytes().startswith(b'%PDF-')
            w.reports.generate_student_report(1)
        else:
            assert w.tx.report_warning  # Existing lesson.view denial remains enforced.
            assert w.reports.get_report_file_path(-1) is None
        assert not w.post_accept_writes
        w.journal.assert_replaceable()


def test_one_report_failure_does_not_skip_other_dirty_students(reporting, monkeypatch):
    w = reporting
    assert w.tx.start_editing()
    w.tx.mark_student_dirty(1)
    w.tx.mark_student_dirty(2)
    original = w.reports._generator.generate
    def render(student_id, path):
        if student_id == 1:
            raise OSError('synthetic first report failure')
        return original(student_id, path)
    monkeypatch.setattr(w.reports._generator, 'generate', render)
    assert w.tx.finish_editing()
    assert w.tx.report_warning
    assert w.reports.get_report_file_path(-2)
    assert w.journal.inspect()['status'] == 'CLEAN'
    assert not w.post_accept_writes
