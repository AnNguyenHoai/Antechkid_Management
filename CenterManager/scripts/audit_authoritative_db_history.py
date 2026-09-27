# -*- coding: utf-8 -*-
"""Audit authoritative data-repository exposure before SEC-01 encryption cutover.

This tool is deliberately read-only. It checks the current authoritative DB artifact
and every reachable Git commit that contains ``database/center.db``. A plaintext DB
in history remains readable even after the current file is encrypted, so SEC-01
cutover must not be declared complete until that historical exposure is remediated.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Standalone scripts are executed with CenterManager/scripts as sys.path[0].
# Bootstrap the application source tree exactly like run.py so
# ``python scripts/audit_authoritative_db_history.py`` works from a clean shell
# without requiring an editable install or caller-provided PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
if _SRC_ROOT.is_dir() and str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from git import Repo

from centermanager.core.paths import get_paths


SQLITE_HEADER = b"SQLite format 3\x00"
DB_REPO_PATH = "database/center.db"


@dataclass(frozen=True)
class HistoryFinding:
    commit: str
    plaintext: bool


@dataclass(frozen=True)
class AuditResult:
    repository: str
    database_path: str
    current_exists: bool
    current_plaintext: bool | None
    reachable_versions: int
    reachable_plaintext_versions: int
    plaintext_commits: list[str]
    safe_for_in_place_append_only_cutover: bool
    recommendation: str


def _blob_prefix(commit, path: str, size: int = 16) -> bytes | None:
    try:
        blob = commit.tree / path
    except KeyError:
        return None
    stream = blob.data_stream
    return stream.read(size)


def audit_repository(repo_path: Path, db_repo_path: str = DB_REPO_PATH) -> AuditResult:
    repo_path = Path(repo_path).resolve()
    repo = Repo(repo_path)

    current_path = repo_path / db_repo_path
    current_exists = current_path.is_file()
    current_plaintext: bool | None = None
    if current_exists:
        with current_path.open("rb") as handle:
            current_plaintext = handle.read(16) == SQLITE_HEADER

    findings: list[HistoryFinding] = []
    seen: set[str] = set()
    for commit in repo.iter_commits("--all"):
        sha = commit.hexsha
        if sha in seen:
            continue
        seen.add(sha)
        prefix = _blob_prefix(commit, db_repo_path)
        if prefix is None:
            continue
        findings.append(HistoryFinding(commit=sha, plaintext=prefix == SQLITE_HEADER))

    plaintext = [f.commit for f in findings if f.plaintext]
    safe_append_only = bool(current_exists) and not bool(plaintext)

    if plaintext:
        recommendation = (
            "PLAINTEXT_HISTORY_PRESENT: do not merely encrypt the current file and append a commit. "
            "Cut over to a clean encrypted-only data repository/history, revoke access to the old "
            "plaintext repository, and delete/re-clone employee working copies before SEC-01 is complete."
        )
    elif current_plaintext:
        recommendation = (
            "CURRENT_PLAINTEXT_ONLY: encrypt the authoritative artifact with the shared workspace key "
            "before production startup."
        )
    elif current_exists:
        recommendation = "NO_REACHABLE_PLAINTEXT_HISTORY_DETECTED. Validate ciphertext with the workspace key before cutover."
    else:
        recommendation = "AUTHORITATIVE_DB_MISSING: repair the data repository before startup."

    return AuditResult(
        repository=str(repo_path),
        database_path=db_repo_path,
        current_exists=current_exists,
        current_plaintext=current_plaintext,
        reachable_versions=len(findings),
        reachable_plaintext_versions=len(plaintext),
        plaintext_commits=plaintext,
        safe_for_in_place_append_only_cutover=safe_append_only,
        recommendation=recommendation,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SEC-01 authoritative database history audit.")
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Data repository path. Defaults to runtime/repository.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_path = args.repo or (get_paths().runtime_root / "repository")
    try:
        result = audit_repository(repo_path)
    except Exception as exc:
        print(f"[ERROR] Audit failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        print(f"Repository: {result.repository}")
        print(f"Current DB exists: {result.current_exists}")
        print(f"Current DB plaintext: {result.current_plaintext}")
        print(f"Reachable DB versions: {result.reachable_versions}")
        print(f"Reachable plaintext versions: {result.reachable_plaintext_versions}")
        if result.plaintext_commits:
            print("Plaintext commits:")
            for sha in result.plaintext_commits:
                print(f"  - {sha}")
        print(f"Recommendation: {result.recommendation}")

    # Exit 10 means a security cutover is required; this is not an execution error.
    if result.current_plaintext or result.reachable_plaintext_versions:
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
