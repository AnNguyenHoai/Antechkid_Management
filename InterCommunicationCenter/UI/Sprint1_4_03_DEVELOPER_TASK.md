# CenterManager

# Sprint 1.4

# 03_DEVELOPER_TASK.md

Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Tạo Student Summary Layer.

Sau Sprint này.

Giáo viên chỉ cần nhìn 5 giây là hiểu được tình trạng hiện tại của học sinh.

Không cần cuộn xuống từng Section.

Summary Layer chỉ tổng hợp dữ liệu.

Không tạo dữ liệu mới.

---

# Product Philosophy

Student Workspace có hai tầng.

Summary Layer

↓

Detail Sections

Summary trả lời.

"Học sinh này hiện đang như thế nào?"

Detail trả lời.

"Tại sao?"

---

# Summary Position

Summary nằm ngay dưới Header.

Trên Basic Information.

Không tạo cửa sổ mới.

---

# Summary Content

Hiển thị.

----------------------------------------

Current Level

Python Advance

----------------------------------------

Latest Assessment

★★★★☆

20 Mar 2026

----------------------------------------

Primary Contact

Nguyễn Văn Sử

0905719965

----------------------------------------

Last Activity

Assessment Created

Today 17:33

----------------------------------------

Learning Status

ACTIVE

----------------------------------------

Age

27

----------------------------------------

Timeline Count

12 Events

----------------------------------------

Assessment Count

5 Assessments

----------------------------------------

Parent Count

2 Contacts

----------------------------------------

Không hiển thị nếu chưa có dữ liệu.

---

# Summary Cards

Mỗi mục hiển thị dạng Mini Card.

Card thống nhất.

Icon

↓

Title

↓

Value

↓

Sub Value (nếu có)

Không dùng Table.

Không dùng Form.

---

# Data Source

Summary không có Database riêng.

Dữ liệu lấy từ.

StudentService

ParentService

AssessmentService

TimelineService

Không duplicate dữ liệu.

---

# Summary Service

Tạo.

StudentSummaryService

API.

get_student_summary(student_id)

Trả về.

StudentSummaryDTO

Không để UI tự gọi nhiều Service.

---

# StudentSummaryDTO

Fields.

student_name

current_level

learning_status

latest_assessment

latest_assessment_score

latest_assessment_date

primary_contact_name

primary_contact_phone

last_activity_title

last_activity_time

assessment_count

timeline_count

parent_count

age

---

# Latest Assessment

Nếu có Assessment.

Hiển thị.

★★★★☆

Monthly

20 Mar 2026

Nếu chưa có.

No assessment

---

# Primary Contact

Ưu tiên.

Primary Contact.

Nếu chưa có.

Lấy Contact đầu tiên.

Nếu không có.

No contact

---

# Last Activity

Lấy Event mới nhất.

Ví dụ.

Assessment Created

Today 17:33

Không hiển thị Event Type.

Không hiển thị metadata.

---

# Empty State

Nếu chưa có dữ liệu.

Card vẫn hiển thị.

Ví dụ.

Latest Assessment

No assessment

Primary Contact

No contact

Timeline

No activity

Giữ bố cục ổn định.

---

# UI Layout

Summary sử dụng Grid.

2 cột.

Desktop.

Không scroll riêng.

---

# Performance

Summary chỉ load một lần.

Khi đổi Student.

Refresh toàn bộ Summary.

Không refresh từng Card.

---

# Code Organization

services/

student_summary_service.py

dto/

student_summary_dto.py

ui/

summary/

summary_card.py

summary_widget.py

---

# Architecture Rules

Summary chỉ đọc.

Không ghi dữ liệu.

Không cập nhật Database.

Không gọi Repository trực tiếp.

---

# Not In Scope

Chart

Dashboard

Analytics

AI

Prediction

Recommendation

PDF

Export

---

# Acceptance Criteria

□ StudentSummaryService

□ Summary DTO

□ Summary Cards

□ Latest Assessment

□ Primary Contact

□ Last Activity

□ Assessment Count

□ Timeline Count

□ Parent Count

□ Empty State

□ Build OK

□ No Crash

---

# Deliverables

Source Code

Screenshot

Student Summary

Demo Video

Workflow.

Open Student

↓

Summary Load

↓

Edit Parent

↓

Summary Refresh

↓

Add Assessment

↓

Summary Refresh

CHANGELOG.md

KnownIssues.md

---

# Definition of Done

Một giáo viên mở hồ sơ học sinh.

↓

Trong vòng 5 giây.

Biết được.

- học sinh đang học gì
- đánh giá gần nhất
- ai là người liên hệ chính
- hoạt động gần nhất
- tình trạng học tập

Sau đó.

Nếu cần.

Mới cuộn xuống Detail Sections.

---

END OF DOCUMENT