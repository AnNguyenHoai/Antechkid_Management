#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify final EP-PROD-05 two-machine UAT evidence without reading live data."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REQUIRED_SCENARIOS = (
    "a_to_b_publish_sync",
    "b_to_a_publish_sync",
    "internet_loss",
    "finish_failure",
    "crash_in_write",
    "competing_lease",
    "stale_runtime",
    "restart_retry",
    "recovery_snapshot",
)


class TwoMachineUATError(RuntimeError):
    """Raised when the physical UAT evidence does not satisfy the release gate."""


@dataclass(frozen=True)
class VerificationReport:
    status: str
    task: str
    release_version: str
    source_commit: str
    repository_head: str
    remote_fingerprint: str
    authoritative_database_sha256: str
    machine_a_fingerprint: str
    machine_b_fingerprint: str
    scenarios: tuple[str, ...]
    verified_at_utc: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TwoMachineUATError(f"Could not read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TwoMachineUATError(f"Evidence must be a JSON object: {path}")
    return value


def _require(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    value = mapping.get(key)
    if value is None or value == "":
        raise TwoMachineUATError(f"Missing {context}.{key}")
    return value


def _validate_machine(evidence: Mapping[str, Any], expected_role: str) -> None:
    if evidence.get("schema_version") != 1:
        raise TwoMachineUATError(f"Machine {expected_role}: unsupported evidence schema")
    if evidence.get("task") != "EP-PROD-05":
        raise TwoMachineUATError(f"Machine {expected_role}: wrong task marker")
    if evidence.get("role") != expected_role:
        raise TwoMachineUATError(
            f"Expected role {expected_role}, got {evidence.get('role')!r}"
        )

    release = evidence.get("release")
    repository = evidence.get("repository")
    database = evidence.get("database")
    if not isinstance(release, Mapping):
        raise TwoMachineUATError(f"Machine {expected_role}: missing release evidence")
    if not isinstance(repository, Mapping):
        raise TwoMachineUATError(f"Machine {expected_role}: missing repository evidence")
    if not isinstance(database, Mapping):
        raise TwoMachineUATError(f"Machine {expected_role}: missing database evidence")

    for key in ("version", "source_commit"):
        _require(release, key, f"machine_{expected_role}.release")
    for key in ("head", "remote_fingerprint"):
        _require(repository, key, f"machine_{expected_role}.repository")
    for key in ("runtime_sha256", "authoritative_sha256"):
        _require(database, key, f"machine_{expected_role}.database")
    _require(evidence, "machine_fingerprint", f"machine_{expected_role}")

    if repository.get("available") is not True:
        raise TwoMachineUATError(f"Machine {expected_role}: repository is unavailable")
    if database.get("authoritative_matches_runtime") is not True:
        raise TwoMachineUATError(
            f"Machine {expected_role}: runtime DB is not the authoritative repository DB"
        )
    if database.get("runtime_sha256") != database.get("authoritative_sha256"):
        raise TwoMachineUATError(
            f"Machine {expected_role}: database hashes contradict convergence flag"
        )


def _validate_scenarios(report: Mapping[str, Any]) -> tuple[str, ...]:
    if report.get("task") != "EP-PROD-05":
        raise TwoMachineUATError("Scenario report has wrong task marker")
    rows = report.get("scenarios")
    if not isinstance(rows, list):
        raise TwoMachineUATError("Scenario report must contain a scenarios array")

    seen: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise TwoMachineUATError("Every scenario entry must be an object")
        name = row.get("scenario")
        status = row.get("status")
        if not isinstance(name, str) or not name:
            raise TwoMachineUATError("Scenario entry is missing scenario name")
        if name in seen:
            raise TwoMachineUATError(f"Duplicate scenario: {name}")
        seen[name] = str(status).upper() if status is not None else ""

    missing = [name for name in REQUIRED_SCENARIOS if name not in seen]
    extra = [name for name in seen if name not in REQUIRED_SCENARIOS]
    if missing:
        raise TwoMachineUATError(f"Missing required scenarios: {', '.join(missing)}")
    if extra:
        raise TwoMachineUATError(f"Unknown scenarios in gate report: {', '.join(extra)}")

    failed = [name for name in REQUIRED_SCENARIOS if seen[name] != "PASS"]
    if failed:
        detail = ", ".join(f"{name}={seen[name] or 'MISSING_STATUS'}" for name in failed)
        raise TwoMachineUATError(f"Physical UAT is not fully PASS: {detail}")
    return REQUIRED_SCENARIOS


def verify_evidence(
    machine_a: Mapping[str, Any],
    machine_b: Mapping[str, Any],
    scenario_report: Mapping[str, Any],
) -> VerificationReport:
    _validate_machine(machine_a, "A")
    _validate_machine(machine_b, "B")
    scenarios = _validate_scenarios(scenario_report)

    a_release = machine_a["release"]
    b_release = machine_b["release"]
    a_repo = machine_a["repository"]
    b_repo = machine_b["repository"]
    a_db = machine_a["database"]
    b_db = machine_b["database"]

    if a_release["version"] != b_release["version"]:
        raise TwoMachineUATError("Machine A/B release versions differ")
    if a_release["source_commit"] != b_release["source_commit"]:
        raise TwoMachineUATError("Machine A/B release source commits differ")
    if a_repo["remote_fingerprint"] != b_repo["remote_fingerprint"]:
        raise TwoMachineUATError("Machine A/B Git remote fingerprints differ")
    if a_repo["head"] != b_repo["head"]:
        raise TwoMachineUATError("Machine A/B repository HEADs have not converged")
    if a_db["authoritative_sha256"] != b_db["authoritative_sha256"]:
        raise TwoMachineUATError("Machine A/B authoritative database hashes differ")

    a_machine = str(machine_a["machine_fingerprint"])
    b_machine = str(machine_b["machine_fingerprint"])
    if a_machine == b_machine:
        raise TwoMachineUATError("Machine A/B evidence came from the same machine fingerprint")

    return VerificationReport(
        status="PASSED",
        task="EP-PROD-05",
        release_version=str(a_release["version"]),
        source_commit=str(a_release["source_commit"]),
        repository_head=str(a_repo["head"]),
        remote_fingerprint=str(a_repo["remote_fingerprint"]),
        authoritative_database_sha256=str(a_db["authoritative_sha256"]),
        machine_a_fingerprint=a_machine,
        machine_b_fingerprint=b_machine,
        scenarios=scenarios,
        verified_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify final two-machine EP-PROD-05 evidence and physical scenario results."
    )
    parser.add_argument("--machine-a", required=True, type=Path)
    parser.add_argument("--machine-b", required=True, type=Path)
    parser.add_argument("--scenario-report", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = verify_evidence(
            _load_json(args.machine_a),
            _load_json(args.machine_b),
            _load_json(args.scenario_report),
        )
    except TwoMachineUATError as exc:
        print(f"EP-PROD-05 TWO-MACHINE COLLABORATION UAT: FAILED\n{exc}", file=sys.stderr)
        return 1

    serialized = json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True)
    print("EP-PROD-05 TWO-MACHINE COLLABORATION UAT: PASSED")
    print(serialized)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Verification report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
