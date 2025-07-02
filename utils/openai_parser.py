import os
import asyncio
from typing import Dict, Any, List
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import openai
import json
from dotenv import load_dotenv

from schemas import FundingData

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Current parsing prompt version for tracking
CURRENT_PARSING_PROMPT_VERSION = "v2.1"

# Define expected fields for the gold-standard structure
EXPECTED_FIELDS = {
    "required": ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"],
    "optional": ["duration", "how_to_apply", "published_date", "contact_info"],
    "meta": ["opportunity_url"]
}

async def fetch_webpage_content(url: str) -> str:
    """Fetch and extract text content from a webpage using Playwright for JavaScript rendering"""
    browser = None
    context = None
    page = None
    
    try:
        logger.info(f"🌐 Starting Playwright fetch for URL: {url}")
        
        # Launch Playwright browser in headless mode
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        # Create browser context with realistic settings
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York"
        )
        
        # Create new page
        page = await context.new_page()
        
        # Set additional headers
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        # Navigate to the page with timeout
        logger.info(f"📄 Navigating to page: {url}")
        response = await page.goto(
            url, 
            wait_until="networkidle",
            timeout=10000  # 10 second timeout
        )
        
        # Check if page loaded successfully
        if response is None:
            raise Exception("Failed to load page - no response received")
        
        if response.status >= 400:
            raise Exception(f"HTTP {response.status}: {response.status_text}")
        
        logger.info(f"✅ Page loaded successfully with status: {response.status}")
        
        # Wait a moment for any remaining JavaScript to execute
        await page.wait_for_timeout(2000)  # 2 second additional wait
        
        # Get the full page HTML content
        html_content = await page.content()
        logger.info(f"📝 Retrieved HTML content ({len(html_content)} characters)")
        
        # Parse HTML content with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Limit content size but allow more for complex pages
        final_text = text[:15000]  # Increased limit for JavaScript-heavy pages
        
        logger.info(f"🎯 Extracted {len(final_text)} characters of clean text content")
        return final_text
        
    except Exception as e:
        error_msg = f"Playwright fetch failed for {url}: {str(e)}"
        logger.error(f"🔴 {error_msg}")
        
        # Log specific error types for debugging
        if "403" in str(e):
            logger.error("🚫 403 Forbidden - Website blocking access despite browser simulation")
        elif "timeout" in str(e).lower():
            logger.error("⏰ Timeout - Page took too long to load")
        elif "net::" in str(e):
            logger.error("🌐 Network error - Connection or DNS issues")
        
        raise Exception(f"Failed to fetch webpage content: {str(e)}")
        
    finally:
        # Ensure cleanup happens even if there's an error
        try:
            if page:
                await page.close()
                logger.debug("📄 Page closed")
            if context:
                await context.close()
                logger.debug("🔒 Context closed")
            if browser:
                await browser.close()
                logger.debug("🌐 Browser closed")
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Cleanup error: {cleanup_error}")

