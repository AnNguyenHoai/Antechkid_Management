"""Regression: origin reconciliation must preserve clone's preclone_capture contract."""
from pathlib import Path

import pytest

from centermanager.platform.synchronization import git_origin_reconciliation as origin


class FakeProvider:
    def __init__(self, repo_path):
        self._repo_path = repo_path
        self._repo = None
        self._repository_url = "https://github.com/example/management.git"
        self.calls = []

    def clone(self, progress_callback=None, *, preclone_capture=None):
        self.calls.append(("clone", progress_callback, preclone_capture))
        return True

    def connect(self):
        return True


def test_new_clone_forwards_preclone_capture(tmp_path):
    provider_type = type("CloneProvider", (FakeProvider,), {})
    origin.install_origin_reconciliation(provider_type)
    provider = provider_type(tmp_path / "repository")
    callback = lambda *args: None
    capture = tmp_path / "capture"

    assert provider.clone(progress_callback=callback, preclone_capture=capture)
    assert provider.calls == [("clone", callback, capture)]


def test_existing_repo_rejects_preclone_capture(tmp_path):
    from centermanager.platform.write_recovery import RecoveryRequired

    provider_type = type("ExistingProvider", (FakeProvider,), {})
    origin.install_origin_reconciliation(provider_type)
    repo = tmp_path / "repository"
    (repo / ".git").mkdir(parents=True)
    provider = provider_type(repo)
    provider._repo = object()

    with pytest.raises(RecoveryRequired, match="Preclone capture cannot authorize"):
        provider.clone(preclone_capture=tmp_path / "capture")

    assert provider.calls == []
