from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum
from db import Base

class StatusEnum(enum.Enum):
    raw = "raw"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"

class TemplateStatusEnum(enum.Enum):
    ready = "ready"
    failed = "failed"
    pending = "pending"

class DocumentSourceEnum(enum.Enum):
    pdf = "pdf"
    url = "url"
    upload = "upload"

class SourceTypeEnum(enum.Enum):
    crawler = "crawler"
    api = "api"

class OCRStatusEnum(enum.Enum):
    not_needed = "not_needed"
    pending = "pending"
    done = "done"
    failed = "failed"

class SecurityEvent(Base):
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # login_success, login_failure, rate_limit, forbidden
    user_email = Column(String(255), nullable=True, index=True)
    ip_hashed = Column(String(64), nullable=False, index=True)
    role = Column(String(50), nullable=True, index=True)
    details = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="info")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

class FundingOpportunity(Base):
    __tablename__ = "funding_opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, unique=True, index=True, nullable=False)
    json_data = Column(JSON, nullable=True)
    editable_text = Column(Text, nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.raw, nullable=False)
    variants = Column(JSONB, nullable=False, default=list, server_default='[]')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class ParsedDataFeedback(Base):
    __tablename__ = "parsed_data_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    field_name = Column(String, nullable=False)
    original_value = Column(Text, nullable=True)
    edited_value = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True, default="v1.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class PostEditFeedback(Base):
    __tablename__ = "post_edit_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    section = Column(String, nullable=False)  # e.g. "post_title", "how_to_apply_section"
    original_text = Column(Text, nullable=True)
    edited_text = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True, default="v1.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="qa", nullable=False, index=True)  # admin, qa, editor
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class BlogPost(Base):
    __tablename__ = "blog_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, nullable=False, index=True)  # Foreign key to funding_opportunities.id
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)  # HTML content
    meta_title = Column(String, nullable=True)
    meta_description = Column(Text, nullable=True)
    seo_keywords = Column(String, nullable=True)
    tags = Column(JSON, nullable=True, default=list)  # JSON array of tags
    categories = Column(JSON, nullable=True, default=list)  # JSON array of categories
    tone = Column(String, nullable=True, default="professional")
    length = Column(String, nullable=True, default="medium")
    extra_instructions = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True, default="v1.0")
    word_count = Column(Integer, nullable=True)
    is_published_to_wp = Column(Boolean, default=False, nullable=False)
    wp_post_id = Column(Integer, nullable=True)  # WordPress post ID if published
    wp_post_url = Column(String, nullable=True)  # WordPress post URL if published
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ProposalTemplate(Base):
    __tablename__ = "proposal_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    funding_opportunity_id = Column(Integer, ForeignKey("funding_opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    docx_path = Column(Text, nullable=True)
    pdf_path = Column(Text, nullable=True)
    status = Column(Enum(TemplateStatusEnum), default=TemplateStatusEnum.pending, nullable=False)
    notes = Column(Text, nullable=True)
    hash = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    funding_opportunity = relationship("FundingOpportunity", backref="proposal_templates")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    funding_opportunity_id = Column(Integer, ForeignKey("funding_opportunities.id", ondelete="CASCADE"), nullable=True, index=True)
    source = Column(Enum(DocumentSourceEnum), nullable=False)
    storage_path = Column(Text, nullable=False)
    mime = Column(Text, nullable=True)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    pages = Column(Integer, nullable=True)
    ocr_status = Column(Enum(OCRStatusEnum), default=OCRStatusEnum.not_needed, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    funding_opportunity = relationship("FundingOpportunity", backref="documents")

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(Text, nullable=False, index=True)
    type = Column(Enum(SourceTypeEnum), nullable=False)
    domain = Column(Text, nullable=True, index=True)
    config = Column(JSONB, nullable=True, default=dict, server_default='{}')
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    items_seen = Column(Integer, default=0, nullable=False)
    items_ingested = Column(Integer, default=0, nullable=False)
    errors = Column(JSONB, default=dict, server_default='{}', nullable=False)
    
    # Relationships
    source = relationship("Source", backref="ingestion_runs") 