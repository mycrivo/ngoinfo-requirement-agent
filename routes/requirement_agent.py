from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
import logging
import json
from typing import Dict, Any

# Database imports
from db import get_db
from models import FundingOpportunity, StatusEnum
from schemas import (
    ParseRequirementRequest, 
    ParseRequirementResponse, 
    FundingOpportunityResponse,
    FundingData,
    GenerateBlogRequest,
    GenerateBlogResponse
)

# Enhanced parser import
from utils.openai_parser import parse_funding_opportunity_from_url
from utils.variant_utils import apply_primary_to_top_level

# Set up logging
logger = logging.getLogger(__name__)

def enrich_extracted_data(extracted_data: Dict[str, Any], json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Silently enrich extracted_data with missing information from json_data
    """
    # Create a copy to avoid modifying the original
    enriched_data = extracted_data.copy()
    
    # Rule 1: Add donor if missing in extracted_data but available in json_data
    if not enriched_data.get('donor') and json_data.get('donor'):
        enriched_data['donor'] = json_data.get('donor')
    
    # Rule 2: Add themes as comma-separated string if missing in extracted_data
    if not enriched_data.get('themes') and json_data.get('themes'):
        themes = json_data.get('themes')
        if isinstance(themes, list):
            enriched_data['themes'] = ", ".join(str(theme) for theme in themes if theme)
        elif themes:
            enriched_data['themes'] = str(themes)
    
    # Rule 3: Clean location to region/country level if missing or verbose
    json_location = json_data.get('location')
    if json_location and (not enriched_data.get('location') or len(enriched_data.get('location', '')) > 100):
        # Clean location to region/country level
        location_str = str(json_location)
        # Extract key location identifiers (country, region)
        location_keywords = ['UK', 'United Kingdom', 'England', 'Scotland', 'Wales', 'Northern Ireland', 
                           'Europe', 'North America', 'USA', 'Canada', 'Australia', 'Global', 'International']
        
        # Try to find a concise location
        for keyword in location_keywords:
            if keyword.lower() in location_str.lower():
                enriched_data['location'] = keyword
                break
        else:
            # If no keyword found, use first 50 chars and clean up
            clean_location = location_str.strip()[:50].strip()
            if clean_location:
                enriched_data['location'] = clean_location
    
    # Rule 4: Normalize "Unknown" to "Not specified" across all fields
    for key, value in enriched_data.items():
        if isinstance(value, str) and value.strip().lower() == 'unknown':
            enriched_data[key] = 'Not specified'
    
    return enriched_data

def generate_blog_post(opportunity: dict) -> str:
    """
    Generate a clean, markdown-formatted blog post from a funding opportunity record
    
    Args:
        opportunity: Dictionary containing funding opportunity data with json_data
    
    Returns:
        str: Markdown-formatted blog post content
    """
    # Extract json_data from opportunity record
    json_data = opportunity.get('json_data', {})
    
    # Extract key fields with fallbacks
    title = json_data.get('title', 'Funding Opportunity')
    location = json_data.get('location', 'Location TBA')
    amount = json_data.get('amount', 'Amount TBA')
    deadline = json_data.get('deadline', 'Deadline TBA')
    donor = json_data.get('donor', 'Donor TBA')
    summary = json_data.get('summary', 'Summary to be added.')
    eligibility = json_data.get('eligibility', [])
    opportunity_url = json_data.get('opportunity_url', opportunity.get('source_url', '#'))
    
    # Clean and format title
    blog_title = f"{title} – {location} ({amount})"
    
    # Start building the markdown content
    markdown_content = f"# {blog_title}\n\n"
    
    # Opportunity Snapshot section
    markdown_content += "## Opportunity Snapshot\n\n"
    markdown_content += f"**Deadline:** {deadline}\n\n"
    markdown_content += f"**Funding Size:** {amount}\n\n"
    markdown_content += f"**Donor:** {donor}\n\n"
    markdown_content += f"**Country:** {location}\n\n"
    markdown_content += f"**Opportunity URL:** [{opportunity_url}]({opportunity_url})\n\n"
    
    # Summary Paragraph
    markdown_content += "## Summary\n\n"
    markdown_content += f"{summary}\n\n"
    
    # Funding Details (if available in summary)
    if summary and len(summary.strip()) > 0:
        markdown_content += "## Funding Details\n\n"
        markdown_content += f"{summary}\n\n"
    
    # Eligibility Criteria
    markdown_content += "## Eligibility Criteria\n\n"
    if eligibility:
        if isinstance(eligibility, list):
            for criterion in eligibility:
                if criterion and str(criterion).strip():
                    markdown_content += f"- {str(criterion).strip()}\n"
        elif isinstance(eligibility, str) and eligibility.strip():
            # If eligibility is a string, split by common delimiters and create bullet points
            criteria_items = []
            for delimiter in [', ', '; ', ' and ', ' & ']:
                if delimiter in eligibility:
                    criteria_items = [item.strip() for item in eligibility.split(delimiter) if item.strip()]
                    break
            
            if criteria_items:
                for criterion in criteria_items:
                    markdown_content += f"- {criterion}\n"
            else:
                markdown_content += f"- {eligibility}\n"
        markdown_content += "\n"
    else:
        markdown_content += "- Eligibility criteria to be confirmed\n\n"
    
    # Geographic Focus
    markdown_content += "## Geographic Focus\n\n"
    markdown_content += f"This opportunity is open to organizations based in {location}.\n\n"
    
    # Selection Criteria
    markdown_content += "## Selection Criteria\n\n"
    markdown_content += "_Selection criteria to be added by QA._\n\n"
    
    return markdown_content

def serialize_opportunity_with_variants(opportunity: FundingOpportunity) -> FundingOpportunityResponse:
    """
    Serialize a FundingOpportunity model to FundingOpportunityResponse with variant mapping.
    
    This function ensures that when variants exist, the top-level fields are derived
    from the primary variant for backward compatibility.
    """
    # Convert to dict first
    opportunity_dict = {
        "id": opportunity.id,
        "source_url": opportunity.source_url,
        "json_data": opportunity.json_data,
        "editable_text": opportunity.editable_text,
        "status": opportunity.status,
        "variants": opportunity.variants or [],
        "created_at": opportunity.created_at
    }
    
    # Apply primary variant mapping if variants exist
    if opportunity.variants:
        opportunity_dict = apply_primary_to_top_level(opportunity_dict)
    
    # Create response model
    return FundingOpportunityResponse(**opportunity_dict)

# Create router
router = APIRouter(prefix="/api", tags=["requirement-agent"])

@router.post("/requirement/parse", response_model=ParseRequirementResponse)
async def parse_requirement(
    request: ParseRequirementRequest,
    force_refresh: bool = Query(False, description="If True, bypass cache and re-parse the URL even if it exists"),
    db: Session = Depends(get_db)
):
    """
    Parse a funding opportunity from a URL using enhanced OpenAI extraction with database storage
    
    Args:
        request: ParseRequirementRequest containing the URL to parse
        force_refresh: If True, bypass cache and re-parse the URL even if it exists (default: False)
        db: Database session dependency
    """
    try:
        url_str = str(request.url)
        logger.info(f"🔍 Processing funding opportunity request for URL: {url_str} (force_refresh={force_refresh})")
        
        # Check if URL already exists in database
        existing_opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.source_url == url_str
        ).first()
        
        # If existing record found and force_refresh is False, return existing data with already_exists flag
        if existing_opportunity and not force_refresh:
            logger.info(f"📋 Found existing record for URL: {url_str} (ID: {existing_opportunity.id}) - returning cached data")
            
            # Convert stored JSON data to FundingData for response
            existing_extracted_data = None
            if existing_opportunity.json_data:
                try:
                    # Create FundingData from stored JSON (backward compatibility)
                    json_data = existing_opportunity.json_data
                    
                    # Convert eligibility list to string if needed
                    eligibility_value = json_data.get('eligibility')
                    if isinstance(eligibility_value, list):
                        eligibility_str = ", ".join(str(item) for item in eligibility_value if item)
                    else:
                        eligibility_str = eligibility_value if eligibility_value is not None else None
                    
                    # Create base extracted_data
                    base_extracted_data = {
                        'title': json_data.get('title'),
                        'description': json_data.get('summary') or json_data.get('description'),
                        'amount': json_data.get('amount'),
                        'deadline': json_data.get('deadline'),
                        'eligibility': eligibility_str,
                        'requirements': json_data.get('how_to_apply') or json_data.get('requirements'),
                        'contact_info': json_data.get('contact_info')
                    }
                    
                    # Enrich with missing information from json_data
                    enriched_data = enrich_extracted_data(base_extracted_data, json_data)
                    
                    existing_extracted_data = FundingData(**enriched_data)
                except Exception as e:
                    logger.warning(f"⚠️ Could not convert stored JSON to FundingData: {e}")
            
            return ParseRequirementResponse(
                success=True,
                message="This funding opportunity already exists in the database. You can re-parse it to update the data.",
                already_exists=True,
                existing_entry=serialize_opportunity_with_variants(existing_opportunity),
                existing_extracted_data=existing_extracted_data,
                data=serialize_opportunity_with_variants(existing_opportunity),  # For backward compatibility
                extracted_data=existing_extracted_data  # For backward compatibility
            )
        
        # Store existing data for comparison if force_refresh=True
        existing_entry_for_comparison = None
        existing_extracted_for_comparison = None
        
        if existing_opportunity and force_refresh:
            logger.info(f"🔄 Force refresh requested for URL: {url_str} (ID: {existing_opportunity.id}) - re-parsing and updating")
            
            # Store existing data for comparison
            existing_entry_for_comparison = serialize_opportunity_with_variants(existing_opportunity)
            
            # Convert existing JSON data to FundingData for comparison
            if existing_opportunity.json_data:
                try:
                    json_data = existing_opportunity.json_data
                    
                    # Convert eligibility list to string if needed
                    eligibility_value = json_data.get('eligibility')
                    if isinstance(eligibility_value, list):
                        eligibility_str = ", ".join(str(item) for item in eligibility_value if item)
                    else:
                        eligibility_str = eligibility_value if eligibility_value is not None else None
                    
                    # Create base extracted_data for existing
                    base_extracted_data = {
                        'title': json_data.get('title'),
                        'description': json_data.get('summary') or json_data.get('description'),
                        'amount': json_data.get('amount'),
                        'deadline': json_data.get('deadline'),
                        'eligibility': eligibility_str,
                        'requirements': json_data.get('how_to_apply') or json_data.get('requirements'),
                        'contact_info': json_data.get('contact_info')
                    }
                    
                    # Enrich with missing information from json_data
                    enriched_data = enrich_extracted_data(base_extracted_data, json_data)
                    existing_extracted_for_comparison = FundingData(**enriched_data)
                except Exception as e:
                    logger.warning(f"⚠️ Could not convert existing JSON to FundingData for comparison: {e}")
        
        # Parse new URL using enhanced parser
        logger.info(f"🚀 Parsing new URL with enhanced gold-standard extraction: {url_str}")
        parsed_data = await parse_funding_opportunity_from_url(url_str)
        
        # Log extraction quality for QA team
        confidence_score = parsed_data.get('_confidence_score', 0.0)
        extraction_warning = parsed_data.get('_extraction_warning')
        missing_required = parsed_data.get('_missing_required', [])
        
        if confidence_score >= 80:
            logger.info(f"✅ High confidence extraction ({confidence_score}%) for {url_str}")
        elif confidence_score >= 60:
            logger.warning(f"⚠️ Medium confidence extraction ({confidence_score}%) for {url_str}")
        else:
            logger.error(f"🔴 Low confidence extraction ({confidence_score}%) for {url_str}")
        
        if missing_required:
            logger.warning(f"🚨 QA ALERT - Missing required fields for {url_str}: {missing_required}")
        
        # Create or update database record
        if existing_opportunity and force_refresh:
            # Update existing record with new parsed data
            existing_opportunity.json_data = parsed_data
            existing_opportunity.status = StatusEnum.raw  # Reset status to raw for QA review
            funding_opportunity = existing_opportunity
            logger.info(f"🔄 Updated existing funding opportunity (ID: {existing_opportunity.id}) with fresh data")
        else:
            # Create new database record
            funding_opportunity = FundingOpportunity(
                source_url=url_str,
                json_data=parsed_data,  # Store the complete enhanced JSON structure
                editable_text="",  # Empty for now as requested
                status=StatusEnum.raw
            )
            db.add(funding_opportunity)
            logger.info(f"💾 Created new funding opportunity record")
        
        db.commit()
        db.refresh(funding_opportunity)
        
        logger.info(f"💾 Successfully saved funding opportunity to database (ID: {funding_opportunity.id})")
        
        # Create FundingData response for backward compatibility
        # Convert eligibility list to string if needed
        eligibility_value = parsed_data.get('eligibility')
        if isinstance(eligibility_value, list):
            eligibility_str = ", ".join(str(item) for item in eligibility_value if item)
        else:
            eligibility_str = eligibility_value if eligibility_value is not None else None
        
        # Create base extracted_data
        base_extracted_data = {
            'title': parsed_data.get('title'),
            'description': parsed_data.get('summary') or parsed_data.get('description'),
            'amount': parsed_data.get('amount'),
            'deadline': parsed_data.get('deadline'),
            'eligibility': eligibility_str,
            'requirements': parsed_data.get('how_to_apply') or parsed_data.get('requirements'),
            'contact_info': parsed_data.get('contact_info')
        }
        
        # Enrich with missing information from json_data
        enriched_data = enrich_extracted_data(base_extracted_data, parsed_data)
        
        extracted_data = FundingData(**enriched_data)
        
        # Determine response message based on extraction quality and operation type
        operation = "updated" if (existing_opportunity and force_refresh) else "parsed and saved"
        
        if confidence_score >= 80:
            message = f"Successfully {operation} funding opportunity with high confidence ({confidence_score}%)"
        elif confidence_score >= 60:
            message = f"{operation.capitalize()} funding opportunity with medium confidence ({confidence_score}%) - QA review recommended"
        else:
            message = f"{operation.capitalize()} funding opportunity with low confidence ({confidence_score}%) - Manual QA required"
        
        if extraction_warning:
            message += f" | Warning: {extraction_warning}"
        
        # Prepare response with comparison data for force_refresh cases
        if existing_opportunity and force_refresh:
            # Force refresh case - provide comparison data
            return ParseRequirementResponse(
                success=True,
                message=message,
                already_exists=False,  # False because we successfully re-parsed
                existing_entry=existing_entry_for_comparison,
                existing_extracted_data=existing_extracted_for_comparison,
                new_entry=serialize_opportunity_with_variants(funding_opportunity),
                new_extracted_data=extracted_data,
                data=serialize_opportunity_with_variants(funding_opportunity),  # For backward compatibility
                extracted_data=extracted_data  # For backward compatibility
            )
        else:
            # New URL case - normal response
            return ParseRequirementResponse(
                success=True,
                message=message,
                already_exists=False,
                data=serialize_opportunity_with_variants(funding_opportunity),
                extracted_data=extracted_data
            )
        
    except Exception as e:
        logger.error(f"🔴 Error processing funding opportunity for {request.url}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse and save funding opportunity: {str(e)}"
        )

@router.post("/requirement/generate-blog", response_model=GenerateBlogResponse)
async def generate_blog(
    request: GenerateBlogRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a blog post from an existing funding opportunity record
    
    Args:
        request: GenerateBlogRequest containing opportunity_id
        db: Database session dependency
    
    Returns:
        GenerateBlogResponse with blog content or error message
    """
    try:
        opportunity_id = request.opportunity_id
        logger.info(f"🖊️ Generating blog post for opportunity ID: {opportunity_id}")
        
        # Look up the funding opportunity by ID
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == opportunity_id
        ).first()
        
        if not opportunity:
            logger.warning(f"❌ Funding opportunity with ID {opportunity_id} not found")
            return GenerateBlogResponse(
                success=False,
                message=f"Funding opportunity with ID {opportunity_id} not found"
            )
        
        # Convert SQLAlchemy model to dictionary for generate_blog_post function
        opportunity_dict = {
            "id": opportunity.id,
            "source_url": opportunity.source_url,
            "json_data": opportunity.json_data or {},
            "editable_text": opportunity.editable_text,
            "status": opportunity.status.value,
            "created_at": opportunity.created_at
        }
        
        # Generate blog post content
        blog_content = generate_blog_post(opportunity_dict)
        
        # Extract title for response
        json_data = opportunity.json_data or {}
        title = json_data.get('title', 'Funding Opportunity')
        location = json_data.get('location', 'Location TBA')
        amount = json_data.get('amount', 'Amount TBA')
        generated_title = f"{title} – {location} ({amount})"
        
        logger.info(f"✅ Successfully generated blog post for opportunity ID: {opportunity_id}")
        
        return GenerateBlogResponse(
            success=True,
            opportunity_id=opportunity_id,
            title=generated_title,
            blog_post=blog_content,
            message="Blog post generated successfully"
        )
        
    except Exception as e:
        logger.error(f"🔴 Error generating blog post for opportunity ID {request.opportunity_id}: {str(e)}")
        return GenerateBlogResponse(
            success=False,
            message=f"Failed to generate blog post: {str(e)}"
        )

