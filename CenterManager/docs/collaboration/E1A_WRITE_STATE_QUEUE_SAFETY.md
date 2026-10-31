# E1A — WRITE state, queue and session release safety

Status: CURRENT — CI and human review gates are recorded on the PR.
Base: `main_repos` `259e744f09d621074a79e492767d6310dd11609e`, including merged E0 #523.
Task contract: the founder's E1A-01 through E1A-04 request. No Issue number was supplied.

## Scope and unchanged policies

This implementation repairs E0-03 (grace/hidden queue), E0-04 (same-username
release), E0-07 (unknown lock masquerading as absent), and E0-08 (newcomer FIFO
bypass). It does not implement Admin revoke, remote process termination, a
durable ownership epoch or end-to-end data publication fencing. No production
database, production remote or production lock is used in tests; no schema
migration is introduced.

Provider TTL remains 60s, clock-skew grace 600s, renewal timer 20s with its
existing half-TTL threshold, waiting poll 3s and idle policy 30 minutes. Invalid
lease data now fails closed; this is a validation change, not a shorter grace.

## Root causes and changed paths

Paths are relative to `src/centermanager/` unless stated otherwise.

| Path | Root cause / resulting change |
|---|---|
| `platform/synchronization/lock_observation.py` | New `RemoteLockState` vocabulary: ACTIVE, GRACE, RECLAIMABLE, ABSENT, UNKNOWN; validate identity/expiry/revision before time classification |
| `platform/synchronization/git_synchronization_provider.py` | Ref reads previously swallowed network/read/JSON failures. Now only a successful empty ref read proves absence; status preserves UNKNOWN. Release uses locally acquired session/revision/OID capabilities; queue head consumption is CAS-based; cancellation always advances queue ref |
| `platform/synchronization/lock_acquisition_diagnostics.py` | Validate observed/requested authority before preparing a grant, retain sanitized operational failure versus contention classification, remember exact candidate capability and reconcile a lost push response |
| `platform/synchronization/git_clock_skew_guard.py` | Missing/malformed/uncomparable expiry cannot authorize reclaim; valid expiry retains the 600s rule and same-session rule |
| `platform/synchronization/git_provider_safety.py`, `__init__.py` | Serialize complete acquire/renew/release operations per provider so capability metadata and its Git operation stay coherent; existing per-command Git mutex remains |
| `platform/collaboration/collaboration_manager.py` | One remote Start Editing queue path; retain request intent before mutation, verified cancellation, priority/FIFO rechecks, provisional lease cleanup, session-targeted release and precise unknown diagnostics |
| `platform/collaboration/false_waiting_guard.py`, `__init__.py` | Former lease-only wrapper incorrectly converted valid grace WAITING to ERROR. Canonical manager now owns arbitration; deprecated installer is a no-op for import compatibility |
| `platform/collaboration/poller.py` | UNKNOWN observations cannot trigger handoff or be emitted as a successful authoritative snapshot; timers/cadence unchanged |
| `services/write_transaction.py` | WAITING validates visible request intent, not a live competing lease. Failed cancel/release cannot reset transaction or remove its snapshot |
| `ui/main_window.py` | Project grace/unknown/pending acknowledgement clearly; do not clear WAITING from an uncertain cancellation; reconcile a deferred grant by exact request through WAITING→GRANTING→EDITING |
| `platform/sync/runtime_sync_service.py` | Background runtime replacement also defers during a provisional lease/handoff, including the interval after queue consumption and before final WRITE projection |
| `platform/backup/recovery_authority.py` | Release the captured recovery principal/session, never a newly initialized session; failed release retains its capability for retry and reports uncertainty |

## Before / after transitions

