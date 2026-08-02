# -*- coding: utf-8 -*-
"""
Application bootstrap for CenterManager.
"""
import sys
import logging

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
from centermanager.services.finance_service import FinanceService
from centermanager.services.income_service import IncomeService
from centermanager.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)


def ensure_schema():
    from alembic.config import Config
    from alembic import command
    from centermanager.database.engine import get_database_path
    db_path = get_database_path()
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")


def main() -> int:
    paths = get_paths()
    paths.ensure_directories()
    init_config()
    config = get_config()

    setup_logging(
        log_dir=paths.logs_dir,
        app_name=config.get("application", {}).get("name", "CenterManager"),
        app_version=config.get("application", {}).get("version", "0.1.0"),
    )

    logger.info("CenterManager starting")
    logger.info(f"Configuration loaded: version {config.get('application', {}).get('version')}")
    logger.info(f"Runtime directories prepared at {paths.runtime_root}")

    ensure_schema()

    qapp = QApplication(sys.argv)
    qapp.setApplicationName(config.get("application", {}).get("name", "CenterManager"))
    qapp.setOrganizationName("CenterManager")

    from sqlalchemy.orm import sessionmaker
    engine = create_production_engine(echo=False)
    session_factory = sessionmaker(bind=engine)

    # Seed roles and permissions
    with session_factory() as session:
        seed_roles_and_permissions(session)

    # --- Initialize PermissionService ---
    permission_service = PermissionService(session_factory)

    # --- Show Login Dialog ---
    login_dialog = LoginDialog(permission_service)
    if login_dialog.exec() != LoginDialog.DialogCode.Accepted:
        logger.info("Login cancelled. Exiting.")
        return 0

    current_user = login_dialog.get_user()
    if current_user is None:
        logger.warning("No user after login. Exiting.")
        return 1

    set_current_user(current_user)
    logger.info(f"User authenticated: {current_user.username} (role: {current_user.role.name if current_user.role else 'none'})")

    # --- Initialize Services ---
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

    # Class services
    class_timeline_service = ClassTimelineService(session_factory)
    class_service = ClassService(
        session_factory,
        timeline_service=class_timeline_service,
    )

    # Finance Services
    finance_service = FinanceService(session_factory)
    expense_service = ExpenseService(session_factory)

    # Income Service - requires additional dependencies
    income_service = IncomeService(
        session_factory=session_factory,
        student_service=student_service,
        class_service=class_service,
        timeline_service=timeline_service,
        permission_service=permission_service,
    )

    logger.info("All services initialized")

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
        finance_service=finance_service,
        income_service=income_service,
        expense_service=expense_service,
    )
    window.show()
    logger.info("Main window initialized")

    exit_code = qapp.exec()
    logger.info(f"Application exiting with code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())