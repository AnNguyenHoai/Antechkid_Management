# Finance Wallet V2 — Implementation Tracker

> **Canonical progress tracker.** `FINANCE_WALLET_V2_DOMAIN_SPEC.md` is the domain source of truth; this tracker records implementation state and evidence.

## Metadata

| Field | Value |
|---|---|
| Original baseline | `main_repos@c4fec158d8956d631bb8ce50f9f5b12938dd37a8` |
| Current implementation base | `main_repos@8e95ed8855a7bfe799fceefd82f6ef0b58643439` |
| Domain source | `FINANCE_WALLET_V2_DOMAIN_SPEC.md` |
| Settlement auth clarification | `FINANCE_WALLET_V2_SETTLEMENT_AUTHORIZATION.md` |
| Current phase | `FW2-08 — UI Integration` |
| Current task | `Issue #340 — Canonical FinancePeriod selector + capability/state UI projection` |
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
13. Settlement authorization uses the canonical `Capability` vocabulary; UI-only Settlement permission policy is forbidden.
14. Settlement view/create/update are persisted capabilities; confirm/reopen are admin-only capabilities.

## Roadmap

| Status | ID | Outcome |
|---|---|---|
| `[x]` | FW2-01 | Canonical FinancePeriod resolution foundation |
| `[x]` | FW2-02 | Expense canonical period assignment + future realized validation |
| `[x]` | FW2-03 | Income canonical assignment + future realized validation + enrollment-at-date |
| `[x]` | FW2-04 | Closed-period service guard |
| `[x]` | FW2-05 | Settlement confirmation/reopen lifecycle + complete aggregation |
| `[x]` | FW2-06 | Wallet CASH/BANK accounting aggregation and DTOs |
| `[x]` | FW2-07 | Outstanding/Class.fee historical correctness and obligation semantics |
| `[>]` | FW2-08 | Canonical period selector + capability/state UI projection |
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

### FW2-07 — `[x] DONE`
Outstanding canonical period semantics, enrollment-overlap billing, complete Tuition Income aggregation and effective-dated `ClassFeeHistory` completed. CI #184 exposed one false-positive architecture text scan; the guard was corrected to inspect real imports. Pytest Suite #187 passed and PR #339 merged at `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e`.

## FW2-08 — UI Integration — `[>] CURRENT`

Implementation contract: GitHub Issue #340.

Approved Settlement authorization clarification:

- `finance.settlement.view` — persisted; Finance/Manager/Admin;
- `finance.settlement.create` — persisted; Finance/Manager/Admin;
- `finance.settlement.update` — persisted; Finance/Manager/Admin;
- `finance.settlement.confirm` — admin-only;
- `finance.settlement.reopen` — admin-only;
- `FinancialSettlementService` remains authoritative; UI only projects the same decisions;
- confirm requires the appropriate create/update permission path plus admin-only confirm;
- reopen requires admin-only reopen plus existing CONFIRMED/reason/audit rules.

Implementation evidence on `finance-wallet-v2-fw2-08`:

- [x] selector enumerates actual resolved FinancePeriod bounds, including mid-month and multi-month buckets;
- [x] selected canonical period is shared by Dashboard, Income, Expense, Outstanding and Settlement and is preserved across Finance navigation;
- [x] export/list filters consume the selected exact bounds rather than independently inferring Month/Year;
- [x] Income/Expense mutation controls project WRITE + canonical capability + open-period state;
- [x] Settlement service and UI enforce/project the approved view/create/update/confirm/reopen capabilities;
- [x] persisted Settlement view/create/update permissions are seeded and migrated for Admin/Finance/Manager; confirm/reopen remain role-derived admin-only capabilities;
- [x] confirmed period disables normal Income/Expense mutation controls while existing service ledger guards remain authoritative;
- [x] realized Income/Expense write forms expose only canonical `CASH`/`BANK`; unsupported `Other` is removed and unknown historical values require explicit resolution;
- [x] application Clock is used for Finance workspace business-date defaults touched by this phase;
- [x] focused FW2-08 regression coverage added and FW2-05 lifecycle tests isolated from the new independent authorization matrix;
- [ ] full GitHub Actions regression green;
- [ ] independent review + human review before DONE.

Recovery evidence: an interrupted Codex working-tree upload accidentally included runtime snapshots/heartbeats. It was preserved at `recovery/fw2-08-codex-token-cutoff`; the implementation branch was reset to the exact approved base and reconstructed with source-only changes. Runtime artifacts are not part of the FW2-08 diff.

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
| 2026-09-24 | Settlement view/create/update are canonical persisted capabilities; confirm/reopen are canonical admin-only capabilities. | FINAL |
| 2026-09-24 | Finance UI accounting identity is the selected resolved FinancePeriod bounds, never Month/Year. | FINAL |

## Implementation journal

### 2026-09-24 — FW2-08 interrupted-work recovery

The Codex session ended after token/usage exhaustion with uncommitted work. A manual recovery upload also captured runtime snapshots, heartbeats and local runtime metadata. The checkpoint was preserved on `recovery/fw2-08-codex-token-cutoff`, then the feature branch was reset to the exact approved base and reconstructed with only Issue #340 source/test/migration changes. This prevents local runtime state from entering the review diff.

### 2026-09-24 — FW2-08 implementation

The Finance shell now enumerates canonical resolved periods and shares one exact selected period context across all Finance surfaces. Income/Expense UI mutation state uses collaboration WRITE + canonical capability + open-period state. Settlement authorization is enforced in `FinancialSettlementService` and projected by the UI. Migration `1e10a029` installs persisted Settlement draft capabilities without persisting admin-only close/reopen authority. Realized transaction wallet controls now expose only `CASH` and `BANK`; legacy read aliases remain supported without guessing unknown values.

### 2026-09-24 — FW2-08 authorization conflict resolved

Codex correctly stopped before editing because R6 required fine-grained Settlement capabilities while the canonical registry had none and `FinancialSettlementService` relied on Admin checks. Product/Architecture approved `FINANCE_WALLET_V2_SETTLEMENT_AUTHORIZATION.md`: Settlement view/create/update become persisted canonical capabilities, while confirm/reopen become `ADMIN_ONLY_CAPABILITIES`. Finance and Manager can view/save drafts; only Admin can confirm ledger closure or reopen. Service authorization remains authoritative and the UI must project the same decisions.

### 2026-09-24 — FW2-08 workflow transition

The project moved to the Issue-driven flow: Product/Architecture defines the contract, Codex implements from the exact base, local tests and self-review precede PR, GitHub Actions is an independent gate, then independent review and human review precede merge. Root `AGENTS.md` contains the standing developer rules and Issue #340 is the implementation contract.

### 2026-09-24 — FW2-07 completed

Pytest Suite #187 passed after the CI #184 architecture false-positive fix. PR #339 merged into `main_repos@b2de00a2fe934fc43309623266f97f27a7e7da5e`.
