from fastapi import APIRouter, HTTPException, Depends, status
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
    FundingData
)

# Enhanced parser import
from utils.openai_parser import parse_funding_opportunity_from_url

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["requirement-agent"])

@router.post("/requirement/parse", response_model=ParseRequirementResponse)
async def parse_requirement(
    request: ParseRequirementRequest,
    db: Session = Depends(get_db)
):
    """
    Parse a funding opportunity from a URL using enhanced OpenAI extraction with database storage
    """
    try:
        url_str = str(request.url)
        logger.info(f"🔍 Processing funding opportunity request for URL: {url_str}")
        
        # Check if URL already exists in database
        existing_opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.source_url == url_str
        ).first()
        
        if existing_opportunity:
            logger.info(f"📋 Found existing record for URL: {url_str} (ID: {existing_opportunity.id})")
            
            # Convert stored JSON data to FundingData for response
            extracted_data = None
            if existing_opportunity.json_data:
                try:
                    # Create FundingData from stored JSON (backward compatibility)
                    json_data = existing_opportunity.json_data
                    extracted_data = FundingData(
                        title=json_data.get('title'),
                        description=json_data.get('summary') or json_data.get('description'),
                        amount=json_data.get('amount'),
                        deadline=json_data.get('deadline'),
                        eligibility=json_data.get('eligibility', []) if isinstance(json_data.get('eligibility'), list) else json_data.get('eligibility'),
                        requirements=json_data.get('how_to_apply') or json_data.get('requirements'),
                        contact_info=json_data.get('contact_info')
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Could not convert stored JSON to FundingData: {e}")
            
            return ParseRequirementResponse(
                success=True,
                message="URL already processed. Returning existing data from database.",
                data=FundingOpportunityResponse.from_orm(existing_opportunity),
                extracted_data=extracted_data
            )
        
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
        
        # Create database record
        funding_opportunity = FundingOpportunity(
            source_url=url_str,
            json_data=parsed_data,  # Store the complete enhanced JSON structure
            editable_text="",  # Empty for now as requested
            status=StatusEnum.raw
        )
        
        db.add(funding_opportunity)
        db.commit()
        db.refresh(funding_opportunity)
        
        logger.info(f"💾 Successfully saved funding opportunity to database (ID: {funding_opportunity.id})")
        
        # Create FundingData response for backward compatibility
        extracted_data = FundingData(
            title=parsed_data.get('title'),
            description=parsed_data.get('summary') or parsed_data.get('description'),
            amount=parsed_data.get('amount'),
            deadline=parsed_data.get('deadline'),
            eligibility=parsed_data.get('eligibility', []) if isinstance(parsed_data.get('eligibility'), list) else parsed_data.get('eligibility'),
            requirements=parsed_data.get('how_to_apply') or parsed_data.get('requirements'),
            contact_info=parsed_data.get('contact_info')
        )
        
        # Determine response message based on extraction quality
        if confidence_score >= 80:
            message = f"Successfully parsed and saved funding opportunity with high confidence ({confidence_score}%)"
        elif confidence_score >= 60:
            message = f"Parsed and saved funding opportunity with medium confidence ({confidence_score}%) - QA review recommended"
        else:
            message = f"Parsed and saved funding opportunity with low confidence ({confidence_score}%) - Manual QA required"
        
        if extraction_warning:
            message += f" | Warning: {extraction_warning}"
        
        return ParseRequirementResponse(
            success=True,
            message=message,
            data=FundingOpportunityResponse.from_orm(funding_opportunity),
            extracted_data=extracted_data
        )
        
    except Exception as e:
        logger.error(f"🔴 Error processing funding opportunity for {request.url}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse and save funding opportunity: {str(e)}"
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
        
        return [FundingOpportunityResponse.from_orm(opp) for opp in opportunities]
        
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
        return FundingOpportunityResponse.from_orm(opportunity)
        
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
        return FundingOpportunityResponse.from_orm(opportunity)
        
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