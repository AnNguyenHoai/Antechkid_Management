# -*- coding: utf-8 -*-
"""
Application bootstrap for CenterManager.
"""
import sys
import logging
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config, init_config
from centermanager.core.logging import setup_logging
from centermanager.core.current_user import set_current_user
from centermanager.database.engine import create_production_engine
from centermanager.database.seed import seed_roles_and_permissions
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
from centermanager.services.auto_report_service import AutoReportService

logger = logging.getLogger(__name__)

def ensure_schema():
    """
    Ensure database schema is up-to-date using Alembic.
    If migration fails, attempt to create tables directly as fallback.
    """
    try:
        from alembic.config import Config
        from alembic import command
        from centermanager.database.engine import get_database_path, create_engine_for_path
        from centermanager.database.base import Base
        import centermanager.models  # noqa: F401

        db_path = get_database_path()
        logger.info(f"Ensuring schema for database: {db_path}")

        # Kiểm tra xem có file alembic.ini không
        alembic_ini = Path("alembic.ini")
        if not alembic_ini.exists():
            logger.warning("alembic.ini not found. Creating tables directly.")
            engine = create_engine_for_path(db_path)
            Base.metadata.create_all(engine)
            logger.info("Tables created directly.")
            return

        # Cấu hình Alembic
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        # Kiểm tra xem bảng alembic_version đã tồn tại chưa
        from sqlalchemy import inspect
        engine = create_engine_for_path(db_path)
        inspector = inspect(engine)
        has_alembic_table = "alembic_version" in inspector.get_table_names()

        if has_alembic_table:
            # Đã có migration, chỉ cần upgrade
            logger.info("Alembic version table found. Running upgrade...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Schema upgrade completed.")
        else:
            # Chưa có migration, tạo bảng trực tiếp (dành cho lần chạy đầu)
            logger.info("No alembic_version table. Creating all tables directly.")
            Base.metadata.create_all(engine)
            logger.info("Tables created directly.")
            # Sau đó stamp version để Alembic biết
            try:
                command.stamp(alembic_cfg, "head")
                logger.info("Stamped alembic version.")
            except Exception as e:
                logger.warning(f"Could not stamp alembic version: {e}")

    except Exception as e:
        logger.error(f"ensure_schema failed: {e}")
        # Fallback: tạo bảng trực tiếp
        try:
            from centermanager.database.engine import create_engine_for_path
            from centermanager.database.base import Base
            from centermanager.database.engine import get_database_path
            import centermanager.models  # noqa: F401

            db_path = get_database_path()
            engine = create_engine_for_path(db_path)
            Base.metadata.create_all(engine)
            logger.info("Fallback: Tables created directly.")
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            raise


def main() -> int:
    try:
        logger.info("[STARTUP-00] Application start")
        paths = get_paths()
        paths.ensure_directories()
        init_config()
        config = get_config()
        setup_logging(
            log_dir=paths.logs_dir,
            app_name=config.get("application", {}).get("name", "CenterManager"),
            app_version=config.get("application", {}).get("version", "0.1.0"),
        )
        logger.info("[STARTUP-01] Config and logging initialized")

        logger.info(f"Configuration loaded: version {config.get('application', {}).get('version')}")
        logger.info(f"Runtime directories prepared at {paths.runtime_root}")

        ensure_schema()
        logger.info("[STARTUP-02] Schema migration completed")

        logger.info("[STARTUP-03] Creating QApplication...")
        qapp = QApplication(sys.argv)
        qapp.setApplicationName(config.get("application", {}).get("name", "CenterManager"))
        qapp.setOrganizationName("CenterManager")
        logger.info("[STARTUP-04] QApplication created")

        from sqlalchemy.orm import sessionmaker
        engine = create_production_engine(echo=False)
        session_factory = sessionmaker(bind=engine)
        logger.info("[STARTUP-05] Database session factory created")

        logger.info("[STARTUP-06] Seeding roles and permissions...")
        try:
            with session_factory() as session:
                seed_roles_and_permissions(session)
            logger.info("[STARTUP-07] Roles and permissions seeded")
        except Exception as e:
            logger.exception("Error seeding roles/permissions")
            raise

        logger.info("[STARTUP-08] Initializing PermissionService...")
        permission_service = PermissionService(session_factory)
        logger.info("[STARTUP-09] PermissionService initialized")

        logger.info("[STARTUP-10] Showing login dialog...")
        login_dialog = LoginDialog(permission_service)
        if login_dialog.exec() != LoginDialog.DialogCode.Accepted:
            logger.info("[STARTUP-11] Login cancelled. Exiting.")
            return 0
        logger.info("[STARTUP-12] Login accepted")

        current_user = login_dialog.get_user()
        if current_user is None:
            logger.error("[STARTUP-13] No user after login. Exiting.")
            return 1
        logger.info(f"[STARTUP-14] User authenticated: id={current_user.id}, username={current_user.username}, role={current_user.role.name if current_user.role else 'None'}")

        set_current_user(current_user)
        logger.info("[STARTUP-15] Current user set")

        logger.info("[STARTUP-16] Initializing services...")
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
        event_bus = EventBus()
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
        class_service = ClassService(
            session_factory,
            timeline_service=class_timeline_service,
        )

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

        # Tạo attendance_service tạm thời chưa có report_policy
        attendance_service = AttendanceService(
            session_factory=session_factory,
            timeline_service=timeline_service,
            permission_service=permission_service,
            report_policy=None,
            report_service=None,
        )

        # Tạo report_service (cần attendance_service)
        report_service = ReportService(
            student_service=student_service,
            parent_service=parent_service,
            attendance_service=attendance_service,
            session_service=session_service,
            student_note_service=student_note_service,
            outstanding_service=outstanding_service,
            income_service=income_service,
            session_factory=session_factory,   # THÊM DÒNG NÀY
        )

        # Tạo report_policy (cần attendance_service và report_service)
        report_policy = ReportPolicy(
            student_service=student_service,
            session_service=session_service,
            class_service=class_service,
            attendance_service=attendance_service,
            report_service=report_service,
        )
        auto_report_service = AutoReportService(
            student_service=student_service,
            report_service=report_service,
        )
        # Gán report_policy và report_service vào attendance_service
        attendance_service._report_policy = report_policy
        attendance_service._report_service = report_service

        logger.info("[STARTUP-17] All services initialized")

        # Tạo MainWindow
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
        )
        auto_report_service.run_daily_check()
        logger.info("[STARTUP-19] MainWindow instance created")
        window.show()
        logger.info("[STARTUP-20] MainWindow shown")

        exit_code = qapp.exec()
        logger.info(f"[STARTUP-21] QApplication.exec finished with code {exit_code}")
        return exit_code

    except Exception as e:
        logger.exception("[STARTUP-ERROR] Fatal error")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())