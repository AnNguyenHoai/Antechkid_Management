# CenterManager – Hướng dẫn triển khai

**Dành cho quản trị viên hệ thống**

---

## 1. Xây dựng từ mã nguồn

### Yêu cầu
- Python 3.9+ (64-bit)
- Git
- Pip

### Các bước
```bash
# Clone repository
git clone https://github.com/your-org/CenterManager.git
cd CenterManager

# Tạo môi trường ảo (khuyến nghị)
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# Cài đặt dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Chạy script build
python build_release.py