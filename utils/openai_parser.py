import os
import asyncio
from typing import Dict, Any, List
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import openai
import json
import re
from dotenv import load_dotenv

from schemas import FundingData

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Current parsing prompt version for tracking
CURRENT_PARSING_PROMPT_VERSION = "v3.0_sectioned"

# Define expected fields for the gold-standard structure
EXPECTED_FIELDS = {
    "required": ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"],
    "optional": ["duration", "how_to_apply", "published_date", "contact_info"],
    "meta": ["opportunity_url"]
}

async def extract_sectioned_content(page, url: str) -> str:
    """Extract key content sections from the DOM using Playwright and format them for LLM parsing"""
    try:
        logger.info(f"🔍 Extracting sectioned content from: {url}")
        
        # Define section keywords and patterns for intelligent extraction
        section_patterns = {
            "title": ["h1", "h2", "[class*='title']", "[class*='heading']", "[id*='title']"],
            "summary": ["[class*='summary']", "[class*='description']", "[class*='overview']", ".intro", ".about"],
            "amount": ["[class*='amount']", "[class*='fund']", "[class*='grant']", "[class*='budget']", "[class*='value']"],
            "deadline": ["[class*='deadline']", "[class*='close']", "[class*='due']", "[class*='date']"],
            "duration": ["[class*='duration']", "[class*='period']", "[class*='timeline']"],
            "eligibility": ["[class*='eligib']", "[class*='criteria']", "[class*='requirement']", "[class*='who']"],
            "themes": ["[class*='theme']", "[class*='focus']", "[class*='area']", "[class*='priority']", "[class*='subject']"],
            "how_to_apply": ["[class*='apply']", "[class*='application']", "[class*='submit']", "[class*='process']"],
            "contact": ["[class*='contact']", "[class*='enquir']", "[class*='email']", "[class*='phone']"]
        }
        
        sectioned_content = {}
        
        # Extract title (most important - try multiple approaches)
        title_text = ""
        try:
            # Try h1 first
            title_h1 = await page.locator("h1").first.inner_text()
            if title_h1 and len(title_h1.strip()) > 3:
                title_text = title_h1.strip()
            else:
                # Try title tag
                title_tag = await page.title()
                if title_tag:
                    title_text = title_tag.strip()
        except:
            # Fallback to page title
            try:
                title_text = await page.title() or "Unknown Title"
            except:
                title_text = "Unknown Title"
        
        sectioned_content["TITLE"] = title_text
        
        # Extract summary/overview (look for intro paragraphs)
        summary_text = ""
        try:
            # Look for common summary patterns
            for pattern in ["[class*='summary']", "[class*='description']", "[class*='overview']", "[class*='intro']", "p"]:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements[:3]:  # First 3 matching elements
                        text = await element.inner_text()
                        if text and len(text.strip()) > 50:  # Substantial content
                            summary_text += text.strip() + "\n\n"
                    if summary_text:
                        break
                except:
                    continue
        except:
            pass
        
        sectioned_content["SUMMARY"] = summary_text.strip() if summary_text else "Not found"
        
        # Extract amount/funding information
        amount_text = ""
        try:
            # Look for currency symbols and amount keywords
            amount_selectors = [
                "[class*='amount']", "[class*='fund']", "[class*='grant']", 
                "[class*='budget']", "[class*='value']", "[class*='award']"
            ]
            
            for selector in amount_selectors:
                try:
                    elements = await page.locator(selector).all()
                    for element in elements:
                        text = await element.inner_text()
                        # Check if contains currency symbols or amount keywords
                        if re.search(r'[£$€¥]|amount|fund|grant|budget|\d+[,\d]*', text, re.I):
                            amount_text += text.strip() + "\n"
                except:
                    continue
                    
            # If no specific amount sections found, search entire page for currency mentions
            if not amount_text:
                try:
                    page_text = await page.locator("body").inner_text()
                    # Extract sentences containing currency or funding terms
                    sentences = re.split(r'[.!?]', page_text)
                    for sentence in sentences:
                        if re.search(r'[£$€¥]|\b(fund|grant|budget|amount|value|award)\b.*\d', sentence, re.I):
                            amount_text += sentence.strip() + ". "
                            if len(amount_text) > 500:  # Limit to avoid too much text
                                break
                except:
                    pass
                    
        except:
            pass
            
        sectioned_content["AMOUNT"] = amount_text.strip() if amount_text else "Not found"
        
        # Extract deadline information
        deadline_text = ""
        try:
            deadline_selectors = [
                "[class*='deadline']", "[class*='close']", "[class*='due']", 
                "[class*='date']", "[class*='apply']"
            ]
            
            for selector in deadline_selectors:
                try:
                    elements = await page.locator(selector).all()
                    for element in elements:
                        text = await element.inner_text()
                        # Look for date patterns
                        if re.search(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', text, re.I):
                            deadline_text += text.strip() + "\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["DEADLINE"] = deadline_text.strip() if deadline_text else "Not found"
        
        # Extract duration information
        duration_text = ""
        try:
            duration_patterns = ["[class*='duration']", "[class*='period']", "[class*='timeline']"]
            for pattern in duration_patterns:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements:
                        text = await element.inner_text()
                        if re.search(r'\b(month|year|week|day)\b', text, re.I):
                            duration_text += text.strip() + "\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["DURATION"] = duration_text.strip() if duration_text else "Not found"
        
        # Extract eligibility criteria
        eligibility_text = ""
        try:
            eligibility_patterns = [
                "[class*='eligib']", "[class*='criteria']", "[class*='requirement']", 
                "[class*='who']", "[class*='apply']"
            ]
            for pattern in eligibility_patterns:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements:
                        text = await element.inner_text()
                        if len(text.strip()) > 20:  # Substantial content
                            eligibility_text += text.strip() + "\n\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["ELIGIBILITY"] = eligibility_text.strip() if eligibility_text else "Not found"
        
        # Extract themes/focus areas
        themes_text = ""
        try:
            theme_patterns = [
                "[class*='theme']", "[class*='focus']", "[class*='area']", 
                "[class*='priority']", "[class*='subject']", "[class*='topic']"
            ]
            for pattern in theme_patterns:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements:
                        text = await element.inner_text()
                        if len(text.strip()) > 10:
                            themes_text += text.strip() + "\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["THEMES"] = themes_text.strip() if themes_text else "Not found"
        
        # Extract how to apply information
        apply_text = ""
        try:
            apply_patterns = [
                "[class*='apply']", "[class*='application']", "[class*='submit']", 
                "[class*='process']", "[class*='how']"
            ]
            for pattern in apply_patterns:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements:
                        text = await element.inner_text()
                        if len(text.strip()) > 30:
                            apply_text += text.strip() + "\n\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["HOW TO APPLY"] = apply_text.strip() if apply_text else "Not found"
        
        # Extract contact information
        contact_text = ""
        try:
            contact_patterns = [
                "[class*='contact']", "[class*='enquir']", "[class*='email']", 
                "[class*='phone']", "[class*='support']"
            ]
            for pattern in contact_patterns:
                try:
                    elements = await page.locator(pattern).all()
                    for element in elements:
                        text = await element.inner_text()
                        if re.search(r'@|phone|tel|contact', text, re.I):
                            contact_text += text.strip() + "\n"
                except:
                    continue
        except:
            pass
            
        sectioned_content["CONTACT INFO"] = contact_text.strip() if contact_text else "Not found"
        
        # Format sectioned content for LLM
        formatted_content = ""
        for section, content in sectioned_content.items():
            formatted_content += f"=== {section} ===\n{content}\n\n"
        
        logger.info(f"✅ Extracted {len(sectioned_content)} content sections ({len(formatted_content)} characters)")
        return formatted_content
        
    except Exception as e:
        logger.error(f"🔴 Sectioned extraction failed: {str(e)}")
        # Fallback to simple text extraction
        try:
            body_text = await page.locator("body").inner_text()
            return f"=== FULL CONTENT ===\n{body_text[:8000]}"  # Truncate for safety
        except:
            return "=== ERROR ===\nFailed to extract any content"

async def fetch_webpage_content(url: str) -> str:
    """Fetch and extract sectioned content from a webpage using Playwright"""
    browser = None
    context = None
    page = None
    
    try:
        logger.info(f"🌐 Starting Playwright sectioned fetch for URL: {url}")
        
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
        
        # Extract sectioned content instead of full HTML
        sectioned_content = await extract_sectioned_content(page, url)
        
        logger.info(f"🎯 Extracted sectioned content for LLM parsing")
        return sectioned_content
        
    except Exception as e:
        error_msg = f"Playwright sectioned fetch failed for {url}: {str(e)}"
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

def create_structured_extraction_prompt(sectioned_html: str, url: str) -> str:
    """Create the new structured field extraction prompt as specified"""
    
    prompt = f"""You are an expert data parser. Given the following structured content about a funding opportunity, extract a JSON object with the following fields:

title (string)
donor (string)
summary (string)
amount (string)
deadline (string)
location (list of strings)
eligibility (list of strings)
themes (list of strings)
duration (string)
how_to_apply (string)
opportunity_url (string)
published_date (string or "Unknown")
contact_info (string)
_confidence_score (float 0–100)
_missing_required (list of string field names)
_low_quality_fields (list of string field names)

Only use information explicitly present in the content below. Do not invent or guess. If something is missing, mark it as "Unknown" or [] accordingly.

{sectioned_html}

Extract the data and return ONLY valid JSON with no additional text or formatting."""
    
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
        "_extraction_warning": f"Parsing failed: {error_message if error_message else 'Unknown error'}",
        "_confidence_score": 0.0,
        "_missing_required": EXPECTED_FIELDS["required"],
        "_low_quality_fields": []
    }
    
    logger.error(f"🔴 QA CRITICAL - Complete parsing failure for {url}: {error_message}")
    
    return fallback_data

