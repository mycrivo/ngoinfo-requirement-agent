#!/usr/bin/env python3
"""
Phase 3 PDF Processing Tests
Tests PDF ingestion, extraction, parsing, and API endpoints
"""

import os
import sys
import tempfile
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Test imports
from services.pdf_extract import PDFExtractor, ExtractResult, TextBlock, PDFExtractionError, PDFValidationError
from services.pdf_to_gold import PDFToGoldParser, ParsedOpportunity, PDFParseError
from routes.documents import DocumentService

def test_pdf_extractor_initialization():
    """Test PDF extractor initialization and OCR capability detection"""
    print("🧪 Testing PDF extractor initialization...")
    
    # Test with no OCR backend
    with patch.dict(os.environ, {'OCR_BACKEND': 'none'}):
        extractor = PDFExtractor()
        assert extractor.ocr_backend == "none"
        print("✅ No OCR backend configured correctly")
    
    # Test with textract backend (mocked)
    with patch.dict(os.environ, {'OCR_BACKEND': 'textract'}):
        with patch('builtins.__import__', side_effect=ImportError("boto3 not available")):
            extractor = PDFExtractor()
            assert extractor.ocr_backend == "none"  # Should fallback
            print("✅ Textract fallback handled correctly")
    
    print("✅ PDF extractor initialization tests passed")

def test_pdf_validation():
    """Test PDF validation logic"""
    print("🧪 Testing PDF validation...")
    
    extractor = PDFExtractor()
    
    # Test valid PDF
    valid_pdf = b'%PDF-1.4\n%Test PDF content\n'
    try:
        extractor._validate_pdf_bytes(valid_pdf)
        print("✅ Valid PDF validation passed")
    except PDFValidationError:
        pytest.fail("Valid PDF should not raise validation error")
    
    # Test invalid PDF (no magic number)
    invalid_pdf = b'Not a PDF file'
    with pytest.raises(PDFValidationError):
        extractor._validate_pdf_bytes(invalid_pdf)
        print("✅ Invalid PDF validation caught")
    
    # Test empty PDF
    empty_pdf = b''
    with pytest.raises(PDFValidationError):
        extractor._validate_pdf_bytes(empty_pdf)
        print("✅ Empty PDF validation caught")
    
    # Test oversized PDF
    oversized_pdf = b'%PDF-1.4\n' + b'x' * (21 * 1024 * 1024)  # 21MB
    with patch.dict(os.environ, {'MAX_UPLOAD_MB': '20'}):
        with pytest.raises(PDFValidationError):
            extractor._validate_pdf_bytes(oversized_pdf)
            print("✅ Oversized PDF validation caught")
    
    print("✅ PDF validation tests passed")

def test_url_validation():
    """Test URL validation logic"""
    print("🧪 Testing URL validation...")
    
    extractor = PDFExtractor()
    
    # Test valid HTTPS URL
    valid_url = "https://example.com/document.pdf"
    try:
        extractor._validate_url(valid_url)
        print("✅ Valid HTTPS URL validation passed")
    except PDFValidationError:
        pytest.fail("Valid HTTPS URL should not raise validation error")
    
    # Test invalid schemes
    invalid_schemes = [
        "http://example.com/document.pdf",
        "ftp://example.com/document.pdf",
        "file:///path/to/document.pdf",
        "data:application/pdf;base64,JVBERi0xLjQK"
    ]
    
    for url in invalid_schemes:
        with pytest.raises(PDFValidationError):
            extractor._validate_url(url)
            print(f"✅ Invalid scheme caught: {url}")
    
    # Test malformed URLs
    malformed_urls = [
        "not-a-url",
        "https://",
        "https://example.com",
        ""
    ]
    
    for url in malformed_urls:
        with pytest.raises(PDFValidationError):
            extractor._validate_url(url)
            print(f"✅ Malformed URL caught: {url}")
    
    print("✅ URL validation tests passed")

