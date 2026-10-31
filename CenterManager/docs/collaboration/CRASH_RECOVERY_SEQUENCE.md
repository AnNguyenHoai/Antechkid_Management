# Crash recovery sequences and deterministic race matrix

Status: E0 audit baseline and proposed acceptance; no runtime changes.
Base: `d76c61c15096089311bf7a688c6ae45f37cd5663`.
See [source audit](EMERGENCY_RECOVERY_SOURCE_AUDIT.md) and
[proposed fencing contract](WRITE_AUTHORITY_FENCING_CONTRACT.md).

## Scenario timelines

| Scenario | CURRENT timeline | Required approved behavior |
|---|---|---|
| Healthy user away | Poller ticks every 20s, renews near half TTL; GUI idle timer reaches 30 min. No changes releases immediately; dirty transaction pauses and suspends renewal, retains work | 10/20 min away is legitimate. No keyboard/mouse activity is not evidence of crash. Preserve existing idle policy |
| UI-only freeze | Local heartbeat thread and poller QThread can continue independently. No GUI progress signal gates renewal. GUI idle/failure handlers may not execute | SUSPECT observation; do not grant another writer on UI health alone. Require tested long-operation and sleep handling before changing renewal behavior |
| Full process kill | No release/renew. Last lease stays `locked=True`; strict expiry at last renewal+60s; other session blocked until expiry+600s | Existing queued head may retry and CAS acquire. Remote grant alone does not prove old in-flight publisher is fenced |
| Start request after expiry during grace | Provider denies reclaim. Wrapper converts WAITING to ERROR; transaction returns IDLE; request remains remote and can be refreshed | E1 must keep explicit grace waiting/retry state consistent, or cancel a rejected request durably; never orphan a grant |
| No network/auth failure | Collaboration health tests remote fetch; renewal fails and GUI handler can pause editing. Some lock read failures collapse into absent. Queue can expire after 180s without refresh | UNKNOWN, deny unverified mutation/publish; preserve work, bounded backoff; connectivity recovery revalidates epoch before any writes |
| Laptop sleep / app suspend | Neither thread executes while process suspended; leases/request ages continue according to independent wall clocks. Wake resumes callbacks, perhaps after authority changed | Reconnect handshake before writes; monotonic liveness reset and independent authority check. No assumption that screen lock pauses process |
| Windows screen lock | INFERRED: may keep ordinary process threads running; power policy may later sleep | Treat according to measured progress/authority, not screen-lock event alone; Windows UAT required |
| Finish Editing hangs | Earlier authority check may succeed; local save, snapshot/staging and final MAIN push follow. Local 120s deadline is not atomic with publish | Protect in-flight work; publish/revoke order must linearize at authoritative CAS. Timeout alone cannot authorize unfenced takeover |
| Two admins | No safe Admin protocol currently; raw force deletion unsafe | Exact target/OID/epoch and idempotent command. One wins CAS; other returns stale target, cannot retarget successor |
| Old owner returns | Stale-recovery method checks MAIN against original base; changed MAIN becomes PUBLISH_CONFLICT. Normal handoff resets repository/runtime | Quarantine before any reset/sync; permanently reject revoked epoch; explicit reconciliation of retained local edits |

## Measured source-default baseline

`test_e0_killed_owner_queue_handoff_baseline` uses real disposable Git refs,
separate managers/runtimes and injected wall time. It calls the existing poller
handoff handler and provider acquisition; DB/UI handoff is a successful synthetic
guard, so this measures **remote grant**, not complete Windows EDITING readiness.
Heartbeat threads are disabled for deterministic scheduling. No production remote
or data is involved. No elapsed wall-time sleeps are used.

| Last renewal | Simulated crash | Expiry | Grace end | First sampled eligible poll | Crash→remote grant |
|---|---|---|---|---|---|
| 0s | 0s | 60s | 660s | 660s | 660s (11m00s) |
| 0s | 19s | 60s | 660s | 661s | 642s (10m42s) |
| 0s | 39s | 60s | 660s | 662s | 623s (10m23s) |

