from fastapi import APIRouter, HTTPException
import logging
import json
from pydantic import BaseModel
from utils.openai_parser import fetch_webpage_content, parse_funding_opportunity

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["requirement-agent"])

# Input model for request
class RequestData(BaseModel):
    url: str

# Output model for gold-standard response
class ParseResponse(BaseModel):
    success: bool
    message: str
    extracted_data: dict

@router.post("/requirement/parse", response_model=ParseResponse)
async def parse_opportunity(data: RequestData):
    """
    Parse a funding opportunity from a URL using OpenAI with gold-standard extraction
    """
    try:
        logger.info(f"Parsing URL: {data.url}")
        
        # Fetch webpage content
        content = await fetch_webpage_content(data.url)
        
        # Use the robust parser with URL context
        json_response = parse_funding_opportunity(content).replace("URL_PLACEHOLDER", data.url)
        
        # Parse the JSON response
        parsed_data = json.loads(json_response)
        
        # Log extraction quality
        if "_extraction_warning" in parsed_data:
            logger.warning(f"Low confidence extraction for {data.url}: {parsed_data['_extraction_warning']}")
        
        return ParseResponse(
            success=True,
            message="Successfully parsed funding opportunity using gold-standard extraction",
            extracted_data=parsed_data
        )

    except Exception as e:
        logger.error(f"Error parsing {data.url}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse funding opportunity: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Requirement Agent API is running"}

# Test endpoint for debugging
@router.post("/test/parse-text")
async def test_parse_text(data: dict):
    """
    Test endpoint to parse raw text content (for debugging)
    """
    try:
        if "text" not in data:
            raise HTTPException(status_code=400, detail="Text field required")
        
        text = data["text"]
        url = data.get("url", "test-url")
        
        logger.info("Testing text parsing...")
        
        # Parse the text
        json_response = parse_funding_opportunity(text).replace("URL_PLACEHOLDER", url)
        parsed_data = json.loads(json_response)
        
        return {
            "success": True,
            "message": "Text parsed successfully",
            "extracted_data": parsed_data
        }
        
    except Exception as e:
        logger.error(f"Error in test parsing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse text: {str(e)}"
        ) 