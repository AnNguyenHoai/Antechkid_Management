#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the EP-PROD-04 database upgrade rehearsal against a real DB copy."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from centermanager.database.upgrade_gate import (  # noqa: E402
    DatabaseUpgradeGateError,
    run_database_upgrade_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a consistent snapshot of a production-like CenterManager SQLite DB, "
            "upgrade only the snapshot to Alembic head, and validate integrity/data invariants."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        type=Path,
        help="Path to the real/production-like center.db. The source is opened read-only.",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=PROJECT_ROOT / "release-evidence",
        help="Parent directory for timestamped upgrade evidence (default: release-evidence).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = args.evidence_root.resolve() / f"database-upgrade-{stamp}"

    try:
        report = run_database_upgrade_gate(args.database, evidence_dir)
    except DatabaseUpgradeGateError as exc:
        print(f"PROD-04 DATABASE UPGRADE GATE: FAILED\n{exc}", file=sys.stderr)
        print(f"Evidence directory: {evidence_dir}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            "PROD-04 DATABASE UPGRADE GATE: FAILED with unexpected migration error\n"
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"Evidence directory: {evidence_dir}", file=sys.stderr)
        return 1

    print("PROD-04 DATABASE UPGRADE GATE: PASSED")
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Evidence directory: {evidence_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
