# CenterManager

# 02_UX_DESIGN_SPEC.md

Version: 1.0

Status: Draft

Author: Product Design Team

Reference:
- 01_PRODUCT_VISION.md

---

# Part I

# Foundation

---

# 1. Purpose

Tài liệu này định nghĩa toàn bộ trải nghiệm người dùng (User Experience) và cấu trúc giao diện (User Interface) của CenterManager.

Đây là tài liệu thiết kế.

Không phải tài liệu kỹ thuật.

Không mô tả:

- Qt
- SQL
- Database
- Python
- Implementation

Mọi quyết định về giao diện đều phải tuân theo tài liệu này.

Nếu implementation khác với tài liệu này thì implementation cần được điều chỉnh, không phải ngược lại.

---

# 2. Design Philosophy

CenterManager được thiết kế theo triết lý:

> Teacher Workspace First.

Phần mềm phải phản ánh đúng cách giáo viên làm việc ngoài thực tế.

Không thiết kế theo tư duy của lập trình viên.

Không thiết kế theo cấu trúc database.

Không thiết kế theo mô hình CRUD truyền thống.

Mọi quyết định về UX đều phải xuất phát từ câu hỏi:

"Giáo viên cần gì ở thời điểm này?"

---

# 3. Product Mental Model

Người dùng không nghĩ theo bảng dữ liệu.

Người dùng nghĩ theo học sinh.

Do đó sản phẩm cũng phải tổ chức theo học sinh.

Sai:

Student Table

↓

Open Dialog

↓

Close

↓

Open Dialog

↓

Close

Đúng:

Student

↓

Student Workspace

↓

Làm việc liên tục

---

# 4. UX Principles

CenterManager tuân theo 6 nguyên tắc thiết kế.

---

## Principle 1

One Student = One Workspace

Một học sinh luôn có đúng một Workspace.

Không có nhiều Profile.

Không có nhiều cửa sổ.

Không có nhiều popup.

Workspace luôn tồn tại.

---

## Principle 2

Navigation ≠ Information

Navigation chỉ để tìm.

Không dùng Navigation để hiển thị dữ liệu.

Ví dụ:

Student List

Chỉ hiển thị

✓ Name

✓ Code

Không hiển thị

×

Age

×

Gender

×

Status

×

Parent

×

Notes

Những thông tin đó thuộc Workspace.

---

## Principle 3

Everything Has A Home

Mỗi loại dữ liệu chỉ có đúng một vị trí.

Ví dụ

Assessment

Luôn nằm trong Assessment Section.

Không hiển thị lại ở nơi khác.

Parent

Luôn thuộc Parent Section.

Điều này giúp giáo viên hình thành trí nhớ vị trí.

---

## Principle 4

Progressive Disclosure

Không hiển thị tất cả thông tin cùng lúc.

Thông tin được chia thành các tầng.

Ví dụ

Header

↓

Basic Information

↓

Learning

↓

Assessment

↓

Timeline

↓

Attachments

Người dùng chỉ đọc tới phần mình cần.

---

## Principle 5

Minimal Navigation

Trong toàn bộ sản phẩm.

Người dùng chỉ nên cần:

Search

↓

Click Student

↓

Làm việc

Không nên chuyển nhiều màn hình.

Không nên mở nhiều cửa sổ.

---

## Principle 6

Workspace Never Changes

Layout tổng thể không thay đổi.

Sau này chỉ thêm Section.

Không redesign toàn bộ.

---

# 5. Information Architecture

CenterManager chia thành hai vùng.

Navigation

Workspace

Chúng có nhiệm vụ hoàn toàn khác nhau.

---

Navigation

Chỉ làm một việc.

Tìm học sinh.

Navigation KHÔNG lưu dữ liệu.

Navigation KHÔNG edit dữ liệu.

Navigation KHÔNG hiển thị chi tiết.

---

Workspace

Workspace là trung tâm.

Workspace chứa toàn bộ dữ liệu.

Mọi thao tác đều diễn ra tại đây.

---

# 6. Global Layout

Toàn bộ CenterManager sử dụng một layout duy nhất.

+--------------------------------------------------------------+

 Toolbar

+--------------------------------------------------------------+

 Search

+----------------------+---------------------------------------+

|                      |                                       |

|                      |                                       |

| Student List         |                                       |

|                      |                                       |

|                      |                                       |

|                      |                                       |

|                      |                                       |

+----------------------+                                       |

|                      |                                       |

|                      |                                       |

|                      |                                       |

|                      |                                       |

|                      |                                       |

+----------------------+---------------------------------------+

Navigation               Student Workspace

Không sử dụng nhiều cửa sổ.

Không sử dụng MDI.

