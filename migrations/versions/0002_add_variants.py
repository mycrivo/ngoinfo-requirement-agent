"""add variants

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add variants JSONB column to funding_opportunities table
    # Default to empty array [] to maintain backward compatibility
    op.add_column('funding_opportunities', 
        sa.Column('variants', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=False, 
                  server_default='[]')
    )


def downgrade() -> None:
    # Remove variants column
    op.drop_column('funding_opportunities', 'variants')
