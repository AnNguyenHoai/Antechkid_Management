# WRITE Start / Finish Performance Trace (Step A)

**Scope:** diagnostics only. No changes to Git MAIN CAS, queue/lock ownership, WRITE lease, SQLCipher DB, recovery journal acceptance, save, publish or retry logic.

## How to collect a useful log

1. Build and install the Windows EXE containing this PR (use a separate UAT runtime; do not alter production data or recovery folders to make a test pass).
2. Launch, sign in, select **Start Editing**, and either finish a valid edit or stop on the actual failure. If editing succeeds, use **Finish Editing**.
3. Keep CenterManager's existing log, searching for `PERF write_trace_begin`, `PERF write_phase`, `PERF write_trace op=`, and existing `PERF start_edit`/`PERF finish_edit`.
4. Run at least 10–20 completed cycles under representative conditions to estimate median/P90 and network variance. Failed operations are recorded as `not_completed` and must be analyzed separately.

## Example output schema (illustrative, not measured)

```text
PERF write_trace_begin op=start id=abc123
PERF write_phase op=start id=abc123 phase=request_write ms=12000.0
PERF write_trace op=start id=abc123 total_ms=18400.0 result=success git_calls=15 git_wait_ms=100.0 phases_ms=handoff:3800.0,recovery_begin:2100.0,request_write:12000.0,snapshot:50.0 git_calls_ms=ls-remote:8/8000.0,push:2/2500.0,show:5/800.0 git_failures=none
```

All Git counters are scoped to the current synchronous transaction thread. Poller/background operations are not attributed to the user's Start/Finish action. `git_calls_ms` reports total subprocess run time by command category, including repeated commands; it is not the total transaction time because some local work and lock waits are outside Git. The existing `PERF git` debug lines show individual command wait/run times. The new INFO summary works without enabling additional sensitive Git debug lines.

Logged only: operation kind, randomized short correlation ID, stable phase name, durations, safe Git command type, counts, success/failure. Git arguments, repository URL, token, student data, filenames, SQL text, and exception text are excluded.

## Interpretation

- **Start:** `request_write` (queue/lock network), `handoff` (fetch/DB install/migration/UI), `recovery_begin`, `snapshot`.
- **Finish:** `authority`, `local_save`, `pending_version`, `materialize`, and `publish_and_release` (with nested `capture_before_publish`, `git_publish`, `recovery_published`, `reports`, `post_publish_validation`, `release_lock`).
- Nested phases are **inclusive**, so do not add `publish_and_release` and its child phases together.
- For a new performance baseline, wait until the separate recovery fix PR #590 has passed UAT. This tracing PR should be independently reviewable and rebased against the latest `main_repos` if #590 merges first.
- Do not infer whether remote MAIN was published solely from `result=not_completed`; verify repository state and journal status.

## Acceptance criteria

1. Startup, start, finish and failure paths behave identically with tracing enabled.
2. Logging exceptions do not expose secrets and there are no changes to functional authorization.
3. Three Windows CI shards PASS.
4. Confirm `operation_id` groups phases and Git categories correctly; test real Windows EXE for both successful and failed editing.
