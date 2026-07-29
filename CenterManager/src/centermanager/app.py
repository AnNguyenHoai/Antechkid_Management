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
from centermanager.database.engine import create_production_engine
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
from centermanager.events.event_bus import EventBus
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.events.handlers.highlight_timeline_handler import HighlightTimelineHandler
from centermanager.ui.main_window import MainWindow
from centermanager.services.home_dashboard_service import HomeDashboardService


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

    # Services
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

    # Event Bus
    event_bus = EventBus()
    highlight_service = StudentHighlightService(session_factory, session_service, event_bus)

    # Register timeline handler
    timeline_handler = HighlightTimelineHandler(timeline_service, session_service)
    event_bus.register(StudentHighlightCreated, timeline_handler)

    # Dashboard, Analytics, Home, Filter, Export, Import
    dashboard_service = StudentDashboardService(session_factory)
    filter_service = StudentFilterService(session_factory)
    export_service = StudentExportService(student_service)
    import_service = StudentImportService(student_service)
    home_service = HomeDashboardService(session_factory)
    analytics_service = StudentAnalyticsService(session_factory)

    logger.info("All services initialized")

    # Tạo MainWindow với tất cả dịch vụ cần thiết
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
    )
    window.show()
    logger.info("Main window initialized")

    exit_code = qapp.exec()
    logger.info(f"Application exiting with code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())