Không sử dụng Tab cho Student.

---

# 7. Layout Zones

CenterManager chia thành 5 vùng.

Zone A

Toolbar

Zone B

Search

Zone C

Navigation

Zone D

Workspace Header

Zone E

Workspace Content

Mỗi Zone có nhiệm vụ riêng.

Không trùng lặp.

---

# 8. Navigation Specification

Navigation gồm hai phần.

Search Box

Student List

Không có gì khác.

Không đặt Button Edit.

Không đặt Button Delete.

Không đặt Statistics.

Navigation phải cực kỳ đơn giản.

---

# 9. Search

Search luôn nằm trên Student List.

Search hoạt động theo thời gian thực.

Khi nhập.

↓

Danh sách lọc ngay.

Không cần bấm Enter.

Search hỗ trợ:

Student Name

Student Code

---

# 10. Student List

Student List chỉ hiển thị thông tin định danh.

Ví dụ

HS001

Nguyễn Văn An

Không hiển thị:

Current Level

Status

Gender

DOB

Phone

Notes

Những dữ liệu đó thuộc Workspace.

---

# 11. Selection Behavior

Single Click

↓

Workspace cập nhật.

Double Click

↓

Không bắt buộc.

Có thể dùng như shortcut.

Không phụ thuộc vào Double Click.

Single Click là hành vi chuẩn.

---

# 12. Empty Navigation

Nếu chưa có học sinh.

Hiển thị.

No students found.

Không hiển thị Table rỗng.

Không hiển thị nhiều cột.

---

# 13. Workspace Philosophy

Workspace là nơi giáo viên làm việc.

Workspace không phải Dialog.

Workspace không phải Form.

Workspace giống hồ sơ của học sinh.

Giáo viên có thể đọc liên tục từ trên xuống dưới.

Không phải mở nhiều cửa sổ.

---

# 14. Workspace Scroll Rule

Workspace luôn có thể scroll.

Navigation không scroll theo Workspace.

Header luôn giữ nguyên.

Chỉ phần Content scroll.

Điều này giúp giáo viên luôn biết mình đang xem học sinh nào.

---

# 15. Future Compatibility

Mọi module mới phải gắn vào Workspace.

Ví dụ

Assessment

↓

Workspace

Parent

↓

Workspace

Products

↓

Workspace

Timeline

↓

Workspace

Attachment

↓

Workspace

Không tạo màn hình mới nếu không thật sự cần thiết.

---

# 16. UX Do

✓ Một nơi cho một loại thông tin

✓ Ít popup

✓ Đọc từ trên xuống

✓ Scroll liên tục

✓ Click để chuyển học sinh

✓ Header luôn hiển thị

✓ Layout ổn định

---

# 17. UX Don't

✗ Mở nhiều dialog

✗ Chia nhỏ dữ liệu nhiều màn hình

✗ Hiển thị thông tin trùng lặp

✗ Navigation quá nhiều dữ liệu

✗ Popup để xem Profile

✗ Redesign Layout sau mỗi Sprint

---

# End of Part I

# Part II

# Student Workspace Specification

---

# 18. Student Workspace

Student Workspace là khu vực làm việc chính của CenterManager.

Toàn bộ thông tin của một học sinh được hiển thị tại đây.

Workspace phải luôn tồn tại trong Main Window.

Workspace không được mở dưới dạng Dialog.

Workspace không được thay đổi bố cục giữa các Sprint.

Mọi module mới đều được mở rộng bên trong Workspace.

---

# 19. Workspace Structure

Workspace gồm hai phần.

+---------------------------------------------------------+

Workspace Header

-----------------------------------------------------------

Workspace Content

-----------------------------------------------------------

Content có thể scroll.

Header luôn cố định.

---

# 20. Workspace Header

Workspace Header luôn nằm ở đầu Workspace.

Header giúp giáo viên ngay lập tức biết mình đang làm việc với học sinh nào.

Header không chứa dữ liệu học tập.

Header chỉ chứa thông tin định danh.

---

Layout

+-------------------------------------------------------------+

(Avatar)

Nguyễn Văn An

HS001

[ Edit ]

[ Export PDF ]

+-------------------------------------------------------------+

---

# 21. Header Components

Workspace Header bao gồm:

Avatar

Student Name

Student Code

Edit Button

Export Button

Không đặt thêm thông tin khác.

---

# 22. Avatar

Avatar là placeholder.

Nếu chưa có ảnh.

Hiển thị icon mặc định.

Sau này có thể mở rộng:

Student Photo

QR Code

ID Card

Nhưng vị trí Avatar không thay đổi.

---

# 23. Student Name

Student Name là thành phần nổi bật nhất của Header.

