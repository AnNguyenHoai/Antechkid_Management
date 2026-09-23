# Finance Wallet V2 — Domain Specification

Status: **APPROVED DOMAIN CONTRACT**  
Baseline: `main_repos@e12b7f56cb8e3336bfe535f287ad92ee5845a473`  
Date: 2026-09-23  
Scope: FinancePeriod, Wallet/Ledger, Income, Expense, Outstanding, Settlement and Finance authorization projection.

---

## 1. Purpose

Finance Wallet V2 defines one canonical accounting domain for the CenterManager Finance Workspace.

The goal is not to redesign the UI first. The goal is to remove ambiguous financial semantics so Dashboard, Income, Expense, Outstanding and Settlement always answer the same questions from the same domain rules.

This specification is the source of truth for the next Finance implementation tasks. Where current behavior conflicts with this document, this document is the target V2 behavior. Migration must preserve historical data and must not silently reinterpret money without an explicit migration rule.

---

## 2. Problems this contract resolves

The Finance Workspace audit found that the current system is operational but still has domain ambiguity in six areas:

1. a Month/Year selector cannot uniquely identify a mid-month FinancePeriod;
2. Expense can exist without a canonical FinancePeriod;
3. future-dated realized transactions produce different totals across surfaces;
4. confirmed Settlement freezes a snapshot but does not close the underlying ledger;
5. `Class.fee` has no explicit billing meaning when FinancePeriod duration is greater than one month;
6. mutation controls are mostly projected from collaboration WRITE mode instead of the same fine-grained Finance capabilities enforced by services.

These six requirement changes are approved for Wallet V2.

---

## 3. Domain vocabulary

### 3.1 FinancePeriod

A **FinancePeriod** is the canonical accounting bucket used by all Finance read and write operations.

A period has an exact inclusive range:

```text
period_start <= transaction_date <= period_end
```

The period identity is its canonical `period_start`. Month/Year is presentation metadata only and must never be used as the primary period identity.

### 3.2 Wallet

A **Wallet** is a canonical money location.

Wallet V2 initially defines exactly two system wallets:

- `CASH`
- `BANK`

Existing payment-method values are mapped to one of these wallets for accounting aggregation. Legacy aliases remain readable during migration, but new writes use canonical values.

Wallet is not a free-text payment method. A payment method may describe how money moved; Wallet describes where the realized money balance belongs.

### 3.3 Ledger transaction

A **ledger transaction** is a realized financial posting that changes a Wallet balance inside exactly one FinancePeriod.

For V2, realized postings are:

- ACTIVE Income;
- realized/completed Expense.

VOIDED Income and non-realized/pending Expense do not change live Wallet balances.

### 3.4 Outstanding

**Outstanding** is a derived tuition obligation. It is not an independent Wallet transaction.

It is derived from:

```text
Enrollment
+ billable tuition obligation for FinancePeriod
- qualifying tuition Income allocated to that obligation
```

### 3.5 Settlement

A **Settlement** reconciles the expected Wallet balances with the actual Cash/Bank balances for one FinancePeriod.

In Wallet V2, confirming a Settlement closes that FinancePeriod for realized ledger mutation.

---

## 4. Approved requirement changes

## R1 — Replace Month/Year inference with canonical FinancePeriod selection

### Requirement

Every Finance surface MUST operate on one explicitly selected canonical FinancePeriod.

The selector MUST identify the period by exact bounds, for example:

```text
Current period · 15/09/2026 – 14/10/2026
Previous period · 15/08/2026 – 14/09/2026
```

Month/Year alone MUST NOT resolve a period because one calendar month can overlap two canonical periods.

### Required behavior

- Default selection: the FinancePeriod containing `today`.
- Historical selection: choose an actual FinancePeriod instance/bounds, not an inferred calendar month.
- Dashboard, Income, Expense, Outstanding and Settlement receive the same selected period context.
- Navigation between Finance pages preserves the selected period.
- Export uses the same selected period as the visible data.
- A period selector change refreshes every active projection that depends on FinancePeriod.

### Invariant

```text
One visible Finance context == one canonical period_start/period_end pair.
```

---

## R2 — Every realized Income and Expense belongs to exactly one FinancePeriod

### Requirement

Wallet V2 does not allow unscoped realized transactions.

