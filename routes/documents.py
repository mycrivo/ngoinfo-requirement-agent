from fastapi import APIRouter, HTTPException, Depends, status, Request, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
import os

# Database imports
from db import get_db
from models import Document, DocumentSourceEnum, OCRStatusEnum, FundingOpportunity, StatusEnum, ParsedDataFeedback
from schemas import CreateProposalTemplateRequest, ProposalTemplateResponse
from utils.auth import require_admin_auth
from services.storage import storage_service, StorageError
from services.pdf_extract import pdf_extractor, PDFExtractionError, PDFValidationError
from services.pdf_to_gold import pdf_to_gold_parser, ParsedOpportunity, PDFParseError

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

class DocumentService:
    """Service for managing document ingestion and processing"""
    
    def __init__(self):
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        self.max_upload_bytes = self.max_upload_mb * 1024 * 1024
    
    def ingest_pdf_url(self, url: str, funding_opportunity_id: Optional[int], db: Session) -> Dict[str, Any]:
        """Ingest PDF from URL"""
        try:
            logger.info(f"🚀 PDF URL ingestion request: {url}")
            
            # Check if already exists
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            existing_doc = db.query(Document).filter(Document.sha256 == url_hash).first()
            if existing_doc:
                logger.info(f"🔄 Reusing existing document {existing_doc.id} for URL {url}")
                return self._build_document_response(existing_doc, db)
            
            # Download and extract PDF
            extract_result = pdf_extractor.extract_from_url(url)
            
            # Parse to gold standard
            parsed_opportunity = pdf_to_gold_parser.parse_to_gold_standard(extract_result, url)
            
            # Store PDF and extracted text
            pdf_path = f"pdfs/{url_hash[:2]}/{url_hash}.pdf"
            text_path = f"pdfs/{url_hash[:2]}/{url_hash}.txt"
            
            # Note: We don't have the actual PDF bytes from URL extraction
            # In a real implementation, we'd need to download and store the PDF
            # For now, we'll create a placeholder document record
            
            # Create document record
            document = Document(
                source=DocumentSourceEnum.url,
                storage_path=pdf_path,
                mime="application/pdf",
                sha256=url_hash,
                pages=extract_result.pages,
                ocr_status=OCRStatusEnum.not_needed if not extract_result.ocr_used else OCRStatusEnum.done
            )
            
            # Link to funding opportunity if provided
            if funding_opportunity_id:
                document.funding_opportunity_id = funding_opportunity_id
                # Update opportunity with parsed data
                self._update_funding_opportunity(funding_opportunity_id, parsed_opportunity, db)
            else:
                # Create new funding opportunity
                new_opportunity = self._create_funding_opportunity(parsed_opportunity, url, db)
                document.funding_opportunity_id = new_opportunity.id
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"✅ PDF URL ingestion successful: document {document.id}")
            return self._build_document_response(document, db)
            
        except PDFValidationError as e:
            logger.error(f"❌ PDF validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF validation failed: {str(e)}"
            )
        except PDFExtractionError as e:
            logger.error(f"❌ PDF extraction error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF extraction failed: {str(e)}"
            )
        except PDFParseError as e:
            logger.error(f"❌ PDF parsing error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF parsing failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error in PDF URL ingestion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF ingestion failed: {str(e)}"
            )
    
    def ingest_pdf_upload(self, file: UploadFile, funding_opportunity_id: Optional[int], db: Session) -> Dict[str, Any]:
        """Ingest PDF from file upload"""
        try:
            logger.info(f"🚀 PDF upload ingestion request: {file.filename}")
            
            # Validate file
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only PDF files are allowed"
                )
            
            # Read file content
            pdf_bytes = file.file.read()
            if len(pdf_bytes) > self.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds maximum limit of {self.max_upload_mb}MB"
                )
            
            # Check if already exists
            file_hash = hashlib.sha256(pdf_bytes).hexdigest()
            existing_doc = db.query(Document).filter(Document.sha256 == file_hash).first()
            if existing_doc:
                logger.info(f"🔄 Reusing existing document {existing_doc.id} for file {file.filename}")
                return self._build_document_response(existing_doc, db)
            
            # Extract text from PDF
            extract_result = pdf_extractor.extract_from_bytes(pdf_bytes, file.filename)
            
            # Parse to gold standard
            parsed_opportunity = pdf_to_gold_parser.parse_to_gold_standard(extract_result, file.filename)
            
            # Store PDF and extracted text
            pdf_path = f"pdfs/{file_hash[:2]}/{file_hash}.pdf"
            text_path = f"pdfs/{file_hash[:2]}/{file_hash}.txt"
            
            try:
                # Save PDF to storage
                storage_service.save_bytes(pdf_path, pdf_bytes)
                
                # Save extracted text to storage
                text_bytes = extract_result.text.encode('utf-8')
                storage_service.save_bytes(text_path, text_bytes)
                
                logger.info(f"💾 Files saved to storage: {pdf_path}, {text_path}")
                
            except StorageError as e:
                logger.error(f"❌ Storage error: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save files: {str(e)}"
                )
            
            # Create document record
            document = Document(
                source=DocumentSourceEnum.upload,
                storage_path=pdf_path,
                mime="application/pdf",
                sha256=file_hash,
                pages=extract_result.pages,
                ocr_status=OCRStatusEnum.not_needed if not extract_result.ocr_used else OCRStatusEnum.done
            )
            
            # Link to funding opportunity if provided
            if funding_opportunity_id:
                document.funding_opportunity_id = funding_opportunity_id
                # Update opportunity with parsed data
                self._update_funding_opportunity(funding_opportunity_id, parsed_opportunity, db)
            else:
                # Create new funding opportunity
                new_opportunity = self._create_funding_opportunity(parsed_opportunity, file.filename, db)
                document.funding_opportunity_id = new_opportunity.id
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"✅ PDF upload ingestion successful: document {document.id}")
            return self._build_document_response(document, db)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in PDF upload ingestion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF ingestion failed: {str(e)}"
            )
    
    def _update_funding_opportunity(self, opportunity_id: int, parsed_opportunity: ParsedOpportunity, db: Session):
        """Update existing funding opportunity with parsed PDF data"""
        try:
            opportunity = db.query(FundingOpportunity).filter(FundingOpportunity.id == opportunity_id).first()
            if not opportunity:
                raise ValueError(f"Funding opportunity {opportunity_id} not found")
            
            # Update JSON data with parsed information
            if not opportunity.json_data:
                opportunity.json_data = {}
            
            # Merge parsed data, preferring existing data
            opportunity.json_data.update({
                "title": parsed_opportunity.title if parsed_opportunity.title != "Unknown" else opportunity.json_data.get("title", "Unknown"),
                "donor": parsed_opportunity.donor if parsed_opportunity.donor != "Unknown" else opportunity.json_data.get("donor", "Unknown"),
                "summary": parsed_opportunity.summary if parsed_opportunity.summary != "No summary available" else opportunity.json_data.get("summary", "No summary available"),
                "amount": parsed_opportunity.amount if parsed_opportunity.amount != "Unknown" else opportunity.json_data.get("amount", "Unknown"),
                "deadline": parsed_opportunity.deadline if parsed_opportunity.deadline != "Unknown" else opportunity.json_data.get("deadline", "Unknown"),
                "location": parsed_opportunity.location if parsed_opportunity.location != "Unknown" else opportunity.json_data.get("location", "Unknown"),
                "eligibility": parsed_opportunity.eligibility if parsed_opportunity.eligibility else opportunity.json_data.get("eligibility", []),
                "themes": parsed_opportunity.themes if parsed_opportunity.themes else opportunity.json_data.get("themes", []),
                "duration": parsed_opportunity.duration or opportunity.json_data.get("duration"),
                "how_to_apply": parsed_opportunity.how_to_apply or opportunity.json_data.get("how_to_apply"),
                "contact_info": parsed_opportunity.contact_info or opportunity.json_data.get("contact_info"),
                "source": "pdf",
                "pdf_confidence": parsed_opportunity.confidence_score,
                "pdf_extraction_engine": parsed_opportunity.extraction_engine
            })
            
            # Create feedback record for QA review
            feedback = ParsedDataFeedback(
                funding_opportunity_id=opportunity_id,
                field_edits=opportunity.json_data,
                prompt_version="pdf_parser_v1.0"
            )
            
            db.add(feedback)
            db.commit()
            
            logger.info(f"✅ Updated funding opportunity {opportunity_id} with PDF data")
            
        except Exception as e:
            logger.error(f"❌ Failed to update funding opportunity: {e}")
            db.rollback()
            raise
    
    def _create_funding_opportunity(self, parsed_opportunity: ParsedOpportunity, source_name: str, db: Session) -> FundingOpportunity:
        """Create new funding opportunity from parsed PDF data"""
        try:
            # Create JSON data
            json_data = {
                "title": parsed_opportunity.title,
                "donor": parsed_opportunity.donor,
                "summary": parsed_opportunity.summary,
                "amount": parsed_opportunity.amount,
                "deadline": parsed_opportunity.deadline,
                "location": parsed_opportunity.location,
                "eligibility": parsed_opportunity.eligibility,
                "themes": parsed_opportunity.themes,
                "duration": parsed_opportunity.duration,
                "how_to_apply": parsed_opportunity.how_to_apply,
                "contact_info": parsed_opportunity.contact_info,
                "source": "pdf",
                "pdf_confidence": parsed_opportunity.confidence_score,
                "pdf_extraction_engine": parsed_opportunity.extraction_engine,
                "pdf_source_name": source_name
            }
            
            # Create opportunity
            opportunity = FundingOpportunity(
                source_url=f"pdf://{source_name}",
                json_data=json_data,
                status=StatusEnum.raw
            )
            
            db.add(opportunity)
            db.commit()
            db.refresh(opportunity)
            
            # Create feedback record for QA review
            feedback = ParsedDataFeedback(
                funding_opportunity_id=opportunity.id,
                field_edits=json_data,
                prompt_version="pdf_parser_v1.0"
            )
            
            db.add(feedback)
            db.commit()
            
            logger.info(f"✅ Created new funding opportunity {opportunity.id} from PDF")
            return opportunity
            
        except Exception as e:
            logger.error(f"❌ Failed to create funding opportunity: {e}")
            db.rollback()
            raise
    
    def _build_document_response(self, document: Document, db: Session) -> Dict[str, Any]:
        """Build response for document operations"""
        try:
            # Get funding opportunity info
            opportunity = None
            if document.funding_opportunity_id:
                opportunity = db.query(FundingOpportunity).filter(FundingOpportunity.id == document.funding_opportunity_id).first()
            
            response = {
                "document_id": document.id,
                "sha256": document.sha256,
                "source": document.source.value,
                "mime": document.mime,
                "pages": document.pages,
                "ocr_status": document.ocr_status.value,
                "created_at": document.created_at.isoformat(),
                "funding_opportunity_id": document.funding_opportunity_id,
                "storage_path": document.storage_path
            }
            
            if opportunity:
                response["opportunity"] = {
                    "id": opportunity.id,
                    "title": opportunity.json_data.get("title", "Unknown") if opportunity.json_data else "Unknown",
                    "status": opportunity.status.value,
                    "source": opportunity.json_data.get("source", "unknown") if opportunity.json_data else "unknown"
                }
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Failed to build document response: {e}")
            raise

