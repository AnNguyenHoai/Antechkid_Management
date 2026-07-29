# -*- coding: utf-8 -*-
"""
StudentExportService - exports student data to Excel.
"""
from datetime import datetime
from pathlib import Path
from typing import List

import openpyxl
from openpyxl.styles import Font, Alignment

from centermanager.core.paths import get_paths
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService


class StudentExportService:
    """Service to export student list to Excel."""

    def __init__(self, student_service: StudentService) -> None:
        self._student_service = student_service

    def export_all_active(self, file_path: Path = None) -> Path:
        """Export all active students to an Excel file."""
        if file_path is None:
            export_dir = get_paths().excel_export_dir
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = export_dir / f"students_{timestamp}.xlsx"

        students = self._student_service.list_students()
        return self._write_excel(students, file_path)

    def _write_excel(self, students: List[Student], file_path: Path) -> Path:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Students"

        # Headers
        headers = [
            "Code", "Full Name", "Preferred Name", "Date of Birth",
            "Gender", "Status", "Level", "Notes"
        ]
        ws.append(headers)
        # Style header
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # Data rows
        for s in students:
            ws.append([
                s.student_code,
                s.full_name,
                s.preferred_name or "",
                s.date_of_birth.strftime("%Y-%m-%d") if s.date_of_birth else "",
                s.gender or "",
                s.status or "",
                s.current_level or "",
                s.notes or ""
            ])

        # Auto adjust column widths (simple)
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_len:
                        max_len = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_len + 2, 30)
            ws.column_dimensions[col_letter].width = adjusted_width

        wb.save(file_path)
        return file_path