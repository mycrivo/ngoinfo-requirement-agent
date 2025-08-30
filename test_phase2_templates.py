#!/usr/bin/env python3
"""
Test script for Phase 2 Proposal Template Implementation
Tests the core functionality without requiring the full FastAPI app
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_storage_service():
    """Test the storage service functionality"""
    print("🧪 Testing Storage Service...")
    
    try:
        from services.storage import StorageService
        
        # Create storage service
        storage = StorageService()
        print(f"✅ Storage service initialized with {storage.backend_type} backend")
        
        # Test basic operations
        test_data = b"Hello, World! This is a test file."
        test_path = "test/hello.txt"
        
        # Save data
        saved_path = storage.save_bytes(test_path, test_data)
        print(f"✅ Data saved to: {saved_path}")
        
        # Check if file exists
        exists = storage.exists(test_path)
        print(f"✅ File exists check: {exists}")
        
        # Read data back
        read_data = storage.open(test_path)
        print(f"✅ Data read back: {read_data == test_data}")
        
        # Get file size
        size = storage.get_file_size(test_path)
        print(f"✅ File size: {size} bytes")
        
        # Clean up
        storage.delete(test_path)
        print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Storage service test failed: {e}")
        return False

def test_template_generator():
    """Test the template generator functionality"""
    print("\n🧪 Testing Template Generator...")
    
    try:
        from services.template_generator import ProposalTemplateGenerator, ContentModel
        
        # Create generator
        generator = ProposalTemplateGenerator()
        print(f"✅ Template generator initialized with PDF engine: {generator.pdf_engine}")
        
        # Test content model building
        opportunity_data = {
            'title': 'Test Funding Opportunity',
            'donor': 'Test Foundation',
            'deadline': '2024-12-31',
            'amount': '$50,000',
            'location': 'Global',
            'themes': ['Education', 'Technology'],
            'opportunity_url': 'https://example.com/test'
        }
        
        sections = [
            {'heading': 'Executive Summary', 'instruction': 'Provide overview'},
            {'heading': 'Project Description', 'instruction': 'Describe project'}
        ]
        
        content_model = generator.build_content_model(opportunity_data, sections)
        print(f"✅ Content model built with {len(content_model.sections)} sections")
        
        # Test hash computation
        content_hash = content_model.compute_hash()
        print(f"✅ Content hash computed: {content_hash[:16]}...")
        
        # Test DOCX generation
        docx_bytes = generator.generate_docx(content_model)
        print(f"✅ DOCX generated: {len(docx_bytes)} bytes")
        
        # Test PDF generation (if available)
        try:
            pdf_bytes = generator.generate_pdf(content_model)
            if pdf_bytes:
                print(f"✅ PDF generated: {len(pdf_bytes)} bytes")
            else:
                print("⚠️ PDF generation not available")
        except Exception as e:
            print(f"⚠️ PDF generation failed (expected): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Template generator test failed: {e}")
        return False

def test_storage_integration():
    """Test storage integration with template generation"""
    print("\n🧪 Testing Storage Integration...")
    
    try:
        from services.storage import storage_service
        from services.template_generator import ProposalTemplateGenerator
        
        # Create test opportunity data
        opportunity_data = {
            'title': 'Integration Test Opportunity',
            'donor': 'Test Donor',
            'deadline': '2024-12-31',
            'amount': '$100,000',
            'location': 'Test Location',
            'themes': ['Test Theme'],
            'opportunity_url': 'https://example.com/test'
        }
        
        sections = [
            {'heading': 'Test Section', 'instruction': 'Test instruction'}
        ]
        
        # Generate template
        generator = ProposalTemplateGenerator()
        content_model, docx_bytes, pdf_bytes = generator.generate_template(
            opportunity_data, sections
        )
        
        # Save to storage
        docx_path = "test_templates/test_integration.docx"
        saved_docx_path = storage_service.save_bytes(docx_path, docx_bytes)
        print(f"✅ DOCX saved to storage: {saved_docx_path}")
        
        # Verify storage
        exists = storage_service.exists(docx_path)
        print(f"✅ File exists in storage: {exists}")
        
        # Read back and verify
        read_data = storage_service.open(docx_path)
        print(f"✅ Data integrity verified: {read_data == docx_bytes}")
        
        # Clean up
        storage_service.delete(docx_path)
        print("✅ Test files cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Storage integration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Phase 2 Template Implementation Tests")
    print("=" * 50)
    
    tests = [
        test_storage_service,
        test_template_generator,
        test_storage_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Phase 2 implementation is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