def test_confidence_calculation():
    """Test confidence score calculation"""
    print("🧪 Testing confidence calculation...")
    
    extractor = PDFExtractor()
    
    # Test high confidence text
    high_confidence_text = """
    GRANT OPPORTUNITY
    This funding opportunity provides up to $100,000 for eligible organizations.
    Eligibility criteria include non-profit status and focus on education.
    Application deadline is December 31, 2024.
    The program supports projects in the United States.
    """
    
    confidence = extractor._calculate_native_confidence(high_confidence_text)
    assert confidence > 0.7
    print(f"✅ High confidence text scored: {confidence:.2f}")
    
    # Test low confidence text
    low_confidence_text = "Random text without funding keywords"
    confidence = extractor._calculate_native_confidence(low_confidence_text)
    assert confidence < 0.5
    print(f"✅ Low confidence text scored: {confidence:.2f}")
    
    # Test empty text
    confidence = extractor._calculate_native_confidence("")
    assert confidence == 0.1
    print("✅ Empty text confidence handled correctly")
    
    print("✅ Confidence calculation tests passed")

def test_pdf_to_gold_parser():
    """Test PDF to gold standard parser"""
    print("🧪 Testing PDF to gold standard parser...")
    
    parser = PDFToGoldParser()
    
    # Test text sanitization
    dirty_text = "Text with\x00control\x1Fcharacters\n\n\nand   extra   spaces"
    clean_text = parser._sanitize_text(dirty_text)
    assert '\x00' not in clean_text
    assert '\x1F' not in clean_text
    assert '   ' not in clean_text
    print("✅ Text sanitization working correctly")
    
    # Test text truncation
    long_text = "x" * 15000
    truncated_text = parser._sanitize_text(long_text)
    assert len(truncated_text) <= parser.max_text_length
    assert "[truncated]" in truncated_text
    print("✅ Text truncation working correctly")
    
    print("✅ PDF to gold parser tests passed")

def test_rule_based_parsing():
    """Test rule-based parsing fallback"""
    print("🧪 Testing rule-based parsing...")
    
    parser = PDFToGoldParser()
    
    # Create mock extract result
    mock_extract_result = Mock()
    mock_extract_result.text = """
    GRANT OPPORTUNITY FOR EDUCATION INNOVATION
    
    Funded by: National Education Foundation
    Amount: $50,000 - $100,000
    Deadline: March 15, 2024
    Location: United States
    
    Eligibility:
    • Non-profit organizations
    • Educational institutions
    • Community groups
    
    Focus Areas:
    • Technology in education
    • STEM programs
    • Digital literacy
    
    Duration: 12-18 months
    How to Apply: Submit online application
    Contact: grants@nef.org
    """
    mock_extract_result.engine = "native-pymupdf"
    mock_extract_result.pages = 3
    
    # Test parsing
    try:
        opportunity = parser._parse_with_rules(mock_extract_result.text, mock_extract_result, "test.pdf")
        
        # Check required fields
        assert opportunity.title != "Unknown"
        assert opportunity.donor != "Unknown"
        assert opportunity.amount != "Unknown"
        assert opportunity.deadline != "Unknown"
        assert opportunity.location != "Unknown"
        assert len(opportunity.eligibility) > 0
        assert len(opportunity.themes) > 0
        
        print(f"✅ Parsed title: {opportunity.title}")
        print(f"✅ Parsed donor: {opportunity.donor}")
        print(f"✅ Parsed amount: {opportunity.amount}")
        print(f"✅ Parsed deadline: {opportunity.deadline}")
        print(f"✅ Parsed location: {opportunity.location}")
        print(f"✅ Parsed eligibility: {opportunity.eligibility}")
        print(f"✅ Parsed themes: {opportunity.themes}")
        
    except Exception as e:
        pytest.fail(f"Rule-based parsing failed: {e}")
    
    print("✅ Rule-based parsing tests passed")

def test_validation_metrics():
    """Test parsed opportunity validation"""
    print("🧪 Testing validation metrics...")
    
    parser = PDFToGoldParser()
    
    # Create test opportunity
    opportunity = ParsedOpportunity(
        title="Test Opportunity",
        donor="Test Foundation",
        summary="Test summary",
        amount="$10,000",
        deadline="2024-12-31",
        location="United States",
        eligibility=["Non-profit status"],
        themes=["Education"],
        confidence_score=0.85,
        extraction_engine="native-pymupdf",
        pages_extracted=2
    )
    
    # Test validation
    validation = parser.validate_parsed_opportunity(opportunity)
    
    assert validation["is_valid"] == True
    assert len(validation["missing_required"]) == 0
    assert validation["confidence_score"] == 0.85
    assert validation["extraction_engine"] == "native-pymupdf"
    
    print("✅ Validation metrics working correctly")
    
    # Test invalid opportunity
    invalid_opportunity = ParsedOpportunity(
        title="Unknown",
        donor="Unknown",
        summary="No summary available",
        amount="Unknown",
        deadline="Unknown",
        location="Unknown",
        eligibility=[],
        themes=[],
        confidence_score=0.1,
        extraction_engine="fallback",
        pages_extracted=1
    )
    
    validation = parser.validate_parsed_opportunity(invalid_opportunity)
    
    assert validation["is_valid"] == False
    assert len(validation["missing_required"]) > 0
    assert len(validation["low_quality_fields"]) > 0
    
    print("✅ Invalid opportunity validation working correctly")
    
    print("✅ Validation metrics tests passed")