Every new Income and every realized Expense MUST resolve to a covering FinancePeriod before persistence succeeds.

### Required behavior

- Income retains canonical FinancePeriod assignment.
- Expense gains the same canonical period assignment contract.
- Creating a realized transaction for a date not covered by a FinancePeriod MUST fail validation.
- Editing a transaction date MUST recompute its canonical FinancePeriod.
- A transaction MUST NOT carry a period that does not contain its transaction date.
- Historical legacy Expense without period assignment must be backfilled deterministically from `payment_date` when a unique covering period exists.
- Legacy rows that cannot be assigned safely must be surfaced as migration exceptions; they must not be silently attached to an arbitrary period.

### Target persistence contract

Both Income and Expense expose a canonical period identity, preferably through a real FinancePeriod foreign key in the V2 schema. During incremental migration, `finance_period_start` may remain as a compatibility bridge, but service/domain APIs MUST treat the period as an entity, not free text.

### Invariant

```text
realized transaction -> exactly one FinancePeriod
```

---

## R3 — Future-dated realized postings are prohibited

### Requirement

Income and realized Expense represent money that has actually moved. Their transaction date MUST NOT be later than the effective business date.

```text
payment_date <= business_date
```

For the current application, `business_date` defaults to the local application date.

### Required behavior

- Creating future-dated ACTIVE Income MUST fail validation.
- Moving an existing Income into the future MUST fail validation.
- Creating a future-dated realized/completed Expense MUST fail validation.
- Moving a realized Expense into the future MUST fail validation.
- A pending/planned Expense MAY use a future date only if it is explicitly modeled as non-realized and therefore excluded from Wallet balance, Settlement and realized Dashboard totals.
- Future scheduled tuition or expected payments are not Income. If required later, they must use a separate planned/receivable domain model.

### Read-model consequence

Dashboard, list, Settlement and Wallet totals no longer need different interpretations of future realized transactions. Realized money is always posted-to-date money.

### Invariant

```text
realized == occurred, never scheduled
```

---

## R4 — Confirmed Settlement closes the FinancePeriod ledger

### Requirement

`CONFIRMED` Settlement is not merely an immutable snapshot. It is the domain event that closes the FinancePeriod for realized financial mutation.

### Closed-period rules

After Settlement confirmation, the following operations for that FinancePeriod MUST be rejected by the domain/service layer:

- create Income;
- update Income;
- void/delete Income;
- create realized Expense;
- update realized Expense;
- delete/void realized Expense;
- move a transaction into or out of the closed period by changing its date/period.

Read, export and historical reporting remain available.

### Reopen rule

V2 MAY support reopening a closed period, but only as an explicit Admin operation with an audit record containing at minimum:

- period identity;
- actor;
- timestamp;
- reason/comment;
- previous Settlement identity/status.

Until reopen is implemented, a confirmed period is terminally closed from normal UI flows.

### Confirmation preconditions

Settlement confirmation MUST:

1. recalculate live ledger activity for the selected FinancePeriod;
2. calculate expected closing Cash/Bank;
3. require actual closing Cash/Bank;
4. calculate differences;
5. require a comment when a configured non-zero difference exists;
6. persist the confirmed snapshot atomically;
7. make the period closed only if the confirmation transaction succeeds.

### Invariant

```text
Settlement.CONFIRMED <=> FinancePeriod ledger closed for normal mutation
```

---

## R5 — `Class.fee` is the tuition charge per student per canonical FinancePeriod

### Requirement

For the current CenterManager product, `Class.fee` is defined as the tuition amount expected from one enrolled student for one canonical FinancePeriod in which that enrollment is billable.

It is **not** automatically multiplied by `FinancePeriod.duration_months`.

### Expected tuition

For a billable Enrollment in period `P`:

```text
expected_tuition(enrollment, P) = Class.fee
```

The FinancePeriod may span one or multiple calendar months; that does not change the charge automatically.

### Billable enrollment

An Enrollment is billable for period `P` when its active date range overlaps the FinancePeriod according to the existing enrollment-period overlap contract.

V2 does not introduce automatic daily proration. Partial-period discounts, scholarships, credits or custom tuition require explicit future domain objects/rules rather than hidden arithmetic in Outstanding.