def create_enhanced_extraction_prompt(content: str, url: str) -> str:
    """Create a comprehensive prompt for extracting funding opportunity data across different donor websites"""
    
    prompt = f"""
You are an expert funding opportunity analyst specializing in extracting structured information from diverse donor websites including UK Government portals, foundation websites, and CSR funding pages.

WEBPAGE URL: {url}

WEBPAGE CONTENT:
{content}

EXTRACTION REQUIREMENTS:
Your task is to extract funding opportunity information into a standardized JSON format. This data will be used by an AI Proposal Generator, so accuracy and completeness are critical.

CORE EXTRACTION RULES:
1. Extract each field as accurately as possible from the content
2. If a field is not explicitly stated, infer from context when reasonable
3. For missing fields, return "Unknown" rather than null
4. Normalize all financial amounts to readable formats (e.g., "£10,000", "Up to $50K")
5. Standardize deadlines to clear formats (e.g., "31 March 2024", "Rolling basis")
6. Extract eligibility as a comprehensive list, even if criteria are scattered
7. Identify themes/focus areas from purpose statements and objectives
8. Always set opportunity_url to the provided URL

REQUIRED JSON OUTPUT STRUCTURE:
{{
  "title": "Full official name of the funding opportunity",
  "donor": "Organization, foundation, or agency providing the funding",
  "summary": "Concise 2-3 sentence overview of the funding purpose and scope",
  "amount": "Funding amount, range, or scale (e.g., '£5,000-£50,000', 'Up to €100K')",
  "deadline": "Application deadline or submission timeframe",
  "location": "Geographic eligibility or focus area",
  "eligibility": ["Who can apply", "Organization types", "Sector requirements", "Size criteria"],
  "themes": ["Primary focus areas", "Sector themes", "Priority topics", "Subject areas"],
  "duration": "Project length or funding period",
  "how_to_apply": "Application process summary (max 3 sentences)",
  "opportunity_url": "{url}",
  "published_date": "Publication or announcement date",
  "contact_info": "Contact details, email, or inquiry information"
}}

SPECIFIC FIELD EXTRACTION GUIDELINES:

TITLE: Look for main headings, grant names, program titles, or opportunity names
DONOR: Identify from logos, "funded by" statements, organization names, or footer information
SUMMARY: Synthesize from objectives, purpose statements, and program descriptions
AMOUNT: Extract from "funding available", "grant value", "budget", or award information
DEADLINE: Find application deadlines, closing dates, or submission timeframes
LOCATION: Determine from eligible areas, geographic scope, or regional focus
ELIGIBILITY: Compile all applicant criteria including organization type, size, sector, location
THEMES: Extract from focus areas, priority themes, subject categories, or strategic objectives
DURATION: Look for project timeframes, funding periods, or grant duration
HOW_TO_APPLY: Summarize application process, requirements, and submission methods
PUBLISHED_DATE: Find announcement dates, publication dates, or launch information
CONTACT_INFO: Extract contact emails, phone numbers, or inquiry details

QUALITY STANDARDS:
- Prioritize accuracy over completeness
- Use "Unknown" for genuinely missing information
- Infer reasonable values from context when appropriate
- Maintain consistency in formatting and terminology
- Focus on information most relevant to potential applicants

RETURN ONLY VALID JSON WITHOUT ANY ADDITIONAL TEXT, FORMATTING, OR EXPLANATIONS.
"""
    
    return prompt

def validate_extracted_fields(parsed_data: dict, url: str) -> dict:
    """Validate extracted fields and log missing data for QA team"""
    
    missing_required = []
    missing_optional = []
    low_quality_fields = []
    
    # Check required fields
    for field in EXPECTED_FIELDS["required"]:
        if field not in parsed_data:
            missing_required.append(field)
        else:
            value = parsed_data[field]
            # Check for low-quality data
            if not value or str(value).strip().lower() in ['unknown', 'n/a', '', 'none']:
                low_quality_fields.append(field)
            elif field in ['eligibility', 'themes'] and isinstance(value, list):
                if len(value) == 0 or (len(value) == 1 and str(value[0]).strip().lower() in ['unknown', 'n/a']):
                    low_quality_fields.append(field)
    
    # Check optional fields
    for field in EXPECTED_FIELDS["optional"]:
        if field not in parsed_data or not parsed_data[field] or str(parsed_data[field]).strip().lower() in ['unknown', 'n/a', '', 'none']:
            missing_optional.append(field)
    
    # Add meta fields
    parsed_data["opportunity_url"] = url
    
    # Log missing fields for QA team
    if missing_required:
        logger.warning(f"🚨 QA ALERT - Missing REQUIRED fields for {url}: {missing_required}")
        
    if low_quality_fields:
        logger.warning(f"⚠️ QA ALERT - Low quality data in fields for {url}: {low_quality_fields}")
        
    if missing_optional:
        logger.info(f"📝 QA INFO - Missing optional fields for {url}: {missing_optional}")
    
    # Calculate confidence score
    total_required = len(EXPECTED_FIELDS["required"])
    high_quality_required = total_required - len(missing_required) - len(low_quality_fields)
    confidence_score = (high_quality_required / total_required) * 100
    
    # Add extraction metadata
    if confidence_score < 60:
        parsed_data['_extraction_warning'] = "Low confidence extraction. Manual QA strongly recommended."
        logger.error(f"🔴 QA CRITICAL - Low confidence extraction ({confidence_score:.0f}%) for {url}")
    elif confidence_score < 80:
        parsed_data['_extraction_warning'] = "Medium confidence extraction. QA review recommended."
        logger.warning(f"🟡 QA WARNING - Medium confidence extraction ({confidence_score:.0f}%) for {url}")
    else:
        logger.info(f"✅ QA SUCCESS - High confidence extraction ({confidence_score:.0f}%) for {url}")
    
    parsed_data['_confidence_score'] = round(confidence_score, 1)
    parsed_data['_missing_required'] = missing_required
    parsed_data['_low_quality_fields'] = low_quality_fields
    
    return parsed_data

