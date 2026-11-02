# DEV-P0-01 — Publication Fencing Architecture Audit & Founder Decision

**Status:** Architecture decision proposed; **no production code, credential, branch protection or remote configuration changes**.
**Repository:** `AnNguyenHoai/Antechkid_Management`
**Audited baseline:** `main_repos` at `470b7385d60d776bde8e555396520a71fd99c9b9` (2026-11-02). Re-audit changed code before implementation.
**Companion independent QA:** QA-P0-02 and PR #533. QA results are separate from this source-level audit.

## Executive decision

**Recommendation: choose Option A, an authenticated publication coordinator as the only principal permitted to update the authoritative data and authority refs.** Keep desktop clients able to *read* approved snapshots and submit *immutable encrypted candidates*, but remove direct authority/data-ref push permissions from all EXEs, including retired builds. Launch a distinct founder-approved infrastructure implementation project; do **not** activate Admin force-revoke until server-side stale-client publication denial and version/credential cutover are independently verified.

An optional **Option B (managed Git-only, atomic dual-ref CAS)** is viable only if the fleet and push privileges are fully controlled and **all legacy direct-push credentials are denied by the remote**. An atomic two-ref Git push by updated clients alone is not a security boundary for old clients.

Current release verdict: **NOT VERIFIED / HOLD for remote publication fencing**. This is a demonstrated *architecture gap in source contract*, **not** a reproduced unauthorized production push.

## 1. Source-traced publication paths and boundaries

| Entry / evidence | Observed behavior | Security consequence |
| --- | --- | --- |
| `services/write_transaction.py` `_publish_database_and_manifest` (~817), `_publish` (~862), `_do_publish` (~935) | WAL-safe local materialization, durable journal status, then `sync_service.publish_only(message, user, expected_main_commit=self._base_main_commit)`. It later verifies acceptance, generates derived reports and attempts exact-session release. | Local transactional/recovery protections do **not** authorize remote acceptance after authority handoff. |
| `platform/synchronization/synchronization_manager.py` `publish_only` (~347) | Validates local environment, materializes repository DB if needed, delegates to provider. | Application-side preflight only; no server-enforced authority predicate visible at this boundary. |
| `platform/synchronization/git_synchronization_provider.py` `publish_only` (~1204) | Observes remote MAIN, uses expected MAIN commit, stages validated encrypted DB + identity/manifest, and publishes via Git. Source contract states MAIN CAS via `--force-with-lease`. | If ownership changes without changing MAIN, MAIN-only expected-OID CAS does not encode lost WRITE authority. |
| Same provider `_push_lock_branch`, `_delete_lock_branch`, `acquire_lock`, `release_lock` | Collaboration authority ref is changed via Git expected-OID locking; ownership uses exact session and lease revision. | Lock ref and MAIN ref are currently independent remote update boundaries. |
| `platform/synchronization/git/git_provider.py` `push` (~94) | Generic Git push method exists, `git push origin <branch>`. | Must audit actual reachability/legacy compatibility: this is a potential bypass path, **not a claim that this method updates production MAIN today**. |
| `services/git_config_service.py`, `git_credential_helper.py`, `git_windows_auth.py` | Token-based Git credentials are loaded on desktop; Windows local token can be DPAPI-protected at rest and supplied to Git. | Encryption at rest does not revoke a token's remote push privileges. Credential scope and legacy copies require verification. |
| `docs/collaboration/WRITE_AUTHORITY_FENCING_CONTRACT.md` | Explicitly `PROPOSED / NOT IMPLEMENTED`; recommends coordinator with epoch/session/expected-data OID; conditional fully-managed atomic Git alternative. | Proposal must not be described as a deployed guarantee. |
| `platform/write_recovery.py`, `database/artifact_security.py`, `database/mutation_authority.py` | Local preservation, SQLCipher artifact validation and local mutation gates. | Protect local data; cannot enforce permissions on an external remote push by a legacy binary. |

**Other publication paths requiring call-graph verification during implementation:** initial repository bootstrap, startup sync, administrative backup/restore, recovery publisher, generic `GitProvider.push`, migration/import tools, CLI/script invocations and packaged EXE older than current source. Static source scan is not evidence that these paths are unreachable; implement an exhaustive `git push` / `update-ref` invocation inventory before cutover.

## 2. Credential and GitHub permissions audit