Font lớn nhất trong Workspace.

Luôn hiển thị đầy đủ.

Nếu quá dài.

Cho phép xuống dòng.

Không cắt "...".

---

# 24. Student Code

Student Code nằm ngay dưới tên.

Font nhỏ hơn.

Màu nhạt hơn.

Ví dụ

HS001

Đây là thông tin nhận diện.

Không phải tiêu đề.

---

# 25. Action Buttons

Hai nút nằm bên phải Header.

Edit

Export PDF

Export PDF có thể disabled nếu chưa implement.

Không ẩn nút.

Điều này giúp giao diện ổn định giữa các phiên bản.

---

# 26. Workspace Content

Workspace Content được chia thành nhiều Section.

Mỗi Section đại diện cho một nhóm thông tin.

Ví dụ

Basic Information

Learning

Assessment

Timeline

Notes

Không trộn dữ liệu giữa các Section.

---

# 27. Section Layout

Mọi Section đều có cùng cấu trúc.

+-----------------------------------------------------------+

SECTION TITLE

-----------------------------------------------------------

Content

+-----------------------------------------------------------+

Điều này giúp người dùng hình thành thói quen đọc.

---

# 28. Section Order

Thứ tự Section luôn cố định.

1.

Basic Information

↓

2.

Parents

↓

3.

Learning

↓

4.

Assessment

↓

5.

Products

↓

6.

Attachments

↓

7.

Timeline

↓

8.

Notes

Không thay đổi thứ tự.

Không cho phép kéo thả.

---

# 29. Basic Information

Đây là Section đầu tiên.

Hiển thị thông tin nhận diện.

Bao gồm

Preferred Name

Date of Birth

Age

Gender

Không hiển thị ID Database.

Không hiển thị Primary Key.

---

Ví dụ

👤 BASIC INFORMATION

Preferred Name

An

Date of Birth

01/01/2014

Age

11

Gender

Male

---

# 30. Parents

Section này dành cho thông tin phụ huynh.

Sprint đầu chỉ hiển thị Empty State.

Sau này mở rộng:

Father

Mother

Guardian

Emergency Contact

---

# 31. Learning

Learning là Section giáo viên xem nhiều nhất.

Nằm ngay dưới Basic Information.

Sprint đầu hiển thị:

Current Level

Status

Sau này mở rộng:

Current Course

Teacher

Class

Enrollment Date

Learning Path

Completion

---

Ví dụ

🎓 LEARNING

Current Level

Python 2

Status

Active

---

# 32. Assessment

Section dành cho đánh giá.

Sprint đầu.

Không có CRUD.

Chỉ Empty State.

Sau này.

Assessment sẽ trở thành Timeline dạng Card.

---

# 33. Student Products

Hiển thị các sản phẩm của học sinh.

Không lưu file.

Chỉ lưu Link.

Ví dụ

Scratch

Python

Robot

GitHub

Google Drive

Video

Điều này giúp database nhỏ.

Workspace nhẹ.

---

# 34. Attachments

Attachment lưu các tài liệu.

Ví dụ

Registration Form

Certificate

Images

Documents

Không hiển thị Preview lớn.

Chỉ danh sách.

---

# 35. Timeline

Timeline là lịch sử phát triển.

Không phải nhật ký hệ thống.

Ví dụ

Joined Center

Completed Course

Assessment

Competition

Award

Teacher Comment

Timeline luôn hiển thị theo thời gian.

Mới nhất ở trên.

---

# 36. Notes

Notes luôn nằm cuối Workspace.

Đây là nơi giáo viên ghi chú tự do.

Cho phép xuống dòng.

Không giới hạn chiều cao.

Không giới hạn số ký tự ở mức UI.

---

# 37. Empty State

Nếu một Section chưa có dữ liệu.

Không để trống.

Hiển thị Empty State.

Ví dụ

No parent information.

No assessments.

No products.

No attachments.

No activity.

Không dùng

Coming Soon

Under Construction

N/A

---

# 38. Scroll Behavior

Workspace Content scroll độc lập.

Header không scroll.

Navigation không scroll theo.

Điều này giúp giáo viên luôn biết mình đang xem học sinh nào.

---

# 39. Empty Workspace

Nếu chưa chọn học sinh.

Workspace hiển thị.

+--------------------------------------------------+

No student selected.

Select a student from the list.

+--------------------------------------------------+

Không hiển thị Section.

Không hiển thị Header.

---

# 40. Refresh Rule

Khi đổi Student.

Workspace cập nhật toàn bộ.

Không refresh từng Section riêng.

Điều này đảm bảo mọi dữ liệu luôn đồng bộ.

---

# 41. Edit Workflow

Click Edit

