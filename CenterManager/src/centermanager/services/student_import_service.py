# -*- coding: utf-8 -*-
"""
StudentImportService - imports students from Excel.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import openpyxl
from sqlalchemy.orm import sessionmaker

from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.student_service import StudentService
from centermanager.services.exceptions import StudentValidationError

logger = logging.getLogger(__name__)


class StudentImportService:
    """Service to import students from Excel file."""

    def __init__(
        self,
        session_factory: sessionmaker,
        student_service: StudentService,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._student_service = student_service
        self._repository_provider = repository_provider or create_default_repository_provider()

    def import_from_excel(self, file_path: Path) -> Tuple[int, int, List[str]]:
        """Import students from Excel file."""
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        errors: List[str] = []
        success = 0

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or (not row[0] and not row[1]):
                continue

            try:
                code = row[0] if row[0] else None
                full_name = row[1]
                if not full_name:
                    errors.append(f"Row {row_idx}: Full name is required")
                    continue

                if code:
                    with self._session_factory() as session:
                        repo = self._repository_provider.students(session)
                        existing = repo.get_by_code(str(code))
                    if existing:
                        errors.append(f"Row {row_idx}: Student code {code} already exists")
                        continue

                dob = None
                if row[3]:
                    try:
                        if isinstance(row[3], datetime):
                            dob = row[3].date()
                        else:
                            dob = datetime.strptime(str(row[3]), "%Y-%m-%d").date()
                    except ValueError:
                        errors.append(f"Row {row_idx}: Invalid date format (use YYYY-MM-DD)")
                        continue

                student = self._student_service.create_student(
                    full_name=str(full_name).strip(),
                    preferred_name=str(row[2]).strip() if row[2] else None,
                    date_of_birth=dob,
                    gender=str(row[4]).strip() if row[4] else None,
                    status=str(row[5]).strip() if row[5] else "ACTIVE",
                    current_level=str(row[6]).strip() if row[6] else None,
                    notes=str(row[7]).strip() if row[7] else None,
                )
                success += 1
                logger.info("Imported student %s: %s", student.student_code, student.full_name)
            except StudentValidationError as e:
                errors.append(f"Row {row_idx}: {str(e)}")
            except Exception as e:
                logger.exception("Error importing row %s", row_idx)
                errors.append(f"Row {row_idx}: {str(e)}")

        return success, len(errors), errors
