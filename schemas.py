from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime
from models import StatusEnum

class ParseRequirementRequest(BaseModel):
    url: HttpUrl

class FundingData(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[str] = None
    deadline: Optional[str] = None
    eligibility: Optional[str] = None
    requirements: Optional[str] = None
    contact_info: Optional[str] = None

class FundingOpportunityResponse(BaseModel):
    id: int
    source_url: str
    json_data: Optional[Dict[Any, Any]] = None
    editable_text: Optional[str] = None
    status: StatusEnum
    created_at: datetime
    
    class Config:
        orm_mode = True

class ParseRequirementResponse(BaseModel):
    success: bool
    message: str
    data: Optional[FundingOpportunityResponse] = None
    extracted_data: Optional[FundingData] = None 