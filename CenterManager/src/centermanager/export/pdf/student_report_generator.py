# -*- coding: utf-8 -*-
"""
StudentReportGenerator - builds a PDF report for a single student.
Vietnamese localization.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from centermanager.core.paths import get_paths
from centermanager.models.attendance import Attendance
from centermanager.models.note import Note
from centermanager.models.student import Student
from centermanager.models.parent import Parent
from centermanager.models.enrollment import Enrollment
from centermanager.models.class_ import Class
from centermanager.models.session import Session

logger = logging.getLogger(__name__)


def register_vietnamese_font() -> str:
    """
    Tìm font hỗ trợ tiếng Việt trên hệ thống và đăng ký với ReportLab.
    Trả về tên font đã đăng ký, hoặc 'Helvetica' nếu không tìm thấy.
    """
    font_paths = []
    if sys.platform == 'win32':
        font_paths = [
            os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'arial.ttf'),
            os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'times.ttf'),
        ]
    elif sys.platform == 'darwin':
        font_paths = [
            '/Library/Fonts/Arial.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/Library/Fonts/Times New Roman.ttf',
        ]
    else:  # Linux
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
        ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('VietnameseFont', path))
                return 'VietnameseFont'
            except Exception:
                continue
    # Fallback
    logger.warning("Không tìm thấy font hỗ trợ tiếng Việt, sử dụng Helvetica mặc định.")
    return 'Helvetica'


class StudentReportGenerator:
    def __init__(
        self,
        student_service,
        parent_service,
        attendance_service,
        session_service,
        student_note_service,
        outstanding_service,
        income_service,
    ) -> None:
        self._student_service = student_service
        self._parent_service = parent_service
        self._attendance_service = attendance_service
        self._session_service = session_service
        self._student_note_service = student_note_service
        self._outstanding_service = outstanding_service
        self._income_service = income_service

    def generate(self, student_id: int, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            report_dir = get_paths().student_profile_dir
            report_dir.mkdir(parents=True, exist_ok=True)
            student = self._student_service.get_student_with_relations(student_id)
            safe_name = student.full_name.replace(" ", "").replace("/", "_")
            filename = f"{student.student_code}_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
            output_path = report_dir / filename

        data = self._collect_data(student_id)
        self._build_pdf(output_path, data)
        logger.info(f"Student report generated: {output_path}")
        return output_path

    def _collect_data(self, student_id: int) -> Dict[str, Any]:
        student = self._student_service.get_student_with_relations(student_id)
        parents = self._parent_service.get_parents_for_student(student_id)
        attendances = self._attendance_service.get_attendance_for_student(student_id)
        notes = self._student_note_service.get_notes_for_student(student_id)
        outstanding_summary = self._outstanding_service.get_student_summary(student_id)

        enrollments: List[Enrollment] = student.enrollments
        class_info: List[Dict] = []
        all_sessions: List[Session] = []
        for enrollment in enrollments:
            cls: Optional[Class] = enrollment.class_
            if cls:
                teacher_names = ", ".join([t.full_name for t in cls.teachers]) if cls.teachers else ""
                class_info.append({
                    "name": cls.name,
                    "course": cls.course or "",
                    "teacher": teacher_names,
                    "start_date": cls.start_date,
                    "end_date": cls.end_date,
                })
                sessions = self._session_service.get_sessions_for_class(cls.id)
                all_sessions.extend(sessions)

        total_sessions = len(all_sessions)
        present_count = sum(1 for a in attendances if a.status == "Present")
        attendance_rate = (present_count / total_sessions * 100) if total_sessions > 0 else 0.0

        sorted_attendances = sorted(
            attendances,
            key=lambda a: a.session.scheduled_date if a.session else datetime.min,
            reverse=True,
        )
        latest_attendances = sorted_attendances[:5]

        sorted_notes = sorted(notes, key=lambda n: n.created_at, reverse=True)
        latest_notes = sorted_notes[:5]

        if outstanding_summary:
            expected = outstanding_summary.total_expected
            paid = outstanding_summary.total_paid
            outstanding = outstanding_summary.total_outstanding
        else:
            expected = paid = outstanding = 0

        incomes, _ = self._income_service.list_incomes(student_id=student_id, page=1, per_page=1)
        last_payment = incomes[0] if incomes else None

        return {
            "student": student,
            "parents": parents,
            "attendances": attendances,
            "notes": notes,
            "class_info": class_info,
            "all_sessions": all_sessions,
            "latest_attendances": latest_attendances,
            "latest_notes": latest_notes,
            "expected": expected,
            "paid": paid,
            "outstanding": outstanding,
            "last_payment": last_payment,
            "attendance_rate": attendance_rate,
            "total_sessions": total_sessions,
            "present_count": present_count,
        }

    def _build_pdf(self, output_path: Path, data: Dict[str, Any]) -> None:
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        font_name = register_vietnamese_font()
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=18,
            alignment=1,
            spaceAfter=12,
            fontName=font_name,
        )
        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading2"],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            fontName=font_name,
        )
        subheading_style = ParagraphStyle(
            "Subheading",
            parent=styles["Heading3"],
            fontSize=12,
            spaceAfter=6,
            spaceBefore=8,
            fontName=font_name,
        )
        normal_style = styles["Normal"]
        normal_style.fontSize = 10
        normal_style.leading = 14
        normal_style.fontName = font_name

        story = []

        # ---- Header ----
        header_data = [
            [Paragraph("AN TECHKIDS", title_style)],
            [Paragraph("HỒ SƠ HỌC SINH", title_style)],
            [Paragraph(f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style)],
        ]
        header_table = Table(header_data, colWidths=[doc.width])
        header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 0.5 * cm))

        # ---- Section 1: Thông tin học sinh ----
        story.append(Paragraph("THÔNG TIN HỌC SINH", heading_style))
        student: Student = data["student"]
        parents: List[Parent] = data["parents"]

        # Optional profile image. A missing/corrupt image must never prevent
        # the latest report from being generated.
        profile_image_path = getattr(student, "profile_image_path", None)
        if profile_image_path:
            image_path = Path(profile_image_path)
            if not image_path.is_absolute():
                image_path = get_paths().attachment_dir / image_path
            if image_path.exists():
                try:
                    story.append(Image(str(image_path), width=3.0 * cm, height=3.0 * cm))
                    story.append(Spacer(1, 0.25 * cm))
                except Exception:
                    logger.warning("Unable to embed student profile image: %s", image_path)

        primary_parent = next((p for p in parents if p.is_primary_contact), parents[0] if parents else None)

        profile_items = [
            ("Mã học sinh", student.student_code),
            ("Họ và tên", student.full_name),
            ("Giới tính", student.gender or ""),
            ("Ngày sinh", student.date_of_birth.strftime("%d/%m/%Y") if student.date_of_birth else ""),
            ("Số điện thoại", ""),
            ("Email", ""),
            ("Địa chỉ", ""),
            ("Trạng thái", student.status or ""),
            ("Ngày nhập học", student.enrollment_date.strftime("%d/%m/%Y") if student.enrollment_date else ""),
        ]

        if primary_parent:
            profile_items.append(("Tên phụ huynh", primary_parent.name or ""))
            profile_items.append(("SĐT phụ huynh", primary_parent.phone or ""))
            profile_items.append(("Email phụ huynh", primary_parent.email or ""))
            profile_items.append(("Địa chỉ phụ huynh", primary_parent.address or ""))
        else:
            profile_items.extend([
                ("Tên phụ huynh", ""),
                ("SĐT phụ huynh", ""),
                ("Email phụ huynh", ""),
                ("Địa chỉ phụ huynh", ""),
            ])

        class_info = data["class_info"]
        if class_info:
            cls = class_info[0]
            profile_items.append(("Lớp hiện tại", cls["name"]))
            profile_items.append(("Giáo viên", cls["teacher"]))
        else:
            profile_items.append(("Lớp hiện tại", ""))
            profile_items.append(("Giáo viên", ""))

        half = len(profile_items) // 2 + len(profile_items) % 2
        profile_table_data = []
        for i in range(half):
            left = profile_items[i] if i < len(profile_items) else ("", "")
            right = profile_items[i + half] if i + half < len(profile_items) else ("", "")
            profile_table_data.append([left[0], left[1], right[0], right[1]])

        profile_table = Table(profile_table_data, colWidths=[2.5 * cm, 4 * cm, 2.5 * cm, 4 * cm])
        profile_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.grey),
                ]
            )
        )
        story.append(profile_table)
        story.append(Spacer(1, 0.3 * cm))

        # ---- Section 2: Tình hình học tập ----
        story.append(Paragraph("TÌNH HÌNH HỌC TẬP", heading_style))
        academic_items = []
        if class_info:
            academic_items.append(("Lớp hiện tại", class_info[0]["name"]))
        else:
            academic_items.append(("Lớp hiện tại", "Chưa có lớp"))
        academic_items.append(("Số buổi đã học", str(data["total_sessions"])))
        academic_items.append(("Số buổi còn lại", "Chưa xác định"))
        academic_items.append(("Tỷ lệ chuyên cần", f"{data['attendance_rate']:.1f}%"))

        if data["latest_attendances"]:
            latest = data["latest_attendances"][0]
            academic_items.append(("Trạng thái gần nhất", latest.status))
            academic_items.append(("Buổi học gần nhất", latest.session.title if latest.session else ""))
        else:
            academic_items.append(("Trạng thái gần nhất", "Chưa có dữ liệu"))
            academic_items.append(("Buổi học gần nhất", ""))

        academic_items.append(("Tình trạng học tập", student.status or ""))

        academic_table_data = []
        for i in range(0, len(academic_items), 2):
            left = academic_items[i] if i < len(academic_items) else ("", "")
            right = academic_items[i + 1] if i + 1 < len(academic_items) else ("", "")
            academic_table_data.append([left[0], left[1], right[0], right[1]])

        academic_table = Table(academic_table_data, colWidths=[3 * cm, 4 * cm, 3 * cm, 4 * cm])
        academic_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.grey),
                ]
            )
        )
        story.append(academic_table)
        story.append(Spacer(1, 0.3 * cm))

        # ---- Section 3: Thông tin học phí ----
        story.append(Paragraph("THÔNG TIN HỌC PHÍ", heading_style))
        financial_items = [
            ("Học phí dự kiến", f"{data['expected']:,.0f} VND" if data["expected"] else "0 VND"),
            ("Đã đóng", f"{data['paid']:,.0f} VND" if data["paid"] else "0 VND"),
            ("Học phí còn nợ", f"{data['outstanding']:,.0f} VND" if data["outstanding"] else "0 VND"),
        ]
        if data["last_payment"]:
            financial_items.append(("Ngày đóng gần nhất", data["last_payment"].payment_date.strftime("%d/%m/%Y")))
            financial_items.append(("Hình thức thanh toán", data["last_payment"].payment_method))
        else:
            financial_items.append(("Ngày đóng gần nhất", ""))
            financial_items.append(("Hình thức thanh toán", ""))

        financial_table_data = []
        for i in range(0, len(financial_items), 2):
            left = financial_items[i] if i < len(financial_items) else ("", "")
            right = financial_items[i + 1] if i + 1 < len(financial_items) else ("", "")
            financial_table_data.append([left[0], left[1], right[0], right[1]])

        financial_table = Table(financial_table_data, colWidths=[3 * cm, 4 * cm, 3 * cm, 4 * cm])
        financial_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.grey),
                ]
            )
        )
        story.append(financial_table)
        story.append(Spacer(1, 0.3 * cm))

        # ---- Section 4: Điểm danh gần đây ----
        story.append(Paragraph("ĐIỂM DANH GẦN ĐÂY", heading_style))
        latest_attendances = data["latest_attendances"]
        if latest_attendances:
            att_table_data = [["Ngày", "Trạng thái", "Giáo viên", "Ghi chú"]]
            for att in latest_attendances:
                session = att.session
                teacher = ""
                if session and session.class_:
                    teacher = ", ".join([t.full_name for t in session.class_.teachers]) if session.class_.teachers else ""
                comment = att.teacher_note or ""
                att_table_data.append([
                    session.scheduled_date.strftime("%d/%m/%Y") if session and session.scheduled_date else "",
                    att.status,
                    teacher,
                    comment,
                ])
            att_table = Table(att_table_data, colWidths=[2.5 * cm, 2.5 * cm, 3 * cm, 4 * cm])
            att_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )
            story.append(att_table)
        else:
            story.append(Paragraph("Chưa có dữ liệu điểm danh", normal_style))
        story.append(Spacer(1, 0.3 * cm))

        # ---- Section 5: Nhận xét của giáo viên ----
        story.append(Paragraph("NHẬN XÉT CỦA GIÁO VIÊN", heading_style))
        latest_notes: List[Note] = data["latest_notes"]
        if latest_notes:
            for note in latest_notes:
                story.append(
                    Paragraph(
                        f"<b>{note.note_type}</b> - {note.created_at.strftime('%d/%m/%Y')}",
                        subheading_style,
                    )
                )
                story.append(Paragraph(note.content, normal_style))
                story.append(Spacer(1, 0.2 * cm))
        else:
            story.append(Paragraph("Chưa có nhận xét nào.", normal_style))

        # ---- Footer ----
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph("Được tạo bởi CenterManager - Trang 1", normal_style))

        doc.build(story)