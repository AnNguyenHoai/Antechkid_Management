# Finance Phase 0A — candidate diagnostic rule catalog

This catalog is a **design input for Phase 0B**, not an implemented engine. The 2026-09-23 `F-20` etc. labels identify old code findings; the `D01` etc. labels below identify future data checks and avoid colliding with those findings. No production anomaly counts were measured.

| Rule | Candidate condition / evidence | Severity and false-positive treatment | 0B disposition |
|---|---|---|---|
| D01 | Tuition Income has no `enrollment_id`; show Income ID, student/class IDs and candidate count, without family names in logs. | REVIEW. Legitimate legacy rows may await reconciliation. | Implement read-only if bounded query/permission is available. Never auto-attribute. |
| D02 | Linked Tuition Income has student/class IDs different from its Enrollment, or points to a reconciled-away Enrollment. | HIGH if ACTIVE. Historical reconciliation lineage may explain an old row; inspect lineage. | Implement with joined/controlled batched reads and exact evidence IDs. |
| D03 | Realized Income/Expense has missing period, or its persisted period does not cover payment date under the current definition. | REVIEW/HIGH depending on context. A retroactive configuration can make old rows look stale; this is not automatic permission to reclassify. | Implement only after specifying whether comparison is against posting-time or current period definition. Mark decision required. |
| D04 | Aggregate OWED and PREPAID by exact Enrollment; flag unresolved tuition contracts and exceptional signed balances separately. | INFO/REVIEW. Negative balance can be legitimate advance payment, not itself a defect. | Implement separate sums with as-of date, no cross-enrollment netting; threshold policy needs approval. |
| D05 | Draft/confirmed Settlement has Cash/Bank difference; expose period, amount and recorded explanation/status. | REVIEW only when explanation missing under applicable policy. A nonzero explained difference is permitted by Wallet V2. | Read-only audit after verifying stored reason/comment fields. |
| D06 | Similar amount/date/method/reference across Income/Expense rows. | LOW candidate, never a confirmed duplicate. Recurring fees and same-day payments are common. | Defer matching/scoring until data fields and review process are specified. |
| D07 | Refund/credit exceeds its origin or repeats a command key, or origin lineage is absent where required. | HIGH if exact rule is supported; legacy/unlinked adjustments require separate interpretation. | Scope by adjustment kind and idempotency schema before implementation. |
| D08 | Money value has fractional precision incompatible with a selected VND policy. | REVIEW; Float representation is not proof of business error. | Audit representation and actual rounding policy first; do not flag every binary Float artifact. |
| D09 | Transaction lacks required evidence/document. | Policy dependent. Current schema does not establish a complete document attachment contract. | BLOCKED until evidence model and mandatory-document policy exist. |
| D10 | Bank statement line unmatched to Income/Expense. | Not measurable without imported bank statement records. | BLOCKED until Bank Reconciliation design and data source exist. |

## Phase 0B contract

- One `finance.view` authorized, bounded read service; persistence queries stay in repositories. Return a typed finding with stable rule ID, entity IDs, evidence references, as-of date and source version. No amount mutation, migration or new write workflow.
- Limit and page queries at the database boundary. A timeout or detector error returns an explicit ERROR state, never an empty successful result. Metrics require a measured fixture size and query count before setting thresholds.
- Test both anomaly and legitimate counterexample: withdrawn/archived old debt, multiple Enrollment contracts, VOIDED Income, PREPAID, pending Expense, refund/credit, confirmed Settlement and retroactive-period uncertainty.
- Prove no business writes through a read-only session/connection and logical row snapshots. Do not rely only on byte hashes of a live SQLite/WAL file. Mask personal data in export and sanitize spreadsheet formula prefixes.
- Start with D01/D02 and bounded balance/period evidence where source supports it. D03 and D05 require precise temporal/reason policy. D06–D10 remain explicitly deferred or blocked as above.
