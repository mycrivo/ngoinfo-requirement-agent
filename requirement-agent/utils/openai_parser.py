import os
import asyncio
from typing import Dict, Any
import logging
import httpx
from bs4 import BeautifulSoup
import openai
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

async def fetch_webpage_content(url: str) -> str:
    """Fetch and extract text content from a webpage"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(url)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:12000]  # Increased limit for better context
            
    except Exception as e:
        logger.error(f"Error fetching webpage content: {str(e)}")
        raise Exception(f"Failed to fetch webpage content: {str(e)}")

def create_robust_extraction_prompt(content: str, url: str) -> str:
    """Create a comprehensive prompt for extracting funding opportunity data across different donor websites"""
    
    prompt = f"""
You are an expert at extracting structured information from funding opportunity websites. Your task is to parse content from various donor websites (UK Gov, foundations, CSR portals, etc.) into a standardized JSON format.

WEBPAGE URL: {url}

WEBPAGE CONTENT:
{content}

EXTRACTION RULES:
1. Extract each required field as accurately as possible
2. If a field is missing, infer from context or return "Unknown"
3. Parse eligibility and themes as lists, even if not explicitly labeled
4. Summarize long text for summary and how_to_apply in 2-3 lines max
5. Normalize deadline and amount into readable formats
6. Always set opportunity_url as the input URL
7. Detect if page is not in English and return error if so

REQUIRED JSON OUTPUT STRUCTURE:
{{
  "title": "Full name/title of the funding opportunity",
  "donor": "Organization/agency providing the funding",
  "summary": "Brief 2-3 line summary of what the funding is for",
  "amount": "Funding amount or range (e.g., '£10,000', '£5K-£50K', 'Up to $100,000')",
  "deadline": "Application deadline in readable format (e.g., '31 March 2024', 'Rolling basis')",
  "location": "Geographic focus or eligible locations (e.g., 'UK', 'Global', 'London boroughs')",
  "eligibility": ["List of who can apply", "Age requirements", "Organization types", "etc."],
  "themes": ["Main focus areas", "Sector themes", "Priority topics", "etc."],
  "duration": "Project duration or funding period (optional)",
  "how_to_apply": "Brief application process summary (optional, 2-3 lines max)",
  "opportunity_url": "{url}",
  "published_date": "When the opportunity was published (optional)",
  "contact_info": "Contact details for questions (optional)"
}}

SPECIFIC EXTRACTION GUIDELINES:
- TITLE: Look for main headings, page titles, or prominent grant names
- DONOR: Look for "funded by", organization logos, "about us" sections
- SUMMARY: Combine purpose, objectives, and what the funding supports
- AMOUNT: Look for "funding available", "grant value", "award amount", currency symbols
- DEADLINE: Look for "deadline", "closing date", "apply by", date formats
- LOCATION: Look for "eligible areas", "geographic scope", country/region mentions
- ELIGIBILITY: Extract all criteria about who can apply (age, org type, location, etc.)
- THEMES: Identify focus areas, sectors, priority themes, subject areas
- DURATION: Look for "project length", "funding period", time-related terms
- HOW_TO_APPLY: Summarize application process, requirements, submission methods

ERROR HANDLING:
If fewer than 5 core fields (title, donor, deadline, amount, eligibility) contain meaningful data (not "Unknown"), include this warning field:
"_extraction_warning": "Low confidence extraction. Manual QA recommended."

RETURN ONLY VALID JSON - NO OTHER TEXT OR FORMATTING.
"""
    
    return prompt

def validate_extraction_quality(parsed_data: dict) -> dict:
    """Validate the quality of extraction and add warning if confidence is low"""
    
    core_fields = ['title', 'donor', 'deadline', 'amount', 'eligibility']
    meaningful_fields = 0
    
    for field in core_fields:
        if field in parsed_data:
            value = parsed_data[field]
            # Check if field has meaningful content (not empty, not "Unknown", not just whitespace)
            if value and str(value).strip() and str(value).strip().lower() != 'unknown':
                if field == 'eligibility' and isinstance(value, list) and len(value) > 0:
                    meaningful_fields += 1
                elif field != 'eligibility':
                    meaningful_fields += 1
    
    # Add warning if less than 5 core fields found
    if meaningful_fields < 5:
        parsed_data['_extraction_warning'] = "Low confidence extraction. Manual QA recommended."
        logger.warning(f"Low confidence extraction: only {meaningful_fields}/5 core fields found")
    
    return parsed_data

def parse_funding_opportunity(text: str) -> str:
    """Parse a funding opportunity from raw text using OpenAI with robust extraction"""
    try:
        if not openai.api_key:
            raise Exception("OpenAI API key not found. Please check your .env file.")
        
        # Create comprehensive prompt
        prompt = create_robust_extraction_prompt(text, "URL_PLACEHOLDER")
        
        # Call OpenAI API using v0.28.1 format with improved parameters
        logger.info("Calling OpenAI API for robust content extraction")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert funding opportunity analyst. Extract information accurately and comprehensively. Always return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,  # Increased for more detailed extraction
            temperature=0.1,   # Low temperature for consistency
        )
        
        # Extract the response content
        content = response.choices[0].message.content.strip()
        
        # Remove any markdown formatting if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        # Parse and validate the JSON
        try:
            parsed_data = json.loads(content.strip())
            
            # Validate extraction quality
            parsed_data = validate_extraction_quality(parsed_data)
            
            # Convert back to JSON string
            return json.dumps(parsed_data, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from OpenAI: {content}")
            # Return a basic structure if JSON parsing fails
            fallback_data = {
                "title": "Unknown",
                "donor": "Unknown", 
                "summary": "Failed to parse content",
                "amount": "Unknown",
                "deadline": "Unknown",
                "location": "Unknown",
                "eligibility": ["Unknown"],
                "themes": ["Unknown"],
                "duration": "Unknown",
                "how_to_apply": "Unknown",
                "opportunity_url": "URL_PLACEHOLDER",
                "published_date": "Unknown",
                "contact_info": "Unknown",
                "_extraction_warning": "JSON parsing failed. Manual review required."
            }
            return json.dumps(fallback_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error parsing funding opportunity: {str(e)}")
        raise Exception(f"Failed to parse funding opportunity: {str(e)}")

async def parse_funding_opportunity_from_url(url: str) -> dict:
    """Parse a funding opportunity from a URL using the robust extraction method"""
    try:
        # Fetch webpage content
        logger.info(f"Fetching content from URL: {url}")
        content = await fetch_webpage_content(url)
        
        # Create prompt with actual URL
        prompt = create_robust_extraction_prompt(content, url)
        
        # Call OpenAI API
        logger.info("Calling OpenAI API for robust URL-based extraction")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert funding opportunity analyst. Extract information accurately and comprehensively. Always return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.1,
        )
        
        # Extract and process response
        content_response = response.choices[0].message.content.strip()
        
        # Remove markdown formatting
        if content_response.startswith("```json"):
            content_response = content_response[7:]
        if content_response.endswith("```"):
            content_response = content_response[:-3]
        
        # Parse JSON and validate
        parsed_data = json.loads(content_response.strip())
        parsed_data = validate_extraction_quality(parsed_data)
        
        # Return the gold-standard structure directly
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error parsing funding opportunity from URL: {str(e)}")
        raise Exception(f"Failed to parse funding opportunity from URL: {str(e)}") 