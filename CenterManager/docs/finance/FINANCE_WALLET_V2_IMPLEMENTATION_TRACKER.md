# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** `FINANCE_WALLET_V2_DOMAIN_SPEC.md` remains the accounting-domain source of truth. `FINANCE_WALLET_V2_TUITION_BOUNDARY.md` is the approved FW2-09 amendment that supersedes the old per-FinancePeriod tuition semantics. This tracker records implementation state and evidence.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| FW2-08 stacked base | `finance-wallet-v2-fw2-08@d510d233d7e2a1616e8179594d23d6650c851019` |
| Accounting domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Tuition boundary amendment | `FINANCE_WALLET_V2_TUITION_BOUNDARY.md` |
| Settlement auth clarification | `FINANCE_WALLET_V2_SETTLEMENT_AUTHORIZATION.md` |
| Current phase | `FW2-09 — AccountingPeriod Semantic Boundary` |
| Current task | `Issue #342 — AccountingPeriod semantic boundary + tuition decoupling guard` |
| FW2-08 state | `CI green; PR #341 still awaiting merge/human gate` |
| Last merged phase | `FW2-07 — Outstanding / Tuition Obligation (transitional tuition semantics)` |
| Last updated | `2026-09-24` |

Legend: `[ ] TODO` · `[>] CURRENT` · `[x] DONE` · `[!] BLOCKED`.

## Domain guardrails

