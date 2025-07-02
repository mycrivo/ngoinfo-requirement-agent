from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE

# Database imports
from db import get_db
from models import FundingOpportunity, StatusEnum
from schemas import CreateProposalTemplateRequest, ProposalTemplateResponse
from utils.auth import require_admin_auth

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["proposal-template"])

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

class ProposalTemplateGenerator:
    """Service for generating proposal template documents"""
    
    def __init__(self):
        self.templates_dir = "static/templates"
        os.makedirs(self.templates_dir, exist_ok=True)
    
    def create_proposal_template(
        self, 
        opportunity_data: Dict[str, Any],
        sections: list,
        funder_notes: Optional[str] = None
    ) -> str:
        """
        Create a .docx proposal template with opportunity context and QA-defined sections
        
        Args:
            opportunity_data: Funding opportunity data for context
            sections: List of sections with heading and instruction
            funder_notes: Optional funder-specific notes
            
        Returns:
            str: Filename of the generated document
        """
        try:
            # Create new document
            doc = Document()
            
            # Add title
            title = opportunity_data.get('title', 'Funding Opportunity Proposal')
            title_paragraph = doc.add_heading(f"Proposal Template: {title}", 0)
            title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            
            # Add opportunity metadata section
            doc.add_heading('Opportunity Information', level=1)
            
            # Create opportunity details table
            table = doc.add_table(rows=0, cols=2)
            table.style = 'Table Grid'
            
            # Add opportunity details
            metadata_fields = [
                ('Donor/Funder', opportunity_data.get('donor', 'Not specified')),
                ('Deadline', opportunity_data.get('deadline', 'Not specified')),
                ('Funding Amount', opportunity_data.get('amount', 'Not specified')),
                ('Location/Eligibility', opportunity_data.get('location', 'Not specified')),
                ('Themes/Focus Areas', ', '.join(opportunity_data.get('themes', [])) if isinstance(opportunity_data.get('themes'), list) else opportunity_data.get('themes', 'Not specified')),
                ('Opportunity URL', opportunity_data.get('opportunity_url', 'Not provided'))
            ]
            
            for label, value in metadata_fields:
                row_cells = table.add_row().cells
                row_cells[0].text = label
                row_cells[0].paragraphs[0].runs[0].bold = True
                row_cells[1].text = str(value)
            
            # Add some spacing
            doc.add_paragraph('')
            
            # Add funder notes if provided
            if funder_notes and funder_notes.strip():
                doc.add_heading('Funder Requirements & Notes', level=1)
                funder_para = doc.add_paragraph(funder_notes.strip())
                funder_para.style = 'Intense Quote'
                doc.add_paragraph('')
            
            # Add instruction paragraph
            instruction_para = doc.add_paragraph()
            instruction_para.add_run('Instructions: ').bold = True
            instruction_para.add_run('This template provides the structure for your proposal. Replace the instructional text below with your actual content. Each section includes guidance on what to include.')
            doc.add_paragraph('')
            
            # Add user-defined sections
            doc.add_heading('Proposal Sections', level=1)
            
            for i, section in enumerate(sections, 1):
                # Add section heading
                section_heading = doc.add_heading(f"{i}. {section['heading']}", level=2)
                
                # Add instruction as placeholder text
                instruction_para = doc.add_paragraph()
                instruction_para.add_run('[INSTRUCTION] ').bold = True
                instruction_para.add_run(section['instruction'])
                instruction_para.style = 'Subtle Emphasis'
                
                # Add placeholder for actual content
                content_para = doc.add_paragraph()
                content_para.add_run('[Your content for this section goes here]')
                content_para.style = 'Quote'
                
                # Add spacing between sections
                doc.add_paragraph('')
            
            # Add footer with generation info
            doc.add_page_break()
            footer_heading = doc.add_heading('Template Information', level=2)
            footer_para = doc.add_paragraph()
            footer_para.add_run('Generated: ').bold = True
            footer_para.add_run(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            footer_para.add_run('\nBy: ').bold = True
            footer_para.add_run('ReqAgent Proposal Template Generator')
            footer_para.add_run('\nOpportunity Source: ').bold = True
            footer_para.add_run(opportunity_data.get('opportunity_url', 'Not provided'))
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            filename = f"proposal_template_{safe_title}_{timestamp}.docx"
            filepath = os.path.join(self.templates_dir, filename)
            
            # Save document
            doc.save(filepath)
            
            logger.info(f"✅ Generated proposal template: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ Failed to generate proposal template: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate proposal template: {str(e)}"
            )

@router.get("/proposal-template/start", response_class=HTMLResponse)
async def proposal_template_start(
    request: Request,
    record_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Display the proposal template creation form
    """
    try:
        opportunity_data = None
        
        # If record_id is provided, fetch the opportunity data
        if record_id:
            opportunity = db.query(FundingOpportunity).filter(
                FundingOpportunity.id == record_id
            ).first()
            
            if not opportunity:
                raise HTTPException(
                    status_code=404,
                    detail=f"Funding opportunity with ID {record_id} not found"
                )
            
            # Check if opportunity is approved
            if opportunity.status != StatusEnum.approved:
                raise HTTPException(
                    status_code=400,
                    detail=f"Opportunity must be approved before creating proposal template. Current status: {opportunity.status.value}"
                )
            
            opportunity_data = {
                "id": opportunity.id,
                "title": opportunity.json_data.get('title', 'Unknown') if opportunity.json_data else 'Unknown',
                "donor": opportunity.json_data.get('donor', 'Unknown') if opportunity.json_data else 'Unknown',
                "deadline": opportunity.json_data.get('deadline', 'Unknown') if opportunity.json_data else 'Unknown',
                "amount": opportunity.json_data.get('amount', 'Unknown') if opportunity.json_data else 'Unknown',
                "themes": opportunity.json_data.get('themes', []) if opportunity.json_data else [],
                "location": opportunity.json_data.get('location', 'Unknown') if opportunity.json_data else 'Unknown',
                "opportunity_url": opportunity.json_data.get('opportunity_url', opportunity.source_url) if opportunity.json_data else opportunity.source_url
            }
        
        # Get all approved opportunities for selection
        approved_opportunities = db.query(FundingOpportunity).filter(
            FundingOpportunity.status == StatusEnum.approved
        ).order_by(FundingOpportunity.created_at.desc()).limit(50).all()
        
        opportunities_list = []
        for opp in approved_opportunities:
            opp_data = {
                "id": opp.id,
                "title": opp.json_data.get('title', 'Unknown') if opp.json_data else 'Unknown',
                "donor": opp.json_data.get('donor', 'Unknown') if opp.json_data else 'Unknown',
                "created_at": opp.created_at.strftime("%Y-%m-%d")
            }
            opportunities_list.append(opp_data)
        
        return templates.TemplateResponse(
            "proposal_template_form.html",
            {
                "request": request,
                "opportunity": opportunity_data,
                "opportunities": opportunities_list,
                "current_user": current_user,
                "page_title": "Create Proposal Template"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in proposal template start: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load proposal template form: {str(e)}"
        )

@router.post("/proposal-template/generate", response_model=ProposalTemplateResponse)
async def generate_proposal_template(
    request: CreateProposalTemplateRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Generate a .docx proposal template based on QA-defined sections
    """
    try:
        logger.info(f"🚀 Generating proposal template for record ID: {request.record_id} (User: {current_user})")
        
        # Fetch the funding opportunity
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == request.record_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=404,
                detail=f"Funding opportunity with ID {request.record_id} not found"
            )
        
        # Check if opportunity is approved
        if opportunity.status != StatusEnum.approved:
            raise HTTPException(
                status_code=400,
                detail=f"Opportunity must be approved before creating proposal template. Current status: {opportunity.status.value}"
            )
        
        # Extract opportunity data
        opportunity_data = opportunity.json_data or {}
        opportunity_data['opportunity_url'] = opportunity_data.get('opportunity_url', opportunity.source_url)
        
        # Validate sections
        if not request.sections:
            raise HTTPException(
                status_code=400,
                detail="At least one section is required to generate a proposal template"
            )
        
        # Convert sections to dict format
        sections_data = [
            {
                "heading": section.heading,
                "instruction": section.instruction
            }
            for section in request.sections
        ]
        
        # Generate the template
        generator = ProposalTemplateGenerator()
        filename = generator.create_proposal_template(
            opportunity_data=opportunity_data,
            sections=sections_data,
            funder_notes=request.funder_notes
        )
        
        # Create download URL
        download_url = f"/admin/proposal-template/download/{filename}"
        
        return ProposalTemplateResponse(
            success=True,
            message=f"Successfully generated proposal template with {len(sections_data)} sections",
            filename=filename,
            download_url=download_url,
            timestamp=datetime.now().isoformat(),
            opportunity_title=opportunity_data.get('title', 'Unknown Opportunity')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating proposal template: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate proposal template: {str(e)}"
        )

@router.get("/proposal-template/download/{filename}")
async def download_proposal_template(
    filename: str,
    current_user: str = Depends(require_admin_auth)
):
    """
    Download a generated proposal template
    """
    try:
        file_path = os.path.join("static/templates", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail="Template file not found"
            )
        
        logger.info(f"📥 Downloading proposal template: {filename} (User: {current_user})")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading template: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download template: {str(e)}"
        ) 