@router.get("/requirement/opportunities", response_model=list[FundingOpportunityResponse])
async def get_funding_opportunities(
    skip: int = 0,
    limit: int = 50,
    status_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Get list of funding opportunities with optional filtering
    """
    try:
        query = db.query(FundingOpportunity)
        
        if status_filter:
            try:
                status_enum = StatusEnum(status_filter)
                query = query.filter(FundingOpportunity.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter. Valid options: {[s.value for s in StatusEnum]}"
                )
        
        opportunities = query.offset(skip).limit(limit).all()
        logger.info(f"📋 Retrieved {len(opportunities)} funding opportunities (skip={skip}, limit={limit})")
        
        return [serialize_opportunity_with_variants(opp) for opp in opportunities]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Error fetching funding opportunities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch funding opportunities: {str(e)}"
        )

@router.get("/requirement/opportunities/{opportunity_id}", response_model=FundingOpportunityResponse)
async def get_funding_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific funding opportunity by ID
    """
    try:
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == opportunity_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {opportunity_id} not found"
            )
        
        logger.info(f"📋 Retrieved funding opportunity ID: {opportunity_id}")
        return serialize_opportunity_with_variants(opportunity)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Error fetching funding opportunity {opportunity_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch funding opportunity: {str(e)}"
        )