async def retry_field_extraction(sectioned_html: str, field_name: str, url: str) -> str:
    """Retry extraction for a specific field with focused prompt"""
    try:
        focused_prompts = {
            "amount": f"""Extract ONLY the funding amount/budget information from this content. Look for currency symbols (£, $, €), numbers, and amount ranges. Return the amount as a string or "Unknown" if not found.

Content:
{sectioned_html}

Return only the amount value as a string.""",
            
            "location": f"""Extract ONLY the geographic location/eligibility information from this content. Look for city names, regions, countries, or geographic restrictions. Return as a list of strings or [] if not found.

Content:
{sectioned_html}

Return only the location as a JSON array of strings.""",
            
            "themes": f"""Extract ONLY the themes/focus areas from this content. Look for subject areas, priority topics, program focus, or thematic categories. Return as a list of strings or [] if not found.

Content:
{sectioned_html}

Return only the themes as a JSON array of strings."""
        }
        
        if field_name not in focused_prompts:
            return "Unknown"
            
        prompt = focused_prompts[field_name]
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only the requested information in the specified format."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.0,
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"🔄 Retry extraction for {field_name}: {content[:50]}...")
        return content
        
    except Exception as e:
        logger.error(f"🔴 Retry extraction failed for {field_name}: {str(e)}")
        return "Unknown"

