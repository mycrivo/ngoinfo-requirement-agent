from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any

from db import get_db
from models import FundingOpportunity, StatusEnum
from utils.auth import (
    verify_admin_credentials,
    is_logged_in,
    create_admin_session,
    clear_admin_session,
    require_login,
    get_current_admin,
    get_csrf_token,
    verify_csrf_token
)
from utils.feedback_service import FeedbackService
from utils.migrate import run_migrations, check_migration_status
from schemas import QAUpdateRequest, FeedbackResponse

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["qa-admin"])

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """
    Admin login page
    """
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error if error else None
        }
    )

@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """
    Process admin login using environment variables
    """
    try:
        # Verify credentials against environment variables
        if verify_admin_credentials(email, password):
            # Create session
            create_admin_session(request)
            
            # Redirect to dashboard
            response = RedirectResponse(
                url="/admin/dashboard",
                status_code=303
            )
            
            logger.info(f"✅ Admin login successful for: {email}")
            return response
        else:
            logger.warning(f"❌ Failed login attempt for: {email}")
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "Invalid email or password",
                    "email": email
                }
            )
    except Exception as e:
        logger.error(f"🔴 Error during login: {str(e)}")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "An error occurred during login",
                "email": email
            }
        )

@router.get("/logout")
async def logout(request: Request):
    """
    Admin logout - clear session and redirect to login
    """
    clear_admin_session(request)
    response = RedirectResponse(url="/admin/login", status_code=303)
    logger.info("🔓 Admin logout successful")
    return response

@router.get("/migrations", response_class=HTMLResponse)
@require_login
async def migration_dashboard(request: Request):
    """
    Migration management dashboard - shows current status and allows retry
    """
    try:
        # Get current migration status
        status = check_migration_status()
        
        return templates.TemplateResponse(
            "migrations.html",
            {
                "request": request,
                "status": status,
                "csrf_token": get_csrf_token(request)
            }
        )
    except Exception as e:
        logger.error(f"🔴 Error loading migration dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load migration status")

@router.post("/migrations/retry")
@require_login
async def retry_migrations(request: Request):
    """
    Retry failed migrations
    """
    try:
        # Verify CSRF token
        if not verify_csrf_token(request):
            raise HTTPException(status_code=400, detail="Invalid CSRF token")
        
        logger.info("🔄 Admin requested migration retry")
        
        # Run migrations
        success = run_migrations()
        
        if success:
            logger.info("✅ Migration retry successful")
            return {"success": True, "message": "Migrations completed successfully"}
        else:
            logger.error("❌ Migration retry failed")
            return {"success": False, "message": "Migration retry failed"}
            
    except Exception as e:
        logger.error(f"🔴 Error during migration retry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration retry failed: {str(e)}")

@router.get("/qa-review", response_class=HTMLResponse)
async def qa_review_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    QA Review Dashboard - Display all raw funding opportunities for review
    """
    try:
        # Fetch all funding opportunities with status = "raw"
        raw_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.raw
        ).order_by(FundingOpportunity.created_at.desc()).all()
        
        current_user = get_current_admin(request)
        logger.info(f"📋 Retrieved {len(raw_opportunities)} raw funding opportunities for QA review (User: {current_user})")
        
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
                "variants": opp.variants or [],
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
                "page_title": "QA Review Dashboard",
                "current_user": current_user
            }
        )
        
    except HTTPException as e:
        if e.status_code == 302:
            # Redirect to login
            return RedirectResponse(url="/admin/login", status_code=302)
        raise
    except Exception as e:
        logger.error(f"🔴 Error in QA review dashboard: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load QA review dashboard: {str(e)}"
        )

@router.post("/qa-review/update")
async def update_qa_review(
    request: Request,
    id: int = Form(...),
    editable_text: str = Form(...),
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    Update QA review - Update editable_text and set status to reviewed
    """
    try:
        current_user = get_current_admin(request)
        logger.info(f"🔄 Processing QA update for opportunity ID: {id} (User: {current_user})")
        
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
        
        logger.info(f"✅ Successfully updated opportunity ID {id} - status changed to 'reviewed' (User: {current_user})")
        
        # Redirect back to the QA review dashboard
        return RedirectResponse(
            url="/admin/qa-review",
            status_code=303  # POST redirect
        )
        
    except HTTPException as e:
        if e.status_code == 302:
            # Redirect to login
            return RedirectResponse(url="/admin/login", status_code=302)
        raise
    except Exception as e:
        logger.error(f"🔴 Error updating QA review for ID {id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update QA review: {str(e)}"
        )

