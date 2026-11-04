# CenterManager

# Sprint 1.0

# 03_DEVELOPER_TASK.md

Version: 1.0

Status: Approved

Reference

- 01_PRODUCT_VISION.md
- 02_UX_DESIGN_SPEC.md

---

# Sprint Goal

Hoàn thiện Student Workspace.

Sau Sprint này.

Workspace phải gần như hoàn chỉnh về mặt giao diện.

Mặc dù một số module chưa có dữ liệu.

Nhưng toàn bộ cấu trúc phải xuất hiện.

Đây là Sprint hoàn thiện UX.

Không phải Sprint thêm tính năng.

---

# Primary Objectives

1.

Giảm chiều cao Header.

2.

Hoàn thiện Layout.

3.

Bỏ Table Student List.

4.

Thêm đầy đủ Workspace Sections.

5.

Hoàn thiện Empty State.

6.

Chuẩn hóa Spacing.

---

# Task 1

Main Window Layout

Hiện tại khoảng trắng phía trên quá lớn.

Điều chỉnh.

Toolbar

↓

Search

↓

Content

Header không nên cao quá 80 px.

Workspace phải chiếm nhiều diện tích hơn.

---

# Task 2

Student List Redesign

Thay thế TableWidget.

Bằng List Widget.

Một Student Item.

Hiển thị.

HS001

Nguyễn Hoài An

Không còn:

Code | Name

Không còn Header.

Không Grid.

Không Table.

Item được highlight khi được chọn.

---

# Task 3

Workspace Header

Giữ nguyên.

Avatar

Student Name

Student Code

Edit

Export PDF (Disabled)

Nhưng.

Canh lề đẹp hơn.

Giảm chiều cao.

Tăng khoảng trắng ngang.

---

# Task 4

Section Standardization

Tất cả Section phải cùng cấu trúc.

Section Title

Divider

Content

Empty State

Không có Section nào dùng layout riêng.

---

# Task 5

Implement Empty Sections

Thêm vào Workspace.

Parent

Assessment

Products

Attachments

Timeline

Chưa cần CRUD.

Chỉ hiển thị.

Section

↓

No data available.

↓

(Nếu sau này có dữ liệu sẽ thay thế)

---

# Task 6

Basic Information

Đổi cách hiển thị.

Không dùng.

Label: Value

Thành.

Label

↓

Value

Ví dụ.

Preferred Name

Oanh

Date of Birth

-

Age

-

Gender

Female

Đọc theo chiều dọc.

---

# Task 7

Learning Section

Giữ nguyên.

Nhưng chuẩn hóa khoảng cách.

Current Level

↓

Value

Learning Status

↓

Value

---

# Task 8

Notes Section

Hiển thị dạng Card.

Không hiển thị giống Form.

Nếu Notes rỗng.

Hiển thị.

No notes.

---

# Task 9

Workspace Scroll

Header cố định.

Content scroll.

Section cách nhau đồng đều.

---

# Task 10

Empty Workspace

Nếu chưa chọn Student.

Hiển thị.

------------------------------------

👤

No student selected.

Select a student from the list.

------------------------------------

Không render Header.

Không render Section.

---

# Task 11

Selection UX

Đổi Student.

↓

Workspace cuộn lên đầu.

↓

Header cập nhật.

↓

Sections cập nhật.

Không giữ vị trí scroll của Student cũ.

---

# Task 12

Search UX

Nếu Search không có kết quả.

Student List.

Hiển thị.

No students found.

Không hiển thị List rỗng.

---

# Task 13

Spacing

Áp dụng thống nhất.

Section Margin

24 px

Section Padding

16 px

Header Bottom

24 px

Label → Value

8 px

Không dùng khoảng cách ngẫu nhiên.

---

# Task 14

Future Placeholder

Export PDF

Disabled

Tooltip.

Available in future version.

---

# Task 15

Code Refactoring

Nếu file.

student_workspace.py

quá lớn.

Được phép chia.

workspace/

    workspace.py

    header.py

    basic_information.py

    learning.py

    notes.py

    empty_section.py

Không bắt buộc.

Khuyến khích.

---

# Not In Scope

Không implement.

PDF

Google Drive

Dashboard

Attendance

Billing

Certificates

Competition

Statistics

AI

Dark Theme

Import

Export

---

# Acceptance Criteria

□ Header nhỏ gọn.

□ Student List không còn Table.

□ Workspace đầy đủ 8 Sections.

□ Empty State đúng.

□ Notes dạng Card.

□ Layout đúng UX Spec.

□ Scroll đúng.

□ Search đúng.

□ Không crash.

□ Build thành công.

---

# Deliverables

Source Code

Screenshot

Main Window

Demo Video

60 giây.

Workflow.

Search

↓

Select Student

↓

Workspace

↓

Edit

↓

Save

↓

Switch Student

↓

Empty Sections

CHANGELOG.md

Known Issues.md

---

# Definition of Done

Một giáo viên mở phần mềm.

↓

Có thể nhìn toàn bộ hồ sơ học sinh.

↓

Biết ngay.

Thông tin cơ bản.

↓

Tình trạng học.

↓

Các mục sẽ được bổ sung trong tương lai.

↓

Không phải mở thêm cửa sổ nào.

Ngoài Dialog chỉnh sửa.

---

END OF DOCUMENT