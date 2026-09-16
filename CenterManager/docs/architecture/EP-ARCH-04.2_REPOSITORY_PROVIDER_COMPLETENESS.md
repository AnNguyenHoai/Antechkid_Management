# EP-ARCH-04.2 — RepositoryProvider Completeness

## Mục tiêu

Đảm bảo `RepositoryProvider` là boundary hoàn chỉnh giữa application services và toàn bộ concrete repositories. Một repository mới không được tồn tại trong source tree mà không được đăng ký vào provider contract và production provider.

## Audit finding

Audit sau EP-ARCH-04.1 phát hiện `TeacherTimelineRepository` đã tồn tại và `TeacherTimelineService` đã gọi `self._repository_provider.teacher_timeline(...)`, nhưng `RepositoryProvider` và `SqlAlchemyRepositoryProvider` chưa khai báo/triển khai factory tương ứng.

Đây là contract drift: static service-boundary gate vẫn có thể pass vì service không chạm SQLAlchemy trực tiếp, trong khi production execution có thể fail khi `TeacherTimelineService` chạy với provider mặc định.

## Remediation

- Đăng ký `TeacherTimelineRepository` trong `provider.py`.
- Thêm `RepositoryProvider.teacher_timeline(...)`.
- Thêm `SqlAlchemyRepositoryProvider.teacher_timeline(...)`.
- Không thay đổi repository API hoặc transaction ownership.

## Regression gate

`tests/test_ep_arch_04_2_repository_provider_completeness.py` kiểm tra động:

1. Mọi `*_repository.py` có concrete `*Repository` phải được provider import.
2. `RepositoryProvider` và `SqlAlchemyRepositoryProvider` phải có cùng factory surface.
3. Mỗi factory phải khai báo return type là repository đã đăng ký và production provider phải construct đúng repository đó.
4. Mọi service call tới `self._repository_provider.<factory>` phải tồn tại trong `RepositoryProvider` contract.

Gate này không dùng allowlist theo từng service/repository; source tree là nguồn phát hiện chính để ngăn contract drift khi thêm repository mới.

## Non-goals

- Không thay đổi business logic.
- Không thay đổi transaction policy.
- Không nới lỏng EP-ARCH-04.1 service boundary.
- Không chuyển query/persistence logic từ repository sang service.
