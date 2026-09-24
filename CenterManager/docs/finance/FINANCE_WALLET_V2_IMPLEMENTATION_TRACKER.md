# Finance Wallet V2 — Implementation Tracker

> **Canonical progress/evidence tracker.** `FINANCE_WALLET_V2_DOMAIN_SPEC.md` is the Finance domain source of truth. GitHub Issues are implementation contracts for individual tasks.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Last domain implementation merge | `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e` (FW2-07 / PR #339) |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Current phase | `FW2-08 — Canonical period selector + capability/state UI projection` |
| Current implementation contract | GitHub Issue #340 |
| Last completed | `FW2-07 — Outstanding / Tuition Obligation` |
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

| Status | ID | Outcome | Evidence / Contract |
|---|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation | merged implementation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation | merged implementation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date | PR #335 |
| `[x]` | FW2-04 | Closed-period service guard | merged at `c8dbbeeb...` |
| `[x]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation | PR #337 / CI #174 / merged at `44b6fb73...` |
| `[x]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs | PR #338 / merged at `2cd30166...` |
| `[x]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics | PR #339 / CI #187 / merged at `b2de00a2...` |
| `[>]` | FW2-08 | Canonical period selector + capability/state UI projection | Issue #340 |
| `[ ]` | FW2-09 | Backfill/reconciliation/migration exceptions | not started |
| `[ ]` | FW2-10 | Cross-surface regression and production release gate | not started |

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
Atomic Settlement confirm/reopen, complete aggregation, audit and repository-owned flush completed; PR #337 passed after CI audit and merged at `main_repos@44b6fb730b516b2eaa61fa29bc87ac7699aa7570`.

### FW2-06 — `[x] DONE`
Canonical `CASH/BANK` wallet mapping, Wallet DTO/service, legacy alias read compatibility, unknown-alias failure and Settlement integration completed; PR #338 merged at `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be`.

### FW2-07 — `[x] DONE`

Completed behavior:

- Outstanding uses the unique/clamped canonical FinancePeriod resolver and application Clock;
- billability is enrollment-period overlap rather than current enrollment status;
- `Class.fee` represents one obligation per student/class/canonical period and is never multiplied by `duration_months`;
- only qualifying ACTIVE Tuition Income for the same student/class/period reduces obligation;
- Tuition payment totals use complete SQL aggregation rather than row-count/list loading;
- append-only `ClassFeeHistory` preserves effective-dated tuition pricing;
- Class creation/fee edits persist fee history explicitly through service/repository boundaries in the same transaction;
- migration `1e10a028` establishes fee-history schema and explicit cutover provenance;
- unknown pre-cutover tuition price history remains an FW2-09 reconciliation concern rather than being back-priced silently;
- architecture boundary regression was hardened to inspect actual imports instead of false-positive class names in comments.

Evidence:

- PR #339;
- Pytest Suite #184 exposed one false-positive architecture test, which was corrected;
- Pytest Suite #187 passed;
- merged into `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e`.

## FW2-08 — UI Integration — `[>] CURRENT`

Implementation contract: **GitHub Issue #340 — Canonical FinancePeriod Selector & Capability/State UI Projection**.

Scope includes:

- selector uses actual FinancePeriod bounds rather than Month/Year identity;
- selected canonical period is preserved across Finance surfaces/navigation/export;
- selector changes refresh period-dependent projections coherently;
- fine-grained capability + collaboration WRITE + domain-state projection;
- closed periods disable normal realized mutation controls while service guard remains authoritative;
- Settlement confirm/reopen state is projected correctly;
- realized write UI exposes canonical `CASH/BANK` wallet values only;
- realized Expense UI does not offer unsupported `Other` Wallet values;
- UI does not duplicate canonical Finance business calculations.

Status rule: FW2-08 remains CURRENT until implementation PR, GitHub Actions, independent review and human review are complete.

## FW2-09 — Backfill & Reconciliation

Planned:

- Income/Expense deterministic period assignment backfill;
- unresolved/ambiguous transaction report;
- pre-cutover tuition fee-history reconciliation;
- idempotent reconciliation rerun;
- confirmed periods never silently mutated;
- historical Settlement snapshots preserved.

## FW2-10 — Production Gate

Planned:

- cross-surface totals agree;
- period transition/future posting/closure/reopen regression passes;
- capability matrix regression passes;
- high-volume totals prove no truncation;
- legacy compatibility tests pass;
- final Finance audit/release gate.

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
| 2026-09-24 | Architecture boundary tests should inspect actual dependencies, not comments/string spelling. | FINAL |
| 2026-09-24 | From FW2-08 onward, implementation is Issue-driven: ChatGPT/Product+Architecture → Issue → Codex developer → CI → independent review → human review. | FINAL |

## Implementation journal

### 2026-09-24 — Workflow transition / FW2-08 prepared

PR #339 passed Pytest Suite #187 and merged. Repository-root `AGENTS.md` now defines standing Codex engineering rules. Issue #340 defines FW2-08 implementation scope, acceptance criteria, tests and DoD. ChatGPT/Product+Architecture no longer directly implements normal feature tasks by default; Codex owns developer execution and the resulting PR is independently reviewed before human merge.

### 2026-09-24 — FW2-07 completed

FW2-07 closed after its only CI regression was identified as a false-positive raw-text architecture test. The guard was changed to inspect actual Python imports, full CI #187 passed, and PR #339 merged at `b2de00a2fe934fc43309623266f97f27a7e7da5e`.

### 2026-09-24 — FW2-06 completed

PR #338 passed the full pytest suite after CI audit fixed architecture inventory and legacy compatibility contracts, then merged at `main_repos@2cd3016631626b9a8f797380e0ce2f66bb8a83be`.