# -*- coding: utf-8 -*-
"""Application bootstrap for CenterManager."""

import sys
import logging
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config, init_config
from centermanager.core.logging import setup_logging
from centermanager.core.current_user import set_current_user
from centermanager.database.engine import create_production_engine
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
from centermanager.platform.business import BusinessModule

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
from centermanager.events.event_bus import EventBus
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.events.handlers.highlight_timeline_handler import HighlightTimelineHandler
from centermanager.ui.main_window import MainWindow
from centermanager.services.home_dashboard_service import HomeDashboardService
from centermanager.ui.login_dialog import LoginDialog
from centermanager.services.teacher_service import TeacherService
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
# Platform imports
from centermanager.platform import BootstrapManager, RuntimeContextManager, RuntimeState
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials

logger = logging.getLogger(__name__)


def ensure_schema():
    """Ensure all tables exist."""
    from centermanager.database.engine import create_production_engine
    from centermanager.database.base import Base
    import centermanager.models  # noqa: F401

    engine = create_production_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables ensured.")


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

        # ============================================
        # PLATFORM BOOTSTRAP
        # ============================================
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

        # ============================================
        # DATABASE SCHEMA
        # ============================================
        from sqlalchemy.orm import sessionmaker
        engine = create_production_engine(echo=False)
        session_factory = sessionmaker(bind=engine)
        ensure_schema()
        logger.info("[STARTUP] Schema migration completed")

        # ============================================
        # SEED ROLES & PERMISSIONS
        # ============================================
        logger.info("[STARTUP] Seeding roles and permissions...")
        try:
            with session_factory() as session:
                seed_roles_and_permissions(session)
            logger.info("[STARTUP] Roles and permissions seeded")
        except Exception as e:
            logger.exception("Error seeding roles/permissions")

        # ============================================
        # SERVICES INITIALIZATION
        # ============================================
        permission_service = PermissionService(session_factory)

        # Login
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

        # ============================================
        # PLATFORM SERVICES
        # ============================================
        event_bus = EventBus()

        # Synchronization
        sync_provider = None
        git_config = config.raw.get("git", {})
        if git_config.get("repository_url") and git_config.get("token"):
            try:
                repo_path = paths.runtime_root / "repository"
                
                # 1. Clone nếu chưa có
                if not repo_path.exists() or not (repo_path / ".git").exists():
                    logger.info("[STARTUP] Cloning repository...")
                    from centermanager.platform.synchronization.git.git_provider import GitProvider
                    from centermanager.platform.synchronization.git.git_credentials import GitCredentials
                    
                    creds = GitCredentials(
                        repository_url=git_config.get("repository_url"),
                        branch=git_config.get("branch", "main"),
                        token=git_config.get("token"),
                        username=git_config.get("username", ""),
                        email=git_config.get("email", ""),
                    )
                    provider = GitProvider(repo_path, creds)
                    provider.init_repository()  # clone
                    logger.info("[STARTUP] Repository cloned successfully")
                
                # 2. Tạo sync_provider và connect
                sync_provider = GitSynchronizationProvider(
                    repo_path=repo_path,
                    repository_url=git_config.get("repository_url"),
                    token=git_config.get("token"),
                    branch=git_config.get("branch", "main"),
                )
                if sync_provider.connect():
                    logger.info("[STARTUP] Git provider connected")
                else:
                    logger.warning("[STARTUP] Git provider connect failed")
                
            except Exception as e:
                logger.exception(f"Failed to initialize Git provider: {e}")

        sync_policy = SynchronizationPolicy.from_config(config.raw.get("collaboration", {}))

        # Collaboration
        collaboration_manager = CollaborationManager(
            runtime_root=paths.runtime_root,
            event_bus=event_bus,
        )
        collaboration_manager.initialize(
            user_id=str(current_user.id),
            username=current_user.username,
            role=current_user.role.name if current_user.role else "user",
            runtime_version=platform_context.runtime.manifest.runtime_version,
        )

        # Synchronization Manager
        sync_manager = SynchronizationManager(
            provider=sync_provider,
            policy=sync_policy,
            event_bus=event_bus,
        )

        # Runtime Sync Service
        sync_service = RuntimeSyncService(
            sync_manager=sync_manager,
            collab_manager=collaboration_manager,
            context_manager=context_manager,
            event_bus=event_bus,
            poll_interval=30,
        )
        sync_service.start()

        # ============================================
        # BUSINESS MODULES REGISTRATION
        # ============================================
        module_registry = BusinessModuleRegistry()

        # Initialize business services (existing code)
        timeline_service = TimelineService(session_factory)
        student_service = StudentService(session_factory, timeline_service)
        parent_service = ParentService(session_factory, timeline_service)
        assessment_service = AssessmentService(session_factory, timeline_service)
        session_service = SessionService(session_factory)
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
        home_service = HomeDashboardService(session_factory)
        analytics_service = StudentAnalyticsService(session_factory)

        teacher_timeline_service = TeacherTimelineService(session_factory)
        teacher_service = TeacherService(session_factory, teacher_timeline_service)
        teacher_assignment_service = TeacherAssignmentService(session_factory, teacher_timeline_service)
        teacher_document_service = TeacherDocumentService(session_factory, teacher_timeline_service)

        class_timeline_service = ClassTimelineService(session_factory)
        class_service = ClassService(session_factory, timeline_service=class_timeline_service)

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
        finance_dashboard_service = FinanceDashboardService(income_service, expense_service)
        outstanding_service = OutstandingService(session_factory)

        attendance_service = AttendanceService(
            session_factory=session_factory,
            timeline_service=timeline_service,
            permission_service=permission_service,
            report_policy=None,
            report_service=None,
        )

        report_service = ReportService(
            student_service=student_service,
            parent_service=parent_service,
            attendance_service=attendance_service,
            session_service=session_service,
            student_note_service=student_note_service,
            outstanding_service=outstanding_service,
            income_service=income_service,
            session_factory=session_factory,
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

        # ============================================
        # MAIN WINDOW
        # ============================================
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
            class_service=class_service,
            class_timeline_service=class_timeline_service,
            teacher_assignment_service_for_class=teacher_assignment_service,
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
        )

        logger.info("[STARTUP] MainWindow instance created")

        auto_report_service.run_daily_check()

        window.show()
        logger.info("[STARTUP] MainWindow shown")

        exit_code = qapp.exec()
        logger.info(f"[STARTUP] QApplication.exec finished with code {exit_code}")

        # Shutdown
        sync_service.stop()
        collaboration_manager.shutdown()

        return exit_code

    except Exception as e:
        logger.exception("[STARTUP] Fatal error")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())