"""baseline

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type for status
    op.execute("CREATE TYPE statusenum AS ENUM ('raw', 'reviewed', 'approved', 'rejected')")
    
    # Create funding_opportunities table
    op.create_table('funding_opportunities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_url', sa.String(), nullable=False),
        sa.Column('json_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('editable_text', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('raw', 'reviewed', 'approved', 'rejected', name='statusenum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_funding_opportunities_id'), 'funding_opportunities', ['id'], unique=False)
    op.create_index(op.f('ix_funding_opportunities_source_url'), 'funding_opportunities', ['source_url'], unique=True)
    op.create_index(op.f('ix_funding_opportunities_status'), 'funding_opportunities', ['status'], unique=False)
    
    # Create parsed_data_feedback table
    op.create_table('parsed_data_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('edited_value', sa.Text(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parsed_data_feedback_id'), 'parsed_data_feedback', ['id'], unique=False)
    op.create_index(op.f('ix_parsed_data_feedback_record_id'), 'parsed_data_feedback', ['record_id'], unique=False)
    
    # Create post_edit_feedback table
    op.create_table('post_edit_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('edited_text', sa.Text(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_edit_feedback_id'), 'post_edit_feedback', ['id'], unique=False)
    op.create_index(op.f('ix_post_edit_feedback_record_id'), 'post_edit_feedback', ['record_id'], unique=False)
    
    # Create admin_users table
    op.create_table('admin_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_users_id'), 'admin_users', ['id'], unique=False)
    op.create_index(op.f('ix_admin_users_email'), 'admin_users', ['email'], unique=True)
    op.create_index(op.f('ix_admin_users_username'), 'admin_users', ['username'], unique=True)
    
    # Create blog_posts table
    op.create_table('blog_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('meta_title', sa.String(), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('seo_keywords', sa.String(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('categories', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tone', sa.String(), nullable=True),
        sa.Column('length', sa.String(), nullable=True),
        sa.Column('extra_instructions', sa.Text(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('is_published_to_wp', sa.Boolean(), nullable=False),
        sa.Column('wp_post_id', sa.Integer(), nullable=True),
        sa.Column('wp_post_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blog_posts_id'), 'blog_posts', ['id'], unique=False)
    op.create_index(op.f('ix_blog_posts_record_id'), 'blog_posts', ['record_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_blog_posts_record_id'), table_name='blog_posts')
    op.drop_index(op.f('ix_blog_posts_id'), table_name='blog_posts')
    op.drop_table('blog_posts')
    
    op.drop_index(op.f('ix_admin_users_username'), table_name='admin_users')
    op.drop_index(op.f('ix_admin_users_email'), table_name='admin_users')
    op.drop_index(op.f('ix_admin_users_id'), table_name='admin_users')
    op.drop_table('admin_users')
    
    op.drop_index(op.f('ix_post_edit_feedback_record_id'), table_name='post_edit_feedback')
    op.drop_index(op.f('ix_post_edit_feedback_id'), table_name='post_edit_feedback')
    op.drop_table('post_edit_feedback')
    
    op.drop_index(op.f('ix_parsed_data_feedback_record_id'), table_name='parsed_data_feedback')
    op.drop_index(op.f('ix_parsed_data_feedback_id'), table_name='parsed_data_feedback')
    op.drop_table('parsed_data_feedback')
    
    op.drop_index(op.f('ix_funding_opportunities_status'), table_name='funding_opportunities')
    op.drop_index(op.f('ix_funding_opportunities_source_url'), table_name='funding_opportunities')
    op.drop_index(op.f('ix_funding_opportunities_id'), table_name='funding_opportunities')
    op.drop_table('funding_opportunities')
    
    # Drop enum type
    op.execute("DROP TYPE statusenum")