def detect_currency_in_content(content: str) -> bool:
    """Detect if content contains currency symbols or amount indicators"""
    currency_pattern = r'[£$€¥¢₹]|\b(fund|grant|budget|amount|award|value|dollar|pound|euro)\b.*\d'
    return bool(re.search(currency_pattern, content, re.I))

def count_locations_in_content(content: str) -> int:
    """Count potential location mentions in content"""
    # Simple location detection - could be enhanced
    location_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:City|County|Region|State|Province|Country))?)\b'
    matches = re.findall(location_pattern, content)
    # Filter out common non-location words
    non_locations = {'And', 'The', 'For', 'With', 'This', 'That', 'Application', 'Grant', 'Fund'}
    locations = [m for m in matches if m not in non_locations and len(m) > 2]
    return len(set(locations))

async def post_llm_validation(parsed_data: dict, sectioned_html: str, url: str) -> dict:
    """Add post-LLM validation logic with retry for low-quality fields"""
    try:
        retries_performed = []
        
        # Check amount field for retry
        if (parsed_data.get("amount", "Unknown") == "Unknown" and 
            detect_currency_in_content(sectioned_html)):
            logger.info(f"🔄 Retrying amount extraction for {url} - currency detected but not extracted")
            retry_result = await retry_field_extraction(sectioned_html, "amount", url)
            if retry_result and retry_result != "Unknown":
                parsed_data["amount"] = retry_result.strip('"')
                retries_performed.append("amount")
        
        # Check location field quality
        location_field = parsed_data.get("location", [])
        if isinstance(location_field, list) and len(location_field) <= 1:
            content_location_count = count_locations_in_content(sectioned_html)
            if content_location_count > 1:
                logger.info(f"🔄 Retrying location extraction for {url} - {content_location_count} locations detected but only {len(location_field)} extracted")
                retry_result = await retry_field_extraction(sectioned_html, "location", url)
                if retry_result and retry_result != "Unknown":
                    try:
                        new_locations = json.loads(retry_result)
                        if isinstance(new_locations, list) and len(new_locations) > len(location_field):
                            parsed_data["location"] = new_locations
                            retries_performed.append("location")
                    except:
                        pass
        
        # Check themes field quality
        themes_field = parsed_data.get("themes", [])
        if isinstance(themes_field, list) and len(themes_field) <= 1:
            logger.info(f"🔄 Retrying themes extraction for {url} - insufficient themes detected")
            retry_result = await retry_field_extraction(sectioned_html, "themes", url)
            if retry_result and retry_result != "Unknown":
                try:
                    new_themes = json.loads(retry_result)
                    if isinstance(new_themes, list) and len(new_themes) > len(themes_field):
                        parsed_data["themes"] = new_themes
                        retries_performed.append("themes")
                except:
                    pass
        
        # Calculate confidence score
        required_fields = ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"]
        populated_fields = 0
        low_quality_fields = []
        missing_required = []
        
        for field in required_fields:
            if field in parsed_data and parsed_data[field]:
                value = parsed_data[field]
                if isinstance(value, str) and value.lower() not in ["unknown", "not found", "", "n/a"]:
                    populated_fields += 1
                elif isinstance(value, list) and value and value != ["unknown"] and value != []:
                    populated_fields += 1
                else:
                    low_quality_fields.append(field)
            else:
                missing_required.append(field)
        
        confidence_score = (populated_fields / len(required_fields)) * 100
        
        # Add validation metadata
        parsed_data["_confidence_score"] = round(confidence_score, 1)
        parsed_data["_missing_required"] = missing_required
        parsed_data["_low_quality_fields"] = low_quality_fields
        
        if retries_performed:
            parsed_data["_retries_performed"] = retries_performed
            logger.info(f"✅ Performed {len(retries_performed)} field retries for {url}: {retries_performed}")
        
        return parsed_data
        
    except Exception as e:
        logger.error(f"🔴 Post-LLM validation failed for {url}: {str(e)}")
        return parsed_data

