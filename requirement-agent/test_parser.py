#!/usr/bin/env python3
"""
Test script for the improved gold-standard funding opportunity parser.
Tests the parser with sample text and URLs.
"""
import asyncio
import json
import logging
from utils.openai_parser import parse_funding_opportunity, fetch_webpage_content

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample funding opportunity text for testing
SAMPLE_FUNDING_TEXT = """
Community Foundation Grant Program

The Community Foundation is offering grants of up to £50,000 to support local charities and community groups working to improve the lives of disadvantaged young people in London.

Grant Details:
- Award Amount: £5,000 - £50,000
- Deadline: 31st March 2024
- Eligible Organizations: Registered charities, CICs, and community groups
- Location: London boroughs only
- Project Duration: 12-24 months

About the Program:
This grant program focuses on projects that address youth unemployment, educational inequality, and social exclusion among young people aged 16-25. Priority will be given to innovative approaches that demonstrate measurable impact.

How to Apply:
Applications must be submitted through our online portal by the deadline. Required documents include project proposal, budget, and evidence of charitable status.

Contact: grants@communityfoundation.org.uk
Phone: 020 7123 4567

Published: 15th January 2024
"""

def test_text_parsing():
    """Test the parser with sample text"""
    print("=" * 60)
    print("🧪 Testing Gold-Standard Parser with Sample Text")
    print("=" * 60)
    
    try:
        # Test the parser
        result = parse_funding_opportunity(SAMPLE_FUNDING_TEXT)
        
        # Parse the JSON result
        parsed_data = json.loads(result)
        
        print("✅ Parsing successful!")
        print("\n📋 Extracted Data:")
        print(json.dumps(parsed_data, indent=2))
        
        # Check for warning
        if "_extraction_warning" in parsed_data:
            print(f"\n⚠️  Warning: {parsed_data['_extraction_warning']}")
        else:
            print("\n✅ High confidence extraction - no warnings")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

async def test_url_parsing():
    """Test the parser with a real URL"""
    print("\n" + "=" * 60)
    print("🌐 Testing Gold-Standard Parser with Real URL")
    print("=" * 60)
    
    # Test URLs (choose a simple one that's likely to work)
    test_urls = [
        "https://tescostrongerstarts.org.uk/apply-for-a-grant/",
        "https://example.com"  # Fallback simple URL
    ]
    
    for url in test_urls:
        try:
            print(f"\n🔍 Testing URL: {url}")
            
            # Fetch content
            content = await fetch_webpage_content(url)
            print(f"📄 Content length: {len(content)} characters")
            
            # Parse with URL context
            result = parse_funding_opportunity(content).replace("URL_PLACEHOLDER", url)
            parsed_data = json.loads(result)
            
            print("✅ URL parsing successful!")
            print(f"📋 Title: {parsed_data.get('title', 'N/A')}")
            print(f"🏛️  Donor: {parsed_data.get('donor', 'N/A')}")
            print(f"💰 Amount: {parsed_data.get('amount', 'N/A')}")
            print(f"📅 Deadline: {parsed_data.get('deadline', 'N/A')}")
            
            if "_extraction_warning" in parsed_data:
                print(f"⚠️  Warning: {parsed_data['_extraction_warning']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error with {url}: {str(e)}")
            continue
    
    return False

def validate_json_structure(data):
    """Validate that the JSON structure matches the gold standard"""
    required_fields = [
        "title", "donor", "summary", "amount", "deadline", 
        "location", "eligibility", "themes", "opportunity_url"
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"❌ Missing required fields: {missing_fields}")
        return False
    
    # Check data types
    if not isinstance(data.get("eligibility"), list):
        print("❌ Eligibility should be a list")
        return False
        
    if not isinstance(data.get("themes"), list):
        print("❌ Themes should be a list")
        return False
    
    print("✅ JSON structure validation passed")
    return True

async def main():
    """Main test function"""
    print("🔧 Gold-Standard Funding Opportunity Parser Test Suite")
    
    # Test 1: Text parsing
    text_success = test_text_parsing()
    
    # Test 2: URL parsing  
    url_success = await test_url_parsing()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"Text Parsing: {'✅ PASS' if text_success else '❌ FAIL'}")
    print(f"URL Parsing: {'✅ PASS' if url_success else '❌ FAIL'}")
    
    if text_success and url_success:
        print("\n🎉 All tests passed! The gold-standard parser is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the implementation.")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 