@router.put("/requirement/opportunities/{opportunity_id}", response_model=FundingOpportunityResponse)
async def update_funding_opportunity(
    opportunity_id: int,
    updates: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Update a funding opportunity (for QA editing)
    """
    try:
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == opportunity_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {opportunity_id} not found"
            )
        
        # Update allowed fields
        if 'editable_text' in updates:
            opportunity.editable_text = updates['editable_text']
            logger.info(f"📝 Updated editable_text for opportunity {opportunity_id}")
        
        if 'status' in updates:
            try:
                new_status = StatusEnum(updates['status'])
                opportunity.status = new_status
                logger.info(f"📊 Updated status to {new_status.value} for opportunity {opportunity_id}")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Valid options: {[s.value for s in StatusEnum]}"
                )
        
        if 'json_data' in updates:
            opportunity.json_data = updates['json_data']
            logger.info(f"📋 Updated JSON data for opportunity {opportunity_id}")
        
        db.commit()
        db.refresh(opportunity)
        
        logger.info(f"✅ Successfully updated funding opportunity {opportunity_id}")
        return serialize_opportunity_with_variants(opportunity)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Error updating funding opportunity {opportunity_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update funding opportunity: {str(e)}"
        )

@router.delete("/requirement/opportunities/{opportunity_id}")
async def delete_funding_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a funding opportunity
    """
    try:
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == opportunity_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {opportunity_id} not found"
            )
        
        db.delete(opportunity)
        db.commit()
        
        logger.info(f"🗑️ Successfully deleted funding opportunity {opportunity_id}")
        return {"message": f"Funding opportunity {opportunity_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Error deleting funding opportunity {opportunity_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete funding opportunity: {str(e)}"
        )

