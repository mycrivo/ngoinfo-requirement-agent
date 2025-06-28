#!/usr/bin/env python3
"""
Test script for the generate_blog_post function
"""

import sys
import os

# Add the current directory to Python path to import from routes
sys.path.append(os.path.dirname(__file__))

from routes.requirement_agent import generate_blog_post

def test_blog_generation():
    """Test the blog post generation with sample data"""
    
    # Sample funding opportunity record
    sample_opportunity = {
        "id": 1,
        "source_url": "https://example.com/digital-innovation-fund",
        "json_data": {
            "title": "Digital Innovation Fund 2024",
            "donor": "Technology Foundation",
            "location": "United Kingdom",
            "amount": "£15,000 - £75,000",
            "deadline": "15th June 2024",
            "summary": "This initiative aims to accelerate digital transformation within the third sector, with a particular focus on organizations serving disadvantaged communities across England, Scotland, Wales, and Northern Ireland.",
            "eligibility": [
                "Registered charities with annual income between £100K - £5M",
                "Community Interest Companies (CICs)", 
                "Social enterprises with charitable objectives",
                "Minimum 2 years operational experience"
            ],
            "themes": ["Digital inclusion", "Educational technology", "Healthcare innovation"],
            "opportunity_url": "https://techfoundation.org.uk/digital-innovation-fund"
        }
    }
    
    print("🧪 Testing Blog Post Generation")
    print("=" * 50)
    
    # Generate blog post
    blog_content = generate_blog_post(sample_opportunity)
    
    print("📄 Generated Blog Post:")
    print("-" * 30)
    print(blog_content)
    print("-" * 30)
    
    # Test with minimal data
    minimal_opportunity = {
        "source_url": "https://example.com/minimal-grant",
        "json_data": {
            "title": "Basic Grant Program",
            "summary": "A simple funding opportunity for community projects."
        }
    }
    
    print("\n🧪 Testing with Minimal Data")
    print("=" * 50)
    
    minimal_blog = generate_blog_post(minimal_opportunity)
    print("📄 Generated Blog Post (Minimal):")
    print("-" * 30)
    print(minimal_blog)
    print("-" * 30)

if __name__ == "__main__":
    test_blog_generation() 