# Global service instance
document_service = DocumentService()

@router.post("/ingest-url")
@limiter.limit("5/minute")  # Rate limit: 5 URL ingestions per minute
async def ingest_pdf_url(
    url: str = Form(...),
    funding_opportunity_id: Optional[int] = Form(None),
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Ingest PDF from URL with text extraction and parsing
    """
    try:
        logger.info(f"🚀 PDF URL ingestion request from user {current_user}: {url}")
        
        # Validate URL
        if not url or not url.startswith('https://'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid HTTPS URL is required"
            )
        
        # Process ingestion
        result = document_service.ingest_pdf_url(url, funding_opportunity_id, db)
        
        logger.info(f"✅ PDF URL ingestion completed successfully for user {current_user}")
        return {
            "success": True,
            "message": "PDF successfully ingested and parsed",
            "document": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF URL ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF ingestion failed: {str(e)}"
        )

@router.post("/upload")
@limiter.limit("3/minute")  # Rate limit: 3 file uploads per minute
async def upload_pdf(
    file: UploadFile = File(...),
    funding_opportunity_id: Optional[int] = Form(None),
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Upload and ingest PDF file with text extraction and parsing
    """
    try:
        logger.info(f"🚀 PDF upload request from user {current_user}: {file.filename}")
        
        # Validate file
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        max_size = document_service.max_upload_bytes
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size {file_size} bytes exceeds maximum limit of {max_size} bytes"
            )
        
        # Process ingestion
        result = document_service.ingest_pdf_upload(file, funding_opportunity_id, db)
        
        logger.info(f"✅ PDF upload completed successfully for user {current_user}")
        return {
            "success": True,
            "message": "PDF successfully uploaded, extracted, and parsed",
            "document": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF upload failed: {str(e)}"
        )

