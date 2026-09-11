"""Employee domain foundation.
Revision ID: 1e10a001
Revises: 0ce070d8da89
"""
from alembic import op
import sqlalchemy as sa
revision='1e10a001'; down_revision='0ce070d8da89'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('employees',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('employee_code',sa.String(30),nullable=False),
        sa.Column('full_name',sa.String(200),nullable=False),
        sa.Column('date_of_birth',sa.Date()),sa.Column('gender',sa.String(30)),sa.Column('phone',sa.String(30)),sa.Column('email',sa.String(120)),sa.Column('address',sa.String(500)),sa.Column('department',sa.String(100)),sa.Column('position',sa.String(100)),sa.Column('employment_status',sa.String(30),nullable=False,server_default='ACTIVE'),sa.Column('hire_date',sa.Date()),sa.Column('termination_date',sa.Date()),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('employee_code',name='uq_employee_code'),sa.UniqueConstraint('user_id',name='uq_employee_user'))
    op.create_index('ix_employees_status','employees',['employment_status'])
def downgrade(): op.drop_table('employees')
