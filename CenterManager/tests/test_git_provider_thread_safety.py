import threading
import time
from pathlib import Path
from unittest.mock import patch

from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


def test_git_commands_are_serialized_per_provider(tmp_path):
    provider = GitSynchronizationProvider(
        repo_path=Path(tmp_path) / "repository",
        repository_url=str(Path(tmp_path) / "remote.git"),
    )

    active = 0
    max_active = 0
    state_lock = threading.Lock()
    first_started = threading.Event()
    release_first = threading.Event()

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            if active == 1:
                first_started.set()
                assert release_first.wait(2), "first Git command was not released"
            return Result()
        finally:
            with state_lock:
                active -= 1

    def run_command():
        provider._run_git_command(["status"])

    with patch(
        "centermanager.platform.synchronization.git_synchronization_provider.subprocess.run",
        side_effect=fake_run,
    ):
        thread_a = threading.Thread(target=run_command)
        thread_b = threading.Thread(target=run_command)
        thread_a.start()
        assert first_started.wait(1), "first Git command did not start"
        thread_b.start()
        time.sleep(0.05)
        assert max_active == 1, "Git commands for one repository ran concurrently"
        release_first.set()
        thread_a.join(2)
        thread_b.join(2)

    assert not thread_a.is_alive()
    assert not thread_b.is_alive()
    assert max_active == 1
