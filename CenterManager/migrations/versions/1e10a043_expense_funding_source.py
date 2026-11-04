"""Expense funding source (company wallet vs personal advance) + legacy normalization.

BUG-002 / FEAT-001 (Issues #566, #567). PO decision 2026-11-04:

* company wallet expenses (CASH/BANK) are realized immediately;
* personal-account expenses stay non-realized (``Pending`` = "CHƯA HOÀN TRẢ")
  until the center reimburses them from a company wallet;
* legacy rows are rewritten ONLY when they are outside every period closed by
  a CONFIRMED Settlement. Rows in closed periods are left byte-for-byte as is.

Revision ID: 1e10a043
Revises: 1e10a042
Create Date: 2026-11-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "1e10a043"
down_revision = "1e10a042"
branch_labels = None
depends_on = None

PERSONAL = "PERSONAL"
COMPANY = "COMPANY"

_PERSONAL_METHODS = ("TÀI KHOẢN CÁ NHÂN",)
_BANK_METHODS = ("BANK", "Bank", "Bank Transfer", "TÀI KHOẢN CÔNG TY")
_CASH_METHODS = ("CASH", "Cash")
_NOT_REIMBURSED = ("CHƯA HOÀN TRẢ", "Pending")
_REIMBURSED = ("ĐÃ HOÀN TRẢ", "Completed", "Paid")
_COMPANY_LEGACY_REALIZED = ("ĐÃ HOÀN TRẢ", "CHƯA HOÀN TRẢ", "Completed", "Paid")


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(bind).get_columns(table_name)}


def _open_period_clause(bind) -> str:
    """SQL predicate: the expense row is not inside a CONFIRMED settlement period."""
    if not inspect(bind).has_table("financial_settlements"):
        return "1 = 1"
    return (
        "NOT EXISTS (SELECT 1 FROM financial_settlements s "
        "WHERE s.status = 'CONFIRMED' "
        "AND expenses.payment_date >= s.finance_period_start "
        "AND expenses.payment_date <= s.finance_period_end)"
    )


def _in_list(values) -> str:
    return "(" + ", ".join("'" + v.replace("'", "''") + "'" for v in values) + ")"


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "expenses")
    if "funding_source" not in columns:
        op.add_column("expenses", sa.Column("funding_source", sa.String(length=20), nullable=True))
    if "incurred_date" not in columns:
        op.add_column("expenses", sa.Column("incurred_date", sa.Date(), nullable=True))

    open_rows = _open_period_clause(bind)
    base = f"deleted_at IS NULL AND funding_source IS NULL AND {open_rows}"

    # Personal advance, not yet reimbursed -> non-realized personal expense.
    bind.execute(sa.text(
        f"UPDATE expenses SET funding_source = '{PERSONAL}', payment_method = '{PERSONAL}', "
        f"status = 'Pending', incurred_date = payment_date "
        f"WHERE {base} AND payment_method IN {_in_list(_PERSONAL_METHODS)} "
        f"AND status IN {_in_list(_NOT_REIMBURSED)}"
    ))
    # Personal advance already reimbursed. The reimbursing wallet was never
    # recorded; keep the system's existing legacy alias rule (personal -> CASH)
    # so balances do not move to a guessed wallet. Listed for PO review.
    bind.execute(sa.text(
        f"UPDATE expenses SET funding_source = '{PERSONAL}', payment_method = 'CASH', "
        f"status = 'Completed', incurred_date = payment_date "
        f"WHERE {base} AND payment_method IN {_in_list(_PERSONAL_METHODS)} "
        f"AND status IN {_in_list(_REIMBURSED)}"
    ))
    # Company wallet with legacy/realized status -> realized company expense.
    for wallet, aliases in (("BANK", _BANK_METHODS), ("CASH", _CASH_METHODS)):
        bind.execute(sa.text(
            f"UPDATE expenses SET funding_source = '{COMPANY}', payment_method = '{wallet}', "
            f"status = 'Completed' "
            f"WHERE {base} AND payment_method IN {_in_list(aliases)} "
            f"AND status IN {_in_list(_COMPANY_LEGACY_REALIZED)}"
        ))
    # Company-wallet 'Pending' (old "planned" expense) is intentionally left
    # unclassified (funding_source NULL): realizing it could create a future
    # dated posting. It must be reviewed manually.

    # Realized rows must carry their FinancePeriod (Wallet V2 R2) when exactly
    # one configuration covers the payment date.
    if inspect(bind).has_table("finance_periods"):
        covering = (
            "FROM finance_periods p WHERE p.effective_from <= expenses.payment_date "
            "AND (p.effective_to IS NULL OR p.effective_to >= expenses.payment_date)"
        )
        bind.execute(sa.text(
            f"UPDATE expenses SET finance_period_id = (SELECT p.id {covering}) "
            f"WHERE deleted_at IS NULL AND finance_period_id IS NULL AND status = 'Completed' "
            f"AND funding_source IS NOT NULL AND {open_rows} "
            f"AND (SELECT COUNT(*) {covering}) = 1"
        ))


def downgrade() -> None:
    # Data normalization is not reversible (original legacy labels are not
    # retained); only the additive columns are removed.
    with op.batch_alter_table("expenses") as batch:
        batch.drop_column("incurred_date")
        batch.drop_column("funding_source")
