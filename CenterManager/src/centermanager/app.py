# -*- coding: utf-8 -*-
"""Application bootstrap for CenterManager."""

import sys
import logging
import traceback

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config, init_config
from centermanager.core.logging import setup_logging
from centermanager.core.current_user import set_current_user
from centermanager.core.application_identity import configure_windows_app_identity
from centermanager.database.engine import create_production_engine, initialize_runtime_database
from centermanager.database.seed import seed_roles_and_permissions
from centermanager.events.event_bus import EventBus

from centermanager.platform import (
    BootstrapManager,
    RuntimeContextManager,
    RuntimeState,
    CollaborationManager,
    SynchronizationManager,
    SynchronizationPolicy,
    RuntimeSyncService,
    BusinessModuleRegistry,
)
from centermanager.platform.business import BusinessModule
from centermanager.platform.collaboration import CollaborationPoller, PollerMode

from centermanager.ui.main_window import MainWindow
from centermanager.ui.application_icon import build_application_icon
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.services.student_filter_service import StudentFilterService
from centermanager.services.student_export_service import StudentExportService
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_note_service import StudentNoteService
from centermanager.services.student_document_service import StudentDocumentService
from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.services.permission_service import PermissionService
from centermanager.services.report_service import ReportService
from centermanager.services.report_policy import ReportPolicy
from centermanager.services.auto_report_service import AutoReportService
from centermanager.services.git_config_service import GitConfigService
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.events.handlers.highlight_timeline_handler import HighlightTimelineHandler
from centermanager.services.home_dashboard_service import HomeDashboardService
from centermanager.ui.login_dialog import LoginDialog
from centermanager.services.teacher_service import TeacherService
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_document_service import EmployeeDocumentService
from centermanager.services.employee_schedule_service import EmployeeScheduleService
from centermanager.services.employee_working_time_service import EmployeeWorkingTimeService
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.teacher_document_service import TeacherDocumentService
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.services.class_service import ClassService
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.services.income_service import IncomeService
from centermanager.services.expense_service import ExpenseService
from centermanager.services.expense_timeline_service import ExpenseTimelineService
from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.attendance_service import AttendanceService
from centermanager.platform import PlatformContext, PlatformLifecycleState
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.notification import NotificationService
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.platform.version import VersionManager
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.services.enrollment_service import EnrollmentService

logger = logging.getLogger(__name__)


def ensure_schema():
    """Upgrade the runtime database to the current Alembic schema."""
    from centermanager.database.migration import upgrade_database_to_head

    upgrade_database_to_head()
    logger.info("Database schema is at Alembic head.")


def _degrade_startup_to_verified_read(bootstrap, sync_provider, reason: str) -> None:
    """Recovery receipt failures never grant WRITE or veto verified MAIN READ.

    Caller MUST first complete authenticated Git MAIN/SQLCipher installation.
    This does not bypass schema verification, Git integrity or credential gates.
    """
    from centermanager.platform.sync.offline_read_state import (
        protect_read_only_for_process,
    )

    bootstrap._offline_read = True
    protect_read_only_for_process()
    sync_provider._startup_recovery_receipt_warning = True
    logger.warning(
        "[STARTUP] Recovery receipt unavailable; protected READ-only mode: %s",
        reason,
    )


