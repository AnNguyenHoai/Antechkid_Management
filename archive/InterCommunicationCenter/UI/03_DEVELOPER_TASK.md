# CenterManager

# Sprint 0.5

# 03_DEVELOPER_TASK.md

Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Mục tiêu của Sprint 0.5 là tạo ra **Prototype đầu tiên** của CenterManager.

Prototype phải cho phép giáo viên:

- tìm học sinh
- chọn học sinh
- xem thông tin
- chỉnh sửa thông tin

Toàn bộ workflow phải chạy được.

Đây KHÔNG phải Sprint tối ưu UI.

Đây là Sprint xây dựng bộ khung của sản phẩm.

---

# Scope

Implement các thành phần sau.

## Navigation

- Search Box
- Student List

---

## Workspace

Workspace Header

- Avatar Placeholder
- Student Name
- Student Code
- Edit Button
- Export Button (Disabled)

---

Workspace Sections

- Basic Information
- Learning
- Notes

---

# Database

Hoàn thiện các trường cần thiết.

Student

- id
- code
- full_name
- preferred_name
- dob
- gender
- current_level
- learning_status
- notes

Nếu thiếu migration thì bổ sung.

---

# Search

Implement

Search theo:

- Student Name
- Student Code

Realtime filtering.

Không cần Enter.

---

# Student List

Student List chỉ hiển thị.

Student Code

Student Name

Không hiển thị thêm dữ liệu.

Single Click

↓

Workspace Update

---

# Workspace

Implement Layout đúng theo UX SPEC.

Workspace luôn nằm bên phải.

Không dùng Dialog để xem Profile.

---

# Workspace Header

Hiển thị

Avatar Placeholder

Student Name

Student Code

Edit Button

Export Button

Export Button disable.

---

# Basic Information Section

Hiển thị.

Preferred Name

Date of Birth

Age

Gender

Nếu chưa có dữ liệu.

Hiển thị "-"

Không để trống.

---

# Learning Section

Hiển thị.

Current Level

Learning Status

Nếu chưa có.

Hiển thị "-"

---

# Notes Section

Hiển thị.

Teacher Notes

Cho phép nhiều dòng.

Nếu rỗng.

Hiển thị.

"No notes."

---

# Edit Student

Click Edit

↓

Mở Student Dialog hiện tại.

Nếu Dialog chưa đáp ứng.

Được phép chỉnh sửa.

Nhưng không được thay đổi UX của Main Window.

---

# Save Flow

Save

↓

Update Database

↓

Refresh Workspace

↓

Refresh Student List (nếu Name hoặc Code thay đổi)

↓

Close Dialog

Không yêu cầu Refresh thủ công.

---

# Empty Workspace

Nếu chưa chọn Student.

Workspace hiển thị.

------------------------------------

No student selected

Select a student from the list.

------------------------------------

Không hiển thị Header.

Không hiển thị Section.

---

# Empty Section

Nếu chưa có dữ liệu.

Ví dụ

Parents

Assessment

Products

Timeline

Attachments

Không implement.

---

# Layout

Bố cục phải theo UX SPEC.

------------------------------------------------------------

Toolbar

------------------------------------------------------------

Search

------------------------------------------------------------

Student List | Student Workspace

------------------------------------------------------------

Workspace được phép scroll.

Student List scroll độc lập.

---

# Coding Requirements

Không hardcode dữ liệu.

Không duplicate UI.

Không duplicate Repository.

Không duplicate Service.

Không viết business logic trong UI.

---

# Architecture Constraints

Không thay đổi Architecture hiện tại.

Không refactor lớn.

Không tối ưu sớm.

Mục tiêu là Prototype chạy ổn định.

---

# Allowed

Được phép

- sửa UI
- sửa Repository
- sửa Service
- sửa Dialog
- sửa Layout

Nếu cần để đúng UX.

---

# Not Allowed

Không implement.

Parent Module

Assessment

Timeline

Attachment

Product

Dashboard

Export PDF

Google Drive

Import

Theme

Dark Mode

Animation

---

# Acceptance Criteria

Prototype được xem là hoàn thành khi.

□ Project build thành công

□ Không crash khi mở

□ Search hoạt động

□ Student List hoạt động

□ Single Click cập nhật Workspace

□ Workspace hiển thị Header

□ Basic Information hiển thị đúng

□ Learning hiển thị đúng

□ Notes hiển thị đúng

□ Edit Student hoạt động

□ Save hoạt động

□ Workspace refresh

□ Không cần restart để thấy dữ liệu

□ Empty Workspace đúng UX

□ Không dùng Dialog để xem Student Profile

---

# Deliverables

DeepSeek cần gửi.

1.

Source Code

---

2.

Screenshot

Main Window

Không cần nhiều ảnh.

---

3.

Demo Video

30~60 giây.

Thực hiện workflow.

Open

↓

Search

↓

Select Student

↓

Edit

↓

Save

↓

Workspace Update

---

4.

CHANGELOG.md

Liệt kê.

- File đã sửa
- File mới
- Database thay đổi
- Known Issues

---

# Review Checklist

PM sẽ review.

□ Đúng Product Vision

□ Đúng UX Spec

□ Workflow mượt

□ Không có popup thừa

□ Không crash

□ Có thể demo được

Nếu đạt.

Sprint 0.5 hoàn thành.

---

# Definition of Done

Sprint chỉ hoàn thành khi giáo viên có thể:

Mở phần mềm.

↓

Tìm học sinh.

↓

Chọn học sinh.

↓

Đọc thông tin.

↓

Sửa thông tin.

↓

Lưu.

↓

Tiếp tục chọn học sinh khác.

Toàn bộ workflow diễn ra mà không cần đóng ứng dụng.

---

END OF DOCUMENT