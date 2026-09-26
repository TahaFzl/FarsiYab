"""owner claims

Revision ID: 7c1d2e3f4a5b
Revises: 64470ede4aaf
Create Date: 2026-09-26 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1d2e3f4a5b'
down_revision: Union[str, Sequence[str], None] = '64470ede4aaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('business', sa.Column('owner_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('claim',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('method', sa.Text(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('contact_email', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('owner_key_hash', sa.Text(), nullable=True),
    sa.Column('client_hash', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("method IN ('website', 'telegram', 'manual')", name='method_valid'),
    sa.CheckConstraint("status IN ('pending', 'verified', 'rejected')", name='status_valid'),
    sa.ForeignKeyConstraint(['business_id'], ['business.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claim_business_id'), 'claim', ['business_id'], unique=False)
    op.create_index(op.f('ix_claim_client_hash'), 'claim', ['client_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claim_client_hash'), table_name='claim')
    op.drop_index(op.f('ix_claim_business_id'), table_name='claim')
    op.drop_table('claim')
    op.drop_column('business', 'owner_verified_at')
