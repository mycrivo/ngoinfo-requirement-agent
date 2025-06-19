from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any

from db import get_db
from models import FundingOpportunity, StatusEnum

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["qa-admin"])

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

@router.get("/qa-review", response_class=HTMLResponse)
async def qa_review_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    QA Review Dashboard - Display all raw funding opportunities for review
    """
    try:
        # Fetch all funding opportunities with status = "raw"
        raw_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.raw
        ).order_by(FundingOpportunity.created_at.desc()).all()
        
        logger.info(f"📋 Retrieved {len(raw_opportunities)} raw funding opportunities for QA review")
        
        # Extract relevant fields for the template
        opportunities_data = []
        for opp in raw_opportunities:
            # Safely extract JSON data fields
            json_data = opp.json_data or {}
            
            opportunity_data = {
                "id": opp.id,
                "title": json_data.get("title", "No Title"),
                "donor": json_data.get("donor", "Unknown Donor"),
                "deadline": json_data.get("deadline", "No Deadline"),
                "themes": json_data.get("themes", []),
                "editable_text": opp.editable_text or "",
                "source_url": opp.source_url,
                "created_at": opp.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "confidence_score": json_data.get("_confidence_score", 0),
                "extraction_warning": json_data.get("_extraction_warning", ""),
                "missing_required": json_data.get("_missing_required", [])
            }
            
            # Format themes as string if it's a list
            if isinstance(opportunity_data["themes"], list):
                opportunity_data["themes_display"] = ", ".join(opportunity_data["themes"])
            else:
                opportunity_data["themes_display"] = str(opportunity_data["themes"])
            
            opportunities_data.append(opportunity_data)
        
        # Render the template
        return templates.TemplateResponse(
            "qa_review.html",
            {
                "request": request,
                "opportunities": opportunities_data,
                "total_count": len(opportunities_data),
                "page_title": "QA Review Dashboard"
            }
        )
        
    except Exception as e:
        logger.error(f"🔴 Error in QA review dashboard: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load QA review dashboard: {str(e)}"
        )

@router.post("/qa-review/update")
async def update_qa_review(
    id: int = Form(...),
    editable_text: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Update QA review - Update editable_text and set status to reviewed
    """
    try:
        logger.info(f"🔄 Processing QA update for opportunity ID: {id}")
        
        # Fetch the funding opportunity record
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == id
        ).first()
        
        if not opportunity:
            logger.error(f"🔴 Funding opportunity with ID {id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Funding opportunity with ID {id} not found"
            )
        
        # Update the fields
        opportunity.editable_text = editable_text
        opportunity.status = StatusEnum.reviewed
        
        # Commit the changes
        db.commit()
        db.refresh(opportunity)
        
        logger.info(f"✅ Successfully updated opportunity ID {id} - status changed to 'reviewed'")
        
        # Redirect back to the QA review dashboard
        return RedirectResponse(
            url="/admin/qa-review",
            status_code=303  # POST redirect
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Error updating QA review for ID {id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update QA review: {str(e)}"
        ) 