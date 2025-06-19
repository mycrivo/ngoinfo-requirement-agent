from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Enum
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