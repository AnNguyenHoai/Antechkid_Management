# CenterManager

# 01_PRODUCT_VISION.md

**Version:** 1.0

**Author:** Product Team

**Status:** Approved

---

# 1. Vision

CenterManager không phải là một phần mềm quản lý học sinh truyền thống.

Nó không được xây dựng để thay thế Excel.

Nó cũng không được xây dựng như một hệ thống CRM doanh nghiệp.

CenterManager được thiết kế dành riêng cho các trung tâm đào tạo trẻ em với mục tiêu:

> **Giúp giáo viên hiểu rõ từng học sinh và theo dõi sự phát triển của các em trong suốt quá trình học tập.**

Trong CenterManager, mỗi học sinh không chỉ là một dòng dữ liệu.

Mỗi học sinh là một hồ sơ hoàn chỉnh.

---

# 2. Product Philosophy

Triết lý thiết kế của CenterManager có thể tóm gọn trong một câu:

> **One Student = One Workspace**

Một học sinh tương ứng với một không gian làm việc.

Mọi thông tin của học sinh đều tập trung tại một nơi.

Giáo viên không phải tìm kiếm thông tin ở nhiều màn hình khác nhau.

Khi chọn một học sinh, toàn bộ lịch sử học tập của học sinh đó phải xuất hiện ngay lập tức.

---

# 3. Design Goals

CenterManager được xây dựng dựa trên bốn mục tiêu chính.

## 3.1 Fast Navigation

Danh sách học sinh chỉ dùng để điều hướng.

Người dùng phải có thể tìm một học sinh trong vài giây.

Danh sách không nên chứa quá nhiều thông tin.

Thông tin chi tiết luôn thuộc về Student Workspace.

---

## 3.2 Student-Centered

Toàn bộ sản phẩm xoay quanh học sinh.

Không phải lớp học.

Không phải giáo viên.

Không phải khóa học.

Mọi dữ liệu đều liên kết với Student Workspace.

---

## 3.3 Teacher Workflow First

CenterManager được thiết kế theo cách giáo viên làm việc thực tế.

Một giáo viên thường có các câu hỏi như:

- Học sinh này là ai?
- Đang học đến đâu?
- Ba mẹ là ai?
- Cần lưu ý điều gì?
- Đã đánh giá gần đây chưa?
- Có sản phẩm nào nổi bật không?
- Bước tiếp theo nên làm gì?

CenterManager phải giúp giáo viên trả lời những câu hỏi này nhanh nhất có thể.

---

## 3.4 Long-Term Growth

Một học sinh có thể học tại trung tâm trong nhiều năm.

CenterManager phải lưu được toàn bộ hành trình đó.

Không chỉ lưu thông tin đăng ký.

Mà còn lưu:

- lịch sử học
- đánh giá
- sản phẩm
- ghi chú
- tài liệu
- hình ảnh
- thành tích

---

# 4. Information Architecture

CenterManager chia thông tin thành hai nhóm.

## Navigation

Navigation chỉ giúp tìm học sinh.

Bao gồm:

- Search
- Student List

Navigation không chứa dữ liệu chi tiết.

---

## Workspace

Workspace là nơi làm việc chính.

Workspace hiển thị toàn bộ thông tin của học sinh.

Tất cả thao tác của giáo viên diễn ra tại đây.

---

# 5. Core UX Principle

Người dùng không nên mở nhiều cửa sổ.

Không nên xuất hiện nhiều popup.

Không nên phải nhớ vị trí thông tin.

Mọi thông tin đều nằm trong Student Workspace.

Giáo viên chỉ cần:

```
Click Student

↓

Workspace cập nhật
```

Đây là workflow quan trọng nhất của toàn bộ sản phẩm.

---

# 6. Student Workspace

Student Workspace là trái tim của CenterManager.

Workspace phải có khả năng mở rộng trong nhiều năm.

Workspace sẽ dần phát triển để chứa:

- Basic Information
- Parent Information
- Learning
- Assessment
- Student Products
- Attachments
- Timeline
- Teacher Notes

Tất cả đều thuộc về cùng một Student Workspace.

---

# 7. Information Hierarchy

Không phải mọi thông tin đều quan trọng như nhau.

CenterManager ưu tiên hiển thị theo thứ tự:

## Level 1

Thông tin nhận diện

- Avatar
- Student Name
- Student Code

---

## Level 2

Thông tin giáo viên cần xem hàng ngày

- Current Level
- Status
- Notes

---

## Level 3

Thông tin xem theo nhu cầu

- Parent
- Timeline
- Products
- Attachments

---

## Level 4

Thông tin lịch sử

- Assessment History
- Previous Classes
- Previous Teachers

---

# 8. Future Expansion

CenterManager phải có khả năng mở rộng mà không thay đổi cấu trúc giao diện.

Ví dụ:

Sprint đầu:

```
Student Workspace

Basic

Learning

Notes
```

Sau này:

```
Student Workspace

Basic

Parents

Learning

Assessment

Products

Timeline

Attachments

Notes
```

Workspace chỉ mở rộng nội dung.

Không thay đổi bố cục.

---

# 9. User Experience Principles

Trong toàn bộ dự án, mọi tính năng mới phải tuân thủ các nguyên tắc sau.

## Simple

Không hiển thị thông tin không cần thiết.

---

## Consistent

Mọi Student đều có cùng cấu trúc Workspace.

---

## Discoverable

Giáo viên phải biết thông tin nằm ở đâu mà không cần hướng dẫn.

---

## Readable

Thông tin phải dễ đọc.

Khoảng trắng nhiều hơn dữ liệu.

---

## Scalable

Có thể thêm nhiều module mới mà không phải thiết kế lại.

---

# 10. Product Roadmap

CenterManager sẽ phát triển theo từng lớp.

## Foundation

Database

Repository

Service

Desktop UI

---

## Student Workspace

Basic Information

Learning

Notes

---

## Parent Module

Parent Information

Emergency Contact

Guardian

---

## Assessment Module

3 Month Assessment

6 Month Assessment

12 Month Assessment

Teacher Evaluation

---

## Student Product Module

Scratch Projects

Python Projects

Robot Projects

Video

Github

Google Drive

---

## Attachment Module

Images

Registration Form

Certificates

Documents

---

## Timeline Module

Joined Center

Finished Course

Competition

Achievement

Assessment

---

## Report Module

Student PDF

Class Report

Teacher Report

---

# 11. Success Criteria

CenterManager được xem là thành công khi:

Một giáo viên mới mở phần mềm lần đầu tiên.

Chỉ cần click vào tên một học sinh.

Trong vòng vài giây có thể hiểu:

- học sinh là ai
- đang học gì
- cần chú ý gì
- đã học đến đâu
- nên làm gì tiếp theo

Mà không cần tìm kiếm ở nhiều nơi.

---

# 12. Final Statement

CenterManager không được thiết kế để quản lý dữ liệu.

CenterManager được thiết kế để hỗ trợ giáo viên.

Mọi quyết định về UX, UI và tính năng trong tương lai đều phải trả lời được câu hỏi:

> **Liệu thay đổi này có giúp giáo viên hiểu học sinh nhanh hơn và làm việc hiệu quả hơn không?**

Nếu câu trả lời là **Có**, thay đổi đó phù hợp với triết lý của CenterManager.

Nếu câu trả lời là **Không**, thay đổi đó nên được xem xét lại.

---

# END OF DOCUMENT