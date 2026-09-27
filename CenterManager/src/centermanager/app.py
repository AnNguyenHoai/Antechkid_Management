# -*- coding: utf-8 -*-
"""Application bootstrap for CenterManager."""

import os
import sys
import logging
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from centermanager.core.paths import get_paths
from centermanager.core.git_locator import locate_git
from centermanager.core.config import get_config, init_config
from centermanager.core.logging import setup_logging
from centermanager.core.current_user import set_current_user
from centermanager.database.engine import create_production_engine, initialize_runtime_database
from centermanager.database.seed import seed_roles_and_permissions
from centermanager.events.event_bus import EventBus

from centermanager.platform import (
    BootstrapManager,
    RuntimeContextManager,
    RuntimeState,
    CollaborationManager,
    SynchronizationManager,
    GitSynchronizationProvider,
    SynchronizationPolicy,
    RuntimeSyncService,
    BusinessModuleRegistry,
)
from centermanager.platform.sync import StartupSynchronization
from centermanager.platform.business import BusinessModule
from centermanager.platform.collaboration import CollaborationPoller, PollerMode

from centermanager.ui.main_window import MainWindow
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
from centermanager.platform import BootstrapManager, PlatformContext, PlatformLifecycleState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.notification import NotificationService
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.platform.version import VersionManager
from centermanager.services.write_transaction import WriteTransactionManager
from centermanager.services.enrollment_service import EnrollmentService

logger = logging.getLogger(__name__)


def ensure_schema():
    """Upgrade the runtime database to the current Alembic schema."""
    from centermanager.database.migration import upgrade_database_to_head
    upgrade_database_to_head()
    logger.info("Database schema is at Alembic head.")


def _build_permission_service(session_factory):
    """Select local or service-owned authentication for SEC-02 migration/UAT.

    This switch migrates authentication only. It deliberately does not imply
    protected-storage enforcement because startup and remaining domain services
    still use the transitional local SQLAlchemy engine.
    """
    transport = os.environ.get("ANTECHKIDS_AUTH_TRANSPORT", "local").strip().lower()
    if transport == "local":
        return PermissionService(session_factory)
    if transport == "service":
        from centermanager.platform.protected_data_service.permission_adapter import (
            ProtectedPermissionServiceAdapter,
        )
        logger.info("[SEC-02] Authentication transport: AnTechKidsData service")
        return ProtectedPermissionServiceAdapter()
    raise RuntimeError(
        "Unsupported ANTECHKIDS_AUTH_TRANSPORT value; expected 'local' or 'service'."
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

        qapp = QApplication(sys.argv)
        qapp.setApplicationName(config.get("application", {}).get("name", "CenterManager"))
        qapp.setOrganizationName("CenterManager")

        bootstrap = BootstrapManager()
        if not bootstrap.run():
            logger.error("[STARTUP] Bootstrap failed")
            QMessageBox.critical(None, "Startup Error", "Platform bootstrap failed. Please check logs.")
            return 1

        platform_context = bootstrap.get_context()
        context_manager = bootstrap._context_manager
        workspace_registry = bootstrap.get_workspace_registry()
        lifecycle = bootstrap.get_lifecycle()
        logger.info(f"[STARTUP] Platform ready: {platform_context.runtime.state.current.name}")

        from sqlalchemy.orm import sessionmaker

        git_config_service = GitConfigService()
        git_executable = locate_git()
        git_config = None
        sync_provider = None
        if not git_executable:
            logger.warning("[STARTUP] Git executable unavailable; starting in local/offline mode")
        elif git_config_service.has_config():
            git_config = git_config_service.get_config()
            if git_config is None:
                logger.warning("[STARTUP] Git configuration is invalid; starting in local/offline mode")
            else:
                repo_path = paths.runtime_root / "repository"
                sync_provider = GitSynchronizationProvider(
                    repo_path=repo_path,
                    repository_url=git_config.repository_url,
                    token=git_config.token,
                    username=git_config.username,
                    branch=git_config.branch,
                    email=git_config.email or "",
                    git_executable=str(git_executable),
                )
                logger.info("[STARTUP] Running startup synchronization...")
                startup_sync = StartupSynchronization(sync_provider)
                if not startup_sync.run():
                    logger.error("[STARTUP] Startup synchronization failed; refusing to start with a non-authoritative database")
                    QMessageBox.critical(
                        None,
                        "Synchronization Error",
                        "Unable to synchronize the authoritative Git database.\n"
                        "CenterManager will not start with a stale local database.\n\n"
                        "Please check the network connection and Git configuration.",
                    )
                    return 1
                logger.info("[STARTUP] Startup synchronization completed")
        else:
            logger.info("[STARTUP] No Git configuration found; starting in local/offline mode")

        initialize_runtime_database()
        engine = create_production_engine(echo=False)
        session_factory = sessionmaker(bind=engine)
        ensure_schema()
        logger.info("[STARTUP] Schema ensured")

        # SEC-02 B2: service-owned auth can be enabled independently for UAT while
        # the rest of the application remains on transitional local persistence.
        permission_service = _build_permission_service(session_factory)

        login_dialog = LoginDialog(permission_service)
        if login_dialog.exec() != LoginDialog.DialogCode.Accepted:
            logger.info("[STARTUP] Login cancelled. Exiting.")
            return 0
        current_user = login_dialog.get_user()
        if current_user is None:
            logger.error("[STARTUP] No user after login. Exiting.")
            return 1
        set_current_user(current_user)
        logger.info(f"[STARTUP] User authenticated: {current_user.username}")

        event_bus = EventBus()
        sync_policy = SynchronizationPolicy.from_config(config.raw.get("collaboration", {}))
        sync_manager = SynchronizationManager(provider=sync_provider, policy=sync_policy, event_bus=event_bus)
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

        # Remaining application composition is intentionally unchanged below.
        # It stays on the transitional local persistence boundary until each
        # domain is migrated to operation-oriented service APIs.
        from centermanager.app_runtime import run_composed_application
        return run_composed_application(
            qapp=qapp,
            paths=paths,
            config=config,
            platform_context=platform_context,
            context_manager=context_manager,
            lifecycle=lifecycle,
            session_factory=session_factory,
            current_user=current_user,
            permission_service=permission_service,
            event_bus=event_bus,
            sync_provider=sync_provider,
            sync_manager=sync_manager,
            collaboration_manager=collaboration_manager,
            notification_service=notification_service,
            sync_service=sync_service,
        )
    except Exception as exc:
        logger.exception("[STARTUP] Fatal startup error: %s", exc)
        try:
            QMessageBox.critical(None, "Startup Error", str(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