↓

Open Student Dialog

↓

Save

↓

Close Dialog

↓

Workspace Refresh

↓

Student List Refresh

Không cần người dùng Refresh thủ công.

---

# 42. Future Expansion Rule

Mọi module mới đều phải tuân thủ cùng cấu trúc Section.

Không được tạo kiểu giao diện riêng.

Ví dụ

Assessment

Products

Timeline

Parent

đều phải sử dụng cùng mẫu:

Section Title

↓

Section Content

↓

Empty State

Điều này giúp toàn bộ Workspace luôn nhất quán.

---

# End of Part II

# Part III

# Design System & Component Specification

---

# 43. Design System

CenterManager sử dụng một Design System thống nhất.

Mục tiêu của Design System là:

- Tạo trải nghiệm nhất quán.
- Giảm thời gian thiết kế.
- Giảm thời gian phát triển.
- Giúp mọi màn hình có cùng phong cách.

Developer không được tự ý thiết kế Component mới nếu đã có Component tương đương.

---

# 44. Design Principles

Mọi thành phần UI phải tuân theo 5 nguyên tắc.

## Consistency

Một loại dữ liệu chỉ có một cách hiển thị.

Ví dụ:

Student Name

luôn hiển thị giống nhau.

Không được mỗi màn hình một kiểu.

---

## Simplicity

Không thêm hiệu ứng nếu không tạo ra giá trị.

Ưu tiên:

Đơn giản

Dễ đọc

Ít màu

Nhiều khoảng trắng

---

## Readability

Thông tin quan trọng phải đọc được trong vài giây.

Tên học sinh phải nổi bật hơn mã học sinh.

Current Level phải nổi bật hơn Status.

---

## Scalability

Component phải đủ linh hoạt để dùng lại.

Không thiết kế riêng cho một màn hình.

---

## Predictability

Người dùng luôn biết thông tin nằm ở đâu.

Không thay đổi vị trí giữa các phiên bản.

---

# 45. Layout Grid

CenterManager sử dụng khoảng cách cố định.

Spacing Scale

4 px

8 px

12 px

16 px

24 px

32 px

48 px

Không sử dụng giá trị ngẫu nhiên.

Ví dụ

13 px

21 px

37 px

---

# 46. Margin Rules

Khoảng cách giữa các Section

24 px

Khoảng cách Header → Content

24 px

Khoảng cách giữa Label và Value

8 px

Khoảng cách giữa hai dòng dữ liệu

12 px

---

# 47. Padding Rules

Section

16 px

Card

16 px

Dialog

24 px

Button

12 px

---

# 48. Typography Hierarchy

CenterManager chỉ sử dụng một hệ thống Typography.

Level 1

Student Name

Lớn nhất

Bold

---

Level 2

Section Title

Bold

---

Level 3

Label

Normal

---

Level 4

Value

Normal

---

Level 5

Helper Text

Nhỏ

Màu nhạt

---

# 49. Color Philosophy

Không sử dụng nhiều màu.

Màu chỉ dùng để truyền đạt trạng thái.

Ví dụ

Success

Warning

Error

Information

Không dùng màu chỉ để trang trí.

---

# 50. Icon Rules

Icon chỉ dùng để:

Định hướng

Nhận diện

Không thay thế văn bản.

Ví dụ

👤 Basic Information

🎓 Learning

📊 Assessment

📁 Products

📅 Timeline

📝 Notes

Icon luôn đứng trước tiêu đề.

---

# 51. Component Hierarchy

CenterManager chỉ sử dụng một số Component cơ bản.

Button

Card

Section

Divider

Label

Value

Search Box

Student List

Developer không nên tạo Component mới nếu chưa thật sự cần.

---

# 52. Section Component

Section là Component quan trọng nhất.

Structure

Section Header

↓

Divider

↓

Section Content

↓

Empty State (nếu cần)

Mọi Section đều giống nhau.

---

# 53. Card Component

Card dùng để hiển thị dữ liệu theo nhóm.

Ví dụ sau này

Assessment

Timeline

Product

Attachment

đều hiển thị dạng Card.

Không tạo nhiều kiểu Card khác nhau.

---

# 54. Label / Value Pattern

Thông tin luôn hiển thị theo cặp.

Label

↓

Value

Ví dụ

Current Level

Python Level 2

Status

Active

Không dùng Table.

Không dùng nhiều cột.

Ưu tiên đọc từ trên xuống.

---

# 55. Empty State Component

Mỗi Section đều có Empty State.

Structure

Icon

↓

Title

↓

Description

Ví dụ

📄

No assessments yet.

Assessment results will appear here.

Empty State phải giúp người dùng hiểu điều gì sẽ xuất hiện trong tương lai.