def parse_funding_opportunity(sectioned_html: str, url: str = "URL_PLACEHOLDER") -> str:
    """Parse a funding opportunity from sectioned HTML using OpenAI with validation and retry logic"""
    try:
        if not openai.api_key:
            raise Exception("OpenAI API key not found. Please check your .env file.")
        
        if not sectioned_html or sectioned_html.strip() == "":
            raise Exception("No content provided for parsing")
        
        # Create structured prompt
        prompt = create_structured_extraction_prompt(sectioned_html, url)
        
        # Call OpenAI API
        logger.info(f"🔍 Calling OpenAI API for structured extraction of {url}")
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
            
            # Ensure required fields exist
            parsed_data["opportunity_url"] = url
            
            # Run async post-LLM validation in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we'll handle validation in the calling function
                validated_data = parsed_data
            else:
                # If we're in sync context, run the validation
                validated_data = loop.run_until_complete(post_llm_validation(parsed_data, sectioned_html, url))
            
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
    """Parse a funding opportunity from a URL using the structured extraction method with validation"""
    try:
        # Fetch sectioned webpage content
        logger.info(f"📄 Fetching sectioned content from URL: {url}")
        sectioned_content = await fetch_webpage_content(url)
        
        if not sectioned_content or sectioned_content.strip() == "":
            raise Exception("No content retrieved from webpage")
        
        # Parse using structured method
        json_response = parse_funding_opportunity(sectioned_content, url)
        parsed_data = json.loads(json_response)
        
        # Run post-LLM validation for enhanced accuracy
        logger.info(f"🔍 Running post-LLM validation for {url}")
        validated_data = await post_llm_validation(parsed_data, sectioned_content, url)
        
        # Ensure backward compatibility - maintain exact field names and types
        if "location" in validated_data and isinstance(validated_data["location"], list):
            # Convert list to string for backward compatibility if needed
            if len(validated_data["location"]) == 1:
                validated_data["location"] = validated_data["location"][0]
            elif len(validated_data["location"]) > 1:
                validated_data["location"] = ", ".join(validated_data["location"])
        
        # Add multi-tier parsing for variants
        try:
            from .multi_tier_parser import parse_multi_tier_opportunity
            logger.info(f"🔍 Running multi-tier analysis for {url}")
            
            # Parse variants from the HTML content
            variants = parse_multi_tier_opportunity(sectioned_content, url)
            
            if variants:
                # Add variants to the parsed data
                validated_data["variants"] = [variant.dict() for variant in variants]
                logger.info(f"✅ Extracted {len(variants)} variants for {url}")
                
                # Apply primary variant mapping to maintain backward compatibility
                from .variant_utils import apply_primary_to_top_level
                validated_data = apply_primary_to_top_level(validated_data)
                logger.info(f"✅ Applied primary variant mapping for {url}")
            else:
                validated_data["variants"] = []
                logger.info(f"ℹ️ No variants detected for {url}")
                
        except Exception as e:
            logger.warning(f"⚠️ Multi-tier parsing failed for {url}: {str(e)}")
            validated_data["variants"] = []
        
        logger.info(f"✅ Successfully parsed {url} with confidence: {validated_data.get('_confidence_score', 'N/A')}%")
        return validated_data
        
    except Exception as e:
        logger.error(f"🔴 Complete parsing failure for {url}: {str(e)}")
        return create_fallback_structure(url, f"URL parsing failed: {str(e)}")
