#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create an encrypted Git configuration bundle for CenterManager.

Default usage is interactive:

    python scripts/encrypt_git_config.py

The script prompts for repository URL, username, token, branch, and email.
The token is entered with hidden input. CLI arguments remain supported for
automation/backward compatibility.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

# Add src/ so the script can run directly from CenterManager/.
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.core.crypto import encrypt_git_config


def _prompt_required(label: str, current: str | None = None) -> str:
    value = (current or "").strip()
    while not value:
        value = input(f"{label}: ").strip()
        if not value:
            print(f"{label} is required.")
    return value


def _prompt_optional(label: str, current: str | None = None, *, default: str = "") -> str:
    if current is not None:
        return current.strip()
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _prompt_token(current: str | None = None) -> str:
    if current:
        return current.strip()
    token = ""
    while not token:
        token = getpass.getpass("Git token (hidden): ").strip()
        if not token:
            print("Git token is required.")
    return token


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create an encrypted CenterManager Git configuration bundle. "
            "Run without arguments for interactive mode."
        )
    )
    parser.add_argument("-r", "--repository", help="Git repository URL")
    parser.add_argument("-u", "--username", help="Git username")
    parser.add_argument("-t", "--token", help="Git token (not recommended on shared shells)")
    parser.add_argument("-b", "--branch", help="Git branch (default: main)")
    parser.add_argument("-e", "--email", help="Git email (optional)")
    parser.add_argument("-o", "--output", help="Write encrypted bundle to this file")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    print("CenterManager - Encrypt Git Configuration")
    print("-----------------------------------------")
    print("Enter the Git settings used by CenterManager.")
    print("The token will not be displayed while typing.\n")

    repository = _prompt_required("Repository URL", args.repository)
    username = _prompt_required("Git username", args.username)
    token = _prompt_token(args.token)
    branch = _prompt_optional("Git branch", args.branch, default="main")
    email = _prompt_optional("Git email (optional)", args.email)

    config = {
        "repository_url": repository,
        "username": username,
        "token": token,
        "branch": branch,
    }
    if email:
        config["email"] = email

    try:
        plaintext = json.dumps(config, ensure_ascii=False)
        bundle = encrypt_git_config(plaintext)
    except Exception as exc:
        print(f"ERROR: Failed to encrypt Git configuration: {exc}", file=sys.stderr)
        return 1

    print("\nEncrypted configuration created successfully.")

    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(bundle, encoding="utf-8")
        print(f"Bundle saved to: {output}")
    else:
        print("\n========== COPY BUNDLE BELOW ==========")
        print(bundle)
        print("========== END BUNDLE =================")

    print(
        "\nPaste this encrypted bundle into the CenterManager Git Configuration dialog."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
