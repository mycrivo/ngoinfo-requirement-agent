from fastapi import APIRouter, HTTPException, Depends, status, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

# Database imports
from db import get_db
from models import FundingOpportunity, ProposalTemplate, TemplateStatusEnum, StatusEnum
from schemas import CreateProposalTemplateRequest, ProposalTemplateResponse
from utils.auth import require_admin_auth
from services.template_generator import ProposalTemplateGenerator, TemplateBuildError, PDFGenerationError
from services.storage import storage_service, StorageError

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/templates", tags=["templates"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

class TemplateService:
    """Service for managing proposal templates"""
    
    def __init__(self):
        self.generator = ProposalTemplateGenerator()
    
    def generate_template(
        self, 
        opportunity_id: int, 
        sections: list, 
        funder_notes: Optional[str] = None,
        hints: Optional[Dict[str, str]] = None,
        force_regenerate: bool = False,
        db: Session = None
    ) -> Dict[str, Any]:
        """Generate proposal template with deduplication"""
        try:
            # Fetch opportunity
            opportunity = db.query(FundingOpportunity).filter(
                FundingOpportunity.id == opportunity_id
            ).first()
            
            if not opportunity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Funding opportunity with ID {opportunity_id} not found"
                )
            
            # Check if opportunity is approved
            if opportunity.status != StatusEnum.approved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Opportunity must be approved before creating proposal template. Current status: {opportunity.status.value}"
                )
            
            # Extract opportunity data
            opportunity_data = opportunity.json_data or {}
            opportunity_data['id'] = opportunity.id
            opportunity_data['source_url'] = opportunity.source_url
            opportunity_data['opportunity_url'] = opportunity_data.get('opportunity_url', opportunity.source_url)
            
            # Convert sections to dict format
            sections_data = [
                {
                    "heading": section.heading,
                    "instruction": section.instruction
                }
                for section in sections
            ]
            
            # Generate content model and compute hash
            content_model = self.generator.build_content_model(
                opportunity_data, sections_data, funder_notes, hints
            )
            content_hash = content_model.compute_hash()
            
            # Check for existing template (unless force regenerate)
            if not force_regenerate:
                existing_template = db.query(ProposalTemplate).filter(
                    and_(
                        ProposalTemplate.funding_opportunity_id == opportunity_id,
                        ProposalTemplate.hash == content_hash
                    )
                ).first()
                
                if existing_template:
                    # Check if files still exist
                    docx_exists = storage_service.exists(existing_template.docx_path) if existing_template.docx_path else False
                    pdf_exists = storage_service.exists(existing_template.pdf_path) if existing_template.pdf_path else False
                    
                    if docx_exists:
                        logger.info(f"🔄 Reusing existing template {existing_template.id} for opportunity {opportunity_id}")
                        
                        return {
                            "template_id": existing_template.id,
                            "docx_url": f"/api/templates/{existing_template.id}/download?format=docx",
                            "pdf_url": f"/api/templates/{existing_template.id}/download?format=pdf" if pdf_exists else None,
                            "status": existing_template.status.value,
                            "hash": existing_template.hash,
                            "generated_at": existing_template.created_at.isoformat(),
                            "is_existing": True
                        }
            
            # Generate new template
            logger.info(f"🚀 Generating new template for opportunity {opportunity_id}")
            
            # Generate DOCX and PDF
            content_model, docx_bytes, pdf_bytes = self.generator.generate_template(
                opportunity_data, sections_data, funder_notes, hints
            )
            
            # Save files to storage
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = "".join(c for c in opportunity_data.get('title', 'Unknown') if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            
            # Save DOCX
            docx_filename = f"proposal_template_{safe_title}_{timestamp}.docx"
            docx_path = f"templates/{opportunity_id}/{docx_filename}"
            docx_storage_path = storage_service.save_bytes(docx_path, docx_bytes)
            
            # Save PDF if available
            pdf_storage_path = None
            if pdf_bytes:
                pdf_filename = f"proposal_template_{safe_title}_{timestamp}.pdf"
                pdf_path = f"templates/{opportunity_id}/{pdf_filename}"
                pdf_storage_path = storage_service.save_bytes(pdf_path, pdf_bytes)
            
            # Determine status
            if pdf_bytes:
                template_status = TemplateStatusEnum.ready
            else:
                template_status = TemplateStatusEnum.pending
            
            # Save to database
            template = ProposalTemplate(
                funding_opportunity_id=opportunity_id,
                docx_path=docx_storage_path,
                pdf_path=pdf_storage_path,
                status=template_status,
                hash=content_hash,
                notes=f"Generated with {len(sections_data)} sections"
            )
            
            db.add(template)
            db.commit()
            db.refresh(template)
            
            logger.info(f"✅ Template {template.id} generated and saved successfully")
            
            return {
                "template_id": template.id,
                "docx_url": f"/api/templates/{template.id}/download?format=docx",
                "pdf_url": f"/api/templates/{template.id}/download?format=pdf" if pdf_bytes else None,
                "status": template.status.value,
                "hash": template.hash,
                "generated_at": template.created_at.isoformat(),
                "is_existing": False
            }
            
        except TemplateBuildError as e:
            logger.error(f"❌ Template build failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Template generation failed: {str(e)}"
            )
        except StorageError as e:
            logger.error(f"❌ Storage error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage operation failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error in template generation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Template generation failed: {str(e)}"
            )

# Global service instance
template_service = TemplateService()

@router.post("/generate", response_model=ProposalTemplateResponse)
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def generate_template(
    request: CreateProposalTemplateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth),
    req: Request = None
):
    """
    Generate a proposal template with deduplication
    """
    try:
        logger.info(f"🚀 Template generation request from user {current_user} for opportunity {request.record_id}")
        
        # Validate sections
        if not request.sections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one section is required to generate a proposal template"
            )
        
        # Generate template
        result = template_service.generate_template(
            opportunity_id=request.record_id,
            sections=request.sections,
            funder_notes=request.funder_notes,
            db=db
        )
        
        # Build response
        response = ProposalTemplateResponse(
            success=True,
            message=f"Successfully generated proposal template with {len(request.sections)} sections",
            filename=f"template_{result['template_id']}",
            download_url=result['docx_url'],
            timestamp=result['generated_at'],
            opportunity_title="Generated Template"  # Will be populated from opportunity data
        )
        
        # Add additional fields
        response.template_id = result['template_id']
        response.pdf_url = result['pdf_url']
        response.status = result['status']
        response.hash = result['hash']
        response.is_existing = result['is_existing']
        
        logger.info(f"✅ Template generation completed successfully for user {current_user}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Template generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template generation failed: {str(e)}"
        )

