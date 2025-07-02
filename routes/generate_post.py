from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
import logging
import openai
import os
from typing import Dict, Any, List, Optional
import json
import re

# Database imports
from db import get_db
from models import FundingOpportunity, StatusEnum
from schemas import GeneratePostRequest, GeneratePostResponse, PostEditFeedbackRequest, FeedbackResponse
from utils.feedback_service import FeedbackService

# Set up logging
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Create router
router = APIRouter(prefix="/api", tags=["blog-generation"])

class BlogPostGenerator:
    """OpenAI-powered blog post generator for funding opportunities"""
    
    # Current prompt version for tracking
    CURRENT_PROMPT_VERSION = "v1.2"
    
    def __init__(self):
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
    
    def create_blog_generation_prompt(
        self, 
        funding_data: Dict[str, Any], 
        seo_keywords: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium",
        extra_instructions: Optional[str] = None
    ) -> str:
        """Create a structured prompt for OpenAI to generate a blog post"""
        
        # Extract funding information
        title = funding_data.get('title', 'Funding Opportunity')
        donor = funding_data.get('donor', 'N/A')
        summary = funding_data.get('summary', 'Summary not available')
        amount = funding_data.get('amount', 'Amount TBA')
        deadline = funding_data.get('deadline', 'Deadline TBA')
        location = funding_data.get('location', 'Location TBA')
        eligibility = funding_data.get('eligibility', [])
        themes = funding_data.get('themes', [])
        how_to_apply = funding_data.get('how_to_apply', 'Application process TBA')
        opportunity_url = funding_data.get('opportunity_url', '#')
        
        # Convert eligibility to string if it's a list
        if isinstance(eligibility, list):
            eligibility_text = ". ".join(str(item) for item in eligibility if item)
        else:
            eligibility_text = str(eligibility) if eligibility else "Eligibility criteria TBA"
        
        # Convert themes to string if it's a list
        if isinstance(themes, list):
            themes_text = ", ".join(str(theme) for theme in themes if theme)
        else:
            themes_text = str(themes) if themes else "General funding"
        
        # Define length guidelines
        length_guide = {
            "short": "800-1200 words",
            "medium": "1200-1800 words", 
            "long": "1800-2500 words"
        }
        
        # Define tone guidelines
        tone_guide = {
            "professional": "authoritative, formal, and informative",
            "persuasive": "compelling, action-oriented, and motivating",
            "informal": "conversational, accessible, and friendly"
        }
        
        prompt = f"""
You are an expert content writer specializing in funding opportunity blog posts for NGOInfo, a leading resource for nonprofit funding. Create a comprehensive, SEO-optimized blog post about this funding opportunity.

FUNDING OPPORTUNITY DATA:
- Title: {title}
- Donor: {donor}
- Summary: {summary}
- Amount: {amount}
- Deadline: {deadline}
- Location: {location}
- Eligibility: {eligibility_text}
- Themes: {themes_text}
- How to Apply: {how_to_apply}
- Opportunity URL: {opportunity_url}

CONTENT REQUIREMENTS:
- Length: {length_guide.get(length, 'medium length')} ({length})
- Tone: {tone_guide.get(tone, 'professional')} ({tone})
- Target audience: NGO leaders, grant writers, and nonprofit professionals
- SEO Keywords: {seo_keywords if seo_keywords else 'funding, grants, nonprofits, NGO'}

BLOG POST STRUCTURE (use this exact format):
1. Catchy, SEO-optimized title
2. Engaging introduction paragraph (hook readers immediately)
3. About the Donor (background, mission, previous funding)
4. Funding Overview (amount, focus areas, project types)
5. Eligibility Criteria (detailed requirements)
6. How to Apply (step-by-step process)
7. Call-to-action with opportunity URL

WRITING STYLE GUIDELINES:
- Write in {tone_guide.get(tone, 'professional')} tone
- Use subheadings (H2, H3) for better readability
- Include bullet points and lists where appropriate
- Make it conversion-focused and actionable
- Avoid robotic or AI-generated language
- Include relevant internal linking opportunities (mention NGOInfo resources)
- Add urgency around deadlines
- Use power words and emotional triggers appropriate for nonprofits

SEO OPTIMIZATION:
- Include target keywords naturally throughout
- Write compelling meta title and description
- Use semantic keywords related to nonprofit funding
- Structure content for featured snippets

ADDITIONAL INSTRUCTIONS:
{extra_instructions if extra_instructions else 'Follow standard NGOInfo blog formatting and style.'}

OUTPUT FORMAT:
Return a JSON object with exactly these fields:
{{
  "post_title": "SEO-optimized blog post title",
  "post_content": "Full HTML blog post content with proper heading tags",
  "meta_title": "SEO meta title (60 chars max)",
  "meta_description": "SEO meta description (160 chars max)",
  "tags": ["suggested", "blog", "tags"],
  "categories": ["suggested", "categories"]
}}

IMPORTANT: Return ONLY the JSON object, no additional text or formatting.
"""
        return prompt
    
    def generate_blog_post(
        self, 
        funding_data: Dict[str, Any],
        seo_keywords: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium", 
        extra_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate blog post using OpenAI"""
        try:
            # Create the prompt
            prompt = self.create_blog_generation_prompt(
                funding_data, seo_keywords, tone, length, extra_instructions
            )
            
            logger.info(f"🤖 Generating blog post with OpenAI for: {funding_data.get('title', 'Unknown')}")
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert content writer specializing in nonprofit funding blog posts. Always return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=4000,
                temperature=0.7
            )
            
            # Extract response content
            generated_content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                blog_data = json.loads(generated_content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                # Try to extract JSON from response if it's wrapped in text
                json_match = re.search(r'\{.*\}', generated_content, re.DOTALL)
                if json_match:
                    blog_data = json.loads(json_match.group())
                else:
                    raise ValueError("OpenAI returned invalid JSON format")
            
            # Validate required fields
            required_fields = ['post_title', 'post_content', 'meta_title', 'meta_description', 'tags', 'categories']
            for field in required_fields:
                if field not in blog_data:
                    blog_data[field] = ""
            
            # Ensure tags and categories are lists
            if not isinstance(blog_data.get('tags'), list):
                blog_data['tags'] = []
            if not isinstance(blog_data.get('categories'), list):
                blog_data['categories'] = []
            
            logger.info(f"✅ Successfully generated blog post: {blog_data.get('post_title', 'Untitled')}")
            return blog_data
            
        except Exception as e:
            logger.error(f"Failed to generate blog post: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate blog post: {str(e)}"
            )
    
    def extract_suggested_tags(self, funding_data: Dict[str, Any], seo_keywords: Optional[str] = None) -> List[str]:
        """Extract suggested tags from funding data and SEO keywords"""
        tags = []
        
        # Add from SEO keywords
        if seo_keywords:
            seo_tags = [tag.strip() for tag in seo_keywords.split(',') if tag.strip()]
            tags.extend(seo_tags)
        
        # Add from themes
        themes = funding_data.get('themes', [])
        if isinstance(themes, list):
            tags.extend([theme.lower().replace(' ', '-') for theme in themes if theme])
        elif themes:
            tags.append(themes.lower().replace(' ', '-'))
        
        # Add from location
        location = funding_data.get('location', '')
        if location and location != 'Unknown':
            tags.append(location.lower().replace(' ', '-'))
        
        # Add standard funding tags
        tags.extend(['funding', 'grants', 'nonprofit'])
        
        # Remove duplicates and return
        return list(set(tags))
    
    def extract_suggested_categories(self, funding_data: Dict[str, Any]) -> List[str]:
        """Extract suggested categories from funding data"""
        categories = []
        
        # Map themes to categories
        themes = funding_data.get('themes', [])
        if isinstance(themes, list):
            for theme in themes:
                if theme:
                    if any(word in theme.lower() for word in ['environment', 'climate', 'green']):
                        categories.append('Environmental Grants')
                    elif any(word in theme.lower() for word in ['education', 'school', 'university']):
                        categories.append('Education Funding')
                    elif any(word in theme.lower() for word in ['health', 'medical', 'healthcare']):
                        categories.append('Health Grants')
                    elif any(word in theme.lower() for word in ['community', 'social', 'development']):
                        categories.append('Community Development')
                    elif any(word in theme.lower() for word in ['research', 'innovation', 'technology']):
                        categories.append('Research Funding')
        
        # Add location-based categories
        location = funding_data.get('location', '')
        if 'UK' in location or 'United Kingdom' in location:
            categories.append('UK Opportunities')
        elif 'Europe' in location:
            categories.append('European Grants')
        elif 'Global' in location or 'International' in location:
            categories.append('International Funding')
        
        # Default category
        if not categories:
            categories.append('General Grants')
        
        return list(set(categories))

@router.post("/generate-post", response_model=GeneratePostResponse)
async def generate_post(
    request: GeneratePostRequest,
    db: Session = Depends(get_db)
) -> GeneratePostResponse:
    """
    Generate a blog post from an approved funding opportunity using OpenAI
    
    Args:
        request: Blog post generation request with record_id and optional parameters
        db: Database session dependency
    
    Returns:
        GeneratePostResponse: Generated blog post content for preview
    """
    try:
        logger.info(f"🚀 Generating blog post for record ID: {request.record_id}")
        
        # Fetch the funding opportunity from database
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == request.record_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {request.record_id} not found"
            )
        
        # Check if the opportunity is approved
        if opportunity.status != StatusEnum.approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Funding opportunity must be approved before generating blog post. Current status: {opportunity.status.value}"
            )
        
        # Extract funding data
        funding_data = opportunity.json_data or {}
        opportunity_url = funding_data.get('opportunity_url', opportunity.source_url)
        
        # Initialize blog generator
        generator = BlogPostGenerator()
        
        # Generate blog post using OpenAI
        blog_data = generator.generate_blog_post(
            funding_data=funding_data,
            seo_keywords=request.seo_keywords,
            tone=request.tone,
            length=request.length,
            extra_instructions=request.extra_instructions
        )
        
        # Add prompt version to response for tracking
        blog_data['prompt_version'] = generator.CURRENT_PROMPT_VERSION
        
        # Fallback tag and category generation if OpenAI didn't provide them
        if not blog_data.get('tags'):
            blog_data['tags'] = generator.extract_suggested_tags(funding_data, request.seo_keywords)
        
        if not blog_data.get('categories'):
            blog_data['categories'] = generator.extract_suggested_categories(funding_data)
        
        return GeneratePostResponse(
            success=True,
            message=f"Successfully generated blog post for '{funding_data.get('title', 'Unknown Opportunity')}'",
            post_title=blog_data.get('post_title'),
            post_content=blog_data.get('post_content'),
            tags=blog_data.get('tags', []),
            categories=blog_data.get('categories', []),
            meta_title=blog_data.get('meta_title'),
            meta_description=blog_data.get('meta_description'),
            opportunity_url=opportunity_url,
            record_id=request.record_id,
            prompt_version=blog_data.get('prompt_version', generator.CURRENT_PROMPT_VERSION)
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as they already have proper error details
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/generate-post/test/{record_id}")
async def test_generate_post(
    record_id: int,
    db: Session = Depends(get_db)
):
    """Test endpoint to check if a record is ready for blog generation"""
    try:
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == record_id
        ).first()
        
        if not opportunity:
            return {
                "success": False,
                "message": f"Record {record_id} not found",
                "record_exists": False
            }
        
        return {
            "success": True,
            "message": f"Record {record_id} found",
            "record_exists": True,
            "status": opportunity.status.value,
            "is_approved": opportunity.status == StatusEnum.approved,
            "has_data": bool(opportunity.json_data),
            "title": opportunity.json_data.get('title') if opportunity.json_data else None
        }
        
    except Exception as e:
        logger.error(f"Error in test_generate_post: {e}")
        return {
            "success": False,
            "message": f"Error checking record: {str(e)}"
        }

@router.post("/generate-post/feedback", response_model=FeedbackResponse)
async def capture_post_edit_feedback(
    request: PostEditFeedbackRequest,
    db: Session = Depends(get_db)
) -> FeedbackResponse:
    """
    Capture feedback on blog post generation edits
    
    Args:
        request: Post edit feedback request with original and edited sections
        db: Database session dependency
    
    Returns:
        FeedbackResponse: Success status and feedback count
    """
    try:
        logger.info(f"📝 Capturing blog post edit feedback for record ID: {request.record_id}")
        
        # Verify the record exists
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == request.record_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {request.record_id} not found"
            )
        
        # Split the section_edits into original and edited sections
        # Expected format: {"post_title": "edited title", "post_content": "edited content", ...}
        # We'll need to get the original sections from somewhere (could be stored temporarily)
        
        # For now, we'll treat the request.section_edits as the edited sections
        # and assume original sections are empty (can be enhanced later)
        original_sections = {}  # This could be passed in the request or retrieved from cache
        edited_sections = request.section_edits
        
        # Capture feedback
        feedback_count = FeedbackService.capture_post_edit_feedback(
            db=db,
            record_id=request.record_id,
            original_sections=original_sections,
            edited_sections=edited_sections,
            prompt_version=request.prompt_version
        )
        
        return FeedbackResponse(
            success=True,
            message=f"Successfully captured {feedback_count} post edit feedback entries",
            feedback_count=feedback_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error capturing post edit feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture post edit feedback: {str(e)}"
        )

@router.post("/generate-post/feedback-with-original")
async def capture_post_edit_feedback_with_original(
    record_id: int,
    original_post: Dict[str, str],
    edited_post: Dict[str, str],
    prompt_version: str = "v1.0",
    db: Session = Depends(get_db)
) -> FeedbackResponse:
    """
    Capture feedback with both original and edited post sections
    
    Args:
        record_id: ID of the funding opportunity
        original_post: Original generated sections
        edited_post: QA-edited sections
        prompt_version: Version of the generation prompt
        db: Database session dependency
    
    Returns:
        FeedbackResponse: Success status and feedback count
    """
    try:
        logger.info(f"📝 Capturing detailed blog post feedback for record ID: {record_id}")
        
        # Verify the record exists
        opportunity = db.query(FundingOpportunity).filter(
            FundingOpportunity.id == record_id
        ).first()
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Funding opportunity with ID {record_id} not found"
            )
        
        # Capture feedback on the differences
        feedback_count = FeedbackService.capture_post_edit_feedback(
            db=db,
            record_id=record_id,
            original_sections=original_post,
            edited_sections=edited_post,
            prompt_version=prompt_version
        )
        
        return FeedbackResponse(
            success=True,
            message=f"Successfully captured {feedback_count} detailed feedback entries",
            feedback_count=feedback_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error capturing detailed post feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture detailed post feedback: {str(e)}"
        )

@router.get("/generate-post/feedback/section/{section_name}")
async def get_section_feedback(
    section_name: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get feedback for a specific blog post section to analyze editing patterns
    """
    try:
        feedback = FeedbackService.get_post_section_feedback_summary(
            db=db,
            section=section_name,
            limit=limit
        )
        
        return {
            "success": True,
            "section": section_name,
            "feedback": feedback,
            "count": len(feedback),
            "message": f"Retrieved {len(feedback)} feedback entries for section '{section_name}'"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting section feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get section feedback: {str(e)}"
        ) 