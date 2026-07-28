# CenterManager

# Sprint 1.1

# 03_DEVELOPER_TASK.md

Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Hoàn thiện Parent Management.

Sau Sprint này.

Giáo viên có thể:

- xem thông tin phụ huynh
- thêm phụ huynh
- chỉnh sửa phụ huynh
- lưu dữ liệu
- hiển thị trong Workspace

Module phải hoàn chỉnh từ Database đến UI.

Đây là Vertical Slice đầu tiên của CenterManager.

---

# Scope

Implement hoàn chỉnh.

Database

↓

Repository

↓

Service

↓

UI

↓

Workspace

↓

Dialog

---

# Business Model

Một Student có thể có nhiều người liên hệ.

Tuy nhiên.

Sprint này chỉ cần hỗ trợ tối đa 2.

Guardian 1

Guardian 2

Không hardcode Father/Mother.

Điều này giúp linh hoạt hơn.

---

# Parent Entity

Tạo Parent Model.

Fields.

id

student_id

full_name

relationship

phone

email

occupation

notes

created_at

updated_at

---

# Relationship

Relationship sử dụng Enum.

Allowed Values.

Father

Mother

Guardian

Grandparent

Other

Không dùng string tự do.

---

# Database

Tạo bảng Parent.

Thiết lập Foreign Key.

Student

1

↓

N

Parent

Cascade Delete.

Nếu Student bị xóa.

Parent cũng bị xóa.

---

# Repository

Implement.

Create Parent

Update Parent

Delete Parent

Get Parent By Student

Không viết SQL trong UI.

---

# Service

ParentService.

Business Logic.

Validation.

Repository Access.

Không để UI truy cập Repository trực tiếp.

---

# Workspace

Thay thế Empty State.

Hiện tại.

No parent information.

↓

Hiển thị.

Guardian 1

Name

Relationship

Phone

Email

Occupation

Notes

Nếu chưa có.

Vẫn Empty State.

---

# Parent Card

Một Parent hiển thị dạng Card.

Ví dụ.

--------------------------------

Guardian 1

Relationship

Mother

Phone

0123456789

Email

abc@email.com

Occupation

Teacher

--------------------------------

Nếu có Guardian 2.

Hiển thị Card thứ hai.

---

# Parent Dialog

Tạo Dialog riêng.

Không nhét Parent vào Student Dialog.

Dialog.

Guardian Name

Relationship

Phone

Email

Occupation

Notes

Buttons.

Save

Cancel

---

# Validation

Guardian Name.

Required.

Relationship.

Required.

Phone.

Optional.

Email.

Optional.

Occupation.

Optional.

Notes.

Optional.

---

# Workspace Interaction

Workspace.

Parent Section.

↓

Add Parent

↓

Dialog

↓

Save

↓

Workspace Refresh

Không cần restart.

---

# Edit Flow

Click.

Edit Parent

↓

Dialog

↓

Save

↓

Workspace Refresh

---

# Delete Flow

Delete Parent

↓

Confirmation

↓

Delete

↓

Workspace Refresh

---

# Empty State

Nếu chưa có Parent.

Hiển thị.

👨‍👩‍👧

No parent information.

Add a guardian to this student.

Hiển thị nút.

+ Add Parent

---

# Timeline Integration

Chưa implement Timeline.

Nhưng.

Service phải chuẩn bị Event.

Parent Added

Parent Updated

Parent Deleted

TODO.

---

# Architecture

Không viết UI Logic trong Repository.

Không viết SQL trong Service.

Không viết Business Logic trong Widget.

---

# Code Organization

Khuyến nghị.

models/

    parent.py

repositories/

    parent_repository.py

services/

    parent_service.py

ui/

    parents/

        parent_card.py

        parent_dialog.py

---

# Not In Scope

Assessment

Products

Timeline CRUD

Attachment

PDF

Dashboard

Import

Export

Statistics

Notification

---

# Acceptance Criteria

□ Parent Table tạo thành công.

□ Migration chạy.

□ Parent Repository hoạt động.

□ Parent Service hoạt động.

□ Workspace hiển thị Parent.

□ Add Parent hoạt động.

□ Edit Parent hoạt động.

□ Delete Parent hoạt động.

□ Empty State đúng.

□ Không crash.

□ Build thành công.

---

# Deliverables

Source Code

Screenshot

Workspace

Parent Dialog

Demo Video

Workflow.

Open Student

↓

Add Parent

↓

Save

↓

Workspace Update

↓

Edit Parent

↓

Delete Parent

CHANGELOG.md

Known Issues.md

---

# Definition of Done

Sau Sprint này.

Một giáo viên có thể:

Chọn học sinh.

↓

Thêm thông tin phụ huynh.

↓

Lưu.

↓

Đọc lại ngay trên Workspace.

↓

Chỉnh sửa.

↓

Xóa.

Không cần rời khỏi Student Workspace.

Đây là tiêu chuẩn hoàn thành của Sprint 1.1.

---

END OF DOCUMENT