- `GitConfigService` separates portable repository metadata and local protected access token, with DPAPI on Windows.
- Git synchronization provider accepts `token` and constructs Git authentication environment; credential helper is involved in command authentication.
- **Actual granted token scopes, which users share credentials, token expiration/rotation, GitHub organization/repository privileges, and historical EXE credential copies are NOT VERIFIED from source.** No token value should enter QA logs.
- GitHub REST check on this audit date: repository ruleset listing returned `[]`, but the branch protection endpoint for `main_repos` returned **403 Resource not accessible by integration**. Therefore effective branch protection is **UNKNOWN**, not confirmed absent.
- Important target distinction: application authoritative MAIN may be a **data Git remote/branch defined at runtime**, not the software repository's `main_repos`. Verify the configured production data-remote identity and branch through authorized redacted metadata before touching settings.

## 3. Threat model and required invariant

Adversaries/failures: old EXE with still-valid push credential, same-username old session, network partition, ambiguous push ACK, delayed process, stale authority OID, direct Git client bypassing app, compromised desktop token, and coordinator outage.

At authoritative acceptance, verify:

`authenticated principal + permitted operation + exact repository_id + supported protocol + current session_id + durable owner epoch + unexpired authority + expected authority revision/OID + expected accepted data OID + idempotent request ID`.

**Acceptance linearization point** must atomically advance authoritative accepted data pointer and receipt under that same owner epoch. If revoke wins first: stale publish rejected. If publish wins first: its exact accepted data is retained; revoke is reevaluated against latest authority. Missing/ambiguous acknowledgements trigger read-only reconciliation, never blind overwrite.

A local offline EXE can still mutate its private bytes; the enforceable remote invariant is **no unauthorized accepted publication**. Local gate on *managed updated clients* denies invalid authority and preserves quarantine; it does not prove all legacy offline processes stopped.

## 4. Options and tradeoffs

| Criterion | A — Coordinator sole remote writer (recommended) | B — Managed Git-only atomic dual-ref CAS | C — Current MAIN CAS + app checks |
| --- | --- | --- | --- |
| Server rejects ordinary legacy MAIN push | **Yes**, after credential/ref permission cutover verified | **Only if** old direct-push privileges are removed remotely | No demonstrated guarantee |
| Revoke / publish serializable | Single authority record CAS + immutable accepted pointer | Server-supported `--atomic` with both actual changed refs + exact OIDs; requires strict client compatibility | No |
| EXE upgrade mandatory for *publishing* | New protocol; legacy READ-only or blocked | Upgrade all publishers, deny incompatible ones | Legacy publishes possible |
| Hosting/operations | Coordinator service, logs, auth, backup, monitoring, availability | Less new infrastructure, more fragile fleet and Git permissions requirements | Lowest short-term effort; unacceptable fencing guarantee |
| Failure behavior | Fail closed; durable receipts + idempotent retry | Fail closed if atomic unsupported or one ref conflicts | Partial confidence |
| Recommendation | **Approve design/spike** | Only as gated fallback | **Reject for E1C remote fencing** |

**Budget and effort:** qualitative only. Exact hosting cost, volume, latency and engineer effort require a capacity/operating model; do not invent a numeric quote at this stage.

## 5. Proposed coordinator protocol (design, NOT code)

- Persistent authority: `{protocol, repository_id, epoch, session_id, principal, lease_revision, expiry, state, accepted_data_oid, request_receipts, audit_chain_head}`.
- Desktop READ may fetch immutable validated encrypted snapshots. WRITE obtains a server-issued session bound to current repository/epoch/lease.
- Desktop uploads candidate encrypted DB + signed identity/manifest (immutable hash-addressed storage); no direct authoritative MAIN push permission.
- `Publish(request_id, principal, session, epoch, expected_authority_oid, expected_data_oid, candidate_sha)`: authz, validate candidate identity/generation and policy, atomically CAS authoritative record to candidate data + durable receipt. Exact same request_id/payload returns same receipt. Distinct payload reusing ID is rejected.
- `Renew`, `Release`, `Revoke`: same authority record and epoch semantics; revoke changes epoch, writes audit tombstone; cannot silently target successor.
- Derive/project Git MAIN from accepted data using coordinator-only credential; never let MAIN projection get ahead of accepted pointer. All readers verify accepted authority pointer/receipt before adopting a new DB.
- Outage or uncertain coordinator time => cannot grant new WRITE or publish; preserve local journal/SQLCipher candidate, surface explicit recoverable error.
- Keep current 30-min inactivity and approved TTL/grace semantics unless a *separately approved* policy migration changes them.

## 6. Migration and compatibility plan

**M0 — Evidence gate (no production changes):** identify exact production data remote, current token scopes, all versions in circulation, actual GitHub permissions and backup/restore publishers. Collect QA-P0-02 isolated legacy push evidence.