1. Existing `FinancePeriod` remains canonical for **accounting/settlement time**; no parallel Wallet-period table.
2. Canonical accounting period uses exact inclusive, unique/clamped bounds and may be mid-month or multi-month.
3. Every realized Income/Expense resolves to exactly one FinancePeriod.
4. Future ACTIVE Income and future COMPLETED Expense are prohibited.
5. `Settlement.CONFIRMED` closes the accounting ledger; `FinancePeriod.status` is configuration lifecycle only.
6. **FinancePeriod is not a course duration, tuition period, enrollment billing cycle, or tuition-obligation source.**
7. Tuition obligation is owned by the academic chain: Class course contract → Enrollment tuition snapshot → billable Sessions → Tuition Accrual → balance.
8. The existing `OutstandingService` Class.fee/FinancePeriod formula is a transitional compatibility exception only until TUITION-08 (#350); no new tuition feature may extend that dependency.
9. Historical accounting or tuition data must never be silently reclassified or back-priced without provenance.
10. Wallet V2 has exactly `CASH` and `BANK`; unknown aliases are errors, not guesses.
11. Services remain authoritative for domain rules; UI only projects them.
12. Financial totals must be complete and must not depend on arbitrary row caps.
13. Settlement authorization uses the canonical `Capability` vocabulary; UI-only Settlement permission policy is forbidden.
14. Settlement view/create/update are persisted capabilities; confirm/reopen are admin-only capabilities.
15. Accounting payment timing and tuition attribution are separate concerns: Tuition Income posts to a FinancePeriod/Wallet and is later attributed to an Enrollment for tuition balance.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[x]` | FW2-04 | Closed-period service guard |
| `[x]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[x]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[x]` | FW2-07 | Historical Class.fee/Outstanding correctness under the pre-amendment contract; transitional until TUITION-08 |
| `[>]` | FW2-08 | Canonical accounting-period selector + capability/state UI projection — CI green, PR #341 awaiting merge |
| `[>]` | FW2-09 | AccountingPeriod semantic boundary + Tuition decoupling guard — Issue #342 |
| `[ ]` | TUITION-01 | Class Course & Tuition Contract — #343 |
| `[ ]` | TUITION-02 | Class Create/Edit Tuition UX — #344 |
| `[ ]` | TUITION-03 | Enrollment Tuition Snapshot Contract — #345 |
| `[ ]` | TUITION-04 | Mid-course Enrollment Pricing & Session Range — #346 |
| `[ ]` | TUITION-05 | Billable Session Policy — #347 |
| `[ ]` | TUITION-06 | Tuition Accrual Service — #348 |
| `[ ]` | TUITION-07 | Link Tuition Payments to Enrollment — #349 |
| `[ ]` | TUITION-08 | Outstanding V2 Core — #350 |
| `[ ]` | TUITION-09 | Prepaid / Credit Balance Semantics — #351 |
| `[ ]` | TUITION-10 | Student Tuition Detail UX — #352 |
| `[ ]` | TUITION-11 | Attendance-aware Billing Policy — #353 |
| `[ ]` | TUITION-12 | Enrollment Freeze / Tuition Pause — #354 |
| `[ ]` | TUITION-13 | Enrollment Transfer Between Classes — #355 |
| `[ ]` | TUITION-14 | Tuition Credit / Refund Workflow — #356 |
| `[ ]` | TUITION-15 | Promotion & Discount Rules — #357 |
| `[ ]` | Finance release gate | Cross-surface regression, reconciliation/backfill exceptions and production audit after the affected domain migrations stabilize |

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

### FW2-07 — `[x] DONE` under pre-amendment contract
Outstanding canonical-period semantics, enrollment-overlap billing, complete Tuition Income aggregation and effective-dated `ClassFeeHistory` completed. Pytest Suite #187 passed and PR #339 merged at `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e`.

FW2-09 later changed the product tuition contract. FW2-07 remains valid historical/migration behavior, but its `Class.fee per FinancePeriod` obligation formula is explicitly transitional and is scheduled for replacement by TUITION-08 (#350).

## FW2-08 — UI Integration — `[>] CI GREEN / AWAITING MERGE`

Implementation contract: GitHub Issue #340; PR #341.

Implementation evidence on `finance-wallet-v2-fw2-08`:

- [x] selector enumerates actual resolved FinancePeriod bounds, including mid-month and multi-month buckets;
- [x] selected canonical accounting period is shared by Dashboard, Income, Expense, Outstanding and Settlement and preserved across Finance navigation;
- [x] export/list filters consume selected exact accounting bounds rather than independently inferring Month/Year;
- [x] Income/Expense mutation controls project WRITE + canonical capability + open-period state;
- [x] Settlement service/UI enforce and project view/create/update/confirm/reopen capabilities;
- [x] persisted Settlement view/create/update permissions are seeded/migrated; confirm/reopen remain role-derived admin-only;
- [x] confirmed period disables normal Income/Expense mutation controls while service ledger guards remain authoritative;
- [x] realized write forms expose only `CASH`/`BANK`; unknown historical values require explicit resolution;
- [x] application Clock is used for Finance workspace business-date defaults touched by this phase;
- [x] full GitHub Actions regression reported green;
- [ ] PR #341 merged to `main_repos` / human final gate.

FW2-08's period selector remains correct after the FW2-09 amendment because it is an **accounting workspace selector**. Outstanding currently consumes it only through the explicitly transitional pre-TUITION-08 implementation.

## FW2-09 — AccountingPeriod Semantic Boundary — `[>] CURRENT`

Implementation contract: GitHub Issue #342.

Evidence on `finance-wallet-v2-fw2-09`:

- [x] approved `FINANCE_WALLET_V2_TUITION_BOUNDARY.md` amendment defines FinancePeriod as accounting/settlement only;
- [x] old per-FinancePeriod tuition sections are explicitly superseded rather than silently reinterpreted;
- [x] transitional `OutstandingService` exception is documented with an explicit removal target at TUITION-08 (#350);
- [x] architecture tests prevent Class/Enrollment/Session academic core and future `*tuition*.py` modules from importing FinancePeriod semantics;
- [ ] focused/full GitHub Actions green;
- [ ] review/merge into `main_repos` after dependency PR #341 is resolved.

## Deferred reconciliation / release work

The original tracker called historical backfill/reconciliation “FW2-09”. That identifier is now re-scoped by Issue #342 to the semantic boundary required before Tuition work. The underlying reconciliation work is not discarded. It remains required before production release where relevant:

- Income/Expense deterministic period backfill and unresolved/ambiguous transaction reporting;
- pre-cutover tuition fee-history reconciliation without silently inventing historical contracts;
- idempotent reconciliation reruns;
- confirmed Settlement snapshots never silently mutated;
- cross-surface totals/capability/high-volume/legacy compatibility production gates.

These items should receive explicit issues when their target migration design is known, rather than being mixed into the Tuition contract change.

## Decision log

| Date | Decision | Status |
|---|---|---|
| 2026-09-23 | Existing FinancePeriod remains canonical for accounting; no `FinanceWalletPeriod`. | FINAL |
| 2026-09-23 | Resolved accounting buckets are unique/clamped to configuration effective bounds. | FINAL |
| 2026-09-23 | Settlement confirmation owns accounting ledger closure. | FINAL |
| 2026-09-24 | Business-date rules use the application Clock. | FINAL |
| 2026-09-24 | Wallet persistence values are exactly `CASH` and `BANK`. | FINAL |
| 2026-09-24 | Unknown Wallet aliases fail rather than being guessed or dropped. | FINAL |
| 2026-09-24 | Historical fee writes remain provenance-bearing; history is never silently rewritten. | FINAL |
| 2026-09-24 | Architecture boundary tests inspect real dependencies; comments are not production dependencies. | FINAL |
| 2026-09-24 | Settlement view/create/update are canonical persisted capabilities; confirm/reopen are admin-only. | FINAL |
| 2026-09-24 | Finance UI accounting identity is selected resolved FinancePeriod bounds, never Month/Year. | FINAL |
| 2026-09-24 | **Superseded:** `Class.fee` as one tuition charge per FinancePeriod. | SUPERSEDED BY FW2-09 |
| 2026-09-24 | **FinancePeriod is accounting/settlement only; Tuition obligation comes from Class + Enrollment + billable Sessions.** | FINAL |
| 2026-09-24 | Existing period-based Outstanding is transitional until TUITION-08 (#350). | FINAL |

## Implementation journal

### 2026-09-24 — FW2-09 tuition-boundary amendment

Product audit established that the center charges by course/session contract rather than by accounting period. `FINANCE_WALLET_V2_TUITION_BOUNDARY.md` explicitly supersedes the old tuition-specific portions of the Finance Wallet V2 contract without changing Income/Expense/Wallet/Settlement accounting semantics. An architecture guard protects the academic core from acquiring FinancePeriod dependencies while tolerating the documented `OutstandingService` compatibility implementation until #350.

### 2026-09-24 — FW2-08 implementation

The Finance shell enumerates canonical resolved accounting periods and shares one selected period context across Finance surfaces. Income/Expense UI mutation state uses collaboration WRITE + canonical capability + open-period state. Settlement authorization is enforced in `FinancialSettlementService` and projected by UI. Realized transaction wallet controls expose only `CASH` and `BANK`.

### 2026-09-24 — FW2-08 workflow transition

The project moved to the Issue-driven flow: Product/Architecture defines the contract, implementation starts from an exact base, tests and self-review precede PR, GitHub Actions is an independent gate, then human review/merge precedes issue closure.

### 2026-09-24 — FW2-07 completed

Pytest Suite #187 passed after the CI #184 architecture false-positive fix. PR #339 merged into `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e`.