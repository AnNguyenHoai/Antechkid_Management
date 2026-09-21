"""EP-EMP-WEEKLY-01 weekly work registration.

Revision ID: 1e10a023
Revises: 1e10a022
"""

from datetime import date, timedelta

from alembic import op
import sqlalchemy as sa

revision = "1e10a023"
down_revision = "1e10a022"
branch_labels = None
depends_on = None


def _monday(value):
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value - timedelta(days=value.weekday())


def _aggregate_registration_state(sources):
    """Preserve the least-final workflow state when monthly records meet in one week."""
    statuses = {source["status"] for source in sources}
    if "DRAFT" in statuses:
        return "DRAFT", None, None, None
    if "SUBMITTED" in statuses:
        submitted = [source["submitted_at"] for source in sources if source["submitted_at"]]
        return "SUBMITTED", min(submitted) if submitted else None, None, None

    submitted = [source["submitted_at"] for source in sources if source["submitted_at"]]
    accepted = [source["accepted_at"] for source in sources if source["accepted_at"]]
    accepted_by = next(
        (source["accepted_by_user_id"] for source in sources if source["accepted_by_user_id"]),
        None,
    )
    return (
        "ACCEPTED",
        min(submitted) if submitted else None,
        max(accepted) if accepted else None,
        accepted_by,
    )


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    periods = sa.Table("employee_work_registration_periods", meta, autoload_with=bind)
    regs = sa.Table("employee_work_registrations", meta, autoload_with=bind)
    blocks = sa.Table("employee_work_registration_blocks", meta, autoload_with=bind)

    # Keep legacy year/month columns temporarily because they are still NOT NULL
    # while weekly rows are created. Remove their unique constraint first so
    # multiple weekly periods originating from the same month can coexist.
    with op.batch_alter_table("employee_work_registration_periods") as batch:
        batch.add_column(sa.Column("week_start", sa.Date(), nullable=True))
        batch.drop_constraint("uq_employee_work_registration_period_month", type_="unique")

    periods = sa.Table(
        "employee_work_registration_periods", sa.MetaData(), autoload_with=bind
    )
    existing_periods = {
        row.id: row for row in bind.execute(sa.select(periods)).mappings()
    }
    existing_regs = list(bind.execute(sa.select(regs)).mappings())
    existing_blocks = list(bind.execute(sa.select(blocks)).mappings())
    registrations_by_id = {row["id"]: row for row in existing_regs}

    # Group globally by employee + Monday. This intentionally merges the
    # month-boundary case where one calendar week contains blocks from two old
    # monthly aggregates.
    weekly_groups = {}
    for block in existing_blocks:
        source_reg = registrations_by_id[block["registration_id"]]
        ws = _monday(block["work_date"])
        key = (source_reg["employee_id"], ws)
        group = weekly_groups.setdefault(
            key,
            {"blocks": [], "registrations": {}, "periods": {}},
        )
        group["blocks"].append(block)
        group["registrations"][source_reg["id"]] = source_reg
        source_period = existing_periods[source_reg["period_id"]]
        group["periods"][source_period["id"]] = source_period

    weekly_period_ids = {}

    def ensure_period(ws, source_periods):
        if ws in weekly_period_ids:
            return weekly_period_ids[ws]

        sources = list(source_periods.values())
        anchor = min(sources, key=lambda item: item["id"])
        all_closed = all(item["status"] == "CLOSED" for item in sources)
        status = "CLOSED" if all_closed else "OPEN"
        closed_values = [item["closed_at"] for item in sources if item["closed_at"]]
        closed_by = next(
            (item["closed_by_user_id"] for item in sources if item["closed_by_user_id"]),
            None,
        )
        result = bind.execute(
            periods.insert().values(
                year=anchor["year"],
                month=anchor["month"],
                week_start=ws,
                status=status,
                submission_deadline=None,
                closed_at=max(closed_values) if all_closed and closed_values else None,
                closed_by_user_id=closed_by if all_closed else None,
                created_at=min(item["created_at"] for item in sources),
                updated_at=max(item["updated_at"] for item in sources),
            )
        )
        period_id = result.inserted_primary_key[0]
        weekly_period_ids[ws] = period_id
        return period_id

    for (employee_id, ws), group in sorted(weekly_groups.items(), key=lambda item: item[0]):
        period_id = ensure_period(ws, group["periods"])
        source_regs = list(group["registrations"].values())
        status, submitted_at, accepted_at, accepted_by_user_id = (
            _aggregate_registration_state(source_regs)
        )
        result = bind.execute(
            regs.insert().values(
                employee_id=employee_id,
                period_id=period_id,
                status=status,
                submitted_at=submitted_at,
                accepted_at=accepted_at,
                accepted_by_user_id=accepted_by_user_id,
                created_at=min(item["created_at"] for item in source_regs),
                updated_at=max(item["updated_at"] for item in source_regs),
            )
        )
        new_registration_id = result.inserted_primary_key[0]
        block_ids = [block["id"] for block in group["blocks"]]
        bind.execute(
            blocks.update()
            .where(blocks.c.id.in_(block_ids))
            .values(registration_id=new_registration_id)
        )

    # Empty monthly registrations contain no availability and therefore do not
    # become weekly aggregates. All blocks have already moved before cleanup.
    if existing_regs:
        bind.execute(
            regs.delete().where(regs.c.id.in_([row["id"] for row in existing_regs]))
        )
    if existing_periods:
        bind.execute(
            periods.delete().where(periods.c.id.in_(list(existing_periods)))
        )

    with op.batch_alter_table("employee_work_registration_periods") as batch:
        batch.alter_column("week_start", existing_type=sa.Date(), nullable=False)
        batch.create_unique_constraint(
            "uq_employee_work_registration_period_week", ["week_start"]
        )
        batch.drop_column("month")
        batch.drop_column("year")


def downgrade():
    raise RuntimeError(
        "Weekly work-registration migration is intentionally irreversible because "
        "monthly aggregates are split across weeks."
    )
