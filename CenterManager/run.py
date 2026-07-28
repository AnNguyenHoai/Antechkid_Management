#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application entry point for CenterManager.
"""
import sys
from pathlib import Path

# Add src/ to Python path for development
src_path = Path(__file__).resolve().parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.app import main

if __name__ == "__main__":
    sys.exit(main())