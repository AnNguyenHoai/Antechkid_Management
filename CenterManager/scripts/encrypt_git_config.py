#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Encrypt Git configuration for CenterManager.

Usage:
    python scripts/encrypt_git_config.py -r https://github.com/org/repo.git -u username

Output:
    ENC:v1:<base64_payload>
"""

import argparse
import json
import getpass
import sys
from pathlib import Path

# Thêm src vào path để import crypto
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.core.crypto import encrypt_git_config


def main():
    parser = argparse.ArgumentParser(description="Encrypt Git configuration")
    parser.add_argument("-r", "--repository", required=True, help="Git repository URL")
    parser.add_argument("-u", "--username", required=True, help="Git username")
    parser.add_argument("-t", "--token", help="Git token (prompt if not provided)")
    parser.add_argument("-b", "--branch", default="main", help="Git branch")
    parser.add_argument("-e", "--email", help="Git email")
    parser.add_argument("-o", "--output", help="Output file (optional)")

    args = parser.parse_args()

    token = args.token
    if not token:
        token = getpass.getpass("GitHub token: ")

    config = {
        "repository_url": args.repository,
        "username": args.username,
        "token": token,
        "branch": args.branch,
    }
    if args.email:
        config["email"] = args.email

    # Mã hóa
    plaintext = json.dumps(config, ensure_ascii=False)
    bundle = encrypt_git_config(plaintext)

    # In ra không có khoảng trắng thừa
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(bundle)
        print(f"Bundle saved to: {args.output}")
    else:
        print(bundle)

    # In thêm để copy dễ
    print("\nCopy the above bundle (starting with ENC:v1:) and paste into CenterManager.")


if __name__ == "__main__":
    main()