"""create session_notes table

Revision ID: 6_create_session_notes
Revises: e17aaa0fba11
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6_create_session_notes'
down_revision: Union[str, Sequence[str], None] = 'e17aaa0fba11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create session_notes table
    op.create_table(
        'session_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('teaching_progress', sa.String(50), nullable=False),
        sa.Column('class_atmosphere', sa.String(50), nullable=False),
        sa.Column('difficulties', sa.Text(), nullable=True),
        sa.Column('next_plan', sa.Text(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', name='uq_session_note_session')
    )
    op.create_index('idx_session_notes_session_id', 'session_notes', ['session_id'])


def downgrade() -> None:
    op.drop_index('idx_session_notes_session_id')
    op.drop_table('session_notes')