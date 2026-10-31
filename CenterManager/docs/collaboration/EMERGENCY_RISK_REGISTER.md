# E0 emergency risk register and review decisions

Status: **CURRENT audit, implementation not authorized**. See
[source evidence](EMERGENCY_RECOVERY_SOURCE_AUDIT.md),
[fencing proposal](WRITE_AUTHORITY_FENCING_CONTRACT.md) and
[race/UAT matrix](CRASH_RECOVERY_SEQUENCE.md).

| Risk | Impact | Mitigation / acceptance gate | Owner / state |
|---|---|---|---|
| Independent lock/MAIN refs; stale publisher after revoke | P0, accepted data from former owner; conflicting writers | Shared linearization point and technically enforced sole publisher; prove publish/revoke order both ways | Architecture; BLOCKED today |
| Same username releases successor, generation resets to zero | P0, silent authority loss and ABA | Session+durable epoch+exact-OID release; tombstones; idempotent targeted commands | E1/fencing prerequisite |
| Grace ERROR leaves queue entry while transaction IDLE | P0 availability/state mismatch | Coherent GRACE waiting/retry projection and durable cancellation on terminal failure; no invisible grant | E1 after review |
| Local service/DB commit lacks authority gate | P0, stale local changes; remote revoke cannot stop offline CPU | Shared local transaction/DBAPI permit, reconnect handshake, quarantine; remote rejection independently enforced | E1; offline stop claim BLOCKED |
| GUI frozen but worker renews | P1, indefinite service blockage | Independent GUI/service progress observations; long-operation exemptions; no health-only takeover | E1; Windows UAT |
| Arbitrary skew / naive timezone / rollback | P0, early reclaim or prolonged blockage | Keep 600s; approved trusted time and UTC protocol migration; unknown fails closed | Separate approved time design |
| Read failures look unlocked / malformed lease reclaimable | P0 under an unsafe Admin handler | Typed absent/active/grace/unknown observations, strict parse/schema and connectivity; reject uncertainty | E1/E2 diagnostic prerequisite |
| Newcomer bypasses pending queue; queue and lock race | P1 fairness and orphaned ownership | Atomic head validation, priority/sequence semantics, cancel/expiry race handling | E1 |
| Forced release loses unpublished work | P0 financial data loss | Durable encrypted WAL-safe quarantine before local replacement; explicit reconciliation; no automatic binary merge | E1/E2; review retention |
| Unsaved form RAM lost on kill / offline device destroyed | Unrecoverable content | Draft autosave where supported; explicitly disclose unknown/unrecoverable state; no blanket zero-loss guarantee | Founder decision |
| Legacy clients / shared Git credentials bypass fencing | P0 makes new protocol advisory | Fleet inventory; minimum version denial; revoke/rotate write credentials; protected sole-writer refs | Deployment approval required |
| Local DB audit rewritten or not published | P0 weak accountability | Authenticated coordinator-controlled append-only events bound to atomic outcome; external retention; audit failure blocks revoke | E2 architecture |
| No remote kill agent / device unreachable | Availability expectation mismatch | Graceful request and authority revocation only; separate optional Windows agent proposal | Remote kill OUT OF SCOPE |
| Lost network response after publish/revoke | P0 duplicate effects or wrong success | Durable request ID, command digest, receipt reconciliation, explicit UNKNOWN | E1/E2 |
| DB maintenance/Git/GUI blocking interaction | P1 false crash or expired lease mid-handoff | Measure scheduling; no blocking GUI call under shared remote mutex; bounded operations; Windows stress UAT | E1 |
| Characterization PASS mistaken for safety PASS | P0 premature release | PR labels scope clearly; no runtime changes; replace vulnerable assertions when fixes land; full release gate separate | E0 documentation |

## Concrete safe alternative today

No new emergency action is exposed by E0. Preserve failed workstation/runtime
and its DB/WAL/Git files; do not reset/pull/restore or clear lock files to test.
Read-only diagnostics and an authenticated graceful relinquish flow can be
built in E2A after E1 prerequisites. If owner is unavailable and fencing or local
preservation cannot be verified, show `RECOVERY_BLOCKED` with the precise reason.
Normal expiry/polling is existing behavior, not a guarantee that E0 has fixed
recovery or certified stale-publisher safety. Do not operationally force-delete
the remote lock, kill an unmanaged Windows process or shorten the grace.

## Proposed delivery after E0 approval

| Phase / PR | Concrete scope | Gate before next step |
|---|---|---|
| E1A — observation and state consistency | Typed remote errors, ACTIVE/GRACE/UNKNOWN diagnostics, fix grace queue/transaction mismatch, close newcomer FIFO gap, session-targeted release; preserve all timings | Deterministic grace/queue/CAS/error regressions; Windows CI |
| E1B — local recovery safety | Central authority permits, durable dirty-session index/quarantine, returning-client handshake, protect service/raw DB writes and every publish/retry caller; independent progress observations | No reset before quarantine; actual signed SQLCipher lifecycle tests; no false crash on 10/20m away or valid blocking job |
| Fencing infrastructure prerequisite | Choose sole-writer coordinator or fully enforced atomic-ref fleet protocol; prove legacy/direct-write denial, epoch and audit atomicity | Explicit founder scope/deployment approval; end-to-end former-owner publication rejection. This may require its own project/PRs; not hidden inside E1 |
| E1 completion | Automatic head recovery after approved lease-safe eligibility, consistent UI grant, bounded retry classifications | Full Windows CI plus two-machine crash/network/sleep/UAT evidence; no timing-policy reduction |
| E2A — Admin read/graceful request | Dedicated capability, authoritative diagnostics, targeted expiring request, owner choice, durable request/audit receipt | Unauthorized/replay/decline/timeout tests; diagnostics never acquire WRITE |
| E2B — controlled revoke | Exact session/epoch/OID confirmation, mandatory reason and reauth, atomically recorded revoke and queue handoff | All fencing and preservation gates, concurrent Admin/Finish/renew tests, legacy exclusion and Windows UAT. Remains BLOCKED until demonstrated |

## Founder review requested

1. Approve the audit findings and the decision to block immediate revoke on
   current direct-Git architecture. E0 PR merge only adopts evidence/design for
   review; it does not approve any E1/E2 permission behavior.
2. Choose **coordinator with protected sole-writer authority** (recommended for
   enforceability) or a technically managed, version-gated atomic Git fleet.
   The latter is blocked if old clients still possess direct write credentials.
3. Confirm the guarantee boundary: uniqueness of accepted remote writes is
   enforceable; instantly stopping private local writes on an offline unmanaged
   PC is not. Retain a blocked/unknown state when literal E2 local-ack gate cannot
   be met. A remote kill agent is a separate future product/security decision.
4. Approve recovery-copy access/retention, draft autosave scope and explicit
   treatment of uncollected offline work and unsaved RAM. No automatic discard
   or financial-history rewrite is proposed.
5. Approve E1A/E1B as separate reviewed work only after the fencing contract is
   settled; maintain 600s grace, 60s TTL, 20s renewal timer and 30-minute idle.

E0 stops after audit PR and CI. No auto-merge or production operations.
