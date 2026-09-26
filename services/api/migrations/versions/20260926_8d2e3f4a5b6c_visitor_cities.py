"""cities added by visitors

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
Create Date: 2026-09-26 14:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8d2e3f4a5b6c'
down_revision: Union[str, Sequence[str], None] = '7c1d2e3f4a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('city', sa.Column('regions', postgresql.JSONB(astext_type=sa.Text()),
                                    server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column('city', sa.Column('wikivoyage', postgresql.JSONB(astext_type=sa.Text()),
                                    server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column('city', sa.Column('osm_id', sa.Text(), nullable=True))
    op.add_column('city', sa.Column('added_by', sa.Text(), server_default='curated', nullable=False))
    op.add_column('city', sa.Column('created_at', sa.DateTime(timezone=True),
                                    server_default=sa.text('now()'), nullable=False))
    op.create_unique_constraint('city_osm_id_key', 'city', ['osm_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('city_osm_id_key', 'city', type_='unique')
    for column in ('created_at', 'added_by', 'osm_id', 'wikivoyage', 'regions'):
        op.drop_column('city', column)
