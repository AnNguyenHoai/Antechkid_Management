#!/usr/bin/env python3
"""RV-02 Windows microbenchmark: sync mirror vs async Save-path enqueue.

Measure only the recovery mirror component; do NOT present these timings as
end-to-end CenterManager Save, Start Editing, or EXE startup metrics.
This tool uses an ephemeral test-only AES key and temp folders, not live data.
"""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from centermanager.database.encryption import DatabaseKeyStore
from centermanager.platform.recovery_change_mirror import mirror_committed_payload
from centermanager.platform.recovery_mirror_worker import _MirrorWorker


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * p)))
    return ordered[index]


def payload(event_id: str) -> bytes:
    return json.dumps({
        "format": 1, "event_id": event_id, "operation_id": event_id,
        "write_session_id": "benchmark-session",
        "base_main_oid": "a" * 40,
        "occurred_at_utc": "2026-11-05T00:00:00",
        "actor_id": "1",
        "module": "student", "action": "UPDATE",
        "entity_type": "Student", "entity_id": "1234",
        "summary_code": "student_UPDATE",
        "summary_args_json": '{"student_id":"1234"}',
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")


def run(samples: int) -> dict:
    key = bytes(range(32))
    sync: list[float] = []
    queued: list[float] = []
    with tempfile.TemporaryDirectory(prefix="rv02-bench-") as tmp:
        root = Path(tmp)
        synchronous = root / "sync"
        asynchronous = root / "async"
        worker = _MirrorWorker(max_pending=max(512, samples + 1))
        with patch.object(DatabaseKeyStore, "load", lambda self: key):
            for _ in range(samples):
                data = payload(str(uuid.uuid4()))
                begin = time.perf_counter_ns()
                mirror_committed_payload(data, recovery_root=synchronous, encryption_key=key)
                sync.append((time.perf_counter_ns() - begin) / 1_000_000)
            begin_drain = time.perf_counter_ns()
            for _ in range(samples):
                data = payload(str(uuid.uuid4()))
                begin = time.perf_counter_ns()
                if not worker.enqueue(asynchronous, data):
                    raise RuntimeError("Microbenchmark mirror queue overflowed")
                queued.append((time.perf_counter_ns() - begin) / 1_000_000)
            elapsed_submit_ms = (time.perf_counter_ns() - begin_drain) / 1_000_000
            if not worker.drain(timeout_seconds=30):
                raise RuntimeError("Microbenchmark mirror worker failed/timed out")
            elapsed_through_drain_ms = (time.perf_counter_ns() - begin_drain) / 1_000_000
        if len(list(asynchronous.rglob("*.enc"))) != samples:
            raise RuntimeError("Microbenchmark missing encrypted mirror segments")
    return {
        "label": "RV02 component microbenchmark: synthetic event mirror only",
        "samples": samples,
        "sync_mirror_call_ms": {
            "median": round(statistics.median(sync), 3),
            "p95": round(percentile(sync, 0.95), 3),
        },
        "async_save_enqueue_ms": {
            "median": round(statistics.median(queued), 3),
            "p95": round(percentile(queued, 0.95), 3),
        },
        "async_batch_submit_ms": round(elapsed_submit_ms, 3),
        "async_all_mirrors_fsynced_ms": round(elapsed_through_drain_ms, 3),
        "note": (
            "Does not include SQLCipher commit, outbox INSERT/SELECT, Qt UI, "
            "Windows EXE cold startup, Git MAIN, backup copy, or lock contention."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--json", type=Path)
    options = parser.parse_args()
    if not 1 <= options.samples <= 1000:
        parser.error("--samples must be between 1 and 1000")
    result = run(options.samples)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if options.json:
        options.json.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