# Legacy endpoints for backward compatibility and testing
@router.post("/requirement/parse-text")
async def parse_text_content(data: Dict[str, Any]):
    """
    Parse funding opportunity from raw text content (for testing and debugging)
    Note: This endpoint does not save to database
    """
    try:
        if "text" not in data:
            raise HTTPException(status_code=400, detail="'text' field is required")
        
        from utils.openai_parser import parse_funding_opportunity
        
        text = data["text"]
        test_url = data.get("url", "text-input-test")
        
        logger.info(f"🧪 Testing enhanced text parsing for: {test_url}")
        
        # Parse the text using enhanced method (returns JSON string)
        json_response = parse_funding_opportunity(text, test_url)
        parsed_data = json.loads(json_response)
        
        # Extract QA metadata
        confidence_score = parsed_data.get('_confidence_score', 0.0)
        extraction_warning = parsed_data.get('_extraction_warning')
        
        return {
            "success": True,
            "message": f"Text parsing completed with {confidence_score}% confidence",
            "extracted_data": {k: v for k, v in parsed_data.items() if not k.startswith('_')},
            "confidence_score": confidence_score,
            "qa_warning": extraction_warning
        }
        
    except Exception as e:
        logger.error(f"🔴 Text parsing error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse text content: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Enhanced health check endpoint with database and parser validation"""
    try:
        from utils.openai_parser import parse_funding_opportunity
        
        # Test basic parser functionality
        test_text = "Sample Grant Program - £10,000 available for UK charities working with young people. Deadline: March 2024."
        result = parse_funding_opportunity(test_text, "health-check-test")
        
        return {
            "status": "healthy", 
            "message": "Requirement Agent API is running with enhanced parser and database",
            "parser_status": "operational" if result else "warning",
            "database_status": "connected"
        }
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "message": "API running but some components may have issues",
            "error": str(e)
        }

@router.get("/parser/info")
async def get_parser_info():
    """Get information about the enhanced parser capabilities and database integration"""
    return {
        "parser_version": "2.0-enhanced-with-database",
        "extraction_method": "OpenAI GPT-3.5-turbo with comprehensive validation",
        "database_integration": "PostgreSQL with SQLAlchemy ORM",
        "supported_sources": [
            "UK Government funding portals",
            "Foundation websites", 
            "CSR funding pages",
            "Grant databases",
            "General funding opportunity websites"
        ],
        "output_fields": {
            "required": ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"],
            "optional": ["duration", "how_to_apply", "published_date", "contact_info"],
            "meta": ["opportunity_url"]
        },
        "qa_features": [
            "Confidence scoring",
            "Missing field detection", 
            "Low quality data warnings",
            "Comprehensive logging for QA team",
            "Database storage with status tracking"
        ],
        "database_features": [
            "Duplicate URL detection",
            "JSON data storage",
            "Status workflow (raw → reviewed → approved/rejected)",
            "QA editing capabilities",
            "Audit trail with timestamps"
        ]
    }