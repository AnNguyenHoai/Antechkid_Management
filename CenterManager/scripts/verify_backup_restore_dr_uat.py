#!/usr/bin/env python3
"""Fail-closed verifier for EP-PROD-06 Backup/Restore Disaster Recovery UAT."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_SCENARIOS = (
    "baseline_backup_create",
    "backup_integrity",
    "restore_after_runtime_damage",
    "metadata_restore",
    "restart_after_restore",
    "corrupt_database_rejected",
    "checksum_mismatch_rejected",
    "outside_path_rejected",
    "newer_format_rejected",
    "collaboration_source_of_truth_preserved",
)


class DisasterRecoveryUATError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationReport:
    task: str
    status: str
    release_version: str
    source_commit: str
    backup_database_sha256: str
    runtime_database_sha256: str
    scenarios: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DisasterRecoveryUATError(message)


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} is missing")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    result = _text(value, field).lower()
    _require(len(result) == 64 and all(ch in "0123456789abcdef" for ch in result), f"{field} is not a SHA-256 value")
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise DisasterRecoveryUATError(f"cannot read JSON evidence {path}: {exc}") from exc
    _require(isinstance(data, dict), f"JSON root must be an object: {path}")
    return data


def _verify_scenarios(report: dict[str, Any]) -> tuple[str, ...]:
    _require(report.get("schema_version") == 1, "scenario report schema_version must be 1")
    _require(report.get("task") == "EP-PROD-06", "scenario report task must be EP-PROD-06")
    scenarios = report.get("scenarios")
    _require(isinstance(scenarios, list), "scenario report scenarios must be a list")

    by_name: dict[str, str] = {}
    for item in scenarios:
        _require(isinstance(item, dict), "every scenario entry must be an object")
        name = _text(item.get("scenario"), "scenario name")
        _require(name not in by_name, f"scenario appears more than once: {name}")
        by_name[name] = _text(item.get("status"), f"scenario {name} status").upper()

    required = set(REQUIRED_SCENARIOS)
    actual = set(by_name)
    missing = sorted(required - actual)
    extra = sorted(actual - required)
    _require(not missing, f"missing required scenarios: {', '.join(missing)}")
    _require(not extra, f"unexpected scenarios: {', '.join(extra)}")

    failed = [name for name in REQUIRED_SCENARIOS if by_name[name] != "PASS"]
    _require(not failed, f"required scenarios are not fully PASS: {', '.join(failed)}")
    return REQUIRED_SCENARIOS


def verify_evidence(evidence: dict[str, Any], scenario_report: dict[str, Any]) -> VerificationReport:
    _require(evidence.get("schema_version") == 1, "evidence schema_version must be 1")
    _require(evidence.get("task") == "EP-PROD-06", "evidence task must be EP-PROD-06")

    release = evidence.get("release")
    backup = evidence.get("backup")
    runtime = evidence.get("runtime")
    _require(isinstance(release, dict), "release evidence is missing")
    _require(isinstance(backup, dict), "backup evidence is missing")
    _require(isinstance(runtime, dict), "runtime evidence is missing")

    version = _text(release.get("version"), "release.version")
    source_commit = _text(release.get("source_commit"), "release.source_commit")
    _require(len(source_commit) >= 7, "release.source_commit is invalid")

    _require(backup.get("managed_path") is True, "selected backup is outside the managed backup directory")
    _require(backup.get("metadata_present") is True, "backup metadata is missing")
    _require(backup.get("checksum_matches") is True, "backup manifest checksum does not match database")
    _require(str(backup.get("sqlite_integrity", "")).lower() == "ok", "backup SQLite integrity is not ok")

    manifest_sha = _sha(backup.get("manifest_sha256"), "backup.manifest_sha256")
    backup_sha = _sha(backup.get("database_sha256"), "backup.database_sha256")
    manifest_db_sha = _sha(backup.get("manifest_database_sha256"), "backup.manifest_database_sha256")
    runtime_sha = _sha(runtime.get("database_sha256"), "runtime.database_sha256")
    _require(manifest_sha != "0" * 64, "backup manifest hash is invalid")
    _require(backup_sha == manifest_db_sha, "backup checksum fields contradict checksum_matches")
    _require(runtime.get("matches_selected_backup") is True, "runtime does not match selected restored backup")
    _require(runtime_sha == backup_sha, "runtime database hash differs from selected backup")

    temp_count = runtime.get("restore_temp_artifact_count")
    _require(isinstance(temp_count, int) and temp_count == 0, "restore temporary artifacts remain after recovery")

    scenarios = _verify_scenarios(scenario_report)
    return VerificationReport(
        task="EP-PROD-06",
        status="PASSED",
        release_version=version,
        source_commit=source_commit,
        backup_database_sha256=backup_sha,
        runtime_database_sha256=runtime_sha,
        scenarios=scenarios,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--scenario-report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        report = verify_evidence(_load_json(args.evidence), _load_json(args.scenario_report))
    except DisasterRecoveryUATError as exc:
        print("EP-PROD-06 BACKUP/RESTORE DISASTER RECOVERY UAT: FAILED")
        print(f"Reason: {exc}")
        return 1

    payload = {
        "task": report.task,
        "status": report.status,
        "release_version": report.release_version,
        "source_commit": report.source_commit,
        "backup_database_sha256": report.backup_database_sha256,
        "runtime_database_sha256": report.runtime_database_sha256,
        "scenarios": list(report.scenarios),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("EP-PROD-06 BACKUP/RESTORE DISASTER RECOVERY UAT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