@router.post("/qa-review/update-with-feedback", response_model=FeedbackResponse)
async def update_qa_review_with_feedback(
    fastapi_request: Request,
    request: QAUpdateRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    Enhanced QA update that captures feedback on field changes
    """
    try:
        current_user = get_current_admin(fastapi_request)
        logger.info(f"🔄 Processing enhanced QA update for record ID: {request.record_id} (User: {current_user})")
        
        # Fetch the funding opportunity record
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == request.record_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=404,
                detail=f"Funding opportunity with ID {request.record_id} not found"
            )
        
        # Get original data for feedback comparison
        original_data = opportunity.json_data or {}
        
        # Capture feedback on field changes
        feedback_count = 0
        if request.field_updates and original_data:
            feedback_count = FeedbackService.capture_parsed_data_feedback(
                db=db,
                record_id=request.record_id,
                original_data=original_data,
                edited_data=request.field_updates,
                prompt_version=request.prompt_version or "v1.0"
            )
        
        # Update the JSON data with new field values
        if request.field_updates:
            updated_json_data = original_data.copy()
            updated_json_data.update(request.field_updates)
            opportunity.json_data = updated_json_data
        
        # Update editable text if provided
        if request.editable_text is not None:
            opportunity.editable_text = request.editable_text
        
        # Update status if provided
        if request.status:
            if request.status in ["raw", "reviewed", "approved", "rejected"]:
                opportunity.status = StatusEnum(request.status)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {request.status}"
                )
        
        # Commit changes
        db.commit()
        db.refresh(opportunity)
        
        logger.info(f"✅ Successfully updated record {request.record_id} with {feedback_count} feedback entries")
        
        return FeedbackResponse(
            success=True,
            message=f"Successfully updated record with {feedback_count} feedback entries captured",
            feedback_count=feedback_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in enhanced QA update: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update record: {str(e)}"
        )

@router.get("/feedback/stats")
async def get_feedback_statistics(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    Get feedback statistics for analysis
    """
    try:
        stats = FeedbackService.get_feedback_statistics(db)
        return {
            "success": True,
            "data": stats,
            "message": "Feedback statistics retrieved successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error getting feedback stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feedback statistics: {str(e)}"
        )

@router.get("/feedback/field/{field_name}")
async def get_field_feedback(
    request: Request,
    field_name: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    Get feedback for a specific field to analyze editing patterns
    """
    try:
        feedback = FeedbackService.get_field_feedback_summary(
            db=db,
            field_name=field_name,
            limit=limit
        )
        return {
            "success": True,
            "field_name": field_name,
            "feedback": feedback,
            "count": len(feedback),
            "message": f"Retrieved {len(feedback)} feedback entries for field '{field_name}'"
        }
    except Exception as e:
        logger.error(f"❌ Error getting field feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get field feedback: {str(e)}"
        )

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(require_login)
):
    """
    Main Admin Dashboard - Overview of all admin functions
    """
    try:
        current_user = get_current_admin(request)
        logger.info(f"📊 Loading admin dashboard for user: {current_user}")
        
        # Get statistics for dashboard
        total_opportunities = db.query(FundingOpportunity).count()
        raw_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.raw
        ).count()
        reviewed_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.reviewed
        ).count()
        approved_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.approved
        ).count()
        
        # Get recent opportunities
        recent_opportunities = db.query(FundingOpportunity).order_by(
            FundingOpportunity.created_at.desc()
        ).limit(5).all()
        
        recent_data = []
        for opp in recent_opportunities:
            json_data = opp.json_data or {}
            recent_data.append({
                "id": opp.id,
                "title": json_data.get("title", "Unknown"),
                "donor": json_data.get("donor", "Unknown"),
                "status": opp.status.value,
                "created_at": opp.created_at.strftime("%Y-%m-%d %H:%M")
            })
        
        # Get feedback statistics
        try:
            feedback_stats = FeedbackService.get_feedback_statistics(db)
        except:
            feedback_stats = {
                "parsed_data_feedback": {"total_edits": 0, "most_edited_fields": []},
                "post_edit_feedback": {"total_edits": 0, "most_edited_sections": []}
            }
        
        return templates.TemplateResponse(
            "admin_dashboard.html",
            {
                "request": request,
                "current_user": current_user,
                "page_title": "Admin Dashboard",
                "stats": {
                    "total_opportunities": total_opportunities,
                    "raw_opportunities": raw_opportunities,
                    "reviewed_opportunities": reviewed_opportunities,
                    "approved_opportunities": approved_opportunities
                },
                "recent_opportunities": recent_data,
                "feedback_stats": feedback_stats,
                "csrf_token": get_csrf_token(request)
            }
        )
        
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/admin/login", status_code=302)
        raise
    except Exception as e:
        logger.error(f"🔴 Error in admin dashboard: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load admin dashboard: {str(e)}"
        ) 