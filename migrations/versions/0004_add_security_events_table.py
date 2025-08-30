"""add security events table for analytics

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create security_events table
    op.create_table('security_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('user_email', sa.String(255), nullable=True, index=True),
        sa.Column('ip_hashed', sa.String(64), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=True, index=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, default='info'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, index=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for analytics queries
    op.create_index('ix_security_events_event_type_created_at', 'security_events', ['event_type', 'created_at'])
    op.create_index('ix_security_events_ip_hashed_created_at', 'security_events', ['ip_hashed', 'created_at'])
    op.create_index('ix_security_events_user_email_created_at', 'security_events', ['user_email', 'created_at'])
    
    # Create TTL index for automatic cleanup (90 days)
    op.execute("""
        CREATE INDEX ix_security_events_ttl 
        ON security_events (created_at) 
        WHERE created_at < NOW() - INTERVAL '90 days'
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_security_events_ttl')
    op.drop_index('ix_security_events_user_email_created_at')
    op.drop_index('ix_security_events_ip_hashed_created_at')
    op.drop_index('ix_security_events_event_type_created_at')
    
    # Drop table
    op.drop_table('security_events')