| Trigger | Before E1A | After E1A |
|---|---|---|
| Start during grace | Enqueue → wrapper ERROR → transaction IDLE, remote request still live | ACQUIRING → visible WAITING/GRACE; same request remains renewed |
| Grace ends, head survives | Remote WRITE could be granted while transaction IDLE ignored it | Queue head + lock CAS + data/UI handoff + queue consume CAS + authority verification → authorized GRANTING → EDITING |
| Request cannot be enqueued, absence/cancel barrier confirmed | ERROR could still leave an unobserved request | ERROR/IDLE only after request absence and the attempted request's cancellation barrier are acknowledged |
| Enqueue response or queue verification lost | Ambiguous ERROR/hidden request | WAITING/UNKNOWN with explicit message, no WRITE, retain exact request intent for observation/cancel |
| Explicit cancel response/read-back lost | Could declare completion from absence or lose intent | Stay WAITING; remember cancellation intent, prevent grant, retry on existing refresh/explicit Cancel |
| Confirmed cancel | Remove request | CAS cancellation barrier + verified absence → IDLE; earlier in-flight enqueue candidates cannot cross that barrier |
| Same username, old session releases successor | Latest OID + username authorized deletion | Reject unless remote identity/revision/OID matches a capability acquired/renewed by this provider for the caller's exact session |
| New equal-priority requester when lock free | Direct acquire could bypass pending head | Join canonical queue; priority DESC then sequence/FIFO; head rechecked before/after lock CAS and inside consume CAS |
| Lock read/JSON/expiry invalid | Often reported unlocked/reclaimable | UNKNOWN; no acquisition, release success claim, or automatic grant |
| Unsuccessful queued handoff cleanup | Could clear local state after failed release | Provisional ownership remains cleanup-pending; never advertise WRITE, never release another session, block competing grants while remote lease exists |

Higher-priority requests retain their approved priority. FIFO applies among
equal-priority live requests; this does not turn the existing priority queue
into unconditional arrival order. Local/standalone mode also retains its queue
head rather than re-enqueuing old requests with old FIFO timestamps.

## Release capability and acknowledgement rules

Release callers in production are CollaborationManager's normal Finish/cancel,
shutdown and provisional-grant rollback, plus RecoveryAuthority. All pass the
runtime/captured session explicitly. The provider checks caller owner, session,
known lease revision and exact OID, then performs only expected-OID CAS deletion
and verifies authoritative absence. A changed session or unknown ref never
becomes a successful release. The magic `force_release` owner has no bypass.

For compatibility, low-level callers omitting the session parameter still need
a capability captured by that provider instance; an unbound username cannot
delete anything. The known current/previous endpoints of an uncertain renewal
are retained: either endpoint can be identified exactly after reconnection.
An explicitly supplied stale OID cannot be silently replaced by the newer one.
An already completed release can be acknowledged again only after verified
absence; a successor remains protected. No arbitrary latest-OID adoption is used.

The dormant manager force-release helper now refuses remote mode. The existing
provider force-release primitive is not exposed in UI or used by these flows.
Historical low-level tests use only isolated remotes; production is untouched.

Queue cancellation writes a fresh queue commit even when the target is absent.
Under the process-local request/cancel serialization, all prior uncertain enqueue
candidates were prepared against earlier queue OIDs. A later expected-OID push
or orphan branch creation from those candidates is rejected after the cancel
barrier. A failed barrier acknowledgement remains pending even if an ordinary
queue read happens to show no request. This is not a server-side idempotent Admin
command protocol and is not a substitute for the E0 coordinator proposal.

## Handoff and concurrency boundaries

Do not hold the session mutex across the synchronous GUI refresh barrier. A
cancel arriving while that barrier runs records intent without remote mutation;
the worker reacquires state, rechecks cancellation, then rolls back its exact
provisional lease. The queue's consume CAS rejects requests cancelled/expired
or displaced by higher priority while synchronization ran.

A provisional lease is not a public WRITE grant. It blocks automatic runtime
replacement until rollback or final ownership projection. Failed release keeps
cleanup intent and uses existing callbacks for retry, not a force-delete.
Deferred Qt grant delivery is reconciled by exact request ID plus fresh owned
lease observation, through the existing transaction handoff methods. Duplicate
grant delivery remains idempotent.

## Test evidence and fixture corrections

