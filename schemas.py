from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime
from models import StatusEnum

# Variant-related schemas
class ApplicationRound(BaseModel):
    round_name: str
    apply_open_month: Optional[str] = None
    apply_open_year_estimate: Optional[int] = None
    apply_close_date: Optional[datetime] = None

class ApplicationWindow(BaseModel):
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    timezone: Optional[str] = None
    application_rounds: Optional[List[ApplicationRound]] = []

class DeliveryPeriod(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class OpportunityVariant(BaseModel):
    variant_title: str
    grant_min: Optional[float] = None
    grant_max: Optional[float] = None
    currency: Optional[str] = None
    funding_type: Optional[str] = None
    application_window: Optional[ApplicationWindow] = None
    application_rounds: Optional[List[ApplicationRound]] = []
    delivery_period: Optional[DeliveryPeriod] = None
    application_link: Optional[str] = None
    notes: Optional[str] = None
    is_primary: Optional[bool] = False

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
    donor: Optional[str] = None
    themes: Optional[str] = None
    location: Optional[str] = None

class FundingOpportunityResponse(BaseModel):
    id: int
    source_url: str
    json_data: Optional[Dict[Any, Any]] = None
    editable_text: Optional[str] = None
    status: StatusEnum
    variants: List[OpportunityVariant] = []
    created_at: datetime
    
    class Config:
        orm_mode = True

class ParseRequirementResponse(BaseModel):
    success: bool
    message: str
    data: Optional[FundingOpportunityResponse] = None
    extracted_data: Optional[FundingData] = None
    # Enhanced fields for re-parsing workflow
    already_exists: Optional[bool] = False
    existing_entry: Optional[FundingOpportunityResponse] = None
    new_entry: Optional[FundingOpportunityResponse] = None
    existing_extracted_data: Optional[FundingData] = None
    new_extracted_data: Optional[FundingData] = None

class GenerateBlogRequest(BaseModel):
    opportunity_id: int

class GenerateBlogResponse(BaseModel):
    success: bool
    opportunity_id: Optional[int] = None
    title: Optional[str] = None
    blog_post: Optional[str] = None
    message: Optional[str] = None

class PublishToWordPressRequest(BaseModel):
    title: str
    content: str  # HTML content
    tags: list[str]
    categories: list[str]
    opportunity_url: str
    meta_title: str
    meta_description: str

class PublishToWordPressResponse(BaseModel):
    success: bool
    message: str
    wordpress_response: Optional[Dict[Any, Any]] = None
    post_id: Optional[int] = None
    post_url: Optional[str] = None

class GeneratePostRequest(BaseModel):
    record_id: int
    seo_keywords: Optional[str] = None
    tone: Optional[str] = "professional"  # professional, persuasive, informal
    length: Optional[str] = "medium"  # short, medium, long
    extra_instructions: Optional[str] = None

class GeneratePostResponse(BaseModel):
    success: bool
    message: str
    post_title: Optional[str] = None
    post_content: Optional[str] = None  # HTML content
    tags: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    opportunity_url: Optional[str] = None
    record_id: Optional[int] = None
    prompt_version: Optional[str] = None
    # Enhanced fields for database persistence
    blog_post_id: Optional[int] = None
    is_existing: Optional[bool] = False
    last_updated: Optional[datetime] = None
    word_count: Optional[int] = None

class SavedBlogPostResponse(BaseModel):
    id: int
    record_id: int
    title: str
    content: str
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    seo_keywords: Optional[str] = None
    tags: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    tone: Optional[str] = None
    length: Optional[str] = None
    extra_instructions: Optional[str] = None
    prompt_version: Optional[str] = None
    word_count: Optional[int] = None
    is_published_to_wp: bool = False
    wp_post_id: Optional[int] = None
    wp_post_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class GetBlogPostRequest(BaseModel):
    record_id: int

class GetBlogPostResponse(BaseModel):
    success: bool
    message: str
    blog_post: Optional[SavedBlogPostResponse] = None
    exists: bool = False

class RegenerateBlogPostRequest(BaseModel):
    record_id: int
    seo_keywords: Optional[str] = None
    tone: Optional[str] = "professional"
    length: Optional[str] = "medium"
    extra_instructions: Optional[str] = None
    force_regenerate: bool = True  # Always overwrite existing

class ParsedDataFeedbackRequest(BaseModel):
    record_id: int
    field_edits: Dict[str, Any]  # field_name -> new_value mapping
    prompt_version: Optional[str] = "v1.0"

class PostEditFeedbackRequest(BaseModel):
    record_id: int
    section_edits: Dict[str, str]  # section -> edited_text mapping
    prompt_version: Optional[str] = "v1.0"

class FeedbackResponse(BaseModel):
    success: bool
    message: str
    feedback_count: Optional[int] = None

class QAUpdateRequest(BaseModel):
    """Enhanced QA update request with individual field edits"""
    record_id: int
    field_updates: Dict[str, Any]  # Updated fields from JSON data
    editable_text: Optional[str] = None
    status: Optional[str] = None
    prompt_version: Optional[str] = "v1.0"

class ProposalSection(BaseModel):
    heading: str
    instruction: str

class CreateProposalTemplateRequest(BaseModel):
    record_id: int
    sections: list[ProposalSection]
    funder_notes: Optional[str] = None

class ProposalTemplateResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None
    download_url: Optional[str] = None
    timestamp: Optional[str] = None
    opportunity_title: Optional[str] = None
    template_id: Optional[int] = None
    pdf_url: Optional[str] = None
    status: Optional[str] = None
    hash: Optional[str] = None
    is_existing: Optional[bool] = False 