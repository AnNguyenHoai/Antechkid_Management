# E0 — WRITE Recovery & Emergency: source audit

Date: 2026-10-31. Status: **CURRENT — founder architecture review required**.
Audited base: `main_repos` at `d76c61c15096089311bf7a688c6ae45f37cd5663`.
Baseline Windows workflow: [Pytest Suite #778, success](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41177666628).

Scope: all six Markdown files in the supplied WRITE Recovery task package,
including `05_GPT_WORK_EXECUTION_PROMPT.md`. This PR adds documentation and
characterization tests only. No runtime, permissions, timer, schema, production
database, production lock, or private data repository changes.

## Decision

**Immediate unilateral Admin revocation is BLOCKED on the present protocol.**
Lock CAS protects a lock ref, and MAIN CAS protects a data ref. Neither proves
that the sender still owns WRITE at the instant MAIN changes. Local generation
checks do not repair that separation. Do not expose `force_release()` in UI.

The [fencing contract](WRITE_AUTHORITY_FENCING_CONTRACT.md) specifies an
enforceable coordinator design and a conditional Git-only alternative. Neither
is implemented or approved by this PR. Natural expiry recovery is already
attempted, but is not an end-to-end stale-publisher safety proof.

## Evidence and confidence

Source links below are relative to `src/centermanager/` and line numbers refer
to the audited base. Tests are in `tests/test_e0_write_recovery_audit.py`.
`CURRENT` means read or executed against this base; `INFERRED` means a scheduling
consequence, not an observed Windows incident. No logs/DB from Việt's machine
were inspected. The exact historical crash time and whether its worker survived
are unknown; do not claim forensic confirmation of that process' failure mode.

Recent merged collaboration PRs reviewed: [#507 shared queue](https://github.com/AnNguyenHoai/Antechkid_Management/pull/507),
[#508 acknowledgement](https://github.com/AnNguyenHoai/Antechkid_Management/pull/508),
[#509 health/time bounds](https://github.com/AnNguyenHoai/Antechkid_Management/pull/509).
Their improvements remain present; none couples lock and MAIN publication.

## Actual runtime composition and timings

| Boundary | Source evidence | CURRENT behavior |
|---|---|---|
| Runtime wiring | [app.py](../../src/centermanager/app.py), `main`, around 190–235 | Instantiates CollaborationManager without timeout overrides; poller normal 10s, WAITING 3s, initial backoff 5s, max 120s; RuntimeSyncService background interval 30s |
| Provider lease | [git_synchronization_provider.py](../../src/centermanager/platform/synchronization/git_synchronization_provider.py):73, `__init__`, `renew_lock` | TTL 60s, remote JSON expiry written from owner `datetime.now()`; revision increments on renewal |
| Renewal worker | [poller.py](../../src/centermanager/platform/collaboration/poller.py), `_on_thread_started`, `_renew_active_lease` | QTimer in poller QThread every 20s; WAITING request refresh uses same timer |
| Renewal threshold | [collaboration_manager.py](../../src/centermanager/platform/collaboration/collaboration_manager.py):811, `renew_remote_lease` | Skip if remaining > `lock_timeout/2` (default 30s); ideal zero-latency schedule renews at 40s, not every 20s |
| User idle | [main_window.py](../../src/centermanager/ui/main_window.py):74, `_on_editing_idle_timeout`, `_record_user_activity` | 30 minutes, monotonic elapsed user activity; Qt GUI timer; distinct from crash and lease expiry |
| Local presence | [heartbeat.py](../../src/centermanager/platform/collaboration/heartbeat.py), `HeartbeatManager` | Python thread every 10s, local files; presence timeout 30s; no remote WRITE authority |
| Reclaim grace | [git_clock_skew_guard.py](../../src/centermanager/platform/synchronization/git_clock_skew_guard.py), `is_remote_write_lock_reclaimable` | Different session waits until expiry +600s; same nonempty session can reacquire immediately after expiry |
| Queue liveness | Provider `__init__`, `_filter_live_queue_requests` | TTL 120s +60s skew protection; remove when age >180s; priority then CAS-assigned sequence; refresh preserves sequence |
| Git timeout | Provider `__init__`, collaboration operations | 15s per bounded remote collaboration command, not a bound on the whole transaction; commands queue behind per-provider RLock |

The legacy `platform/context/configuration_context.py` and
`platform/runtime/context/runtime_configuration.py` read a configurable
`lock_timeout`; the active `app.py` constructor above uses defaults. Provider
TTL is independently fixed to 60s; changing manager timeout alone would not
change the provider TTL. A deployed binary/config/version still needs Windows
verification; these are source defaults, not a measurement of Việt's settings.

Import layers matter: synchronization `__init__.py` installs output/credential,
clock-skew, command serialization and acquisition-diagnostic wrappers. The
effective `acquire_lock` comes from `lock_acquisition_diagnostics.py`, not just
the class body. Collaboration `__init__.py` installs `false_waiting_guard.py`
and `finishing_authority_compat.py`. Services installs `write_transaction_guard.py`.
Public RuntimeSyncService is `authoritative_runtime_sync_service.py`, extending
`write_handoff_runtime_sync_service.py`, then the base service. Auditing only the
base implementation produces incorrect conclusions about DB installation.

## Findings

| ID | Severity | Evidence / reproduction | Consequence |
|---|---|---|---|
| E0-01 | P0 | `_push_only` fences MAIN OID only; `enter_finishing` checks session/generation earlier. `test_e0_data_cas_accepts_old_writer_after_lock_handoff` executes the real final push after replacing the lock | A paused former publisher can update MAIN while another session owns WRITE if MAIN has not changed. This is a final-boundary repro, not a complete signed-finance/UI exploit test |
| E0-02 | P0 | Manager `_build_lock_data` initializes remote generation to 0 on each grant; provider increments `lease_revision`, not durable ownership epoch | Different owners can have the same generation. MAIN OID and signed DB identity are not ownership epoch fences |
| E0-03 | P0 | `false_waiting_guard.guarded_request_write` accepts WAITING only with a live lease, ignoring protected grace. Transaction `start_editing` ERROR path resets IDLE without cancelling the queued request. Reproduced by `test_e0_start_during_grace_returns_error_but_leaves_live_queue_entry` | Exact warning is surfaced; request may remain renewed invisibly. Poller later grants, but MainWindow and transaction ignore grant in IDLE. Apparent failure of automatic recovery can persist after remote takeover |
| E0-04 | P0 | Provider `release_lock(owner)` checks username and newest OID, not session/generation. Manager shutdown/release and recovery release call it by username. `test_e0_same_username_old_session_can_release_new_session` | Old same-account process can delete a successor's lease; CAS does not help if it deliberately reads the successor's current OID |
| E0-05 | P0 | `WriteGuard.can_write` uses cached `is_writing`; `ensure_write` only adds suspended flag. Services such as Income use `require_permission`, which checks business capability, not lease. Engine/session/BaseRepository have no distributed commit fence. SQLCipher repro confirms a local commit remains possible | Disabled UI and FINISHING checks do not guard every local mutation. No guarantee of two locally writable projections after revocation; universal local deny is absent |
| E0-06 | P1 | Poller QThread renewal never consults GUI progress; renewal-failure signal and idle timer are consumed by GUI. `test_e0_background_renewal_has_no_ui_progress_gate` | UI-only freeze can leave renewing owner indefinitely. Full process kill stops renewal. Distinguish these cases before promising a recovery interval |
| E0-07 | P1 | Provider `_remote_lock_oid` uses check=False; absent ref, connectivity error and unreadable JSON may collapse to empty/unlocked. `test_e0_unreadable_lock_is_reported_as_absent` | Cannot safely use this diagnostic as an Admin authority decision. Some higher checks call strict `health()`, but not every status/acquire/release path |
| E0-08 | P1 | Manager `request_write` does not check another pending queue head before direct acquisition when lock free/expired. `test_e0_new_request_can_overtake_existing_queue_head` | Queued handoff checks head, but a newcomer can bypass FIFO between release and head poll |
| E0-09 | P1 | `enter_finishing` writes finishing fields only to local RuntimeLock. `_sync_local_lock` copies remote fields over local; renewal preserves only fields already in remote JSON | Local 120s FINISHING deadline is not a remotely acquired exclusion extension; do not treat it as fencing against Admin or reclaim |
| E0-10 | P1 | `AuditService.record` writes to caller's local DB; force-release has log messages but no dedicated permission, targeted request, durable remote receipt or immutable audit chain | Existing local logs cannot establish secure Admin authorization or durable revocation outcome |

Additional CURRENT behavior: `_try_handoff_waiting_request` tests strict lease
staleness, then asks `grant_existing_waiting_request`; that method rechecks queue
head, acquires with provider CAS, runs handoff sync, and consumes queue entry.
Provider correctly refuses acquisition throughout grace. Head observation and
lock acquisition are still separate refs; request cancellation/expiry can race.
Queue-cancel acknowledgement failure rolls back the grant; release failure in
that rollback can leave the remote lease while local flags are cleared. Normal
`release_write` preserves WRITE projection on failed remote release; shutdown
`_release_write_internal` clears it regardless of acknowledgement.

Lock acquisition of an absent ref uses normal push of a new orphan lock commit;
existing-ref transitions use exact-OID force-with-lease. Renewal validates owner,
session and unexpired lease before CAS, then verifies session. Normal deletion
uses exact-OID CAS and does not force-delete on CAS loss. These protect competing
ref updates, not the semantic right of a same-username caller or a data publisher.

## Local data and publication boundary inventory

See [WRITE_MUTATION_BOUNDARY_INVENTORY.md](WRITE_MUTATION_BOUNDARY_INVENTORY.md)
for the static per-file persistence inventory and its limits. The shared
boundaries that must receive fencing are:

1. Business services → repositories → SQLAlchemy flush/commit, plus bulk/raw
   SQL and direct SQLCipher/SQLite connections. Permission decorators are
   orthogonal. Include finance, attendance, enrollment, users/roles, password
   changes, audit/timeline, import/reset, initialization and migrations; assign
   explicit bootstrap/maintenance permits rather than bypassing the future gate.
2. WRITE entry: direct `request_write`, queued `grant_existing_waiting_request`,
   stale transaction recovery, backup `RecoveryAuthority`, standalone legacy
   workflow. No common durable remote epoch exists across these paths today.
3. Runtime→repository: `WriteTransactionManager._publish_database_and_manifest`,
   `materialize_runtime_database_to_repository`, `wal_safety` checkpoint and
   snapshot; validate/sign database identity and stage DB+identity+manifest.
   WAL/maintenance fences protect file consistency within one process, not
   distributed authority.
4. Publication: transaction `_do_publish` → public RuntimeSyncService inherited
   `publish_only` → SynchronizationManager `publish_only` → provider
   `publish_only` → `_push_only`. Also SynchronizationManager `begin_sync` with
   publish message, provider legacy `publish`/`_push`, legacy
   PublicationTransaction/PublishWorkflow, `AuthoritativeRecoveryPublisher`,
   backup/admin password-change callers. Some compatibility callers supply no
   captured base and provider captures current MAIN immediately before staging.
   Recovery publisher checks authority before AND after, but post-validation
   cannot undo an already accepted stale push.
5. Repository→runtime: public authoritative handoff resets/fetches exact MAIN,
   validates identity, quiesces handles, replaces DB+sidecars under maintenance,
   verifies bytes, refreshes sessions/UI, reobserves MAIN. This is a useful
   consistency barrier. It has no durable unpublished-work quarantine gate.
   Returning dirty writers must not enter it before preservation succeeds.

All `.force_release()` remote calls found: provider definition and manager
`_force_release_lock` call-through. No call sites of that manager helper were
found in `src`. Local `_force_release()` calls in RuntimeLock/LockManager,
collaboration synchronization/cleanup, and RecoveryAuthority only alter local
files; do not confuse these with remote force deletion. The remote provider
method has neither role check nor session targeting and uses
`_delete_lock_branch(force=True)`. The magic username `force_release` also
bypasses normal owner comparison in `release_lock`.

## Time semantics and observed recovery baseline

Naive local ISO timestamps are used across machines. Timezone/DST mismatches,
clock rollback and sleep/wake are not normalized. Aware vs naive timestamp
comparison can fail; parse errors are often treated as stale. Missing/malformed
expiry is reclaimable under the current skew policy. Git commit author and
committer timestamps are supplied by clients and are not trusted server time.
600s is a bounded skew accommodation, not proof against arbitrary skew or a
still-running paused publisher. Keep the current grace unchanged in E0/E1.

Deterministic source-default baseline, measured by real temporary bare Git and
injected time (no 11-minute sleep): last successful renewal t=0, expiry t=60,
grace ends t=660. Surviving waiter refreshes every 20s. Poll phases 0/1/2 seconds
on a 3s cadence grant at 660/661/662. Crash times 0/19/39 therefore yield
**660/642/623 seconds** to remote grant. These samples do not bound a Windows
deployment; in ideal steady state the 40s renewal spacing implies roughly
620–660s residual wait, plus <3s healthy poll delay and Git/handoff execution.
Network errors, 120s backoff, blocked GUI handoff barrier, queued Git commands,
clock offset and expired queue requests make latency unbounded. If UI freezes
while renewals continue, there is no expiry-based recovery interval at all.

## Verification and remaining gates

The E0 tests characterize current faults with passing assertions; they do not
approve those faults or implement fencing. The atomic-push experiment proves
only local bare-Git rejection of a stale two-ref transaction, not production
transport support, legacy exclusion, Admin authentication or data preservation.
Focused/broader test results and exact branch Windows CI evidence are reported
in the PR. Baseline production behavior is unchanged.

Windows two-machine UAT U01–U12 remains **NOT RUN**: use the supplied release
matrix, synthetic encrypted DB, isolated remote, accounts/build IDs, sleep/wake,
UI freeze, kill, network interruption and both Finish/revoke orderings. Preserve
all failed workspaces. No E1/E2 logic is authorized by completion of this audit.