def main() -> int:
    try:
        logger.info("[STARTUP] Application starting")
        paths = get_paths()
        paths.ensure_directories()
        init_config()
        config = get_config()
        setup_logging(
            log_dir=paths.logs_dir,
            app_name=config.get("application", {}).get("name", "CenterManager"),
            app_version=config.get("application", {}).get("version", "0.1.0"),
            console_level="INFO",
            file_level="DEBUG",
        )
        logger.info("[STARTUP] Config and logging initialized")

        # Windows taskbar/shortcut grouping must have a stable identity before
        # QApplication creates any native window handles.
        configure_windows_app_identity()
        qapp = QApplication(sys.argv)
        qapp.setApplicationName(config.get("application", {}).get("name", "CenterManager"))
        qapp.setOrganizationName("CenterManager")
        qapp.setWindowIcon(build_application_icon())

        instance_lock = QLockFile(str(paths.runtime_root / ".centermanager.instance.lock"))
        instance_lock.setStaleLockTime(30_000)
        if not instance_lock.tryLock(0):
            logger.error("[STARTUP] Another CenterManager process owns this runtime workspace")
            QMessageBox.warning(
                None,
                "CenterManager already running",
                "Another CenterManager process is already using this runtime workspace.\n\n"
                "Close the existing CenterManager window/process before starting a new one.",
            )
            return 2

        bootstrap = BootstrapManager()
        if not bootstrap.run():
            logger.error("[STARTUP] Bootstrap failed")
            QMessageBox.critical(None, "Startup Error", "Platform bootstrap failed. Please check logs.")
            return 1

        platform_context = bootstrap.get_context()
        context_manager = bootstrap._context_manager
        workspace_registry = bootstrap.get_workspace_registry()
        lifecycle = bootstrap.get_lifecycle()
        sync_provider = bootstrap.get_sync_provider()

        logger.info(f"[STARTUP] Platform ready: {platform_context.runtime.state.current.name}")

        if sync_provider is None:
            logger.error("[STARTUP] Bootstrap completed without an authoritative synchronization provider")
            QMessageBox.critical(
                None,
                "Synchronization Error",
                "CenterManager could not retain the authoritative Git synchronization context.",
            )
            return 1
        logger.info("[STARTUP] Reusing authoritative Git provider from bootstrap; startup sync already complete")

        from sqlalchemy.orm import sessionmaker

        git_config_service = GitConfigService()

        initialize_runtime_database()
        engine = create_production_engine(echo=False)
        session_factory = sessionmaker(bind=engine)

        # A previously CLEAN receipt certifies the DB before migration.
        # Record that exact pre-Alembic state now; only this uninterrupted
        # bootstrap can certify subsequent schema changes before login.
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        startup_journal = WriteRecoveryJournal()
        manual_reset_main = getattr(sync_provider, "_verified_manual_main_oid", None)
        review_reset_main = getattr(sync_provider, "_verified_review_main_oid", None)
        # Legacy Recovery may be malformed: it is already archived as raw
        # evidence. Never parse it as active metadata for this new MAIN session.
        schema_receipt_before = None
        recovery_advisory_present = bool(manual_reset_main or review_reset_main)
        if not recovery_advisory_present:
            try:
                schema_receipt_before = startup_journal.inspect()
                recovery_advisory_present = (
                    schema_receipt_before is not None
                    and schema_receipt_before.get("status") not in ("CLEAN", "PUBLISHED")
                )
            except Exception:
                # After independent Git MAIN identity/SQLCipher verification,
                # unreadable historical Recovery metadata is never a startup
                # admission or WRITE authority decision.
                logger.exception("Historical Recovery receipt unreadable; review is advisory")
                recovery_advisory_present = True
        # An interrupted local WRITE may have left unaccepted WAL bytes.
        # The authoritative MAIN was already reinstalled by BootstrapManager.
        # Verify that MAIN's packaged schema without executing DDL through an
        # obsolete Recovery guard; never auto-stamp the historical journal.
        if bootstrap._offline_read or recovery_advisory_present:
            # A cached READ must never implicitly stamp/migrate accepted data.
            from centermanager.database.migration import verify_runtime_schema_readonly
            verify_runtime_schema_readonly()
            logger.info("[STARTUP] Offline READ schema verified without mutation")
        else:
            ensure_schema()
            logger.info("[STARTUP] Schema ensured")

        # A first-time installation can legitimately migrate the freshly
        # downloaded MAIN database before login. Only this same-process
        # bootstrap, never an existing legacy runtime, can establish its
        # initial CLEAN receipt after Alembic has verified the schema.
        fresh_main = getattr(sync_provider, "_fresh_install_main_oid", None)
        try:
            if review_reset_main is not None:
                startup_journal.record_verified_review_reset(
                    provider=sync_provider,
                    accepted_main=review_reset_main,
                    notice_path=sync_provider._review_notice_path,
                )
            elif manual_reset_main is not None:
                startup_journal.record_verified_manual_reset(
                    provider=sync_provider,
                    accepted_main=manual_reset_main,
                    archive=sync_provider._verified_manual_backup_path,
                )
            elif fresh_main is not None:
                startup_journal.record_verified_fresh_install(
                    provider=sync_provider, accepted_main=fresh_main
                )
            elif (schema_receipt_before is not None
                    and schema_receipt_before.get("status") == "CLEAN"
                    and not bootstrap._offline_read):
                startup_journal.refresh_verified_bootstrap_migration(
                    provider=sync_provider, before=schema_receipt_before
                )
        except Exception:
            # Recovery is an audit record, never a WRITE permission source.
            # Git MAIN, SQLCipher, schema and remote lease remain independent
            # hard guards. Keep historical evidence and allow normal editing.
            logger.exception(
                "Recovery receipt unavailable; accepted Git MAIN remains usable "
                "for READ and independently authorized WRITE"
            )

        permission_service = PermissionService(session_factory)

        # Credential verification happens before collaboration identity exists,
        # but a forced password mutation must not be committed outside the
        # authoritative WRITE/publication protocol.
        login_dialog = LoginDialog(
            permission_service,
            defer_forced_password_change=True,
        )
        if login_dialog.exec() != LoginDialog.DialogCode.Accepted:
            logger.info("[STARTUP] Login cancelled. Exiting.")
            return 0

        current_user = login_dialog.get_user()
        if current_user is None:
            logger.error("[STARTUP] No user after login. Exiting.")
            return 1

        if bootstrap._offline_read and current_user.force_password_change:
            QMessageBox.warning(
                None, "Internet required for password change",
                "This account requires an authoritative password change. "
                "Connect to Git MAIN and complete password change before accessing cached data.",
            )
            return 1
        set_current_user(current_user)
        logger.info(f"[STARTUP] User authenticated: {current_user.username}")

        event_bus = EventBus()

        sync_policy = SynchronizationPolicy.from_config(config.raw.get("collaboration", {}))
        sync_manager = SynchronizationManager(
            provider=sync_provider,
            policy=sync_policy,
            event_bus=event_bus,
        )

        collaboration_manager = CollaborationManager(
            runtime_root=paths.runtime_root,
            event_bus=event_bus,
            sync_provider=sync_provider,
        )
        notification_service = NotificationService()

        collaboration_manager.initialize(
            user_id=str(current_user.id),
            username=current_user.username,
            role=current_user.role.name if current_user.role else "user",
            runtime_version=platform_context.runtime.manifest.runtime_version,
        )

        sync_service = RuntimeSyncService(
            sync_manager=sync_manager,
            collab_manager=collaboration_manager,
            context_manager=context_manager,
            event_bus=event_bus,
            poll_interval=30,
        )

        collaboration_manager.set_write_handoff_guard(
            sync_service.execute_write_handoff_sync
        )

        poller = CollaborationPoller(
            collaboration_manager=collaboration_manager,
            event_bus=event_bus,
            normal_interval=10,
            waiting_interval=3,
            max_backoff=120,
            initial_backoff=5,
        )
        poller.start()
        logger.info("[STARTUP] CollaborationPoller started")
        sync_service.start()

        module_registry = BusinessModuleRegistry()

        timeline_service = TimelineService(session_factory)

        student_service = StudentService(
            session_factory,
            timeline_service,
            event_bus=event_bus
        )

        parent_service = ParentService(
            session_factory,
            timeline_service,
            event_bus
        )

        assessment_service = AssessmentService(session_factory, timeline_service, event_bus=event_bus)
        session_service = SessionService(session_factory, event_bus=event_bus)
        note_service = SessionNoteService(session_factory, session_service)
        student_note_service = StudentNoteService(session_factory, timeline_service)
        document_service = StudentDocumentService(session_factory, timeline_service)
        summary_service = StudentSummaryService(
            student_service=student_service,
            parent_service=parent_service,
            assessment_service=assessment_service,
            timeline_service=timeline_service,
            session_factory=session_factory,
        )

        highlight_service = StudentHighlightService(session_factory, session_service, event_bus)
        timeline_handler = HighlightTimelineHandler(timeline_service, session_service)
        event_bus.register(StudentHighlightCreated, timeline_handler)

        dashboard_service = StudentDashboardService(session_factory)
        filter_service = StudentFilterService(session_factory)
        export_service = StudentExportService(student_service)
        import_service = StudentImportService(student_service)

        home_service = HomeDashboardService(session_factory, event_bus=event_bus)

        analytics_service = StudentAnalyticsService(session_factory)

        employee_service = EmployeeService(session_factory)
        employee_document_service = EmployeeDocumentService(session_factory, paths.runtime_root / "Attachments")
        employee_schedule_service = EmployeeScheduleService(session_factory)
        employee_working_time_service = EmployeeWorkingTimeService(session_factory, employee_schedule_service)
        employee_work_registration_service = EmployeeWorkRegistrationService(session_factory)

        teacher_timeline_service = TeacherTimelineService(session_factory)
        teacher_service = TeacherService(
            session_factory, teacher_timeline_service, event_bus=event_bus
        )
        teacher_assignment_service = TeacherAssignmentService(
            session_factory, teacher_timeline_service, event_bus=event_bus
        )
        teacher_document_service = TeacherDocumentService(
            session_factory, teacher_timeline_service, event_bus=event_bus
        )
        teacher_assignment_service_for_class = teacher_assignment_service

        class_timeline_service = ClassTimelineService(session_factory)
        class_service = ClassService(session_factory, timeline_service=class_timeline_service, event_bus=event_bus)
        enrollment_service = EnrollmentService(session_factory, event_bus=event_bus)

        expense_timeline_service = ExpenseTimelineService(session_factory)
        expense_service = ExpenseService(
            session_factory=session_factory,
            timeline_service=expense_timeline_service,
            permission_service=permission_service,
        )
        income_service = IncomeService(
            session_factory=session_factory,
            student_service=student_service,
            class_service=class_service,
            timeline_service=timeline_service,
            permission_service=permission_service,
        )
        outstanding_service = OutstandingService(session_factory)
        finance_dashboard_service = FinanceDashboardService(
            income_service, expense_service, outstanding_service
        )

        attendance_service = AttendanceService(
            session_factory=session_factory,
            timeline_service=timeline_service,
            permission_service=permission_service,
            report_policy=None,
            report_service=None,
            event_bus=event_bus,
        )

        from centermanager.platform.business.guard import WriteGuard
        report_service = ReportService(
            student_service=student_service,
            parent_service=parent_service,
            attendance_service=attendance_service,
            session_service=session_service,
            student_note_service=student_note_service,
            outstanding_service=outstanding_service,
            income_service=income_service,
            session_factory=session_factory,
            write_guard=WriteGuard(collaboration_manager),
        )

        report_policy = ReportPolicy(
            student_service=student_service,
            session_service=session_service,
            class_service=class_service,
            attendance_service=attendance_service,
            report_service=report_service,
        )
        student_service._report_policy = report_policy
        student_service._report_service = report_service
        assessment_service._report_policy = report_policy
        assessment_service._report_service = report_service
        attendance_service._report_policy = report_policy
        attendance_service._report_service = report_service

        auto_report_service = AutoReportService(
            student_service=student_service,
            report_service=report_service,
        )

        metadata_dir = paths.runtime_root / "metadata"
        metadata_repo = JsonMetadataRepository(metadata_dir)
        version_manager = VersionManager(metadata_repo, event_bus)

        transaction_manager = WriteTransactionManager(collaboration_manager)
        transaction_manager.enable_local_mutation_gate()
        if sync_service is not None:
            transaction_manager.set_sync_service(sync_service)
        else:
            logger.warning("[STARTUP] WriteTransactionManager: sync service disabled")
        transaction_manager.set_version_manager(version_manager)
        transaction_manager.set_report_callback(report_service.generate_published_reports)

        window = MainWindow(
            student_service=student_service,
            parent_service=parent_service,
            timeline_service=timeline_service,
            assessment_service=assessment_service,
            summary_service=summary_service,
            session_service=session_service,
            note_service=note_service,
            highlight_service=highlight_service,
            dashboard_service=dashboard_service,
            home_service=home_service,
            student_note_service=student_note_service,
            document_service=document_service,
            analytics_service=analytics_service,
            filter_service=filter_service,
            export_service=export_service,
            import_service=import_service,
            teacher_service=teacher_service,
            teacher_assignment_service=teacher_assignment_service,
            teacher_document_service=teacher_document_service,
            teacher_timeline_service=teacher_timeline_service,
            employee_service=employee_service,
            employee_document_service=employee_document_service,
            employee_schedule_service=employee_schedule_service,
            employee_working_time_service=employee_working_time_service,
            employee_work_registration_service=employee_work_registration_service,
            class_service=class_service,
            enrollment_service=enrollment_service,
            class_timeline_service=class_timeline_service,
            teacher_assignment_service_for_class=teacher_assignment_service_for_class,
            permission_service=permission_service,
            income_service=income_service,
            expense_service=expense_service,
            finance_dashboard_service=finance_dashboard_service,
            outstanding_service=outstanding_service,
            attendance_service=attendance_service,
            report_service=report_service,
            platform_context=platform_context,
            collaboration_manager=collaboration_manager,
            sync_service=sync_service,
            module_registry=module_registry,
            transaction_manager=transaction_manager,
            notification_service=notification_service,
            git_config_service=git_config_service,
            event_bus=event_bus,
            poller=poller,
        )

        logger.info("[STARTUP] MainWindow instance created")

        # MainWindow owns the write-state transition. Publish the detailed
        # transaction rejection reason on the next event-loop turn so operator
        # feedback reflects the final GRANTED/WAITING/ERROR result instead of a
        # generic three-second status-bar message.
        def report_start_edit_outcome() -> None:
            def publish_result() -> None:
                message = transaction_manager.last_start_error
                if not message or transaction_manager.is_editing:
                    return
                if transaction_manager.state == WriteTransactionState.WAITING:
                    window.app_top_bar.notify_warning(message)
                elif transaction_manager.state == WriteTransactionState.IDLE:
                    window.app_top_bar.notify_error(message)

            QTimer.singleShot(0, publish_result)

        window.app_top_bar.start_edit_requested.connect(report_start_edit_outcome)

        if not bootstrap._offline_read:
            auto_report_service.run_daily_check()

        window.show()
        logger.info("[STARTUP] MainWindow shown")

        # Forced password changes are authoritative shared-data mutations.
        # Run them only after collaboration, handoff sync, poller and the
        # WriteTransactionManager are all live. The coordinator keeps the
        # workspace restricted until publication succeeds.
        password_change_coordinator = None
        if current_user.force_password_change and not bootstrap._offline_read:
            from centermanager.ui.authoritative_password_change import (
                AuthoritativePasswordChangeCoordinator,
            )

            password_change_coordinator = AuthoritativePasswordChangeCoordinator(
                window=window,
                current_user=current_user,
                permission_service=permission_service,
                transaction_manager=transaction_manager,
                collaboration_manager=collaboration_manager,
            )
            window._authoritative_password_change_coordinator = password_change_coordinator
            QTimer.singleShot(0, password_change_coordinator.start)

        exit_code = qapp.exec()
        logger.info(f"[STARTUP] QApplication.exec finished with code {exit_code}")

        if sync_service is not None:
            sync_service.stop()
        poller.stop()
        collaboration_manager.shutdown()

        return exit_code

    except Exception:
        logger.exception("[STARTUP] Fatal error")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
