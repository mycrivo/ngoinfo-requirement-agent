import os
import logging
import hashlib
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import requests
from urllib.parse import urlparse
import fitz  # PyMuPDF
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from io import BytesIO, StringIO
from PIL import Image
import io

logger = logging.getLogger(__name__)

@dataclass
class TextBlock:
    """Represents a block of extracted text with positioning"""
    type: str  # 'text', 'heading', 'table', 'image'
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    page: int
    confidence: float = 1.0

@dataclass
class ExtractResult:
    """Result of PDF text extraction"""
    pages: int
    text: str
    blocks: List[TextBlock]
    confidence: float
    engine: str
    extraction_time_ms: float
    ocr_used: bool = False

class PDFExtractionError(Exception):
    """Base exception for PDF extraction failures"""
    pass

class PDFValidationError(Exception):
    """Exception for PDF validation failures"""
    pass

class PDFExtractor:
    """PDF text extraction service with native + OCR fallback"""
    
    def __init__(self):
        self.ocr_backend = os.getenv("OCR_BACKEND", "none").lower()
        self.confidence_threshold = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.7"))
        self.max_pages = int(os.getenv("MAX_PDF_PAGES", "150"))
        self._check_ocr_capabilities()
    
    def _check_ocr_capabilities(self):
        """Check available OCR backends"""
        if self.ocr_backend == "textract":
            try:
                import boto3
                logger.info("✅ AWS Textract OCR backend available")
            except ImportError:
                logger.warning("⚠️ AWS Textract not available, falling back to native extraction")
                self.ocr_backend = "none"
        
        elif self.ocr_backend == "vision":
            try:
                from google.cloud import vision
                logger.info("✅ Google Cloud Vision OCR backend available")
            except ImportError:
                logger.warning("⚠️ Google Cloud Vision not available, falling back to native extraction")
                self.ocr_backend = "none"
        
        elif self.ocr_backend == "self_hosted":
            try:
                import pytesseract
                logger.info("✅ Self-hosted Tesseract OCR backend available")
            except ImportError:
                logger.warning("⚠️ Self-hosted Tesseract not available, falling back to native extraction")
                self.ocr_backend = "none"
        
        else:
            logger.info("✅ Native PDF text extraction only (no OCR)")
    
    def extract_from_bytes(self, pdf_bytes: bytes, filename: str = "unknown.pdf") -> ExtractResult:
        """Extract text from PDF bytes with native extraction + OCR fallback"""
        import time
        start_time = time.time()
        
        try:
            # Validate PDF
            self._validate_pdf_bytes(pdf_bytes)
            
            # Try native extraction first
            try:
                result = self._extract_native(pdf_bytes)
                logger.info(f"✅ Native extraction successful for {filename}: {result.pages} pages, {len(result.text)} chars")
                return result
                
            except Exception as e:
                logger.warning(f"⚠️ Native extraction failed for {filename}: {e}")
                
                # Fall back to OCR if available and enabled
                if self.ocr_backend != "none":
                    try:
                        result = self._extract_with_ocr(pdf_bytes, filename)
                        logger.info(f"✅ OCR extraction successful for {filename}: {result.pages} pages, {len(result.text)} chars")
                        return result
                    except Exception as ocr_error:
                        logger.error(f"❌ OCR extraction also failed for {filename}: {ocr_error}")
                
                # If all else fails, return minimal result
                return self._create_fallback_result(pdf_bytes, filename)
                
        except Exception as e:
            logger.error(f"❌ PDF extraction failed for {filename}: {e}")
            raise PDFExtractionError(f"Failed to extract PDF {filename}: {str(e)}")
        
        finally:
            extraction_time = (time.time() - start_time) * 1000
            logger.info(f"⏱️ PDF extraction completed in {extraction_time:.1f}ms")
    
    def extract_from_url(self, url: str) -> ExtractResult:
        """Download and extract PDF from URL"""
        try:
            # Validate URL
            self._validate_url(url)
            
            # Download PDF with limits
            timeout = int(os.getenv("PDF_DOWNLOAD_TIMEOUT", "30"))
            max_redirects = int(os.getenv("PDF_MAX_REDIRECTS", "5"))
            
            response = requests.get(
                url, 
                timeout=timeout, 
                allow_redirects=True,
                max_redirects=max_redirects,
                stream=True
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type:
                raise PDFValidationError(f"URL does not return PDF content: {content_type}")
            
            # Download with size limit
            max_size = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
            pdf_bytes = b""
            
            for chunk in response.iter_content(chunk_size=8192):
                pdf_bytes += chunk
                if len(pdf_bytes) > max_size:
                    raise PDFValidationError(f"PDF exceeds size limit: {len(pdf_bytes)} bytes")
            
            # Extract text
            filename = urlparse(url).path.split('/')[-1] or "downloaded.pdf"
            return self.extract_from_bytes(pdf_bytes, filename)
            
        except requests.RequestException as e:
            raise PDFExtractionError(f"Failed to download PDF from {url}: {str(e)}")
        except Exception as e:
            raise PDFExtractionError(f"Failed to process PDF from {url}: {str(e)}")
    
    def _extract_native(self, pdf_bytes: bytes) -> ExtractResult:
        """Extract text using native PDF libraries"""
        try:
            # Try PyMuPDF first (better text positioning)
            try:
                return self._extract_with_pymupdf(pdf_bytes)
            except Exception as e:
                logger.warning(f"⚠️ PyMuPDF failed, trying pdfminer: {e}")
                return self._extract_with_pdfminer(pdf_bytes)
                
        except Exception as e:
            raise PDFExtractionError(f"Native extraction failed: {str(e)}")
    
    def _extract_with_pymupdf(self, pdf_bytes: bytes) -> ExtractResult:
        """Extract text using PyMuPDF (fitz)"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if doc.page_count > self.max_pages:
            raise PDFValidationError(f"PDF has too many pages: {doc.page_count} > {self.max_pages}")
        
        all_text = ""
        blocks = []
        
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            
            # Extract text blocks with positioning
            text_dict = page.get_text("dict")
            
            for block in text_dict["blocks"]:
                if "lines" in block:
                    block_text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"]
                    
                    if block_text.strip():
                        # Determine block type
                        block_type = "text"
                        if block_text.isupper() and len(block_text) < 100:
                            block_type = "heading"
                        
                        blocks.append(TextBlock(
                            type=block_type,
                            text=block_text.strip(),
                            bbox=block["bbox"],
                            page=page_num + 1
                        ))
                        all_text += block_text + "\n"
        
        doc.close()
        
        # Calculate confidence based on text quality
        confidence = self._calculate_native_confidence(all_text)
        
        return ExtractResult(
            pages=doc.page_count,
            text=all_text.strip(),
            blocks=blocks,
            confidence=confidence,
            engine="native-pymupdf",
            extraction_time_ms=0,  # Will be set by caller
            ocr_used=False
        )
    
    def _extract_with_pdfminer(self, pdf_bytes: bytes) -> ExtractResult:
        """Extract text using pdfminer.six (fallback)"""
        output = StringIO()
        extract_text_to_fp(BytesIO(pdf_bytes), output, laparams=LAParams())
        text = output.getvalue()
        output.close()
        
        # Estimate page count (rough approximation)
        estimated_pages = max(1, len(text) // 2000)  # ~2000 chars per page
        
        if estimated_pages > self.max_pages:
            raise PDFValidationError(f"PDF appears too large: estimated {estimated_pages} pages > {self.max_pages}")
        
        # Create simple blocks (pdfminer doesn't provide positioning)
        blocks = [TextBlock(
            type="text",
            text=text,
            bbox=(0, 0, 0, 0),
            page=1
        )]
        
        confidence = self._calculate_native_confidence(text)
        
        return ExtractResult(
            pages=estimated_pages,
            text=text.strip(),
            blocks=blocks,
            confidence=confidence,
            engine="native-pdfminer",
            extraction_time_ms=0,  # Will be set by caller
            ocr_used=False
        )
    
    def _extract_with_ocr(self, pdf_bytes: bytes, filename: str) -> ExtractResult:
        """Extract text using OCR backend"""
        if self.ocr_backend == "textract":
            return self._extract_with_textract(pdf_bytes, filename)
        elif self.ocr_backend == "vision":
            return self._extract_with_vision(pdf_bytes, filename)
        elif self.ocr_backend == "self_hosted":
            return self._extract_with_tesseract(pdf_bytes, filename)
        else:
            raise PDFExtractionError("No OCR backend available")
    
    def _extract_with_textract(self, pdf_bytes: bytes, filename: str) -> ExtractResult:
        """Extract text using AWS Textract"""
        try:
            import boto3
            
            textract = boto3.client('textract')
            
            # Convert PDF to images for Textract
            images = self._pdf_to_images(pdf_bytes)
            
            all_text = ""
            blocks = []
            page_count = len(images)
            
            for page_num, image in enumerate(images):
                # Convert PIL image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                # Call Textract
                response = textract.detect_document_text(
                    Document={'Bytes': img_bytes.read()}
                )
                
                page_text = ""
                for item in response['Blocks']:
                    if item['BlockType'] == 'LINE':
                        text = item['Text']
                        page_text += text + "\n"
                        
                        # Create block with positioning
                        if 'Geometry' in item:
                            bbox = item['Geometry']['BoundingBox']
                            blocks.append(TextBlock(
                                type="text",
                                text=text,
                                bbox=(bbox['Left'], bbox['Top'], bbox['Left'] + bbox['Width'], bbox['Top'] + bbox['Height']),
                                page=page_num + 1,
                                confidence=item.get('Confidence', 0) / 100.0
                            ))
                
                all_text += page_text
            
            confidence = self._calculate_ocr_confidence(all_text, blocks)
            
            return ExtractResult(
                pages=page_count,
                text=all_text.strip(),
                blocks=blocks,
                confidence=confidence,
                engine="ocr-textract",
                extraction_time_ms=0,  # Will be set by caller
                ocr_used=True
            )
            
        except ImportError:
            raise PDFExtractionError("AWS Textract not available")
        except Exception as e:
            raise PDFExtractionError(f"Textract extraction failed: {str(e)}")
    
    def _extract_with_vision(self, pdf_bytes: bytes, filename: str) -> ExtractResult:
        """Extract text using Google Cloud Vision"""
        try:
            from google.cloud import vision
            
            client = vision.ImageAnnotatorClient()
            
            # Convert PDF to images
            images = self._pdf_to_images(pdf_bytes)
            
            all_text = ""
            blocks = []
            page_count = len(images)
            
            for page_num, image in enumerate(images):
                # Convert PIL image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                # Create Vision API request
                image_vision = vision.Image(content=img_bytes.read())
                response = client.document_text_detection(image=image_vision)
                
                if response.error.message:
                    raise PDFExtractionError(f"Vision API error: {response.error.message}")
                
                page_text = response.full_text_annotation.text
                all_text += page_text + "\n"
                
                # Create blocks from detected text
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                if word_text.strip():
                                    # Get bounding box
                                    vertices = word.bounding_box.vertices
                                    bbox = (
                                        vertices[0].x, vertices[0].y,
                                        vertices[2].x, vertices[2].y
                                    )
                                    
                                    blocks.append(TextBlock(
                                        type="text",
                                        text=word_text,
                                        bbox=bbox,
                                        page=page_num + 1,
                                        confidence=0.9  # Vision API doesn't provide confidence
                                    ))
            
            confidence = self._calculate_ocr_confidence(all_text, blocks)
            
            return ExtractResult(
                pages=page_count,
                text=all_text.strip(),
                blocks=blocks,
                confidence=confidence,
                engine="ocr-vision",
                extraction_time_ms=0,  # Will be set by caller
                ocr_used=True
            )
            
        except ImportError:
            raise PDFExtractionError("Google Cloud Vision not available")
        except Exception as e:
            raise PDFExtractionError(f"Vision API extraction failed: {str(e)}")
    
    def _extract_with_tesseract(self, pdf_bytes: bytes, filename: str) -> ExtractResult:
        """Extract text using self-hosted Tesseract"""
        try:
            import pytesseract
            
            # Convert PDF to images
            images = self._pdf_to_images(pdf_bytes)
            
            all_text = ""
            blocks = []
            page_count = len(images)
            
            for page_num, image in enumerate(images):
                # Extract text with Tesseract
                page_text = pytesseract.image_to_string(image)
                all_text += page_text + "\n"
                
                # Create simple block (Tesseract doesn't provide positioning)
                blocks.append(TextBlock(
                    type="text",
                    text=page_text,
                    bbox=(0, 0, 0, 0),
                    page=page_num + 1,
                    confidence=0.8  # Default confidence for Tesseract
                ))
            
            confidence = self._calculate_ocr_confidence(all_text, blocks)
            
            return ExtractResult(
                pages=page_count,
                text=all_text.strip(),
                blocks=blocks,
                confidence=confidence,
                engine="ocr-tesseract",
                extraction_time_ms=0,  # Will be set by caller
                ocr_used=True
            )
            
        except ImportError:
            raise PDFExtractionError("Tesseract not available")
        except Exception as e:
            raise PDFExtractionError(f"Tesseract extraction failed: {str(e)}")
    
    def _pdf_to_images(self, pdf_bytes: bytes) -> List[Image.Image]:
        """Convert PDF pages to PIL Images"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        for page_num in range(min(doc.page_count, 10)):  # Limit to first 10 pages for OCR
            page = doc.load_page(page_num)
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
        
        doc.close()
        return images
    
    def _calculate_native_confidence(self, text: str) -> float:
        """Calculate confidence score for native extraction"""
        if not text or len(text.strip()) < 100:
            return 0.1
        
        # Check for key funding opportunity terms
        key_terms = [
            "eligibility", "deadline", "budget", "apply", "funding", "grant",
            "opportunity", "application", "requirements", "criteria"
        ]
        
        text_lower = text.lower()
        found_terms = sum(1 for term in key_terms if term in text_lower)
        
        # Base confidence on text length and key terms
        length_score = min(1.0, len(text) / 5000)  # Normalize to 5000 chars
        term_score = found_terms / len(key_terms)
        
        confidence = (length_score * 0.6) + (term_score * 0.4)
        return min(1.0, max(0.1, confidence))
    
    def _calculate_ocr_confidence(self, text: str, blocks: List[TextBlock]) -> float:
        """Calculate confidence score for OCR extraction"""
        if not text or len(text.strip()) < 100:
            return 0.1
        
        # Base confidence on OCR engine and text quality
        base_confidence = 0.7  # OCR is generally less reliable than native
        
        # Adjust based on text length and key terms
        length_score = min(1.0, len(text) / 3000)  # OCR needs more text for confidence
        
        key_terms = [
            "eligibility", "deadline", "budget", "apply", "funding", "grant",
            "opportunity", "application", "requirements", "criteria"
        ]
        
        text_lower = text.lower()
        found_terms = sum(1 for term in key_terms if term in text_lower)
        term_score = found_terms / len(key_terms)
        
        confidence = (base_confidence * 0.5) + (length_score * 0.3) + (term_score * 0.2)
        return min(1.0, max(0.1, confidence))
    
    def _create_fallback_result(self, pdf_bytes: bytes, filename: str) -> ExtractResult:
        """Create minimal result when extraction fails"""
        return ExtractResult(
            pages=1,
            text=f"[PDF extraction failed for {filename}]",
            blocks=[],
            confidence=0.0,
            engine="fallback",
            extraction_time_ms=0,
            ocr_used=False
        )
    
    def _validate_pdf_bytes(self, pdf_bytes: bytes):
        """Validate PDF bytes"""
        if not pdf_bytes or len(pdf_bytes) < 100:
            raise PDFValidationError("PDF file too small or empty")
        
        # Check PDF magic number
        if not pdf_bytes.startswith(b'%PDF'):
            raise PDFValidationError("File does not appear to be a valid PDF")
        
        # Check size limit
        max_size = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
        if len(pdf_bytes) > max_size:
            raise PDFValidationError(f"PDF exceeds size limit: {len(pdf_bytes)} bytes")
    
    def _validate_url(self, url: str):
        """Validate URL for PDF download"""
        parsed = urlparse(url)
        
        # Only allow HTTPS
        if parsed.scheme not in ['https']:
            raise PDFValidationError("Only HTTPS URLs are allowed")
        
        # Block data/file URIs
        if parsed.scheme in ['data', 'file']:
            raise PDFValidationError("Data and file URIs are not allowed")
        
        # Basic URL format validation
        if not parsed.netloc:
            raise PDFValidationError("Invalid URL format")

# Global extractor instance
pdf_extractor = PDFExtractor()

