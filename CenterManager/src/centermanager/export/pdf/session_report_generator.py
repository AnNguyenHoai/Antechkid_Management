# -*- coding: utf-8 -*-
"""Manual PDF generator for a single Class Session."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


_STATUS_LABELS = {
    "Scheduled": "Đã lên lịch",
    "Completed": "Hoàn thành",
    "Cancelled": "Đã hủy",
    "Postponed": "Hoãn",
}


def localize_status(status: str) -> str:
    return _STATUS_LABELS.get(status or "", status or "")


def register_vietnamese_font() -> str:
    candidates = []
    if sys.platform == "win32":
        candidates = [
            os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arial.ttf"),
            os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "times.ttf"),
        ]
    elif sys.platform == "darwin":
        candidates = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("SessionReportVietnamese", path))
                return "SessionReportVietnamese"
            except Exception:
                continue
    return "Helvetica"


class SessionReportGenerator:
    """Builds a privacy-safe, parent-group-friendly PDF for one class session."""

    def generate(self, output_path: Path, data: Dict[str, Any]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font = register_vietnamese_font()
        styles = getSampleStyleSheet()

        title = ParagraphStyle(
            "SessionTitle", parent=styles["Heading1"], fontName=font,
            fontSize=19, leading=24, alignment=1, spaceAfter=5,
        )
        subtitle = ParagraphStyle(
            "SessionSubtitle", parent=styles["Normal"], fontName=font,
            fontSize=10, leading=14, alignment=1, textColor=colors.grey,
            spaceAfter=12,
        )
        heading = ParagraphStyle(
            "SessionHeading", parent=styles["Heading2"], fontName=font,
            fontSize=13, leading=17, spaceBefore=10, spaceAfter=6,
        )
        normal = ParagraphStyle(
            "SessionNormal", parent=styles["Normal"], fontName=font,
            fontSize=10, leading=15,
        )

        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=1.6*cm, bottomMargin=1.6*cm,
        )
        story = []
        session = data["session"]
        class_obj = data["class"]
        note = data["note"]

        story.append(Paragraph("AN TECHKIDS", title))
        story.append(Paragraph("BÁO CÁO BUỔI HỌC", title))
        story.append(Paragraph(
            f"Xuất lúc {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitle
        ))

        teacher_name = data.get("teacher_name")
        if not teacher_name:
            teachers = ", ".join(
                t.full_name for t in getattr(class_obj, "teachers", [])
                if getattr(t, "full_name", None)
            )
            teacher_name = teachers or (getattr(class_obj, "teacher", "") or "")

        time_value = ""
        if session.start_time and session.end_time:
            time_value = f"{session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')}"

        info = [
            ["Lớp", class_obj.name or ""],
            ["Khóa học", class_obj.course or ""],
            ["Buổi học", f"Buổi {session.session_number}: {session.title or ''}"],
        ]
        if session.actual_date and session.scheduled_date and session.actual_date != session.scheduled_date:
            info.extend([
                ["Ngày dự kiến", session.scheduled_date.strftime("%d/%m/%Y")],
                ["Ngày thực tế", session.actual_date.strftime("%d/%m/%Y")],
            ])
        else:
            date_value = session.actual_date or session.scheduled_date
            info.append(["Ngày học", date_value.strftime("%d/%m/%Y") if date_value else ""])
        info.extend([
            ["Thời gian", time_value],
            ["Giáo viên", teacher_name],
            ["Trạng thái", localize_status(session.status)],
        ])
        info_table = Table(info, colWidths=[3.2*cm, 14.5*cm])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F2F5F8")),
            ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8DEE6")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(info_table)

        story.append(Paragraph("NỘI DUNG BUỔI HỌC", heading))
        lesson_content = getattr(note, "lesson_content", None) or session.lesson_topic or session.title
        story.append(Paragraph(lesson_content.replace("\n", "<br/>") if lesson_content else "Chưa cập nhật.", normal))

        story.append(Paragraph("TÌNH HÌNH HỌC TẬP", heading))
        if note:
            rows = [
                ["Tiến độ giảng dạy", getattr(note, "teaching_progress", "") or ""],
                ["Không khí lớp học", getattr(note, "class_atmosphere", "") or ""],
            ]
            if getattr(note, "remark", None):
                rows.append(["Nhận xét", note.remark])
            if getattr(note, "next_plan", None):
                rows.append(["Kế hoạch tiếp theo", note.next_plan])
            note_table = Table(rows, colWidths=[4.2*cm, 13.5*cm])
            note_table.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,-1), font),
                ("FONTSIZE", (0,0), (-1,-1), 10),
                ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F2F5F8")),
                ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8DEE6")),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ]))
            story.append(note_table)
        else:
            story.append(Paragraph("Chưa có nhận xét tổng quan cho buổi học.", normal))

        highlights = data.get("highlights") or []
        if highlights:
            story.append(Paragraph("ĐIỂM NỔI BẬT HỌC SINH", heading))
            highlight_rows = [["Học sinh", "Nội dung"]]
            for item in highlights:
                student = getattr(item, "student", None)
                student_name = getattr(student, "full_name", None) or "Học sinh"
                type_label = getattr(item, "type", "")
                title_text = getattr(item, "title", "") or ""
                description = getattr(item, "description", None)
                content = title_text
                if description:
                    content = f"{content}: {description}" if content else description
                if type_label:
                    content = f"[{type_label}] {content}".strip()
                highlight_rows.append([student_name, content or ""])
            highlight_table = Table(highlight_rows, colWidths=[5.0*cm, 12.7*cm])
            highlight_table.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,-1), font),
                ("FONTSIZE", (0,0), (-1,-1), 10),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F5F8")),
                ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8DEE6")),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ]))
            story.append(highlight_table)

        story.append(Paragraph("BÀI TẬP VỀ NHÀ", heading))
        homework = getattr(note, "homework", None) if note else None
        story.append(Paragraph((homework or "Không có bài tập về nhà.").replace("\n", "<br/>"), normal))

        story.append(Paragraph("CHUYÊN CẦN", heading))
        summary = data["attendance_summary"]
        total = sum(summary.values())
        attendance_rows = [
            ["Có mặt", str(summary.get("Present", 0))],
            ["Đi muộn", str(summary.get("Late", 0))],
            ["Vắng", str(summary.get("Absent", 0))],
            ["Vắng có phép", str(summary.get("Excused", 0))],
            ["Tổng", str(total)],
        ]
        attendance_table = Table(attendance_rows, colWidths=[8.8*cm, 8.9*cm])
        attendance_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D8DEE6")),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#F2F5F8")),
            ("ALIGN", (1,0), (1,-1), "CENTER"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(attendance_table)

        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            "Báo cáo được tạo để chia sẻ thông tin chung của buổi học với phụ huynh.",
            subtitle,
        ))
        doc.build(story)
        return output_path
