# -*- coding: utf-8 -*-
"""Verify the SEC-02 protected-data broker from the desktop/client side."""
from __future__ import annotations

import argparse
import json
import sys

from centermanager.platform.protected_data_service.client import ProtectedDataClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify AnTechKidsData broker health and DB validation.")
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Also request one encrypted protected backup after validation.",
    )
    args = parser.parse_args(argv)
    client = ProtectedDataClient()
    try:
        health = client.health()
        print("[OK] service health:", json.dumps(health, ensure_ascii=False, sort_keys=True))
        if not all(health.get(name) is True for name in ("database_present", "key_present", "metadata_present")):
            raise RuntimeError("Protected storage is incomplete.")
        validation = client.validate_database()
        if validation.get("valid") is not True:
            raise RuntimeError("Protected database validation did not return valid=true.")
        print("[OK] database validated; sha256=" + str(validation.get("database_sha256", "")))
        if args.backup:
            backup = client.create_backup("uat")
            print("[OK] protected backup created: " + str(backup.get("backup_id", "")))
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