**M1 — Staging prototype:** coordinator with durable epoch/receipt, isolated encrypted candidate storage, isolated staging data Git remote. Write deterministic ownership handoff, push-ACK loss, crash/retry and 2+ concurrent clients tests. Independently test offline stale EXE.

**M2 — New client and data adapter:** introduce protocol/version negotiation and coordinator publish adapter behind feature flag, retain current E1B journal, WAL-safe snapshot, signed identity/generation checks and fail-closed local mutation authority. Separate authoritative accepted data pointer from Git sync/read projections.

**M3 — Shadow verification:** compare candidate receipt OIDs, database identities, generations, journal transitions and read-only sync on staging; zero unintended production dual-publish. Prepare rollback rehearsal.

**M4 — One-way credential cutover (requires founder approval):** restrict authoritative refs so only coordinator has update permission; rotate/revoke shared desktop push tokens and legacy tokens; require new client for WRITE; older clients READ-only **only if their startup sync cannot publish**, otherwise block connection. Freeze/handoff outstanding journal safely before cutover.

**M5 — Progressive production deployment:** backup and verify SQLCipher data/identity/manifest, maintenance window, introduce coordinator, verify remote legacy denial using explicitly authorized harmless synthetic probe, test B takeover + A stale publish failure, monitor incidents and roll back clients only to a compatible read-only release.

**M6 — Enable Admin emergency revocation (separate gate):** only after coordinator fencing and all P0 tests pass; distinguish accepted remote fencing from unverifiable offline local process shutdown.

## 7. Rollback / emergency operations

- Before each cutover: verified immutable authoritative DB copy, signed identity/generation manifest, remote ref OIDs, journal/candidate inventory, credential inventory, tested restore runbook.
- On coordinator outage: stop **new WRITE/publish**, retain accepted pointer, allow verified READ-only where safe; never temporarily re-enable old desktop MAIN push as an automatic failover.
- On failed migration: revert UI/transport feature flag to **READ-only**, preserve all local unpublished journal evidence and immutable candidates; reconcile accepted OIDs before any publication.
- If reverting infrastructure is demanded, require a new risk approval and full stale-client fencing revalidation; restoring legacy broad write credentials is **not** a safe rollback.
- Never delete recovery journal or silently reset database generation to make startup succeed.

## 8. Required founder approvals / unresolved questions

1. Approve **Option A coordinator** as architectural direction, or authorize Option B feasibility spike subject to legacy permission denial.
2. Identify and authorize inspection of the **actual data Git repository** (not necessarily software `main_repos`), administrator-managed branch/ruleset settings and token scopes.
3. Approve operational ownership: hosting, availability, backups, monitoring, credential issuance/rotation and incident response.
4. Decide policy for old EXEs (recommended: block WRITE; READ only after verified harmless compatibility).
5. Approve whether Admin immediate revoke is in scope **after**, not before, remote fencing release gate.
6. Obtain QA-P0-02 reproducible source/transport evidence and production-equivalent remote enforcement tests.
7. Define maximum client offline duration and business-operational procedure when coordinator cannot be reached (no implicit offline WRITE).

## 9. Implementation work packages (AFTER approval)

- **E1C-01 Credential & ref-policy inventory:** document effective identities/scope and direct-push paths; no secrets.
- **E1C-02 Coordinator authority/state protocol:** CAS, epoch, idempotent receipt, audit, authentication/authorization.
- **E1C-03 Immutable candidate and signed DB validation:** SQLCipher snapshot, identity/generation, backups.
- **E1C-04 Desktop client transport adapter + version gate:** preserve E1B recovery, fail closed and read-only compatibility.
- **E1C-05 Git projection and exact receipt reconciliation:** coordinator-only MAIN update, rollback discipline.
- **E1C-06 Deployment, credential rotation and legacy denial:** staged cutover, monitoring, incident playbook.
- **E1C-07 Independent QA/UAT release gate:** multi-Windows, crash/fencing races, older EXE and offline cases.

Do not merge dependent code changes as one unreviewable monolith. Each implementation slice requires tests, a migration/reversal strategy and an independent QA verdict.

## 10. Evidence and current limitations

**Source-grounded conclusions:** local publish is MAIN-OID fenced; existing Git lock ref CAS uses exact OID; contract explicitly calls remote fencing unimplemented; local token protection does not itself prevent remote use. **Design inference:** remote server-side coordinator with exclusive push identity can enforce rejection of stale direct-push clients once old permissions are removed. **Not established:** exact production data remote rules, deployable coordinator platform, legacy binary distribution/credentials, live token rotation and successful end-to-end server-side denial.

**Release decision:** **HOLD** E1C publication fencing. This Draft PR is a decision document, not implementation or proof of release readiness.
