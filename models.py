from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum, Boolean
from sqlalchemy.sql import func
import enum
from db import Base

class StatusEnum(enum.Enum):
    raw = "raw"
    reviewed = "reviewed"
    approved = "approved"
    rejected = "rejected"

class FundingOpportunity(Base):
    __tablename__ = "funding_opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, unique=True, index=True, nullable=False)
    json_data = Column(JSON, nullable=True)
    editable_text = Column(Text, nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.raw, nullable=False)
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
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
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