# CenterManager – Hướng dẫn triển khai

**Dành cho quản trị viên hệ thống**

## 1. Bản phát hành Windows

Bản ZIP phát hành dành cho Windows 10/11 64-bit là bản portable. Người dùng chỉ cần giải nén và chạy `CenterManager.exe`.

Gói phát hành đã chứa:
- `CenterManager.exe`
- thư mục `runtime/` cho dữ liệu thay đổi
- thư mục `git/` chứa Git for Windows MinGit được đóng gói và kiểm tra SHA-256
- các asset Alembic cần cho startup

Không yêu cầu máy đích cài Python hoặc Git.

## 2. Build từ mã nguồn

### Yêu cầu máy build

- Windows 10/11 64-bit
- Python 3.10
- Internet để tải dependencies và MinGit trong quá trình build

### Các bước

```powershell
git clone https://github.com/AnNguyenHoai/Antechkid_Management.git
cd Antechkid_Management\CenterManager

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
pip install pyinstaller

python build_release.py
```

Output:

```
release\CenterManager-v0.1.0-prototype-windows-x64.zip
```

Script build tự tải MinGit 2.54.0 từ Git for Windows, kiểm tra SHA-256 rồi mới đưa vào package.

## 3. Kiểm tra release

CI thực hiện các bước:
1. chạy full pytest;
2. build EXE;
3. kiểm tra runtime contract;
4. kiểm tra bundled Git;
5. giải nén ZIP vào thư mục sạch;
6. chạy portable smoke check với PATH hệ thống tối thiểu, không dùng Git/Python cài ngoài;
7. upload ZIP làm artifact.

## 4. Chạy trên máy mới

Giải nén toàn bộ ZIP vào một thư mục, không chỉ copy riêng file EXE.

Cấu trúc tối thiểu:

```
CenterManager-v0.1.0-prototype-windows-x64/
├── CenterManager.exe
├── git/
├── runtime/
├── alembic.ini
├── migrations/
└── README_RELEASE.md
```

Git synchronization là capability tùy chọn. Nếu chưa có Git configuration hoặc Git/network không khả dụng, ứng dụng vẫn có thể mở ở local/offline mode.