### Course duration

Course duration and FinancePeriod duration are separate concepts. A course such as a four-month Scratch course may span multiple FinancePeriods. Tuition obligation is evaluated once for each canonical FinancePeriod in which the enrollment is billable.

### Invariant

```text
Class.fee has one meaning everywhere: per-student charge for one FinancePeriod.
```

---

## R6 — Finance UI actions project the same fine-grained capabilities as services

### Requirement

Collaboration WRITE mode is necessary for mutation but is not sufficient authorization.

Every Finance mutation control MUST require both:

```text
WRITE mode
AND
required Finance capability
AND
any domain-state precondition
```

### Capability projection

At minimum:

| Action | Required capability |
|---|---|
| View Finance workspace | `finance.view` |
| Create Income | `finance.income.create` |
| Update Income | `finance.income.update` |
| Void/Delete Income | corresponding Income mutation capability |
| Create Expense | `finance.expense.create` |
| Update Expense | `finance.expense.update` |
| Delete/Void Expense | corresponding Expense mutation capability |
| View period configuration | `finance.period.view` where administrative period configuration is shown |
| Manage period configuration | `finance.period.manage` |
| View Settlement | settlement view capability |
| Create/Save Settlement | settlement create/update capability plus domain-state guard |
| Confirm Settlement | settlement confirm capability plus Admin/domain-state guard |

Exact permission identifiers already established by the permission registry remain authoritative; this table describes the projection rule rather than inventing duplicate authorization.

### UI behavior

- Unauthorized mutation actions SHOULD be hidden when the action is irrelevant to the role.
- If visibility is useful for discoverability, the control MAY be disabled with an explanation, but clicking it must never be the normal way to discover lack of permission.
- Service checks remain authoritative and MUST NOT be removed because the UI projects permissions.
- Closed-period state from R4 is an additional domain guard even for authorized Admin users unless they explicitly use the reopen workflow.

### Invariant

```text
UI permission projection never grants more than the service/domain contract.
```

---

## 5. Wallet accounting model

## 5.1 Canonical wallets

Wallet V2 starts with two wallets:

```text
CASH
BANK
```

Each realized transaction resolves to exactly one Wallet.

Legacy aliases are normalized on read/migration:

| Legacy/current value | Wallet |
|---|---|
| `Cash` | `CASH` |
| `TÀI KHOẢN CÁ NHÂN` | `CASH` |
| `Bank` | `BANK` |
| `Bank Transfer` | `BANK` |
| `TÀI KHOẢN CÔNG TY` | `BANK` |

Unknown historical values MUST NOT be silently guessed. They must be reported as migration exceptions.

## 5.2 Balance equation

For wallet `W` and FinancePeriod `P`:

```text
closing_expected(W, P)
  = opening_balance(W, P)
  + realized_income(W, P)
  - realized_expense(W, P)
```

Settlement compares:

```text
difference(W, P)
  = actual_closing(W, P)
  - closing_expected(W, P)
```

## 5.3 Wallet continuity

For consecutive periods, the confirmed actual closing balance of period `P` SHOULD become the opening balance candidate for period `P+1`.

V2 implementation must not silently overwrite a manually established opening balance. The carry-forward behavior must be explicit in the Settlement workflow and covered by tests.

## 5.4 Transfers

A transfer between Cash and Bank is not Income and not Expense because it does not change total center assets.

Target V2 representation:

```text
WalletTransfer
- id
- finance_period_id
- transfer_date
- from_wallet
- to_wallet
- amount
- note
- status
- created_by / timestamps
```

A realized transfer decreases one Wallet and increases the other by the same amount.

```text
net_assets_effect(transfer) = 0
```

Transfer implementation may be delivered after the six approved requirements, but the V2 ledger MUST reserve this semantic so future code does not model transfers as fake Income/Expense.

---

## 6. Transaction state semantics

### Income

Canonical accounting states:

- `ACTIVE`: realized and included in Wallet/period totals;
- `VOIDED`: excluded from live totals but retained for audit/history.

### Expense

Canonical accounting states:

- `PENDING`: not realized; excluded from Wallet/Settlement realized outflow;
- `COMPLETED`: realized; included in Wallet/Settlement outflow.

Legacy `Paid` is normalized to `COMPLETED`.

