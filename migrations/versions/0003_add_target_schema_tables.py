"""add target schema tables

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE templatestatusenum AS ENUM ('ready', 'failed', 'pending')")
    op.execute("CREATE TYPE documentsourceenum AS ENUM ('pdf', 'url', 'upload')")
    op.execute("CREATE TYPE sourcetypeenum AS ENUM ('crawler', 'api')")
    op.execute("CREATE TYPE ocrstatusenum AS ENUM ('not_needed', 'pending', 'done', 'failed')")
    
    # Create proposal_templates table
    op.create_table('proposal_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('funding_opportunity_id', sa.Integer(), nullable=False),
        sa.Column('docx_path', sa.Text(), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('ready', 'failed', 'pending', name='templatestatusenum'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('hash', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposal_templates_id'), 'proposal_templates', ['id'], unique=False)
    op.create_index(op.f('ix_proposal_templates_funding_opportunity_id'), 'proposal_templates', ['funding_opportunity_id'], unique=False)
    op.create_index(op.f('ix_proposal_templates_hash'), 'proposal_templates', ['hash'], unique=False)
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('funding_opportunity_id', sa.Integer(), nullable=True),
        sa.Column('source', postgresql.ENUM('pdf', 'url', 'upload', name='documentsourceenum'), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('mime', sa.Text(), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('ocr_status', postgresql.ENUM('not_needed', 'pending', 'done', 'failed', name='ocrstatusenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)
    op.create_index(op.f('ix_documents_funding_opportunity_id'), 'documents', ['funding_opportunity_id'], unique=False)
    op.create_index(op.f('ix_documents_sha256'), 'documents', ['sha256'], unique=True)
    
    # Create sources table
    op.create_table('sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('type', postgresql.ENUM('crawler', 'api', name='sourcetypeenum'), nullable=False),
        sa.Column('domain', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_id'), 'sources', ['id'], unique=False)
    op.create_index(op.f('ix_sources_provider'), 'sources', ['provider'], unique=False)
    op.create_index(op.f('ix_sources_domain'), 'sources', ['domain'], unique=False)
    
    # Create ingestion_runs table
    op.create_table('ingestion_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items_seen', sa.Integer(), nullable=False),
        sa.Column('items_ingested', sa.Integer(), nullable=False),
        sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ingestion_runs_id'), 'ingestion_runs', ['id'], unique=False)
    op.create_index(op.f('ix_ingestion_runs_source_id'), 'ingestion_runs', ['source_id'], unique=False)
    
    # Add foreign key constraints
    op.create_foreign_key('fk_proposal_templates_funding_opportunity_id', 'proposal_templates', 'funding_opportunities', ['funding_opportunity_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_documents_funding_opportunity_id', 'documents', 'funding_opportunities', ['funding_opportunity_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_ingestion_runs_source_id', 'ingestion_runs', 'sources', ['source_id'], ['id'], ondelete='CASCADE')
    
    # Create unique constraint for proposal templates (funding_opportunity_id, hash) nulls not distinct
    op.execute("CREATE UNIQUE INDEX uq_template_unique ON proposal_templates (funding_opportunity_id, hash) WHERE hash IS NOT NULL")
    
    # Seed sources table with initial data
    op.execute("""
        INSERT INTO sources (provider, type, domain, config, enabled, created_at) VALUES
        ('grants.gov', 'api', 'grants.gov', '{"filters": {"status": "open"}, "rate_limit": 100}', true, now()),
        ('UK Government', 'crawler', 'gov.uk', '{}', true, now()),
        ('European Commission', 'crawler', 'ec.europa.eu', '{}', true, now())
    """)


def downgrade() -> None:
    # Drop foreign key constraints
    op.drop_constraint('fk_ingestion_runs_source_id', 'ingestion_runs', type_='foreignkey')
    op.drop_constraint('fk_documents_funding_opportunity_id', 'documents', type_='foreignkey')
    op.drop_constraint('fk_proposal_templates_funding_opportunity_id', 'proposal_templates', type_='foreignkey')
    
    # Drop tables
    op.drop_table('ingestion_runs')
    op.drop_table('sources')
    op.drop_table('documents')
    op.drop_table('proposal_templates')
    
    # Drop enum types
    op.execute("DROP TYPE ocrstatusenum")
    op.execute("DROP TYPE sourcetypeenum")
    op.execute("DROP TYPE documentsourceenum")
    op.execute("DROP TYPE templatestatusenum")

