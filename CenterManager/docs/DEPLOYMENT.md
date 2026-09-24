# CenterManager — Hướng dẫn triển khai

**Dành cho quản trị viên hệ thống**  
Cập nhật: 2026-09-24

## 1. Bản phát hành Windows

Bản ZIP Windows 10/11 64-bit là bản portable. Người dùng giải nén toàn bộ package và chạy `CenterManager.exe`.

Package release có thể chứa:

- `CenterManager.exe`;
- `runtime/` cho dữ liệu thay đổi;
- portable/bundled Git theo release contract;
- Alembic config/migration assets cần cho startup;
- release metadata/docs.

Máy đích không cần cài Python. Nếu release đã bundle Git theo contract thì cũng không cần cài Git riêng.

## 2. Build từ mã nguồn

Baseline CI/build hiện tại là Python 3.10 trên Windows.

```powershell
git clone https://github.com/AnNguyenHoai/Antechkid_Management.git
cd Antechkid_Management\CenterManager

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python build_release.py
```

Tên/version artifact phụ thuộc `VERSION` và release workflow hiện tại; không coi tên `v0.1.0-prototype` cũ là contract cố định.

## 3. Kiểm tra release

Các release/CI workflow có thể bao gồm:

1. full pytest/architecture regression;
2. build executable/package;
3. runtime contract validation;
4. bundled Git validation khi áp dụng;
5. clean extraction/smoke test;
6. artifact upload.

Xem `.github/workflows/` và `build_release.py` để biết contract build chính xác của phiên bản hiện tại.

## 4. Runtime modes

### Local/offline mode

Nếu **không có Git collaboration configuration hợp lệ**, CenterManager có thể chạy với local runtime database.

### Configured collaborative mode

Nếu Git collaboration đã được cấu hình hợp lệ, synchronized repository state là authoritative cho runtime-data lifecycle.

Startup phải synchronize trước khi production database được mở. Nếu authoritative startup synchronization thất bại, ứng dụng **không được** tự động tiếp tục bằng stale local database.

Đây là khác biệt quan trọng với local/offline mode: “mạng lỗi” không có nghĩa là tự động downgrade một deployment đã cấu hình collaboration sang local mode.

## 5. Cấu trúc package/runtime

Giải nén toàn bộ release package; không copy riêng executable.

Runtime data/config/logs/metadata phải được giữ cùng deployment theo contract của `core.paths`/release build.

Không tự ý di chuyển một phần `runtime/` hoặc collaboration metadata giữa các máy nếu không có quy trình backup/restore được xác nhận.

## 6. Database schema

Sau khi authoritative/local runtime database đã được materialize, application startup tự nâng schema lên Alembic head.

Không chạy migration thủ công trên production database trừ khi đang thực hiện một procedure đã được review/backup.

## 7. Backup/restore

Trước thao tác có khả năng ảnh hưởng dữ liệu:

- đóng ứng dụng trên các máy liên quan;
- dùng chức năng/procedure backup hiện có;
- lưu backup ở vị trí tách khỏi deployment đang thao tác;
- trong configured collaboration mode, hiểu rõ authoritative Git state trước khi restore local DB.

Không dùng việc xóa/replace `center.db` như một cách reset user hoặc chữa lỗi thông thường.

## 8. Git credentials/configuration

Git token/repository configuration là deployment credential. Không commit token vào repository source/docs/test fixture.

Nếu synchronization thất bại do credential/network/repository state, xử lý nguyên nhân rồi restart/sync theo platform workflow; không bypass bằng cách ép app dùng stale local data.

## 9. Tài liệu liên quan

- `INSTALL.md` — cài đặt cho người dùng;
- `TROUBLESHOOTING.md` — xử lý sự cố an toàn;
- `ARCHITECTURE.md` — implementation architecture;
- `Deployment_Docs/` — platform/collaboration architecture;
- root `AGENTS.md` — workflow cho coding agents.