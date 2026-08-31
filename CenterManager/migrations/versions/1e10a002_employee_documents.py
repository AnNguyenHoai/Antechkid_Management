"""Employee documents foundation."""
from alembic import op
import sqlalchemy as sa
revision='1e10a002'; down_revision='1e10a001'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('employee_documents',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('employee_id',sa.Integer(),sa.ForeignKey('employees.id'),nullable=False),sa.Column('document_type',sa.String(length=30),nullable=False),sa.Column('original_filename',sa.String(length=255),nullable=False),sa.Column('relative_path',sa.String(length=500),nullable=False),sa.Column('notes',sa.Text(),nullable=True),sa.Column('uploaded_at',sa.DateTime(),nullable=False))
    op.create_index('ix_employee_documents_employee_id','employee_documents',['employee_id'])
def downgrade():
    op.drop_index('ix_employee_documents_employee_id',table_name='employee_documents'); op.drop_table('employee_documents')