---

# 56. Button Specification

Primary Button

Chỉ có một hành động chính.

Ví dụ

Save

---

Secondary Button

Ví dụ

Cancel

Export

Refresh

---

Danger Button

Delete

Reset

Chỉ dùng khi thật sự cần.

---

# 57. Input Specification

Mọi Input sử dụng cùng quy tắc.

Label

↓

Input

↓

Helper Text (nếu có)

↓

Validation Error (nếu có)

Không đặt Placeholder thay cho Label.

---

# 58. Dialog Specification

Dialog chỉ dùng để:

Create

Edit

Delete Confirmation

Không dùng Dialog để hiển thị dữ liệu.

Dữ liệu luôn hiển thị trong Workspace.

---

# 59. Scroll Specification

Chỉ Workspace Content được scroll.

Navigation độc lập.

Header luôn cố định.

Toolbar luôn cố định.

Không tạo nhiều thanh cuộn trên cùng một vùng.

---

# 60. Selection State

Student được chọn phải có trạng thái rõ ràng.

Selected

Hover

Normal

Người dùng luôn biết mình đang làm việc với học sinh nào.

---

# 61. Disabled State

Disabled không được biến mất.

Ví dụ

Export PDF

Nếu chưa hỗ trợ

↓

Button vẫn tồn tại

↓

Disabled

↓

Tooltip

Available in future version.

Điều này giúp giao diện ổn định.

---

# 62. Loading State

Không khóa toàn bộ ứng dụng.

Chỉ Loading phần dữ liệu cần thiết.

Workspace có thể hiển thị Skeleton hoặc Loading Indicator.

Navigation vẫn hoạt động.

---

# 63. Error State

Nếu tải dữ liệu thất bại.

Không hiển thị màn hình trắng.

Hiển thị

Error Title

↓

Description

↓

Retry Button

---

# 64. Responsive Rules

CenterManager là Desktop Application.

Không cần Responsive như Web.

Tuy nhiên.

Khi cửa sổ thu nhỏ.

Workspace vẫn ưu tiên hiển thị.

Navigation có thể thu hẹp.

Không được che mất Workspace.

---

# 65. Future Component Library

Sau này toàn bộ Component sẽ được chuẩn hóa.

Ví dụ

StudentCard

AssessmentCard

TimelineCard

AttachmentCard

ProductCard

ParentCard

Tất cả đều kế thừa cùng Design Language.

---

# 66. Naming Convention

Component

PascalCase

StudentWorkspace

AssessmentCard

ParentSection

TimelineCard

Variable

camelCase

Function

camelCase

File

PascalCase

Không viết tắt.

---

# 67. UI Review Checklist

Trước khi Merge.

Developer phải tự kiểm tra.

□ Đúng Layout

□ Đúng Section Order

□ Đúng Typography

□ Đúng Spacing

□ Đúng Empty State

□ Không tạo Popup mới

□ Không trùng dữ liệu

□ Scroll đúng

□ Selection đúng

□ Refresh đúng

□ Component tái sử dụng

Nếu còn mục nào chưa đạt.

Không Merge.

---

# 68. Design Review Checklist

PM Review.

□ Có đúng Product Vision

□ Có đúng UX Philosophy

□ Có đúng Teacher Workflow

□ Có đúng Information Hierarchy

□ Có đúng Design System

Nếu một tính năng đẹp nhưng không phục vụ giáo viên.

Không chấp nhận.

---

# End of Part III

# Part IV

# Interaction Design & Workflow Specification

---

# 69. Purpose

Part này định nghĩa cách người dùng tương tác với CenterManager.

Nó không mô tả giao diện.

Nó mô tả hành vi của hệ thống.

Mỗi hành động của người dùng phải có phản hồi rõ ràng.

Người dùng không bao giờ được cảm thấy:

"Tôi vừa bấm cái gì?"

---

# 70. Primary User Journey

Workflow chuẩn của giáo viên.

Open CenterManager

↓

Search Student

↓

Select Student

↓

Workspace Updated

↓

Read Information

↓

Edit (if needed)

↓

Save

↓

Continue Next Student

Đây là workflow được tối ưu nhiều nhất.

---

# 71. Navigation Flow

Navigation không phải nơi làm việc.

Navigation chỉ dùng để:

Search

↓

Locate Student

↓

Select Student

Ngay sau khi chọn.

Mọi thao tác chuyển sang Workspace.

---

# 72. Student Selection

Single Click

↓

Student Selected

↓

Highlight Student

↓

Workspace Loading

↓

Workspace Updated

↓

Ready

Không yêu cầu Double Click.

Không cần nút Open.

---

# 73. Workspace Refresh

