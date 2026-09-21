"""EP-EMP-WEEKLY-01 weekly work registration.

Revision ID: 1e10a023
Revises: 1e10a022
"""
from alembic import op
import sqlalchemy as sa
from datetime import date, timedelta

revision = "1e10a023"
down_revision = "1e10a022"
branch_labels = None
depends_on = None


def _monday(value):
    if isinstance(value, str): value=date.fromisoformat(value)
    return value-timedelta(days=value.weekday())


def upgrade():
    bind=op.get_bind(); meta=sa.MetaData()
    periods=sa.Table("employee_work_registration_periods",meta,autoload_with=bind)
    regs=sa.Table("employee_work_registrations",meta,autoload_with=bind)
    blocks=sa.Table("employee_work_registration_blocks",meta,autoload_with=bind)

    with op.batch_alter_table("employee_work_registration_periods") as batch:
        batch.add_column(sa.Column("week_start",sa.Date(),nullable=True))

    periods=sa.Table("employee_work_registration_periods",sa.MetaData(),autoload_with=bind)
    existing_periods={r.id:r for r in bind.execute(sa.select(periods)).mappings()}
    existing_regs=list(bind.execute(sa.select(regs)).mappings())
    existing_blocks=list(bind.execute(sa.select(blocks)).mappings())
    blocks_by_reg={}
    for block in existing_blocks: blocks_by_reg.setdefault(block["registration_id"],[]).append(block)

    weekly_period_ids={}
    def ensure_period(ws, source):
        if ws in weekly_period_ids:return weekly_period_ids[ws]
        result=bind.execute(periods.insert().values(week_start=ws,status=source["status"],submission_deadline=None,closed_at=source["closed_at"],closed_by_user_id=source["closed_by_user_id"],created_at=source["created_at"],updated_at=source["updated_at"]))
        pid=result.inserted_primary_key[0];weekly_period_ids[ws]=pid;return pid

    for reg in existing_regs:
        source=existing_periods[reg["period_id"]]
        grouped={}
        for block in blocks_by_reg.get(reg["id"],[]): grouped.setdefault(_monday(block["work_date"]),[]).append(block)
        for ws, group in grouped.items():
            pid=ensure_period(ws,source)
            result=bind.execute(regs.insert().values(employee_id=reg["employee_id"],period_id=pid,status=reg["status"],submitted_at=reg["submitted_at"],accepted_at=reg["accepted_at"],accepted_by_user_id=reg["accepted_by_user_id"],created_at=reg["created_at"],updated_at=reg["updated_at"]))
            new_reg=result.inserted_primary_key[0]
            for block in group: bind.execute(blocks.update().where(blocks.c.id==block["id"]).values(registration_id=new_reg))

    if existing_regs: bind.execute(regs.delete().where(regs.c.id.in_([r["id"] for r in existing_regs])))
    if existing_periods: bind.execute(periods.delete().where(periods.c.id.in_(list(existing_periods))))

    with op.batch_alter_table("employee_work_registration_periods") as batch:
        batch.alter_column("week_start",existing_type=sa.Date(),nullable=False)
        batch.drop_constraint("uq_employee_work_registration_period_month",type_="unique")
        batch.create_unique_constraint("uq_employee_work_registration_period_week",["week_start"])
        batch.drop_column("month");batch.drop_column("year")


def downgrade():
    raise RuntimeError("Weekly work-registration migration is intentionally irreversible because monthly aggregates are split across weeks.")
