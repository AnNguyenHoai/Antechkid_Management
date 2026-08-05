# -*- coding: utf-8 -*-
"""
ReportStorage - manages saving and loading report PDFs and metadata.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from centermanager.core.paths import get_paths

logger = logging.getLogger(__name__)


class ReportStorage:
    """
    Handles file system operations for report PDFs and metadata.
    Reports are stored under runtime/Export/StudentProfile/{student_code}/year/
    with filenames: {report_type}_{timestamp}.pdf and corresponding .meta.json
    """

    def __init__(self) -> None:
        self._base_dir = get_paths().student_profile_dir

    def _get_student_dir(self, student_code: str) -> Path:
        """Get the directory for a student's reports."""
        student_dir = self._base_dir / student_code
        student_dir.mkdir(parents=True, exist_ok=True)
        return student_dir

    def _get_year_dir(self, student_code: str, year: int) -> Path:
        """Get the year subdirectory for a student."""
        year_dir = self._get_student_dir(student_code) / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir

    def _generate_filename(self, report_type: str, timestamp: datetime) -> str:
        """Generate a unique filename for the report."""
        safe_type = report_type.replace(" ", "_")
        return f"{safe_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

    def save_report(
        self,
        student_code: str,
        pdf_data: bytes,
        metadata: Dict[str, Any],
        report_type: str = "BaoCao",
    ) -> Path:
        """
        Save a report PDF and its metadata.
        Returns the path to the PDF file.
        """
        timestamp = datetime.now()
        year = timestamp.year
        year_dir = self._get_year_dir(student_code, year)

        base_filename = self._generate_filename(report_type, timestamp)
        pdf_filename = f"{base_filename}.pdf"
        meta_filename = f"{base_filename}.meta.json"

        pdf_path = year_dir / pdf_filename
        meta_path = year_dir / meta_filename

        # Save PDF
        with open(pdf_path, "wb") as f:
            f.write(pdf_data)

        # Save metadata
        metadata["filename"] = pdf_filename
        metadata["timestamp"] = timestamp.isoformat()
        metadata["year"] = year
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Report saved: {pdf_path}")
        return pdf_path

    def get_reports_for_student(self, student_code: str) -> List[Dict[str, Any]]:
        """
        Get all reports for a student, including metadata.
        Returns a list of metadata dicts sorted by timestamp descending.
        """
        student_dir = self._get_student_dir(student_code)
        reports = []

        # Walk through year subdirectories
        for year_dir in student_dir.glob("*"):
            if not year_dir.is_dir():
                continue
            for meta_file in year_dir.glob("*.meta.json"):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    # Add file path for opening
                    pdf_file = meta_file.with_suffix(".pdf")
                    if pdf_file.exists():
                        metadata["pdf_path"] = str(pdf_file)
                        metadata["meta_path"] = str(meta_file)
                        reports.append(metadata)
                except Exception as e:
                    logger.error(f"Failed to load metadata from {meta_file}: {e}")

        # Sort by timestamp descending
        reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return reports

    def get_report_pdf_path(self, meta_path: Path) -> Optional[Path]:
        """Get the PDF path from a metadata file path."""
        pdf_file = meta_path.with_suffix(".pdf")
        if pdf_file.exists():
            return pdf_file
        return None

    def delete_report(self, meta_path: Path) -> bool:
        """Delete a report PDF and its metadata file."""
        try:
            pdf_path = meta_path.with_suffix(".pdf")
            if pdf_path.exists():
                pdf_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
            logger.info(f"Deleted report: {meta_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete report {meta_path}: {e}")
            return False