@router.get("/{document_id}")
async def get_document_metadata(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Get document metadata (RBAC: admin only)
    """
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        return document_service._build_document_response(document, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get document metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document metadata: {str(e)}"
        )

@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Download document file (RBAC: admin only)
    """
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        # Check if file exists in storage
        if not storage_service.exists(document.storage_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found in storage"
            )
        
        # Read file data
        file_data = storage_service.open(document.storage_path)
        
        # Determine filename
        filename = f"document_{document_id}.pdf"
        if document.storage_path:
            filename = document.storage_path.split('/')[-1]
        
        logger.info(f"📥 Document {document_id} downloaded by user {current_user}")
        
        # Return streaming response
        return StreamingResponse(
            iter([file_data]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document download failed: {str(e)}"
        )

@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_admin_auth)
):
    """
    Get extracted text from document (RBAC: admin only)
    """
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found"
            )
        
        # Try to get extracted text
        text_path = document.storage_path.replace('.pdf', '.txt')
        
        if not storage_service.exists(text_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extracted text not available for this document"
            )
        
        text_data = storage_service.open(text_path)
        text_content = text_data.decode('utf-8')
        
        logger.info(f"📖 Document {document_id} text retrieved by user {current_user}")
        
        return {
            "document_id": document_id,
            "text": text_content,
            "length": len(text_content),
            "pages": document.pages,
            "ocr_status": document.ocr_status.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get document text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document text: {str(e)}"
        )

# Add rate limit exceeded handler
@router.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please try again later."
    )