Workspace luôn phản ánh đúng Student đang được chọn.

Nếu người dùng click Student khác.

Workspace phải thay đổi ngay.

Không cần bấm Refresh.

Không cần đóng mở.

---

# 74. Search Behavior

Search hoạt động theo thời gian thực.

Khi người dùng nhập.

↓

Student List Filter

↓

Workspace không thay đổi.

Workspace chỉ thay đổi khi người dùng chọn Student.

Điều này tránh thay đổi ngoài ý muốn.

---

# 75. Search Rules

Search hỗ trợ:

Student Code

Student Name

Không phân biệt chữ hoa/chữ thường.

Khoảng trắng đầu và cuối được bỏ qua.

Nếu không có kết quả.

Hiển thị:

No students found.

Không hiển thị lỗi.

---

# 76. Edit Workflow

Workspace

↓

Edit Button

↓

Edit Dialog

↓

User Edit

↓

Save

↓

Validation

↓

Database

↓

Refresh Workspace

↓

Refresh Navigation (nếu cần)

↓

Close Dialog

Không yêu cầu người dùng tải lại dữ liệu.

---

# 77. Cancel Workflow

Edit Dialog

↓

Cancel

↓

Close Dialog

↓

Workspace giữ nguyên

Không thay đổi dữ liệu.

Không refresh.

---

# 78. Unsaved Changes

Nếu người dùng đóng Dialog khi chưa lưu.

Hiển thị xác nhận.

Discard changes?

[Discard]

[Continue Editing]

Không tự động mất dữ liệu.

---

# 79. Save Feedback

Sau khi Save thành công.

Hiển thị thông báo ngắn.

Student updated successfully.

Thông báo tự biến mất.

Không cần người dùng bấm OK.

---

# 80. Delete Workflow

Delete chỉ thực hiện qua Confirmation Dialog.

Không Delete ngay.

Workflow.

Delete

↓

Confirmation

↓

Delete

↓

Refresh List

↓

Clear Workspace (nếu Student đang mở)

---

# 81. Empty Workspace Flow

Nếu chưa chọn Student.

Workspace hiển thị.

No student selected.

Select a student from the list.

Không hiển thị dữ liệu giả.

Không hiển thị Section.

---

# 82. Loading Workflow

Nếu dữ liệu đang tải.

Workspace hiển thị Loading.

Navigation vẫn hoạt động.

Không khóa toàn bộ ứng dụng.

---

# 83. Error Workflow

Nếu tải thất bại.

Hiển thị.

Unable to load student.

[Retry]

Không crash.

Không hiện stack trace.

---

# 84. Keyboard Interaction

Các phím tắt chuẩn:

Ctrl + F

↓

Focus Search

ESC

↓

Close Dialog

Enter

↓

Default Button

Tab

↓

Next Input

Shift + Tab

↓

Previous Input

Không định nghĩa phím tắt riêng nếu chưa cần.

---

# 85. Mouse Interaction

Single Click

↓

Select

Double Click

↓

Optional Shortcut

Right Click

↓

Reserved for future Context Menu

---

# 86. Notification Rules

Notification chia thành 4 loại.

Information

Success

Warning

Error

Notification không che nội dung Workspace.

Không yêu cầu người dùng đóng nếu không cần.

---

# 87. Confirmation Rules

Chỉ hỏi xác nhận khi:

Delete

Discard Changes

Exit With Unsaved Changes

Không hỏi xác nhận khi Save.

---

# 88. Validation Rules

Validation thực hiện trước khi lưu.

Ví dụ.

Student Name

Không được rỗng.

Nếu lỗi.

Highlight Input.

↓

Hiển thị Error.

↓

Không đóng Dialog.

---

# 89. Focus Rules

Sau khi mở Dialog.

Focus vào Input đầu tiên.

Sau khi Save.

Focus quay lại Student đang chọn.

Không mất vị trí.

---

# 90. Scroll Rules

Workspace giữ nguyên vị trí cuộn nếu chỉ cập nhật nội dung nhỏ.

Nếu đổi Student.

Workspace luôn cuộn về đầu.

Điều này giúp giáo viên bắt đầu đọc từ Header.

---

# 91. Selection Persistence

Student đang chọn luôn được giữ Highlight.

Ngay cả khi Workspace Refresh.

Ngay cả khi Edit thành công.

Chỉ đổi Selection khi người dùng chọn Student khác.

---

# 92. Performance Rules

Navigation phải phản hồi ngay lập tức.

Search không được gây cảm giác lag.

Workspace nên hiển thị trong thời gian ngắn nhất có thể.

Nếu tải lâu.

Hiển thị Loading.

Không để giao diện đứng yên.

