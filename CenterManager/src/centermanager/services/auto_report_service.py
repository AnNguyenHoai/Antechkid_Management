# -*- coding: utf-8 -*-
"""
AutoReportService - tự động tạo báo cáo cho tất cả học sinh theo ngày.
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List

from centermanager.core.paths import get_paths
from centermanager.services.student_service import StudentService
from centermanager.services.report_service import ReportService

logger = logging.getLogger(__name__)


class AutoReportService:
    def __init__(
        self,
        student_service: StudentService,
        report_service: ReportService,
    ):
        self._student_service = student_service
        self._report_service = report_service
        self._state_file = get_paths().config_dir / "auto_report_state.json"

    def _get_last_run_date(self) -> date:
        """Đọc ngày chạy báo cáo tự động gần nhất từ file state."""
        if self._state_file.exists():
            try:
                with open(self._state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return datetime.strptime(data.get('last_run_date', '1970-01-01'), '%Y-%m-%d').date()
            except Exception:
                return date(1970, 1, 1)
        return date(1970, 1, 1)

    def _save_last_run_date(self, run_date: date) -> None:
        """Lưu ngày chạy báo cáo tự động."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {'last_run_date': run_date.strftime('%Y-%m-%d')}
        with open(self._state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def run_daily_check(self) -> None:
        """Generate one daily report per student and retry incomplete students."""
        today = date.today()
        last_run = self._get_last_run_date()
        if last_run >= today:
            logger.info("Auto report already completed today (%s), skipping.", last_run)
            return
        try:
            students = self._student_service.list_students()
        except Exception:
            logger.exception("Failed to load students for daily auto report.")
            return
        if not students:
            self._save_last_run_date(today)
            return

        failed = False
        generated_count = 0
        for student in students:
            try:
                if self._report_service.report_exists_on_date(student.id, "daily", today):
                    continue
                self._report_service.generate_student_report(
                    student.id, report_type="automatic",
                    trigger_event="daily", generated_by="system"
                )
                generated_count += 1
            except Exception:
                failed = True
                logger.exception(
                    "Failed to generate daily report for student %s; will retry later.",
                    student.id,
                )

        complete = not failed
        if complete:
            for student in students:
                try:
                    if not self._report_service.report_exists_on_date(student.id, "daily", today):
                        complete = False
                        break
                except Exception:
                    complete = False
                    break

        if complete:
            self._save_last_run_date(today)
            logger.info("Auto report completed: generated=%s total=%s",
                        generated_count, len(students))
        else:
            logger.warning(
                "Auto report incomplete; completion state was not advanced so retry remains enabled."
            )

