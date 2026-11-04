# CenterManager

# Sprint 1.3

# 03_DEVELOPER_TASK.md

Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Triển khai Assessment Capability phiên bản đầu tiên.

Sau Sprint này.

Giáo viên có thể:

- tạo đánh giá
- xem lịch sử đánh giá
- chỉnh sửa đánh giá
- xóa đánh giá
- xem đánh giá mới nhất

Assessment phải tích hợp hoàn toàn với Student Workspace và Timeline.

Đây là Capability.

Không chỉ là CRUD.

---

# Product Philosophy

Assessment dùng để phản ánh sự tiến bộ của học sinh.

Không dùng để chấm điểm.

Điểm số chỉ là một phần.

Điều quan trọng hơn là:

- học sinh làm tốt điều gì
- cần cải thiện điều gì
- mục tiêu tiếp theo là gì

UI phải phản ánh triết lý này.

---

# Business Workflow

Teacher

↓

Open Student

↓

Assessment Section

↓

Add Assessment

↓

Save

↓

Workspace Refresh

↓

Timeline Updated

↓

History Updated

---

# Domain Model

Assessment

Fields

id

student_id

assessment_date

assessment_type

overall_score

strengths

improvements

next_goal

teacher_comment

created_at

updated_at

---

# Assessment Type

Enum.

Monthly

Quarterly

Final

Custom

Không dùng string tự do.

---

# Repository

AssessmentRepository

Implement.

Create

Update

Delete

Find By Student

Latest Assessment

---

# Service

AssessmentService

Business Logic.

Validation.

Repository Access.

Timeline Integration.

---

# Timeline

Sau khi.

Create

↓

TimelineService.log_event()

Assessment Created

---

Update

↓

Assessment Updated

---

Delete

↓

Assessment Deleted

---

# Workspace

Assessment Section.

Thay Empty State.

Hiển thị.

Latest Assessment

-----------------------------------

Monthly Assessment

★★★★★

01 Aug 2026

-----------------------------------

Strengths

...

-----------------------------------

Need Improvement

...

-----------------------------------

Next Goal

...

-----------------------------------

Teacher Comment

...

---

# Assessment History

Ngay dưới Latest Assessment.

Hiển thị dạng List.

-----------------------------------

01 Aug 2026

Monthly

★★★★★

-----------------------------------

15 Jul 2026

Monthly

★★★★☆

-----------------------------------

Không cần Card lớn.

---

# Interaction

Click Assessment

↓

Open Detail Dialog

---

# Detail Dialog

Read Only.

Có nút.

Edit

Delete

Close

---

# Edit Dialog

Fields.

Assessment Date

Assessment Type

Overall Score

Strengths

Need Improvement

Next Goal

Teacher Comment

Save

Cancel

---

# Add Assessment

Button.

+ Add Assessment

Nằm góc phải Section.

Không nằm cuối Section.

---

# Delete

Confirmation.

Delete Assessment?

This action cannot be undone.

---

# Validation

Assessment Date

Required.

Assessment Type

Required.

Strengths

Required.

Need Improvement

Required.

Next Goal

Required.

Teacher Comment

Optional.

Overall Score

Optional.

---

# Score

Overall Score.

0–5.

Sử dụng Rating.

Không TextBox.

Không Number Input.

UI thân thiện hơn.

---

# Latest Assessment

Workspace luôn hiển thị Assessment mới nhất.

Không hiển thị tất cả.

History dùng để xem các Assessment cũ.

---

# Empty State

Nếu chưa có.

📊

No assessments.

Start tracking student progress.

Button.

+ Add Assessment

---

# Code Organization

models/

assessment.py

repositories/

assessment_repository.py

services/

assessment_service.py

ui/

assessment/

assessment_section.py

assessment_dialog.py

assessment_history.py

assessment_detail.py

---

# Architecture Rules

AssessmentService

↓

TimelineService

Không gọi TimelineRepository trực tiếp.

---

# Not In Scope

Assessment Template

Charts

Radar Chart

Statistics

AI Recommendation

Rubrics

PDF

Export

---

# Acceptance Criteria

□ Assessment CRUD

□ Latest Assessment

□ History

□ Timeline Integration

□ Detail Dialog

□ Edit Dialog

□ Delete

□ Rating Control

□ Empty State

□ Build OK

□ No Crash

---

# Deliverables

Source Code

Screenshot

Assessment Workspace

History

Dialog

Demo Video

Workflow.

Student

↓

Assessment

↓

Save

↓

Timeline

↓

History

↓

Edit

↓

Delete

CHANGELOG.md

KnownIssues.md

---

# Definition of Done

Giáo viên có thể:

Mở hồ sơ học sinh.

↓

Đánh giá học sinh.

↓

Lưu.

↓

Xem đánh giá mới nhất.

↓

Xem lịch sử.

↓

Sửa.

↓

Xóa.

Mọi thay đổi đều xuất hiện trong Timeline.

---

END OF DOCUMENT