---

# 93. Future Multi-Window Policy

CenterManager ưu tiên Single Window.

Không tạo thêm cửa sổ chính.

Dialog chỉ dùng cho:

Create

Edit

Delete Confirmation

Không tạo cửa sổ riêng cho Student Profile.

---

# 94. Undo / Redo

Chưa triển khai.

Tuy nhiên.

Mọi thao tác chỉnh sửa phải được thiết kế để có thể hỗ trợ Undo trong tương lai.

---

# 95. Audit-Friendly Workflow

Sau này.

Mọi thao tác quan trọng có thể ghi Timeline.

Ví dụ.

Student Created

Student Updated

Assessment Added

Product Linked

Không hiển thị log kỹ thuật cho giáo viên.

---

# 96. UX Anti-Patterns

Không được phép:

✗ Popup chồng Popup

✗ Refresh toàn bộ ứng dụng sau Save

✗ Dialog chỉ để xem dữ liệu

✗ Phải bấm nhiều bước để xem một Student

✗ Mất Selection sau Refresh

✗ Scroll nhảy lung tung

✗ Thông báo lỗi khó hiểu

---

# 97. Workflow Review Checklist

Mọi tính năng mới phải trả lời được:

□ Người dùng bắt đầu từ đâu?

□ Kết thúc ở đâu?

□ Có cần popup không?

□ Có ít click hơn cách cũ không?

□ Có làm gián đoạn giáo viên không?

□ Có giữ đúng Teacher Workflow First không?

Nếu câu trả lời là "Không", cần thiết kế lại.

---

# End of Part IV

# Part V

# Product Evolution & Governance

---

# 98. Purpose

CenterManager là một sản phẩm sẽ được phát triển trong nhiều năm.

Tài liệu này định nghĩa các quy tắc để sản phẩm có thể mở rộng mà vẫn giữ được trải nghiệm người dùng nhất quán.

Mọi Sprint trong tương lai đều phải tuân thủ các quy tắc dưới đây.

---

# 99. Product Evolution Philosophy

CenterManager không phát triển bằng cách thêm thật nhiều tính năng.

CenterManager phát triển bằng cách:

- Làm cho quy trình của giáo viên tốt hơn.
- Làm cho việc tìm thông tin nhanh hơn.
- Làm cho hồ sơ học sinh đầy đủ hơn.

Mỗi Sprint phải làm cho sản phẩm tốt hơn, không phải chỉ lớn hơn.

---

# 100. One Feature, One Purpose

Mỗi tính năng mới phải có một mục đích rõ ràng.

Ví dụ:

Assessment

→ Theo dõi năng lực.

Timeline

→ Theo dõi lịch sử.

Products

→ Lưu thành quả.

Parents

→ Quản lý liên hệ.

Không tạo một tính năng làm nhiều việc.

---

# 101. Expand Before Create

Khi có yêu cầu mới.

Developer phải tự hỏi.

"Có thể mở rộng Workspace hiện tại không?"

Nếu câu trả lời là Có.

Không tạo màn hình mới.

Ví dụ.

Attendance

↓

Learning Section

Không phải

Attendance Window

---

# 102. New Screen Policy

Chỉ được tạo màn hình mới khi:

- Không thể biểu diễn bằng Workspace.
- Có workflow hoàn toàn khác.
- Có nhiều bước liên tiếp.
- Có yêu cầu riêng về điều hướng.

Nếu không đáp ứng các điều kiện trên.

Không tạo màn hình mới.

---

# 103. Section First Strategy

Tính năng mới ưu tiên:

Thêm Section.

Không thêm Window.

Ví dụ.

Certificates

↓

Attachment Section

Achievements

↓

Timeline Section

Parent Notes

↓

Parent Section

Điều này giữ cho giáo viên luôn làm việc trong một không gian quen thuộc.

---

# 104. Stable Layout Policy

Layout tổng thể của CenterManager là tài sản của sản phẩm.

Không thay đổi chỉ vì một Sprint.

Layout chỉ được thay đổi khi:

- Có nghiên cứu UX.
- Có vấn đề thực tế từ người dùng.
- Có quyết định ở cấp Product.

---

# 105. Product Consistency Rule

Nếu một tính năng mới không giống các tính năng hiện có.

Không được Merge.

Ví dụ.

Nếu mọi Section đều dùng Card.

Không được tạo một Section dùng Table chỉ vì tiện lập trình.

---

# 106. UI Review Process

Mọi tính năng mới phải được review theo trình tự.

Product Vision

↓

UX Design

↓

Implementation

↓

Review

Không được bỏ qua bước UX.

---

# 107. Product Review Questions

Trước khi chấp nhận một tính năng mới.

