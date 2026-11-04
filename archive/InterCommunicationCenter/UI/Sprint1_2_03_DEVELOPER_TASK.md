Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Xây dựng Timeline Engine.

Timeline phải trở thành nơi ghi nhận toàn bộ lịch sử của học sinh.

Đây là Business Capability.

Không phải UI.

Sau Sprint này.

Mọi thay đổi quan trọng của Student và Parent đều được ghi lại.

---

# Architecture Goal

Không để mỗi module tự quản lý lịch sử.

Tạo một Timeline Service dùng chung.

Student

↓

Parent

↓

Assessment

↓

Products

↓

Attachments

↓

Timeline Service

↓

Timeline Repository

↓

Timeline Workspace

---

# Timeline Entity

Tạo TimelineEvent Model.

Fields.

id

student_id

event_type

title

description

created_at

created_by

metadata_json

---

# Event Type

Sử dụng Enum.

Allowed Values.

StudentCreated

StudentUpdated

ParentAdded

ParentUpdated

ParentDeleted

AssessmentCreated

AssessmentUpdated

AssessmentDeleted

ProductAdded

AttachmentAdded

System

Không dùng String tự do.

---

# Database

Tạo TimelineEvent Table.

Foreign Key.

Student

1

↓

N

TimelineEvent

Index.

student_id

created_at

---

# Repository

Implement.

Create Event

Delete Event

Get Events By Student

Latest Events

---

# Service

TimelineService

API.

log_event()

get_student_timeline()

Không để UI truy cập Repository.

---

# Integration

StudentService.

Sau khi.

Create Student

↓

TimelineService.log()

Student Created

---

Update Student

↓

TimelineService.log()

Student Updated

---

ParentService.

Sau khi.

Add Parent

↓

TimelineService.log()

Parent Added

---

Edit Parent

↓

Parent Updated

---

Delete Parent

↓

Parent Deleted

---

# Workspace

Timeline Section.

Thay thế Empty State.

Hiển thị.

Newest

↓

Oldest

---

# Timeline Card

Một Event.

Hiển thị.

--------------------------------

📅

Parent Added

Today 14:35

Mother: Nguyễn Thị Lan

--------------------------------

Card không cho Edit.

Timeline là Read Only.

---

# Empty State

Nếu chưa có Event.

Hiển thị.

📅

No activity yet.

Timeline events will appear here.

---

# UI Rules

Timeline.

Không cho chỉnh sửa.

Không cho xóa.

Timeline phản ánh lịch sử.

Không phải dữ liệu.

---

# Event Description

Ví dụ.

Student Updated

Description.

Updated Preferred Name

---

Parent Added

Description.

Added Father

---

Parent Deleted

Description.

Deleted Guardian

---

# Metadata

metadata_json.

Chuẩn bị cho tương lai.

Ví dụ.

{

old_name

new_name

parent_id

assessment_id

}

Sprint này.

Không cần sử dụng.

---

# Code Organization

models/

timeline_event.py

repositories/

timeline_repository.py

services/

timeline_service.py

ui/

timeline/

timeline_card.py

timeline_widget.py

---

# Architecture Constraint

Không gọi Timeline Repository trực tiếp.

Chỉ Timeline Service.

---

# Not In Scope

Assessment

Products

Attachments

PDF

Dashboard

Notification

Undo

Redo

Audit Viewer

---

# Acceptance Criteria

□ TimelineEvent Table tạo thành công.

□ TimelineService hoạt động.

□ Student Create sinh Event.

□ Student Update sinh Event.

□ Parent Add sinh Event.

□ Parent Update sinh Event.

□ Parent Delete sinh Event.

□ Workspace hiển thị Timeline.

□ Timeline sắp xếp mới nhất trước.

□ Không crash.

---

# Deliverables

Source Code

Screenshot

Timeline

Demo Video.

Workflow.

Create Student

↓

Timeline Update

↓

Add Parent

↓

Timeline Update

↓

Edit Parent

↓

Timeline Update

↓

Delete Parent

↓

Timeline Update

CHANGELOG.md

Known Issues.md

---

# Definition of Done

Sau Sprint này.

Một giáo viên mở Student Profile.

↓

Có thể nhìn thấy toàn bộ lịch sử thay đổi của học sinh.

↓

Không cần hỏi.

"Ai vừa sửa?"

"Thông tin này được thêm khi nào?"

Timeline trở thành bộ nhớ của Student Profile.

---

END OF DOCUMENT