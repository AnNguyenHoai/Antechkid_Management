# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** `FINANCE_WALLET_V2_DOMAIN_SPEC.md` is the domain source of truth; this tracker records implementation state and evidence.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Current implementation base | `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-07 — Outstanding / Tuition Obligation` |
| Current task | `FW2-07 CI audit/fix and full regression rerun` |
| Last completed | `FW2-06 — Wallet Accounting` |
| Last updated | `2026-09-24` |

Legend: `[ ] TODO` · `[>] CURRENT` · `[x] DONE` · `[!] BLOCKED`.

## Domain guardrails

1. Existing `FinancePeriod` remains canonical; no parallel Wallet-period table.
2. Canonical period uses exact inclusive, unique/clamped bounds and may be mid-month or multi-month.
3. Every realized Income/Expense resolves to exactly one FinancePeriod.
4. Future ACTIVE Income and future COMPLETED Expense are prohibited.
5. `Settlement.CONFIRMED` closes the ledger; `FinancePeriod.status` is configuration lifecycle only.
6. `Class.fee` is one tuition charge per billable enrollment per canonical FinancePeriod; never multiply it by `duration_months`.
7. Billability is enrollment overlap with the selected FinancePeriod.
8. Only qualifying ACTIVE Tuition Income for the same student/class/period reduces the obligation.
9. Historical accounting data must never be silently reclassified or back-priced without provenance.
10. Wallet V2 has exactly `CASH` and `BANK`; unknown aliases are errors, not guesses.
11. Services remain authoritative for domain rules; UI only projects them.
12. Financial totals must be complete and must not depend on arbitrary row caps.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[x]` | FW2-04 | Closed-period service guard |
| `[x]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[x]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[>]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[ ]` | FW2-08 | Canonical period selector + capability/state UI projection |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate |

## Completed phases

### FW2-01 — `[x] DONE`
Canonical resolved FinancePeriod model, transition clamping, multi-month and date-edge regression coverage completed.

### FW2-02 — `[x] DONE`
Expense canonical assignment, future COMPLETED validation, ambiguous-period rejection and post-commit safety completed.

### FW2-03 — `[x] DONE`
Income canonical assignment, future ACTIVE rejection, enrollment-at-date validation and application-clock semantics completed.

### FW2-04 — `[x] DONE`
Central closed-ledger guard implemented for Income/Expense source and destination periods; merged at `main_repos@c8dbbeebbc9b6227f722e6f9611c839d8ecea1d1`.

### FW2-05 — `[x] DONE`
Atomic Settlement confirm/reopen, complete aggregation, audit and repository-owned flush completed; merged at `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570` after Pytest Suite #174 passed.

### FW2-06 — `[x] DONE`
Canonical `CASH/BANK` wallet mapping, Wallet DTO/service, legacy alias read compatibility, unknown-alias failure and Settlement integration completed. PR #338 passed full regression and merged at `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be`.

## FW2-07 — Outstanding / Tuition Obligation — `[>] CURRENT`

Implemented on `finance-wallet-v2-fw2-07`:

- [x] Outstanding resolves the same unique/clamped canonical FinancePeriod contract as FW2-01;
- [x] default dates use the application `Clock`;
- [x] billability is determined by enrollment overlap, not current enrollment status;
- [x] expected tuition is exactly one fee per student/class/canonical period;
- [x] `duration_months` never multiplies `Class.fee`;
- [x] only ACTIVE Tuition Income for the same student, class and canonical period reduces obligation;
- [x] qualifying Tuition Income totals use complete SQL `SUM ... GROUP BY student_id,class_id`, not count/list row loading;
- [x] Outstanding remains derived and is not persisted;
- [x] append-only `ClassFeeHistory` provides effective-dated tuition pricing;
- [x] Class creation records an initial fee version and fee edits append a new version in the same Class transaction;
- [x] fee-history persistence is explicit through `ClassService -> ClassRepository`; the model has no mapper-event persistence side effects;
- [x] mid-period enrollment prices from the first billable date in the selected period;
- [x] Alembic `1e10a028` extends `1e10a027` and creates the fee-history schema;
- [x] migration baseline is effective only at the 2026-09-24 cutover and carries explicit `MIGRATION_BASELINE` provenance;
- [x] post-cutover database default provenance remains `CLASS_FEE_CHANGE`, so new rows cannot be mislabeled as migration baselines;
- [x] legacy fee values are never projected backward to `Class.start_date` when historical provenance is unknown;
- [x] pre-cutover obligations without a fee version remain explicitly unresolved/unconfigured and are deferred to FW2-09 reconciliation;
- [x] focused FW2-07 tests cover historical fee stability, multi-month periods, overlap, mid-period enrollment, canonical period resolution, complete qualifying Tuition Income aggregation and migration provenance;
- [x] CI #184 audit confirmed the sole failure was a false-positive architecture text scan; repository-boundary guard now inspects imported names via Python AST rather than matching class names in comments.

Remaining before DONE:

- [>] rerun full GitHub Actions pytest suite after CI #184 fix;
- [x] audit/fix CI #184 compatibility regression;
- [ ] mark FW2-07 DONE only after full regression is green and reviewed.

## FW2-08 — UI Integration

- [ ] selector uses actual FinancePeriod bounds;
- [ ] selected period preserved across Finance surfaces and export;
- [ ] fine-grained capability projection;
- [ ] closed period disables normal mutation controls while service guard remains authoritative;
- [ ] realized Expense UI does not offer unsupported `Other` Wallet values.

## FW2-09 — Backfill & Reconciliation

- [ ] Income/Expense deterministic period assignment backfilled;
- [ ] unresolved/ambiguous transaction rows reported;
- [ ] pre-cutover tuition fee history exceptions reconciled explicitly;
- [ ] reconciliation rerun is idempotent;
- [ ] confirmed periods are never silently mutated;
- [ ] historical Settlement snapshots preserved.

## FW2-10 — Production Gate

- [ ] cross-surface totals agree;
- [ ] period transition/future posting/closure/reopen tests pass;
- [ ] capability matrix tests pass;
- [ ] high-volume totals prove no truncation;
- [ ] legacy compatibility tests pass;
- [ ] final Finance audit completed.

## Decision log

| Date | Decision | Status |
|---|---|---|
| 2026-09-23 | Existing FinancePeriod remains canonical; no `FinanceWalletPeriod`. | FINAL |
| 2026-09-23 | Resolved buckets are unique/clamped to configuration effective bounds. | FINAL |
| 2026-09-23 | Settlement confirmation owns ledger closure. | FINAL |
| 2026-09-23 | Class.fee is per canonical FinancePeriod, never multiplied by duration. | FINAL |
| 2026-09-24 | Business-date rules use the application Clock. | FINAL |
| 2026-09-24 | Wallet persistence values are exactly `CASH` and `BANK`. | FINAL |
| 2026-09-24 | Unknown Wallet aliases fail rather than being guessed or dropped. | FINAL |
| 2026-09-24 | Historical tuition pricing uses append-only effective-dated Class fee versions. | FINAL |
| 2026-09-24 | Fee-history writes are explicit application persistence, not ORM mapper side effects. | FINAL |
| 2026-09-24 | Legacy fee baseline is authoritative from cutover only; it is never silently projected backward. | FINAL |
| 2026-09-24 | Pre-cutover fee-history ambiguity is an FW2-09 reconciliation concern, not an excuse to rewrite history. | FINAL |
| 2026-09-24 | Architecture boundary tests inspect actual imports; class names in comments are not dependencies. | FINAL |

## Implementation journal

### 2026-09-24 — FW2-07 CI audit #1

Pytest Suite #184 on `c1edf2785e1f9740a5e435033a1c4d009a05da30` completed with **1 failure / 1964 passed / 3 skipped**. The sole failure was `test_ep_arch_03_30_outstanding_boundary::test_outstanding_service_uses_repository_provider`: its raw-text assertion treated the word `ClassRepository` inside a compatibility comment as a concrete repository dependency. `OutstandingService` imports only `RepositoryProvider` and routes repository access through the provider, so production architecture was already correct. The guard was hardened to parse Python imports with `ast` and reject concrete repository imports without false-positive matches in comments. Business logic was not weakened. Full regression rerun is pending.

### 2026-09-24 — FW2-07 pre-PR audit hardening

Pre-PR audit removed `Class` mapper-event writes for fee history and moved them to explicit repository-owned persistence in the same Class transaction. Outstanding Tuition Income aggregation was changed from count/list loading to complete SQL grouped sums. Migration provenance was hardened so only explicit cutover rows carry `MIGRATION_BASELINE`; normal post-cutover rows default to `CLASS_FEE_CHANGE`. Focused regression coverage now locks these boundaries. Full CI remains pending.

### 2026-09-24 — FW2-07 started

Created `finance-wallet-v2-fw2-07` from merged FW2-06 base `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be`. Outstanding was moved to the FW2-01 unique/clamped resolver and application Clock. Effective-dated `ClassFeeHistory` was introduced so later fee changes cannot rewrite prior obligations. Migration `1e10a028` establishes only a cutover baseline for legacy classes; unknown pre-cutover fee history remains explicit reconciliation work. Full CI is pending.

### 2026-09-24 — FW2-06 completed

PR #338 passed the full pytest suite after CI audit fixed architecture inventory and legacy compatibility contracts, then merged into `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be`.
