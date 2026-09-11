#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Ghi log lỗi ra file nếu chạy exe
if getattr(sys, 'frozen', False):
    log_file = Path(os.path.dirname(sys.executable)) / "error.log"
    sys.stderr = open(log_file, "w")
    sys.stdout = open(log_file, "a")

# Thêm src/ vào sys.path
src_path = Path(__file__).resolve().parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.app import main

if __name__ == "__main__":
    sys.exit(main())