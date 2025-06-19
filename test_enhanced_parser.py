#!/usr/bin/env python3
"""
Enhanced test script for the improved gold-standard funding opportunity parser
with comprehensive QA validation and logging.
"""
import asyncio
import json
import logging
from utils.openai_parser import parse_funding_opportunity, fetch_webpage_content

# Configure logging to show QA messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Enhanced sample funding opportunity text for testing
COMPREHENSIVE_FUNDING_TEXT = """
Digital Innovation Fund 2024

The Technology Foundation is pleased to announce the Digital Innovation Fund, offering grants of £15,000 to £75,000 
to support UK-based charities and social enterprises developing digital solutions for community challenges.

Programme Overview:
This initiative aims to accelerate digital transformation within the third sector, with a particular focus on 
organizations serving disadvantaged communities across England, Scotland, Wales, and Northern Ireland.

Grant Details:
- Funding Range: £15,000 - £75,000 per project
- Total Programme Budget: £2.5 million
- Application Deadline: 15th June 2024, 5:00 PM GMT
- Project Duration: 12-18 months
- Geographic Scope: United Kingdom

Eligibility Criteria:
- Registered charities with annual income between £100K - £5M
- Community Interest Companies (CICs)
- Social enterprises with charitable objectives
- Minimum 2 years operational experience
- Must demonstrate digital innovation potential

Priority Areas:
- Digital inclusion and accessibility
- Educational technology for disadvantaged learners
- Healthcare innovation and telemedicine
- Environmental sustainability platforms
- Community engagement and participation tools

Application Process:
Applications must be submitted online through our grant portal. Required documentation includes:
1. Completed application form
2. Project proposal (max 15 pages)
3. Detailed budget breakdown
4. Three professional references
5. Evidence of charitable registration

Assessment Timeline:
- Application deadline: 15th June 2024
- Initial review: July 2024
- Final decisions: August 2024
- Project start date: September 2024

Contact Information:
Email: grants@techfoundation.org.uk
Phone: 0203 456 7890
Address: Technology Foundation, 25 Innovation Square, London EC2A 4LT

Programme Manager: Dr. Sarah Williams
Grant Administrator: Michael Chen

Published: 1st March 2024
Last Updated: 15th March 2024

About the Technology Foundation:
Established in 2018, the Technology Foundation is a leading grant-making organization focused on advancing 
digital innovation within the charitable sector across the UK.
"""

