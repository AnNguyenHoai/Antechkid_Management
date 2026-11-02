"""QA-S02 R3: Git connectivity uncertainty preserves committed encrypted work.

Uses synthetic SQLCipher workspace and a local disposable Git remote. Outages
are injected at remote-observation boundaries; this does not impersonate an
actual network outage or Windows packaged EXE.
"""
from types import SimpleNamespace

import pytest

from tests.test_e1b1_durable_write_recovery import (
    workspace, begin, mutate, values,  # noqa: F401
)
from centermanager.platform.write_recovery import WriteRecoveryJournal, RecoveryRequired


@pytest.mark.parametrize("remote_outcome", ["unreachable", "different-oid"])
def test_finish_remote_observation_uncertain_keeps_committed_sqlcipher_and_journal(
    workspace, remote_outcome
):
    begin(workspace)
    mutate(workspace)
    journal = workspace.journal
    journal.preserve("qa-network-pre-push")
    journal.update(status="PUBLISHING")
    before = values(journal.database)
    assert before == ["BASE", "LOCAL_UNACCEPTED"]
    existing_capture = journal.inspect()["last_capture"]

    provider = SimpleNamespace(
        get_local_main_commit=lambda: workspace.base,
        observe_remote_main_commit=(
            (lambda: None) if remote_outcome == "unreachable"
            else (lambda: "0" * 40)
        ),
    )
    with pytest.raises(RecoveryRequired, match="UNKNOWN"):
        journal.published(provider)

    # An uncertain publish is not authority to clean or overwrite the DB.
    restarted = WriteRecoveryJournal()
    document = restarted.inspect()
    assert document["status"] == "PUBLISHING"
    assert document["publication"] == "UNVERIFIED"
    assert document["last_capture"] == existing_capture
    restarted.verify_capture(existing_capture)
    with pytest.raises(RecoveryRequired):
        restarted.assert_replaceable()
    assert values(restarted.database) == before


def test_finish_remote_observation_exception_keeps_recoverable_sqlcipher(workspace):
    begin(workspace)
    mutate(workspace)
    journal = workspace.journal
    journal.preserve("qa-network-before-exception")
    journal.update(status="PUBLISHING")

    def disconnected():
        raise OSError("QA injected Git remote unavailable")

    provider = SimpleNamespace(
        get_local_main_commit=lambda: workspace.base,
        observe_remote_main_commit=disconnected,
    )
    with pytest.raises(OSError, match="Git remote unavailable"):
        journal.published(provider)

    restarted = WriteRecoveryJournal()
    assert restarted.inspect()["status"] == "PUBLISHING"
    assert restarted.inspect()["publication"] == "UNVERIFIED"
    with pytest.raises(RecoveryRequired):
        restarted.assert_replaceable()
    assert values(restarted.database) == ["BASE", "LOCAL_UNACCEPTED"]
