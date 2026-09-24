# Finance Wallet V2 — Settlement Authorization Contract

Status: **APPROVED ARCHITECTURE / PRODUCT DECISION**  
Date: 2026-09-24  
Scope: Settlement authorization for FW2-08 and later Finance Wallet V2 work.

This document clarifies R6 of `FINANCE_WALLET_V2_DOMAIN_SPEC.md`. It does not replace the Domain Spec; it resolves the previously undefined Settlement capability identifiers and role grants.

## 1. Decision

Settlement must use the same canonical capability system as the rest of CenterManager. UI-only Settlement authorization is forbidden.

The canonical capabilities are:

| Capability | Type | Purpose |
|---|---|---|
| `finance.settlement.view` | persisted | Read Settlement projection/history for a FinancePeriod |
| `finance.settlement.create` | persisted | Create/save the first DRAFT Settlement for a FinancePeriod |
| `finance.settlement.update` | persisted | Update an existing DRAFT Settlement |
| `finance.settlement.confirm` | admin-only | Confirm Settlement and close the FinancePeriod ledger |
| `finance.settlement.reopen` | admin-only | Reopen a CONFIRMED Settlement with required audit reason |

These identifiers must be added to `core.capabilities.Capability`; they are the single authorization vocabulary. `PermissionDefinitions` must continue deriving from that canonical registry rather than creating duplicate string constants.

## 2. Role grants

### Admin

Admin may:

- view Settlement;
- create DRAFT Settlement;
- update DRAFT Settlement;
- confirm Settlement;
- reopen Settlement.

`finance.settlement.confirm` and `finance.settlement.reopen` belong in `ADMIN_ONLY_CAPABILITIES`. They are role-derived by `AuthorizationService` and are not assignable through the generic persisted permission matrix.

### Finance

Finance role receives persisted grants for:

- `finance.settlement.view`;
- `finance.settlement.create`;
- `finance.settlement.update`.

Finance role does **not** receive confirm or reopen.

### Manager

Manager receives the three persisted Settlement capabilities through the existing manager permission policy:

- `finance.settlement.view`;
- `finance.settlement.create`;
- `finance.settlement.update`.

Manager does **not** receive confirm or reopen because those are admin-only capabilities.

### Other roles

No Settlement capability is granted unless explicitly provided by the canonical role/permission system.

## 3. Service authorization contract

`FinancialSettlementService` remains authoritative.

### Read operations

Settlement read/projection APIs require:

`finance.settlement.view`

### Save DRAFT

When no Settlement exists for the selected canonical FinancePeriod, saving a draft requires:

`finance.settlement.create`

When a DRAFT Settlement already exists, saving changes requires:

`finance.settlement.update`

### Confirm

Confirming a new Settlement requires:

`finance.settlement.create` **AND** `finance.settlement.confirm`

Confirming an existing DRAFT requires:

`finance.settlement.update` **AND** `finance.settlement.confirm`

`finance.settlement.confirm` is admin-only, so Admin remains mandatory. Existing `_require_admin()` checks may remain as defense in depth but must not be the only authorization rule.

### Reopen

Reopening requires:

`finance.settlement.reopen`

and the existing domain preconditions:

- actor is Admin through the admin-only capability policy;
- Settlement exists;
- Settlement is `CONFIRMED`;
- non-blank reason is provided;
- audit record is written atomically with the state transition.

Existing `_require_admin()` may remain as defense in depth.

## 4. UI projection contract

UI controls project service authorization; they do not define a second policy.

A Settlement action is enabled only when all applicable conditions hold:

```text
collaboration WRITE mode
AND required Settlement capability
AND domain-state precondition
```

Examples:

- View Settlement: `finance.settlement.view` (WRITE mode not required for read).
- Save new draft: WRITE + `finance.settlement.create` + open period / valid domain state.
- Save existing draft: WRITE + `finance.settlement.update` + DRAFT state.
- Confirm: WRITE + `finance.settlement.confirm` + Admin-only authorization + confirmation preconditions.
- Reopen: WRITE + `finance.settlement.reopen` + CONFIRMED state + reason workflow.

The UI must never enable an action that the service would reject for authorization.

## 5. Migration / seeding contract

Adding the three persisted capabilities must preserve the current permission model:

- Admin receives all persisted permissions through the existing seed policy.
- Finance role seed must explicitly include Settlement view/create/update.
- Manager continues receiving persisted permissions according to its existing policy exclusions.
- Existing installations must receive the new permission rows and role grants through the project’s normal permission seeding/upgrade path; do not require destructive database recreation.

Confirm/reopen remain in `ADMIN_ONLY_CAPABILITIES` and therefore are not stored as generic assignable permissions.

## 6. Tests required

At minimum cover:

- Finance can view/create/update Settlement draft;
- Finance cannot confirm or reopen;
- Manager can view/create/update Settlement draft;
- Manager cannot confirm or reopen;
- Admin can perform all Settlement actions subject to domain state;
- read APIs reject principals without `finance.settlement.view`;
- new draft requires create capability;
- existing draft mutation requires update capability;
- confirm requires confirm capability plus appropriate create/update path;
- reopen requires admin-only reopen capability and existing audit/domain rules;
- UI capability projection matches service decisions;
- no separate Settlement permission vocabulary is introduced outside `Capability`.

## 7. Non-goals

This decision does not:

- change Settlement accounting formulas;
- change confirmation/reopen lifecycle semantics;
- make Manager or Finance capable of ledger closure;
- make Admin-only capabilities assignable through the generic role matrix;
- remove collaboration WRITE-mode requirements for mutation;
- weaken service/domain state guards.

## 8. Rationale

R6 requires UI authorization to project the same fine-grained capabilities enforced by services. The previous implementation used only an Admin check for Settlement mutation and no explicit read capability, while the capability registry had no Settlement vocabulary. Keeping that state would force FW2-08 either to invent UI-only authorization or to leave R6 incomplete.

The selected contract fits the existing architecture:

- `Capability` remains the single vocabulary;
- persisted capabilities support normal role grants;
- `ADMIN_ONLY_CAPABILITIES` already models non-assignable privileged actions;
- `AuthorizationService` remains the single decision engine;
- service checks remain authoritative;
- UI remains a projection layer.