Different-session eligibility, when clocks agree:
`last_successful_renewal + provider_TTL + reclaim_grace`.
Then add surviving head poll delay, Git/CAS execution, authoritative data install
and GUI barrier. Ideal normal WAITING poll delay is <3s; it is not a hard deadline.
For default ideal renewals every 40s, residual delay from a kill is roughly
620–660s before poll/Git/handoff. If source TTL/threshold/configuration changes,
recalculate rather than transplanting this range. Clock difference δ moves the
observed eligibility by −δ; 600s grace is not safe for arbitrary clock error.
No finite upper bound under worker/UI stall, lost queue, outage or continued renewal.

## Race schedules and evidence

| ID | Deterministic ordering | CURRENT evidence / required gate |
|---|---|---|
| R01 | Kill → expiry → poll at grace−1 → grace+phase | E0 parameterized test refuses before 660s and grants at 660/661/662s |
| R02 | UI makes no progress → worker renewal ticks | E0 callback test renews at t40/t80/t120; actual GUI-freeze Windows UAT remains pending |
| R03 | Expired lock → Start during grace → ERROR → refresh → handoff | E0 reproduces manager WRITE with transaction IDLE; subsequent grant event ignored |
| R04 | Owner release → newcomer request → queue head poll | E0 reproduces queue head overtaken. Existing queued grants do check head; global FIFO still incomplete |
| R05 | Admin observes L0 → owner renews L1 → Admin CAS-delete L0 | E0 stale-snapshot delete rejected; L1 remains. Do not replace rejection with force delete |
| R06 | Old caller same username → successor acquired → old release reads newest ref | E0 release succeeds incorrectly; session/epoch is mandatory even when CAS is used |
| R07 | Old Finish authority checked → lock transferred → MAIN unchanged → old final push | E0 actual `_push_only` accepts stale publisher. Critical immediate-revoke blocker |
| R08 | New-protocol publisher prepared L0+M0 → renewal advances L1 → atomic publish L0+M0 | E0 local Git-only experiment rejects both refs; no MAIN partial update. Not deployed proof |
| R09 | Revoked session projection still WRITE → local SQLCipher commit | E0 engine+WriteGuard repro; central local permit enforcement required |
| R10 | Queue head vanishes → age >180s → next surviving request | Existing queue filtering + cross-machine tests cover liveness/order primitives; two-machine timing/UAT pending |
| R11 | Queue cancel races grant or fails acknowledgement | Existing fail-closed acknowledgement tests; verify rollback release failure does not advertise availability in E1 |
| R12 | MAIN advances before final push | Existing MAIN force-with-lease rejects wrong base; this protects data history but not R07 |
| R13 | Admin A/B same target; renewal/revoke/publish in both orders | Future coordinator/managed-protocol tests must prove one linearization outcome and durable idempotent receipts; not implemented in E0 |
| R14 | Revoke succeeds but response lost → duplicate/reordered command | Future query-by-request-ID must recover accepted outcome, never revoke later epoch |
| R15 | Audit unavailable / malformed lock / legacy client / time uncertainty | E0 malformed/empty status characterization and existing skew tests expose limits; proposed emergency must fail closed |
| R16 | Restart dirty session → startup sync / handoff reset | Durable quarantine and recovery-index test required before enabling E2; current pre-edit snapshot alone insufficient |

## Windows two-machine release acceptance

All U01–U12 from the supplied `04_RELEASE_UAT_AND_ACCEPTANCE.md` remain **NOT RUN**.
Use an isolated encrypted fixture and Git remote with accounts/build/version
recorded. Never use production lock/database as a fixture.

Record: known crash time, last successful renewal, lease expiry, grace-end,
first queue eligibility, CAS start/end/OID, data handoff result, GUI WRITE grant,
accepted data OID and old-client denial. For each race retain both client logs
with secrets removed and clock-offset observations. Distinguish a measured
remote grant from actual local EDITING readiness.

U01: away 10/20m; U02: kill with waiting head; U03: frozen GUI with live worker;
U04: suspend/resume and ±clock changes; U05: network/auth failure; U06: two
waiters and disappearing head; U07: graceful Admin request/decline/timeout;
U08: proved controlled revoke; U09: revoked writer with unpublished work;
U10: admins vs renewal/Finish in both orders; U11: audit/permission/legacy
denial; U12: Finish while emergency pending. In-flight SQL transaction and
unsaved form draft must be separate data-preservation cases.

The current E0 tests intentionally assert vulnerabilities. When E1/E2 changes
are approved, convert each affected characterization to a rejection/safety
regression; do not keep vulnerable behavior as a permanent compatibility rule.