def create_fallback_structure(url: str, error_message: str = None) -> dict:
    """Create a fallback structure when parsing fails"""
    
    fallback_data = {
        "title": "Unknown",
        "donor": "Unknown",
        "summary": "Failed to extract funding opportunity details",
        "amount": "Unknown",
        "deadline": "Unknown",
        "location": "Unknown",
        "eligibility": ["Unknown"],
        "themes": ["Unknown"],
        "duration": "Unknown",
        "how_to_apply": "Unknown",
        "opportunity_url": url,
        "published_date": "Unknown",
        "contact_info": "Unknown",
        "_extraction_warning": f"Parsing failed: {error_message or 'Unknown error'}",
        "_confidence_score": 0.0,
        "_missing_required": EXPECTED_FIELDS["required"],
        "_low_quality_fields": []
    }
    
    logger.error(f"🔴 QA CRITICAL - Complete parsing failure for {url}: {error_message}")
    
    return fallback_data

def parse_funding_opportunity(text: str, url: str = "URL_PLACEHOLDER") -> str:
    """Parse a funding opportunity from raw text using OpenAI with comprehensive validation"""
    try:
        if not openai.api_key:
            raise Exception("OpenAI API key not found. Please check your .env file.")
        
        # Create enhanced prompt
        prompt = create_enhanced_extraction_prompt(text, url)
        
        # Call OpenAI API
        logger.info(f"🔍 Calling OpenAI API for enhanced extraction of {url}")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert funding opportunity analyst. Extract comprehensive, accurate information and return only valid JSON. Prioritize accuracy and completeness for proposal generation use."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1800,  # Increased for comprehensive extraction
            temperature=0.05,  # Very low temperature for consistency
        )
        
        # Extract and clean response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown formatting
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # Parse and validate JSON
        try:
            parsed_data = json.loads(content)
            
            # Validate and enhance with QA logging
            validated_data = validate_extracted_fields(parsed_data, url)
            
            # Return formatted JSON
            return json.dumps(validated_data, indent=2, ensure_ascii=False)
            
        except json.JSONDecodeError as e:
            logger.error(f"🔴 JSON parsing failed for {url}: {e}")
            fallback_data = create_fallback_structure(url, f"JSON parsing failed: {str(e)}")
            return json.dumps(fallback_data, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"🔴 OpenAI API error for {url}: {str(e)}")
        fallback_data = create_fallback_structure(url, f"OpenAI API error: {str(e)}")
        return json.dumps(fallback_data, indent=2, ensure_ascii=False)

async def parse_funding_opportunity_from_url(url: str) -> dict:
    """Parse a funding opportunity from a URL using the enhanced extraction method"""
    try:
        # Fetch webpage content
        logger.info(f"📄 Fetching content from URL: {url}")
        content = await fetch_webpage_content(url)
        
        # Parse using enhanced method
        json_response = parse_funding_opportunity(content, url)
        parsed_data = json.loads(json_response)
        
        return parsed_data
        
    except Exception as e:
        logger.error(f"🔴 Complete parsing failure for {url}: {str(e)}")
        return create_fallback_structure(url, f"URL parsing failed: {str(e)}")