### Mutation after realization

Before period closure, authorized users may correct realized transactions according to existing audit requirements. After closure, R4 applies and normal mutation is rejected.

---

## 7. Outstanding V2 contract

Outstanding remains a read model, not a Wallet.

For each billable Enrollment and selected FinancePeriod:

```text
expected = Class.fee
paid = qualifying ACTIVE tuition Income allocated to student/class/period
outstanding = expected - paid
```

Canonical statuses:

- `Not Yet`: expected > 0 and paid == 0;
- `Partial`: 0 < paid < expected;
- `Paid`: paid == expected;
- `Overpaid`: paid > expected;
- `No Tuition Configured`: Class fee is absent/unconfigured and obligation cannot be calculated safely.

`Overpaid` is a monetary state (`paid > expected`), not a substitute for an expired period with an incomplete obligation.

Outstanding MUST use the same selected FinancePeriod as Dashboard, Income, Expense and Settlement.

---

## 8. Dashboard V2 contract

Dashboard is a projection of the selected FinancePeriod; it does not define separate accounting semantics.

At minimum it derives:

```text
Income realized to business_date
Expense realized to business_date
Net realized cashflow
Cash wallet movement
Bank wallet movement
Outstanding tuition summary
Settlement status: OPEN / DRAFT / CLOSED
```

For historical closed periods, the Dashboard may show the full confirmed period totals because the period is complete.

For the current open period, totals are realized-to-date. Because R3 prohibits future realized postings, this is consistent with the live ledger.

---

## 9. FinancePeriod lifecycle

Wallet V2 distinguishes configuration activity from accounting closure.

Suggested domain states:

```text
CONFIG_ACTIVE / CONFIG_INACTIVE    # whether a period definition/config is usable
OPEN / CLOSED                      # whether the concrete period ledger accepts mutation
```

The existing `FinancePeriod.status` may continue to represent configuration activation during migration. Ledger closure is derived from confirmed Settlement until/unless a dedicated persisted closure state is introduced.

A period MUST NOT be considered closed merely because its end date is in the past. Closure is an explicit accounting action.

---

## 10. Service boundaries

### FinancePeriodService

Owns:

- period configuration;
- exact period enumeration/selection;
- date -> canonical period resolution;
- overlap/integrity validation.

### IncomeService

Owns:

- Income validation and persistence;
- period assignment;
- Wallet assignment;
- future-date guard;
- closed-period mutation guard;
- Income permissions.

### ExpenseService

Owns:

- Expense validation and persistence;
- period assignment;
- Wallet assignment;
- realized-vs-pending semantics;
- future-date guard for realized Expense;
- closed-period mutation guard;
- Expense permissions.

### OutstandingService

Owns only derived tuition obligation/read-model calculation. It MUST NOT mutate Income, Expense, Wallet or Settlement.

### FinancialSettlementService

Owns:

- live reconciliation calculation;
- opening/expected/actual/difference values;
- confirmation;
- period-close decision;
- reopen workflow when implemented;
- settlement permissions.

### Wallet read model/service

A V2 Wallet service/read model may aggregate Cash/Bank balances, but it MUST consume canonical ledger semantics from Income/Expense/Transfer rather than reimplementing separate payment-method rules in each UI page.

---

## 11. Required domain guards

The following guards MUST be centralized in services/domain logic and covered by tests:

1. transaction date belongs to exactly one canonical FinancePeriod;
2. realized transaction date is not in the future;
3. payment method resolves to a known Wallet;
4. closed period rejects normal ledger mutation;
5. Income/Expense permission is checked independently of collaboration WRITE mode;
6. Settlement confirmation is atomic;
7. FinancePeriod definitions do not create ambiguous overlapping active ranges;
8. migration cannot silently guess unknown Wallet aliases or ambiguous period assignment.

UI validation may mirror these rules for usability but is never authoritative.

---

## 12. Migration requirements

Wallet V2 migration MUST be incremental and auditable.

### Phase A — Domain contract and regression tests

- encode R1–R6 as tests before broad UI migration;
- add canonical Wallet mapping tests;
- add closed-period mutation tests;
- add period-assignment integrity tests.

### Phase B — Period identity

