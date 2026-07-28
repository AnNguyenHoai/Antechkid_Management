"""add class_id to enrollments

Revision ID: 8_add_class_id_to_enrollments
Revises: 7_create_student_highlights
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8_add_class_id_to_enrollments'
down_revision: Union[str, Sequence[str], None] = '7_create_student_highlights'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Thêm cột class_id (nullable)
    op.add_column('enrollments', sa.Column('class_id', sa.Integer(), nullable=True))
    # Tạo index cho truy vấn
    op.create_index('idx_enrollments_class_id', 'enrollments', ['class_id'])
    # Không thêm foreign key constraint vì SQLite không hỗ trợ ALTER TABLE thêm constraint.


def downgrade() -> None:
    op.drop_index('idx_enrollments_class_id')
    op.drop_column('enrollments', 'class_id')