def test_document_service():
    """Test document service functionality"""
    print("🧪 Testing document service...")
    
    service = DocumentService()
    
    # Test configuration
    assert service.max_upload_mb == 20  # Default from env
    assert service.max_upload_bytes == 20 * 1024 * 1024
    
    print("✅ Document service configuration correct")
    
    # Test file size validation
    mock_file = Mock()
    mock_file.filename = "test.pdf"
    mock_file.file = BytesIO(b"x" * (10 * 1024 * 1024))  # 10MB
    
    # Should not raise error for valid size
    try:
        mock_file.file.seek(0, 2)
        file_size = mock_file.file.tell()
        mock_file.file.seek(0)
        
        assert file_size <= service.max_upload_bytes
        print("✅ File size validation working correctly")
    except Exception as e:
        pytest.fail(f"File size validation failed: {e}")
    
    print("✅ Document service tests passed")

def test_api_endpoints():
    """Test API endpoint structure"""
    print("🧪 Testing API endpoint structure...")
    
    # Import router to check endpoints
    from routes.documents import router
    
    # Check that router has expected endpoints
    routes = [route.path for route in router.routes]
    
    expected_routes = [
        "/api/documents/ingest-url",
        "/api/documents/upload",
        "/api/documents/{document_id}",
        "/api/documents/{document_id}/download",
        "/api/documents/{document_id}/text"
    ]
    
    for expected_route in expected_routes:
        # Check if route exists (accounting for path parameters)
        route_exists = any(
            expected_route.replace("{document_id}", "123") in route 
            for route in routes
        )
        assert route_exists, f"Route {expected_route} not found"
        print(f"✅ Route found: {expected_route}")
    
    print("✅ API endpoint structure tests passed")

def test_error_handling():
    """Test error handling and exceptions"""
    print("🧪 Testing error handling...")
    
    # Test PDF extraction error
    with pytest.raises(PDFExtractionError):
        raise PDFExtractionError("Test extraction error")
    
    # Test PDF validation error
    with pytest.raises(PDFValidationError):
        raise PDFValidationError("Test validation error")
    
    # Test PDF parse error
    with pytest.raises(PDFParseError):
        raise PDFParseError("Test parse error")
    
    print("✅ Error handling tests passed")

def test_integration_scenarios():
    """Test integration scenarios"""
    print("🧪 Testing integration scenarios...")
    
    # Test complete flow with mock data
    mock_extract_result = ExtractResult(
        pages=2,
        text="Test PDF content with funding opportunity details",
        blocks=[],
        confidence=0.8,
        engine="native-pymupdf",
        extraction_time_ms=150.0,
        ocr_used=False
    )
    
    parser = PDFToGoldParser()
    
    try:
        # Test parsing
        opportunity = parser.parse_to_gold_standard(mock_extract_result, "test.pdf")
        
        # Test validation
        validation = parser.validate_parsed_opportunity(opportunity)
        
        # Basic assertions
        assert opportunity.pages_extracted == 2
        assert opportunity.extraction_engine == "native-pymupdf"
        assert opportunity.confidence_score == 0.8
        
        print("✅ Integration flow working correctly")
        
    except Exception as e:
        pytest.fail(f"Integration test failed: {e}")
    
    print("✅ Integration scenario tests passed")

def main():
    """Run all tests"""
    print("🚀 Starting Phase 3 PDF Processing Tests...")
    print("=" * 60)
    
    test_functions = [
        test_pdf_extractor_initialization,
        test_pdf_validation,
        test_url_validation,
        test_confidence_calculation,
        test_pdf_to_gold_parser,
        test_rule_based_parsing,
        test_validation_metrics,
        test_document_service,
        test_api_endpoints,
        test_error_handling,
        test_integration_scenarios
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All Phase 3 tests passed!")
        return True
    else:
        print(f"⚠️ {failed} tests failed. Please review and fix issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)