- introduce canonical Expense period assignment;
- prefer real FinancePeriod identity/foreign key for Income and Expense;
- backfill legacy rows by transaction date;
- emit a migration report for unassignable/ambiguous rows.

### Phase C — Ledger guards

- prohibit future realized postings;
- add shared closed-period guard;
- make Settlement confirmation close the period;
- ensure transaction date changes cannot bypass closure.

### Phase D — Billing semantics

- codify `Class.fee` as per-student/per-FinancePeriod charge;
- update Outstanding tests and labels to state this explicitly;
- do not introduce automatic duration multiplication or proration.

### Phase E — Authorization projection

- project fine-grained Finance capabilities into Income/Expense/Settlement controls;
- retain service authorization as final authority.

### Phase F — Finance UI-PROD migration

- replace Month/Year selector with canonical period selector;
- migrate legacy Finance forms/dialogs/feedback to Design System V2;
- remove mixed-language and raw-literal UX debt without changing accounting rules.

### Phase G — Wallet transfer (follow-up)

- add WalletTransfer only after the base ledger contract is stable;
- include transfer in Cash/Bank movement and Settlement;
- keep it out of Income/Expense revenue/cost totals.

---

## 13. Backward compatibility

During migration:

- existing Income/Expense records remain readable;
- legacy payment/status aliases are normalized at boundaries;
- historical confirmed Settlement remains immutable;
- existing exports remain available until a replacement export contract is shipped;
- no migration may silently delete or rewrite historical financial values;
- compatibility fields such as `payment_period` may remain temporarily but MUST NOT be the canonical period source in new V2 logic.

---

## 14. Non-goals

Wallet V2 does **not** introduce:

- double-entry accounting/general ledger;
- bank API integration;
- automatic bank reconciliation;
- invoices, tax/VAT accounting or payroll;
- arbitrary user-created Wallets in the first release;
- automatic daily tuition proration;
- scheduled future Income represented as realized Income;
- hidden mutation of closed periods.

These may be separate future domains.

---

## 15. Acceptance criteria

Wallet V2 domain implementation is complete only when all of the following are true:

1. every Finance page uses the same explicit canonical FinancePeriod context;
2. every realized Income/Expense belongs to exactly one FinancePeriod;
3. future realized postings are rejected;
4. confirming Settlement closes the period and all normal ledger mutation paths respect that closure;
5. `Class.fee` has one tested per-student/per-FinancePeriod meaning across Outstanding and Finance projections;
6. Finance mutation controls require WRITE mode + matching capability + domain state;
7. Cash/Bank Wallet totals are derived from one canonical mapping;
8. Dashboard, Income, Expense, Outstanding and Settlement agree for the same period and business date;
9. legacy aliases/backfill behavior is covered by migration tests;
10. full regression suite remains green.

---

## 16. Required regression matrix

| Scenario | Expected result |
|---|---|
| Mid-month period selected | Exact period bounds preserved across all Finance pages |
| Expense date has no covering period | Mutation rejected |
| Income date has no covering period | Mutation rejected |
| Future ACTIVE Income | Rejected |
| Future COMPLETED Expense | Rejected |
| Future PENDING Expense | Allowed only as non-realized; excluded from Wallet/Settlement |
| Confirm Settlement | Period becomes closed |
| Create/update/void Income in closed period | Rejected |
| Create/update/delete realized Expense in closed period | Rejected |
| Change transaction date into closed period | Rejected |
| Change transaction date out of closed period | Rejected unless explicit reopen workflow permits it |
| FinancePeriod duration > 1 month | Expected tuition remains one `Class.fee` per billable period |
| User has WRITE but lacks create capability | Create control unavailable and service rejects direct call |
| Legacy Bank Transfer / Vietnamese bank alias | Maps to BANK |
| Legacy Vietnamese cash alias | Maps to CASH |
| Unknown wallet alias | Migration/validation exception, never guessed |
| Cash -> Bank transfer | No Income/Expense effect; total assets unchanged when transfer feature ships |

---

## 17. Implementation rule

No implementation task may change the six approved requirements implicitly.

If implementation discovers a conflict, the sequence is:

1. document the conflict;
2. update this domain specification through explicit product decision;
3. add/adjust regression tests;
4. then change production code.

Finance UI must consume this domain contract; it must not redefine accounting semantics locally.
