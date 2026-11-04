# -*- coding: utf-8 -*-
"""BUG-006: publish must mirror the canonical runtime/Attachment tree and
never clear the repository mirror when the runtime tree is missing."""
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider  # noqa: E402


def _provider(runtime: Path) -> GitSynchronizationProvider:
    provider = GitSynchronizationProvider.__new__(GitSynchronizationProvider)
    provider._repo_path = runtime / "repository"
    provider._repo_path.mkdir(parents=True, exist_ok=True)
    return provider


def test_publish_mirrors_canonical_singular_runtime_tree(tmp_path):
    runtime = tmp_path / "runtime"
    source = runtime / "Attachment" / "Employees" / "EMP-00001" / "CV" / "cv.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"cv")
    provider = _provider(runtime)

    provider._sync_employee_attachments_to_repository()

    mirrored = runtime / "repository" / "Attachments" / "Employees" / "EMP-00001" / "CV" / "cv.pdf"
    assert mirrored.read_bytes() == b"cv"


def test_canonical_tree_wins_over_stale_legacy_plural_tree(tmp_path):
    runtime = tmp_path / "runtime"
    canonical = runtime / "Attachment" / "Employees" / "EMP-1" / "new.pdf"
    legacy = runtime / "Attachments" / "Employees" / "EMP-1" / "stale.pdf"
    for path in (canonical, legacy):
        path.parent.mkdir(parents=True)
        path.write_bytes(path.name.encode())
    provider = _provider(runtime)

    provider._sync_employee_attachments_to_repository()

    repo_employee = runtime / "repository" / "Attachments" / "Employees" / "EMP-1"
    assert (repo_employee / "new.pdf").exists()
    assert not (repo_employee / "stale.pdf").exists()


def test_missing_runtime_tree_preserves_repository_mirror(tmp_path):
    runtime = tmp_path / "runtime"
    provider = _provider(runtime)
    existing = runtime / "repository" / "Attachments" / "Employees" / "EMP-1" / "cv.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"from-main")

    provider._sync_employee_attachments_to_repository()

    assert existing.read_bytes() == b"from-main"


def test_deletion_inside_existing_runtime_tree_still_propagates(tmp_path):
    runtime = tmp_path / "runtime"
    source = runtime / "Attachment" / "Employees" / "EMP-1" / "cv.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"cv")
    provider = _provider(runtime)
    provider._sync_employee_attachments_to_repository()

    source.unlink()
    provider._sync_employee_attachments_to_repository()

    assert not (runtime / "repository" / "Attachments" / "Employees" / "EMP-1" / "cv.pdf").exists()
