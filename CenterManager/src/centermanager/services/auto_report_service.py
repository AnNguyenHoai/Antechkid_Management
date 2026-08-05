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
        """Kiểm tra và tạo báo cáo tự động cho tất cả học sinh nếu đã qua ít nhất 1 ngày."""
        today = date.today()
        last_run = self._get_last_run_date()

        if today <= last_run:
            logger.info(f"Auto report already run today (last run: {last_run}), skipping.")
            return

        logger.info(f"Running auto report for all students (last run: {last_run}, today: {today})")
        try:
            students = self._student_service.list_students()
            if not students:
                logger.info("No active students found, skipping auto report.")
                self._save_last_run_date(today)
                return

            generated_count = 0
            for student in students:
                try:
                    # Kiểm tra xem đã có báo cáo daily trong ngày hôm nay chưa
                    if self._report_service.report_exists(student.id, "daily") and self._report_service.report_exists(student.id, "daily"):
                        # Nếu đã có thì bỏ qua (nhưng vẫn tạo nếu chưa có)
                        pass  # có thể bỏ qua
                    # Tạo báo cáo với trigger_event = "daily"
                    self._report_service.generate_student_report(
                        student.id,
                        report_type="automatic",
                        trigger_event="daily",
                        generated_by="system"
                    )
                    generated_count += 1
                except Exception as e:
                    logger.exception(f"Failed to generate daily report for student {student.id}: {e}")

            logger.info(f"Auto report completed. Generated {generated_count} reports for {len(students)} students.")
        except Exception as e:
            logger.exception("Failed to run daily auto report.")
        finally:
            # Luôn cập nhật ngày chạy, kể cả khi có lỗi, để tránh lặp vô hạn
            self._save_last_run_date(today)