@router.get("/{template_id}")
async def get_template_metadata(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Get template metadata (RBAC: admin only)
    """
    try:
        template = db.query(ProposalTemplate).filter(
            ProposalTemplate.id == template_id
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found"
            )
        
        # Get opportunity info
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == template.funding_opportunity_id
        ).first()
        
        return {
            "template_id": template.id,
            "opportunity_id": template.funding_opportunity_id,
            "opportunity_title": opportunity.json_data.get('title', 'Unknown') if opportunity and opportunity.json_data else 'Unknown',
            "status": template.status.value,
            "docx_path": template.docx_path,
            "pdf_path": template.pdf_path,
            "hash": template.hash,
            "notes": template.notes,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get template metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template metadata: {str(e)}"
        )

@router.get("/{template_id}/download")
async def download_template(
    template_id: int,
    format: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Download template file (DOCX or PDF)
    """
    try:
        # Validate format
        if format not in ['docx', 'pdf']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be 'docx' or 'pdf'"
            )
        
        # Get template
        template = db.query(ProposalTemplate).filter(
            ProposalTemplate.id == template_id
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found"
            )
        
        # Determine file path and MIME type
        if format == 'docx':
            if not template.docx_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="DOCX file not available for this template"
                )
            file_path = template.docx_path
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            filename = f"proposal_template_{template_id}.docx"
        else:  # PDF
            if not template.pdf_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDF file not available for this template"
                )
            file_path = template.pdf_path
            mime_type = 'application/pdf'
            filename = f"proposal_template_{template_id}.pdf"
        
        # Check if file exists in storage
        if not storage_service.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template file not found in storage"
            )
        
        # Read file data
        file_data = storage_service.open(file_path)
        
        logger.info(f"📥 Template {template_id} {format} downloaded by user {current_user}")
        
        # Return streaming response
        return StreamingResponse(
            iter([file_data]),
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Template download failed: {e}")
        raise HTTPException(
            status_code=status.HTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template download failed: {str(e)}"
        )

@router.post("/{template_id}/regenerate")
@limiter.limit("5/minute")  # Rate limit: 5 regenerations per minute
async def regenerate_template(
    template_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth),
    req: Request = None
):
    """
    Force regenerate template (admin only)
    """
    try:
        logger.info(f"🔄 Template regeneration request from user {current_user} for template {template_id}")
        
        # Get existing template
        template = db.query(ProposalTemplate).filter(
            ProposalTemplate.id == template_id
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with ID {template_id} not found"
            )
        
        # Get opportunity
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == template.funding_opportunity_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated funding opportunity not found"
            )
        
        # Extract sections from existing template (you might want to store this in the template)
        # For now, we'll use default sections
        default_sections = [
            {"heading": "Executive Summary", "instruction": "Provide a concise overview of your proposal"},
            {"heading": "Organization Background", "instruction": "Describe your organization and its capabilities"},
            {"heading": "Problem Statement", "instruction": "Explain the problem or need your project addresses"},
            {"heading": "Objectives & Outcomes", "instruction": "Define your project objectives and expected outcomes"},
            {"heading": "Activities & Workplan", "instruction": "Detail the activities and timeline for your project"},
            {"heading": "Monitoring & Evaluation", "instruction": "Explain how you will monitor progress and evaluate success"},
            {"heading": "Budget Summary", "instruction": "Provide a summary of your project budget"},
            {"heading": "Sustainability & Risk", "instruction": "Address project sustainability and risk mitigation"}
        ]
        
        # Regenerate with force flag
        result = template_service.generate_template(
            opportunity_id=template.funding_opportunity_id,
            sections=default_sections,
            funder_notes=None,  # Could be stored in template
            force_regenerate=True,
            db=db
        )
        
        logger.info(f"✅ Template {template_id} regenerated successfully by user {current_user}")
        
        return {
            "success": True,
            "message": "Template regenerated successfully",
            "new_template_id": result['template_id'],
            "status": result['status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Template regeneration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template regeneration failed: {str(e)}"
        )

# Add rate limit exceeded handler
@router.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please try again later."
    )

