"""create student_highlights table

Revision ID: 7_create_student_highlights
Revises: 6_create_session_notes
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7_create_student_highlights'
down_revision: Union[str, Sequence[str], None] = '6_create_session_notes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create student_highlights table
    op.create_table(
        'student_highlights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_student_highlights_session_id', 'student_highlights', ['session_id'])
    op.create_index('idx_student_highlights_student_id', 'student_highlights', ['student_id'])
    op.create_index('idx_student_highlights_type', 'student_highlights', ['type'])


def downgrade() -> None:
    op.drop_index('idx_student_highlights_type')
    op.drop_index('idx_student_highlights_student_id')
    op.drop_index('idx_student_highlights_session_id')
    op.drop_table('student_highlights')