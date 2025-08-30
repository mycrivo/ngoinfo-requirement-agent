import os
import logging
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from services.pdf_extract import ExtractResult

# Import existing parser for consistency
from utils.openai_parser import (
    create_structured_extraction_prompt,
    validate_extracted_fields,
    EXPECTED_FIELDS
)

logger = logging.getLogger(__name__)

@dataclass
class ParsedOpportunity:
    """Parsed funding opportunity data matching gold-standard schema"""
    title: str
    donor: str
    summary: str
    amount: str
    deadline: str
    location: str
    eligibility: List[str]
    themes: List[str]
    duration: Optional[str] = None
    how_to_apply: Optional[str] = None
    opportunity_url: Optional[str] = None
    published_date: Optional[str] = None
    contact_info: Optional[str] = None
    source: str = "pdf"
    confidence_score: float = 0.0
    extraction_engine: str = "unknown"
    pages_extracted: int = 0

class PDFParseError(Exception):
    """Exception for PDF parsing failures"""
    pass

class PDFToGoldParser:
    """Convert extracted PDF text to gold-standard funding opportunity schema"""
    
    def __init__(self):
        self.min_confidence_threshold = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.7"))
        self.max_text_length = 12000  # Match existing parser limit
    
    def parse_to_gold_standard(self, extract_result: ExtractResult, source_url: str = None) -> ParsedOpportunity:
        """Parse extracted PDF text into gold-standard schema"""
        try:
            logger.info(f"🔄 Parsing PDF text to gold-standard schema (engine: {extract_result.engine})")
            
            # Sanitize and truncate text
            clean_text = self._sanitize_text(extract_result.text)
            
            # Use existing OpenAI parser if available
            if os.getenv("OPENAI_API_KEY"):
                try:
                    return self._parse_with_openai(clean_text, extract_result, source_url)
                except Exception as e:
                    logger.warning(f"⚠️ OpenAI parsing failed, falling back to rule-based: {e}")
            
            # Fallback to rule-based parsing
            return self._parse_with_rules(clean_text, extract_result, source_url)
            
        except Exception as e:
            logger.error(f"❌ PDF parsing failed: {e}")
            raise PDFParseError(f"Failed to parse PDF to gold-standard: {str(e)}")
    
    def _parse_with_openai(self, text: str, extract_result: ExtractResult, source_url: str) -> ParsedOpportunity:
        """Use existing OpenAI parser for consistent results"""
        try:
            # Create prompt using existing parser logic
            prompt = create_structured_extraction_prompt(text, source_url or "PDF_SOURCE")
            
            # Call OpenAI API (reusing existing logic)
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY")
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert data parser. Extract precise information and return only valid JSON with the specified fields."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1800,
                temperature=0.05,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean response
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            # Parse JSON
            parsed_data = json.loads(content.strip())
            
            # Validate using existing logic
            validated_data = validate_extracted_fields(parsed_data, source_url or "PDF_SOURCE")
            
            # Convert to ParsedOpportunity
            return self._convert_to_parsed_opportunity(validated_data, extract_result, source_url)
            
        except Exception as e:
            logger.error(f"❌ OpenAI parsing failed: {e}")
            raise PDFParseError(f"OpenAI parsing failed: {str(e)}")
    
    def _parse_with_rules(self, text: str, extract_result: ExtractResult, source_url: str) -> ParsedOpportunity:
        """Rule-based parsing as fallback"""
        try:
            logger.info("🔧 Using rule-based PDF parsing")
            
            # Initialize with defaults
            parsed_data = {
                "title": "Unknown",
                "donor": "Unknown",
                "summary": "No summary available",
                "amount": "Unknown",
                "deadline": "Unknown",
                "location": "Unknown",
                "eligibility": [],
                "themes": [],
                "duration": None,
                "how_to_apply": None,
                "opportunity_url": source_url,
                "published_date": None,
                "contact_info": None
            }
            
            # Extract title (look for first line that looks like a title)
            lines = text.split('\n')
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if len(line) > 10 and len(line) < 200 and not line.islower():
                    if any(word in line.lower() for word in ['grant', 'funding', 'opportunity', 'program', 'award']):
                        parsed_data["title"] = line
                        break
            
            # Extract donor (look for common patterns)
            donor_patterns = [
                r'(?:funded by|sponsored by|provided by|grant from)\s*[:.]?\s*([^.\n]+)',
                r'(?:organization|agency|foundation|institution)\s*[:.]?\s*([^.\n]+)',
                r'([A-Z][A-Z\s&]+(?:Foundation|Institute|Agency|Department|Ministry|Council))'
            ]
            
            for pattern in donor_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    donor = match.group(1).strip()
                    if len(donor) > 3 and donor.lower() != "unknown":
                        parsed_data["donor"] = donor
                        break
            
            # Extract amount (look for currency patterns)
            amount_patterns = [
                r'(\$[\d,]+(?:\.\d{2})?(?:\s*-\s*\$[\d,]+(?:\.\d{2})?)?)',
                r'(£[\d,]+(?:\.\d{2})?(?:\s*-\s*£[\d,]+(?:\.\d{2})?)?)',
                r'(€[\d,]+(?:\.\d{2})?(?:\s*-\s*€[\d,]+(?:\.\d{2})?)?)',
                r'([\d,]+(?:\.\d{2})?\s*(?:USD|GBP|EUR|dollars?|pounds?|euros?))',
                r'(up to\s+[\d,]+(?:\.\d{2})?\s*(?:USD|GBP|EUR|dollars?|pounds?|euros?))'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount = match.group(1).strip()
                    if amount.lower() != "unknown":
                        parsed_data["amount"] = amount
                        break
            
            # Extract deadline (look for date patterns)
            deadline_patterns = [
                r'(?:deadline|closing date|due date|apply by|submission deadline)\s*[:.]?\s*([^.\n]+)',
                r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}-\d{2}-\d{2})'
            ]
            
            for pattern in deadline_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    deadline = match.group(1).strip()
                    if deadline.lower() != "unknown":
                        parsed_data["deadline"] = deadline
                        break
            
            # Extract location (look for geographic patterns)
            location_patterns = [
                r'(?:eligible areas?|geographic scope|location|region)\s*[:.]?\s*([^.\n]+)',
                r'(?:open to|available in|restricted to)\s*([^.\n]+)',
                r'(United States|UK|United Kingdom|Canada|Australia|Global|Worldwide|International)'
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    location = match.group(1).strip()
                    if location.lower() != "unknown":
                        parsed_data["location"] = location
                        break
            
            # Extract eligibility (look for eligibility sections)
            eligibility_sections = re.findall(
                r'(?:eligibility|who can apply|requirements|criteria|qualifications?)\s*[:.]?\s*([^.\n]+(?:\n[^.\n]+)*)',
                text,
                re.IGNORECASE
            )
            
            if eligibility_sections:
                eligibility_text = eligibility_sections[0]
                # Split into bullet points or sentences
                eligibility_items = re.split(r'[•\-\*]|\d+\.', eligibility_text)
                parsed_data["eligibility"] = [
                    item.strip() for item in eligibility_items 
                    if item.strip() and len(item.strip()) > 5
                ][:5]  # Limit to 5 items
            
            # Extract themes (look for focus areas)
            theme_patterns = [
                r'(?:focus areas?|themes?|priorities?|sectors?|topics?)\s*[:.]?\s*([^.\n]+(?:\n[^.\n]+)*)',
                r'(?:supporting|funding|grants? for)\s+([^.\n]+)'
            ]
            
            for pattern in theme_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    themes_text = match.group(1)
                    # Extract individual themes
                    themes = re.findall(r'\b(?:education|health|environment|technology|arts|culture|social|economic|youth|community|research|innovation)\b', themes_text, re.IGNORECASE)
                    if themes:
                        parsed_data["themes"] = list(set(themes))  # Remove duplicates
                        break
            
            # Extract duration
            duration_match = re.search(
                r'(?:duration|project length|funding period|timeline)\s*[:.]?\s*([^.\n]+)',
                text,
                re.IGNORECASE
            )
            if duration_match:
                parsed_data["duration"] = duration_match.group(1).strip()
            
            # Extract how to apply
            apply_match = re.search(
                r'(?:how to apply|application process|submission|apply)\s*[:.]?\s*([^.\n]+(?:\n[^.\n]+)*)',
                text,
                re.IGNORECASE
            )
            if apply_match:
                apply_text = apply_match.group(1).strip()
                # Truncate if too long
                if len(apply_text) > 200:
                    apply_text = apply_text[:200] + "..."
                parsed_data["how_to_apply"] = apply_text
            
            # Extract contact info
            contact_match = re.search(
                r'(?:contact|enquiries?|questions?|email|phone)\s*[:.]?\s*([^.\n]+)',
                text,
                re.IGNORECASE
            )
            if contact_match:
                parsed_data["contact_info"] = contact_match.group(1).strip()
            
            # Create summary from extracted data
            summary_parts = []
            if parsed_data["title"] != "Unknown":
                summary_parts.append(parsed_data["title"])
            if parsed_data["amount"] != "Unknown":
                summary_parts.append(f"Funding: {parsed_data['amount']}")
            if parsed_data["location"] != "Unknown":
                summary_parts.append(f"Location: {parsed_data['location']}")
            
            if summary_parts:
                parsed_data["summary"] = ". ".join(summary_parts)
            
            # Convert to ParsedOpportunity
            return self._convert_to_parsed_opportunity(parsed_data, extract_result, source_url)
            
        except Exception as e:
            logger.error(f"❌ Rule-based parsing failed: {e}")
            raise PDFParseError(f"Rule-based parsing failed: {str(e)}")
    
    def _convert_to_parsed_opportunity(self, parsed_data: Dict[str, Any], extract_result: ExtractResult, source_url: str) -> ParsedOpportunity:
        """Convert parsed data to ParsedOpportunity dataclass"""
        try:
            # Ensure required fields exist
            for field in EXPECTED_FIELDS["required"]:
                if field not in parsed_data or not parsed_data[field]:
                    if field == "eligibility":
                        parsed_data[field] = []
                    elif field == "themes":
                        parsed_data[field] = []
                    else:
                        parsed_data[field] = "Unknown"
            
            # Ensure optional fields exist
            for field in EXPECTED_FIELDS["optional"]:
                if field not in parsed_data:
                    parsed_data[field] = None
            
            # Create ParsedOpportunity
            opportunity = ParsedOpportunity(
                title=parsed_data.get("title", "Unknown"),
                donor=parsed_data.get("donor", "Unknown"),
                summary=parsed_data.get("summary", "No summary available"),
                amount=parsed_data.get("amount", "Unknown"),
                deadline=parsed_data.get("deadline", "Unknown"),
                location=parsed_data.get("location", "Unknown"),
                eligibility=parsed_data.get("eligibility", []),
                themes=parsed_data.get("themes", []),
                duration=parsed_data.get("duration"),
                how_to_apply=parsed_data.get("how_to_apply"),
                opportunity_url=source_url,
                published_date=parsed_data.get("published_date"),
                contact_info=parsed_data.get("contact_info"),
                source="pdf",
                confidence_score=extract_result.confidence,
                extraction_engine=extract_result.engine,
                pages_extracted=extract_result.pages
            )
            
            logger.info(f"✅ Successfully parsed PDF to gold-standard schema")
            logger.info(f"   Title: {opportunity.title[:50]}...")
            logger.info(f"   Donor: {opportunity.donor}")
            logger.info(f"   Confidence: {opportunity.confidence_score:.2f}")
            logger.info(f"   Engine: {opportunity.extraction_engine}")
            
            return opportunity
            
        except Exception as e:
            logger.error(f"❌ Failed to convert to ParsedOpportunity: {e}")
            raise PDFParseError(f"Conversion failed: {str(e)}")
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize and truncate extracted text"""
        if not text:
            return ""
        
        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate if too long
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length] + "... [truncated]"
            logger.warning(f"⚠️ PDF text truncated to {self.max_text_length} characters")
        
        return text.strip()
    
    def validate_parsed_opportunity(self, opportunity: ParsedOpportunity) -> Dict[str, Any]:
        """Validate parsed opportunity and return quality metrics"""
        validation_result = {
            "is_valid": True,
            "missing_required": [],
            "low_quality_fields": [],
            "confidence_score": opportunity.confidence_score,
            "extraction_engine": opportunity.extraction_engine,
            "pages_extracted": opportunity.pages_extracted
        }
        
        # Check required fields
        required_fields = ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"]
        for field in required_fields:
            value = getattr(opportunity, field)
            if not value or (isinstance(value, str) and value.lower() in ['unknown', 'n/a', '']):
                validation_result["missing_required"].append(field)
                validation_result["is_valid"] = False
            elif isinstance(value, list) and len(value) == 0:
                validation_result["missing_required"].append(field)
                validation_result["is_valid"] = False
        
        # Check for low quality data
        for field in required_fields:
            value = getattr(opportunity, field)
            if isinstance(value, str) and value.lower() in ['unknown', 'n/a', '']:
                validation_result["low_quality_fields"].append(field)
        
        # Log validation results
        if validation_result["missing_required"]:
            logger.warning(f"⚠️ Missing required fields: {validation_result['missing_required']}")
        
        if validation_result["low_quality_fields"]:
            logger.warning(f"⚠️ Low quality fields: {validation_result['low_quality_fields']}")
        
        if validation_result["is_valid"]:
            logger.info(f"✅ Parsed opportunity validation passed")
        else:
            logger.warning(f"⚠️ Parsed opportunity validation failed")
        
        return validation_result

# Global parser instance
pdf_to_gold_parser = PDFToGoldParser()