`tests/test_e0_write_recovery_audit.py` converts four vulnerability cases into
safety regressions: grace waiting/grant, same-account stale session release,
newcomer FIFO, and unreadable lock. Its real Git/injected-clock crash baseline
remains in place. The remaining publication/local-write characterizations still
prove unresolved blockers; passing them does not mean fencing is fixed.

`tests/test_e1a_write_state_queue_safety.py` covers typed time boundaries and
invalid records, network/JSON failure, simultaneous independent clients,
priority ordering, cancellation/expiry between CAS and grant, stale release OID,
unbound username, lost enqueue/cancel/renewal acknowledgements, delayed enqueue
after a cancellation barrier, cleanup-release failure, GUI handoff/cancel lock
ordering, deferred grant reconciliation and background replacement exclusion.

Existing tests were adjusted where their premise conflicts with E1A:

- Missing expiry previously expected automatic takeover; now expect UNKNOWN.
- Synthetic release providers accept the explicit session argument and model
  acknowledged idempotent cancellation.
- Remote contention scenarios use function-scoped remotes; session-scoped
  queue leftovers must no longer be bypassed merely because a test deleted a lock.
- MAIN-only tests supply real-shaped authority records and explicitly certified
  generation snapshots instead of relying on MagicMock int/bool coercion. MAIN
  conflict, no-pull and no-version-advance assertions remain intact.
- A brittle waiting-label source assertion accepts the optional diagnostic
  projection while retaining the no-duplicate-bottom-message contract.

Exact local/full Windows results, commit and workflow URL are recorded in the
PR. The known baseline Linux `test_e2e_sync.py` missing `temp_repo` fixture is
outside this task and must be reported explicitly if still present; it is
already skipped on Windows. No new test skip is introduced by E1A.

## Remaining blockers

E0-01/E0-02/E0-05/E0-06/E0-09/E0-10 remain: separate data/lock publication refs,
no durable ownership epoch, no universal local DB commit permit, renewing worker
with frozen GUI, no authoritative FINISHING metadata transaction, and no secure
immutable Admin recovery audit/authorization. No immediate Admin revoke is safe
on this basis. [The E0 fencing contract](WRITE_AUTHORITY_FENCING_CONTRACT.md)
remains proposed, not implemented.

Durable WRITE-session journaling before first mutation, WAL-safe quarantine,
restart-before-sync preservation, unsaved form drafts and explicit reconciliation
are E1B prerequisites. E1A neither discards nor automatically publishes stale
work, and does not promise to recover RAM lost in a hard crash.

## Two-machine Windows UAT — not executed by CI

Use two accounts/builds, an isolated test Git remote and synthetic encrypted
finance DB. Record build SHA, remote OIDs, queue request/sequence, expiry/grace,
client clock offsets, actual UI transitions and preserved local artifacts.

| ID | Action | Required outcome |
|---|---|---|
| A01 | Owner away 10/20 minutes | Same valid WRITE owner; no crash classification; 30-minute idle unchanged |
| A02 | Kill owner, request during grace | Visible WAITING; no extra Start click; head auto-grants only after expiry +600s and verified handoff |
| A03 | Two equal-priority waiters, newcomer at release | Existing live head first, then FIFO successor; approved higher-priority ordering remains |
| A04 | Two independent machines press Start concurrently | One remote owner and one EDITING client; loser visibly WAITING |
| A05 | Same username, two sessions; old session releases | Successor session/OID survives; old release fails |
| A06 | Cancel at handoff/queue consume; cancel response lost | No deadlock; either verified grant wins or cancellation stays pending until acknowledged; no hidden request |
| A07 | Git auth/network/invalid lock | UNKNOWN/error clearly visible; no false “No active editor” or WRITE grant |
| A08 | Failed release after successful Finish | MAIN is not republished; release remains pending and retry targets exact session/OID |
| A09 | Delayed grant UI event / slow GUI refresh | Request reconciles through GRANTING→EDITING exactly once; background sync does not replace provisional runtime |
| A10 | Returning owner with unpublished work after successor | No claim E1A solved preservation/fencing; stop and use the E1B recovery design before any reset/publish |

Human review/merge only. E1B/E2 require separate approval and PRs.