PM phải trả lời.

□ Giáo viên có dùng tính năng này thường xuyên không?

□ Nó có giúp giáo viên nhanh hơn không?

□ Nó có làm Workspace rối hơn không?

□ Nó có đúng Product Vision không?

□ Có thể đơn giản hơn không?

Nếu còn nhiều câu trả lời "Không".

Cần thiết kế lại.

---

# 108. Technical Convenience Is Not Product Value

Không chấp nhận các quyết định chỉ vì:

"Dễ code hơn."

"Dễ lưu database hơn."

"Dễ implement hơn."

Thiết kế phải phục vụ người dùng trước.

Kỹ thuật là công cụ để hiện thực hóa thiết kế.

---

# 109. Design Debt

Design Debt là những quyết định làm giảm chất lượng trải nghiệm người dùng theo thời gian.

Ví dụ:

- Popup chồng Popup.
- Mỗi màn hình một phong cách.
- Thông tin trùng lặp.
- Điều hướng vòng vo.
- Nhiều nút nhưng ít giá trị.

Mỗi Sprint nên giảm Design Debt thay vì tạo thêm.

---

# 110. Product Debt Review

Cuối mỗi Sprint.

PM cần tự đánh giá.

□ Có màn hình nào thừa không?

□ Có popup nào có thể loại bỏ không?

□ Có Section nào quá dài không?

□ Có thông tin nào đang hiển thị hai lần không?

□ Có thao tác nào cần quá nhiều click không?

Nếu có.

Đưa vào Sprint tiếp theo.

---

# 111. Backward Compatibility

Tính năng mới không được làm thay đổi cách giáo viên đã quen sử dụng.

Ví dụ.

Nếu Edit luôn nằm ở Header.

Sau này vẫn phải ở Header.

Không tự ý chuyển sang Menu.

---

# 112. Future Modules

CenterManager được thiết kế để có thể mở rộng.

Ví dụ:

- Attendance
- Homework
- Billing
- Certificates
- Competitions
- AI Learning Analysis
- Parent Portal
- Teacher Dashboard

Các module này phải tuân theo Design System hiện có.

---

# 113. Product Success Metrics

Một Sprint không được đánh giá bằng số lượng dòng code.

Sprint được đánh giá bằng:

- Ít click hơn.
- Dễ tìm thông tin hơn.
- Ít lỗi thao tác hơn.
- Giáo viên làm việc nhanh hơn.
- Trải nghiệm nhất quán hơn.

---

# 114. Definition of Done (Product)

Một tính năng chỉ được xem là hoàn thành khi:

□ Đúng Product Vision.

□ Đúng UX Design.

□ Đúng Design System.

□ Đúng Workflow.

□ Có Empty State.

□ Có Error State.

□ Có Loading State.

□ Không phá Layout.

□ Có thể mở rộng trong tương lai.

Code chạy được chưa đủ.

---

# 115. Decision Priority

Khi có nhiều phương án.

Ưu tiên theo thứ tự.

1. Product Vision

↓

2. User Experience

↓

3. Design Consistency

↓

4. Architecture

↓

5. Implementation

Không được đảo ngược.

---

# 116. Product Governance

Mọi thay đổi về UX đều phải cập nhật vào:

02_UX_DESIGN_SPEC.md

Không được chỉ sửa code.

Tài liệu luôn là nguồn thông tin chính thức.

---

# 117. Continuous Improvement

CenterManager sẽ luôn thay đổi.

Nhưng mọi thay đổi phải hướng đến:

Đơn giản hơn.

Nhanh hơn.

Dễ hiểu hơn.

Không phải nhiều tính năng hơn.

---

# 118. Final Design Principle

Mỗi khi thêm một tính năng mới.

Hãy tự hỏi:

> Nếu tôi là một giáo viên đang đứng lớp và chỉ có 30 giây để tìm thông tin về một học sinh, tính năng này có giúp tôi hay làm tôi chậm lại?

Nếu nó giúp giáo viên nhanh hơn.

Đó là một tính năng tốt.

Nếu nó làm giao diện phức tạp hơn.

Hãy thiết kế lại.

---

# 119. Product Manifesto

CenterManager không được xây dựng để quản lý dữ liệu.

CenterManager được xây dựng để hỗ trợ giáo viên.

Chúng ta không tạo ra nhiều màn hình.

Chúng ta tạo ra một không gian làm việc tốt hơn.

Mỗi học sinh có một hồ sơ.

Mỗi hồ sơ kể một câu chuyện.

Mỗi câu chuyện giúp giáo viên hiểu học sinh hơn.

Đó là mục tiêu cuối cùng của CenterManager.

---

# END OF DOCUMENT