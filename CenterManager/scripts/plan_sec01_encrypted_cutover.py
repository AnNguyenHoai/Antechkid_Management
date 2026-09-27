# -*- coding: utf-8 -*-
"""Read-only SEC-01 encrypted-only cutover planner.

This command does not modify the data repository, refs, keys, or remote state. It
combines the authoritative database history audit with local repository topology
and key-enrollment readiness so an administrator can choose a safe cutover plan.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Direct execution from CenterManager/scripts must be able to import both the
# src-layout package and sibling maintenance scripts without PYTHONPATH setup.
CENTERMANAGER_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CENTERMANAGER_ROOT / "src"
SCRIPTS_ROOT = CENTERMANAGER_ROOT / "scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from git import Repo

from centermanager.core.paths import get_paths
from centermanager.database.encryption import DatabaseKeyStore
from centermanager.security.protected_storage import get_protected_storage_layout
from audit_authoritative_db_history import audit_repository


@dataclass(frozen=True)
class CutoverPlan:
    repository: str
    active_branch: str | None
    working_tree_clean: bool
    has_origin: bool
    reachable_plaintext_versions: int
    plaintext_refs: dict[str, int]
    legacy_workspace_key_present: bool
    protected_service_key_present: bool
    destructive_cutover_required: bool
    ready_to_execute_cutover: bool
    blockers: list[str]
    next_action: str


def _plaintext_ref_map(repo: Repo, plaintext_commits: set[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    if not plaintext_commits:
        return result
    for ref in repo.references:
        try:
            reachable = {commit.hexsha for commit in repo.iter_commits(ref.path)}
        except Exception:
            continue
        count = len(reachable.intersection(plaintext_commits))
        if count:
            result[ref.path] = count
    return dict(sorted(result.items()))


def build_plan(repo_path: Path) -> CutoverPlan:
    repo_path = Path(repo_path).resolve()
    repo = Repo(repo_path)
    audit = audit_repository(repo_path)

    try:
        active_branch = repo.active_branch.name
    except Exception:
        active_branch = None

    has_origin = any(remote.name == "origin" for remote in repo.remotes)
    plaintext_refs = _plaintext_ref_map(repo, set(audit.plaintext_commits))

    legacy_key_present = DatabaseKeyStore().bundle_path.is_file()
    protected_key_present = get_protected_storage_layout().key_bundle_path.is_file()

    dirty = repo.is_dirty(untracked_files=True)
    blockers: list[str] = []
    if dirty:
        blockers.append("DATA_REPOSITORY_WORKTREE_DIRTY")
    if not has_origin:
        blockers.append("ORIGIN_REMOTE_MISSING")
    if not audit.current_exists:
        blockers.append("AUTHORITATIVE_DATABASE_MISSING")
    if audit.reachable_plaintext_versions:
        blockers.append("PLAINTEXT_GIT_HISTORY_PRESENT")
    if not legacy_key_present:
        blockers.append("WORKSPACE_KEY_NOT_PROVISIONED")
    if not protected_key_present:
        blockers.append("SERVICE_KEY_NOT_PROVISIONED")

    destructive = bool(audit.reachable_plaintext_versions)
    ready = not blockers

    if destructive:
        next_action = (
            "Create a maintenance-window encrypted-only cutover: preserve the current "
            "business snapshot, provision one shared workspace key, encrypt and validate "
            "the DB, publish a new history root, remove every remote ref that still reaches "
            "plaintext, and force all workstations to delete/re-clone the data repository."
        )
    elif not legacy_key_present or not protected_key_present:
        next_action = (
            "Complete shared workspace-key enrollment and service-key provisioning before "
            "allowing production startup."
        )
    else:
        next_action = "No plaintext history detected; validate encrypted artifact/key and proceed with cutover UAT."

    return CutoverPlan(
        repository=str(repo_path),
        active_branch=active_branch,
        working_tree_clean=not dirty,
        has_origin=has_origin,
        reachable_plaintext_versions=audit.reachable_plaintext_versions,
        plaintext_refs=plaintext_refs,
        legacy_workspace_key_present=legacy_key_present,
        protected_service_key_present=protected_key_present,
        destructive_cutover_required=destructive,
        ready_to_execute_cutover=ready,
        blockers=blockers,
        next_action=next_action,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only SEC-01 encrypted-only cutover planner.")
    parser.add_argument("--repo", type=Path, default=None, help="Data repo path; defaults to runtime/repository.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_path = args.repo or (get_paths().runtime_root / "repository")
    try:
        plan = build_plan(repo_path)
    except Exception as exc:
        print(f"[ERROR] Cutover planning failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
    else:
        print(f"Repository: {plan.repository}")
        print(f"Active branch: {plan.active_branch}")
        print(f"Working tree clean: {plan.working_tree_clean}")
        print(f"Origin configured: {plan.has_origin}")
        print(f"Reachable plaintext DB versions: {plan.reachable_plaintext_versions}")
        print("Plaintext-reaching refs:")
        if plan.plaintext_refs:
            for ref, count in plan.plaintext_refs.items():
                print(f"  - {ref}: {count} plaintext DB version(s)")
        else:
            print("  - none")
        print(f"Legacy workspace key present: {plan.legacy_workspace_key_present}")
        print(f"Protected service key present: {plan.protected_service_key_present}")
        print(f"Destructive cutover required: {plan.destructive_cutover_required}")
        print(f"Ready to execute cutover: {plan.ready_to_execute_cutover}")
        if plan.blockers:
            print("Blockers:")
            for blocker in plan.blockers:
                print(f"  - {blocker}")
        print(f"Next action: {plan.next_action}")

    return 10 if plan.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