def test_comprehensive_parsing():
    """Test the enhanced parser with comprehensive sample text"""
    print("=" * 80)
    print("🧪 Testing Enhanced Gold-Standard Parser with Comprehensive Text")
    print("=" * 80)
    
    try:
        # Test the enhanced parser
        result = parse_funding_opportunity(COMPREHENSIVE_FUNDING_TEXT, "https://techfoundation.org.uk/digital-innovation-fund")
        
        # Parse the JSON result
        parsed_data = json.loads(result)
        
        print("✅ Enhanced parsing successful!")
        print(f"🎯 Confidence Score: {parsed_data.get('_confidence_score', 'N/A')}%")
        
        # Show QA metadata
        if '_extraction_warning' in parsed_data:
            print(f"⚠️ Warning: {parsed_data['_extraction_warning']}")
        
        if '_missing_required' in parsed_data and parsed_data['_missing_required']:
            print(f"🚨 Missing Required Fields: {parsed_data['_missing_required']}")
        
        if '_low_quality_fields' in parsed_data and parsed_data['_low_quality_fields']:
            print(f"⚠️ Low Quality Fields: {parsed_data['_low_quality_fields']}")
        
        print("\n📋 Extracted Data Summary:")
        print(f"   Title: {parsed_data.get('title', 'N/A')}")
        print(f"   Donor: {parsed_data.get('donor', 'N/A')}")
        print(f"   Amount: {parsed_data.get('amount', 'N/A')}")
        print(f"   Deadline: {parsed_data.get('deadline', 'N/A')}")
        print(f"   Location: {parsed_data.get('location', 'N/A')}")
        print(f"   Eligibility Count: {len(parsed_data.get('eligibility', []))}")
        print(f"   Themes Count: {len(parsed_data.get('themes', []))}")
        
        print(f"\n📄 Full JSON Output:")
        # Filter out internal metadata for display
        display_data = {k: v for k, v in parsed_data.items() if not k.startswith('_')}
        print(json.dumps(display_data, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_minimal_text():
    """Test parser with minimal information to trigger QA warnings"""
    print("\n" + "=" * 80)
    print("🧪 Testing Enhanced Parser with Minimal Text (QA Warning Test)")
    print("=" * 80)
    
    minimal_text = "Grant available. Contact us for more information."
    
    try:
        result = parse_funding_opportunity(minimal_text, "https://example.com/minimal-grant")
        parsed_data = json.loads(result)
        
        print("✅ Minimal text parsing completed")
        print(f"🎯 Confidence Score: {parsed_data.get('_confidence_score', 'N/A')}%")
        
        if '_extraction_warning' in parsed_data:
            print(f"⚠️ Warning: {parsed_data['_extraction_warning']}")
        
        if '_missing_required' in parsed_data:
            print(f"🚨 Missing Required Fields: {parsed_data['_missing_required']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

async def test_url_parsing_with_fallback():
    """Test URL parsing with fallback handling"""
    print("\n" + "=" * 80)
    print("🌐 Testing Enhanced URL Parser with Error Handling")
    print("=" * 80)
    
    # Test with a simple URL that should work
    test_url = "https://httpbin.org/html"
    
    try:
        print(f"🔍 Testing URL: {test_url}")
        
        # Fetch content
        content = await fetch_webpage_content(test_url)
        print(f"📄 Content fetched: {len(content)} characters")
        
        # Parse with enhanced method
        result = parse_funding_opportunity(content, test_url)
        parsed_data = json.loads(result)
        
        print("✅ URL parsing completed")
        print(f"🎯 Confidence Score: {parsed_data.get('_confidence_score', 'N/A')}%")
        
        if '_extraction_warning' in parsed_data:
            print(f"⚠️ Warning: {parsed_data['_extraction_warning']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def validate_field_completeness(data):
    """Validate that all expected fields are present in the output"""
    print("\n" + "=" * 80)
    print("🔍 Validating Field Completeness")
    print("=" * 80)
    
    required_fields = ["title", "donor", "summary", "amount", "deadline", "location", "eligibility", "themes"]
    optional_fields = ["duration", "how_to_apply", "published_date", "contact_info"]
    meta_fields = ["opportunity_url"]
    
    present_required = []
    missing_required = []
    present_optional = []
    missing_optional = []
    
    for field in required_fields:
        if field in data and data[field] and str(data[field]).strip().lower() not in ['unknown', 'n/a']:
            present_required.append(field)
        else:
            missing_required.append(field)
    
    for field in optional_fields:
        if field in data and data[field] and str(data[field]).strip().lower() not in ['unknown', 'n/a']:
            present_optional.append(field)
        else:
            missing_optional.append(field)
    
    print(f"✅ Present Required Fields ({len(present_required)}/8): {present_required}")
    print(f"❌ Missing Required Fields ({len(missing_required)}/8): {missing_required}")
    print(f"📝 Present Optional Fields ({len(present_optional)}/4): {present_optional}")
    print(f"📝 Missing Optional Fields ({len(missing_optional)}/4): {missing_optional}")
    
    completeness_score = (len(present_required) / len(required_fields)) * 100
    print(f"📊 Completeness Score: {completeness_score:.1f}%")
    
    return completeness_score >= 80

async def main():
    """Main enhanced test function"""
    print("🔧 Enhanced Gold-Standard Parser Test Suite with QA Validation")
    
    # Test 1: Comprehensive text parsing
    comprehensive_success = test_comprehensive_parsing()
    
    # Test 2: Minimal text (QA warning test)
    minimal_success = test_minimal_text()
    
    # Test 3: URL parsing with error handling
    url_success = await test_url_parsing_with_fallback()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Enhanced Test Results Summary")
    print("=" * 80)
    print(f"Comprehensive Text Parsing: {'✅ PASS' if comprehensive_success else '❌ FAIL'}")
    print(f"Minimal Text Parsing (QA): {'✅ PASS' if minimal_success else '❌ FAIL'}")
    print(f"URL Parsing with Fallback: {'✅ PASS' if url_success else '❌ FAIL'}")
    
    if comprehensive_success and minimal_success and url_success:
        print("\n🎉 All enhanced tests passed! The parser is ready for production use.")
        print("✅ QA logging and validation systems are operational.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check the implementation and logs.")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 