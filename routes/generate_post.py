from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
import logging
import openai
import os
from typing import Dict, Any, List, Optional
import json
import re
from bs4 import BeautifulSoup

# Database imports
from db import get_db
from models import FundingOpportunity, StatusEnum, BlogPost
from schemas import (
    GeneratePostRequest, GeneratePostResponse, PostEditFeedbackRequest, FeedbackResponse,
    SavedBlogPostResponse, GetBlogPostRequest, GetBlogPostResponse, RegenerateBlogPostRequest
)
from utils.feedback_service import FeedbackService

# Set up logging
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Create router
router = APIRouter(prefix="/api", tags=["blog-generation"])

def sanitize_input_string(input_string: str) -> str:
    """Sanitize input strings to remove invalid control characters before sending to OpenAI"""
    if not input_string:
        return ""
    
    # Remove control characters (except newlines and tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", input_string)
    
    # Log if we found and removed problematic characters
    if sanitized != input_string:
        logger.warning(f"🧹 Sanitized input string: removed {len(input_string) - len(sanitized)} control characters")
    
    return sanitized.strip()

def sanitize_openai_response(response_text: str) -> str:
    """Sanitize OpenAI response to remove invalid control characters before json.loads"""
    if not response_text:
        return ""
    
    try:
        # First pass: Encode/decode to handle UTF-8 issues
        safe_text = response_text.encode("utf-8", "ignore").decode("utf-8")
        
        # Second pass: Remove remaining control characters (except newlines and tabs)
        clean_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", safe_text)
        
        # Log if we found and removed problematic characters
        if clean_text != response_text:
            logger.warning(f"🧹 Sanitized OpenAI response: removed {len(response_text) - len(clean_text)} problematic characters")
            logger.debug(f"Original length: {len(response_text)}, Clean length: {len(clean_text)}")
        
        return clean_text
        
    except Exception as e:
        logger.error(f"🔴 Error sanitizing OpenAI response: {e}")
        # Fallback: more aggressive cleaning
        return re.sub(r"[^\x20-\x7E\n\t]", "", response_text)

def count_words_in_html(html_content: str) -> int:
    """Count words in HTML content by extracting text"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        words = len(text.split())
        return words
    except Exception as e:
        logger.warning(f"⚠️ Error counting words in HTML: {e}")
        # Fallback to simple word count
        return len(html_content.split())

def check_seo_keywords_coverage(content: str, seo_keywords: str) -> Dict[str, Any]:
    """Check if SEO keywords appear in the content"""
    if not seo_keywords:
        return {"missing_keywords": [], "coverage_percentage": 100}
    
    keywords = [kw.strip().lower() for kw in seo_keywords.split(',') if kw.strip()]
    content_lower = content.lower()
    
    missing_keywords = []
    found_keywords = []
    
    for keyword in keywords:
        if keyword in content_lower:
            found_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    
    coverage_percentage = (len(found_keywords) / len(keywords)) * 100 if keywords else 100
    
    return {
        "missing_keywords": missing_keywords,
        "found_keywords": found_keywords,
        "coverage_percentage": coverage_percentage
    }

class BlogPostGenerator:
    """OpenAI-powered blog post generator for funding opportunities"""
    
    # Current prompt version for tracking
    CURRENT_PROMPT_VERSION = "v2.0_enhanced"
    
    def __init__(self):
        if not openai.api_key:
            raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
    
    def get_word_count_range(self, length: str) -> tuple[int, int]:
        """Get word count range for the specified length"""
        length_ranges = {
            "short": (800, 1200),
            "medium": (1200, 1800), 
            "long": (1800, 2500)
        }
        return length_ranges.get(length, (1200, 1800))
    
    def estimate_max_tokens(self, target_words: int) -> int:
        """Estimate max tokens needed based on target word count"""
        # Rule of thumb: 1 word ≈ 1.3 tokens, add buffer for HTML tags and structure
        estimated_tokens = int(target_words * 1.5) + 500
        # Cap at OpenAI limits
        return min(estimated_tokens, 4000)
    
    def create_enhanced_blog_prompt(
        self, 
        funding_data: Dict[str, Any], 
        seo_keywords: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium",
        extra_instructions: Optional[str] = None
    ) -> str:
        """Create an enhanced prompt for comprehensive blog post generation"""
        
        # Sanitize all inputs
        seo_keywords = sanitize_input_string(seo_keywords or "")
        extra_instructions = sanitize_input_string(extra_instructions or "")
        
        # Extract and sanitize funding information
        title = sanitize_input_string(funding_data.get('title', 'Funding Opportunity'))
        donor = sanitize_input_string(funding_data.get('donor', 'N/A'))
        summary = sanitize_input_string(funding_data.get('summary', 'Summary not available'))
        amount = sanitize_input_string(funding_data.get('amount', 'Amount TBA'))
        deadline = sanitize_input_string(funding_data.get('deadline', 'Deadline TBA'))
        location = sanitize_input_string(funding_data.get('location', 'Location TBA'))
        how_to_apply = sanitize_input_string(funding_data.get('how_to_apply', 'Application process TBA'))
        opportunity_url = sanitize_input_string(funding_data.get('opportunity_url', '#'))
        
        # Handle eligibility and themes
        eligibility = funding_data.get('eligibility', [])
        themes = funding_data.get('themes', [])
        
        if isinstance(eligibility, list):
            eligibility_text = ". ".join(sanitize_input_string(str(item)) for item in eligibility if item)
        else:
            eligibility_text = sanitize_input_string(str(eligibility)) if eligibility else "Eligibility criteria will be specified in the full application guidelines"
        
        if isinstance(themes, list):
            themes_text = ", ".join(sanitize_input_string(str(theme)) for theme in themes if theme)
        else:
            themes_text = sanitize_input_string(str(themes)) if themes else "General funding"
        
        # Get word count range
        min_words, max_words = self.get_word_count_range(length)
        
        # Define tone instructions
        tone_instructions = {
            "professional": "Use authoritative, formal language suitable for nonprofit professionals and grant writers",
            "persuasive": "Use compelling, action-oriented language that motivates readers to apply",
            "informal": "Use conversational, accessible language that's friendly and approachable"
        }.get(tone, "Use professional, engaging language")
        
        prompt = f"""You are an expert blog writer for nonprofit audiences. Write a detailed, comprehensive blog post using the following funding opportunity data:

FUNDING OPPORTUNITY DATA:
Title: {title}
Donor: {donor}
Summary: {summary}
Amount: {amount}
Deadline: {deadline}
Location: {location}
Themes: {themes_text}
Eligibility: {eligibility_text}
How to Apply: {how_to_apply}
Opportunity URL: {opportunity_url}

CONTENT REQUIREMENTS:
- Target word count: {min_words}-{max_words} words (this is critical - ensure you meet this range)
- Tone: {tone_instructions}
- Target SEO keywords: {seo_keywords if seo_keywords else 'funding, grants, nonprofits'}

BLOG POST STRUCTURE (follow this exactly):
1. **Compelling Headline** - Use keywords naturally
2. **Introduction** (150-200 words)
   - Hook readers with urgent, attention-grabbing opening
   - Highlight the opportunity value and deadline urgency
   - Preview what readers will learn
3. **About the Donor** (200-300 words)
   - Background and mission of the funding organization
   - Previous funding initiatives or success stories
   - Why this opportunity matters
4. **Funding Overview** (300-400 words)
   - Detailed breakdown of funding amount and scope
   - Project types and focus areas supported
   - Examples of fundable activities
5. **Who Can Apply** (200-300 words)
   - Detailed eligibility criteria
   - Organization types and sizes
   - Geographic requirements
6. **Application Process** (200-300 words)
   - Step-by-step application guidance
   - Required documents and deadlines
   - Tips for successful applications
7. **Call to Action** (100-150 words)
   - Urgent appeal to apply
   - Link to opportunity URL
   - Next steps for interested organizations

WRITING GUIDELINES:
- Use clear HTML formatting with <h2>, <h3>, <p>, <ul>, <li>, <a> tags
- Include the SEO keywords naturally in headings and body text
- Add specific examples and elaboration to reach the target word count
- Create urgency around deadlines and opportunity value
- Make content actionable and practical for nonprofit readers
- Use bullet points and lists for better readability
- Include the opportunity URL as a clickable link in the call to action

ADDITIONAL INSTRUCTIONS:
{extra_instructions if extra_instructions else 'Focus on creating comprehensive, valuable content that nonprofit professionals will find immediately actionable.'}

CRITICAL: Ensure your response is between {min_words} and {max_words} words. Use examples, elaboration, and detailed explanations to reach this target. Do not write a short summary - write a full, comprehensive blog post.

Return only clean HTML with properly closed tags. Do not include markdown, backticks, or any other formatting."""

        return prompt
    
    def generate_blog_post(
        self, 
        funding_data: Dict[str, Any],
        seo_keywords: Optional[str] = None,
        tone: str = "professional",
        length: str = "medium", 
        extra_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate blog post using OpenAI with enhanced word count and SEO validation"""
        try:
            # Get target word count
            min_words, max_words = self.get_word_count_range(length)
            max_tokens = self.estimate_max_tokens(max_words)
            
            logger.info(f"🤖 Generating {length} blog post ({min_words}-{max_words} words, max {max_tokens} tokens) for: {funding_data.get('title', 'Unknown')}")
            
            # Create the enhanced prompt
            prompt = self.create_enhanced_blog_prompt(
                funding_data, seo_keywords, tone, length, extra_instructions
            )
            
            # Call OpenAI API with calculated token limit
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are an expert content writer specializing in nonprofit funding blog posts. Always write comprehensive posts that meet the specified word count of {min_words}-{max_words} words. Return only clean HTML without any additional formatting."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            # Extract and sanitize response
            try:
                if hasattr(response, 'choices') and response.choices:
                    raw_content = response.choices[0].message.content.strip()
                else:
                    raise ValueError("Invalid OpenAI response structure")
            except (AttributeError, IndexError, ValueError) as e:
                logger.error(f"🔴 Failed to extract content from OpenAI response: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response from AI service. Please try again."
                )
            
            # Sanitize the response
            post_content = sanitize_openai_response(raw_content)
            
            # Count words in the generated content
            word_count = count_words_in_html(post_content)
            logger.info(f"📊 Generated content word count: {word_count} (target: {min_words}-{max_words})")
            
            # Check if content is too short and retry once
            if word_count < min_words * 0.8:  # If less than 80% of minimum
                logger.warning(f"⚠️ Content too short ({word_count} words), retrying with reinforced instructions")
                
                retry_prompt = f"""The previous response was too short ({word_count} words). Please rewrite the blog post to be between {min_words} and {max_words} words by:
                - Adding more detailed examples
                - Expanding each section with practical insights
                - Including more background information about the donor
                - Providing step-by-step application guidance
                - Adding specific examples of fundable projects

{prompt}

CRITICAL: The response MUST be at least {min_words} words. Expand with relevant, valuable content."""
                
                retry_response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system", 
                            "content": f"You are an expert content writer. The user needs a comprehensive {min_words}-{max_words} word blog post. Your previous response was too short. Please write a much longer, more detailed version."
                        },
                        {
                            "role": "user",
                            "content": retry_prompt
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                
                try:
                    if hasattr(retry_response, 'choices') and retry_response.choices:
                        retry_content = retry_response.choices[0].message.content.strip()
                        post_content = sanitize_openai_response(retry_content)
                        word_count = count_words_in_html(post_content)
                        logger.info(f"🔄 Retry generated {word_count} words (target: {min_words}-{max_words})")
                    else:
                        logger.warning("⚠️ Retry failed, using original content")
                except Exception as e:
                    logger.warning(f"⚠️ Retry failed: {e}, using original content")
            
            # Check SEO keyword coverage
            seo_check = check_seo_keywords_coverage(post_content, seo_keywords or "")
            logger.info(f"🔍 SEO keyword coverage: {seo_check['coverage_percentage']:.1f}%")
            
            if seo_check['missing_keywords']:
                logger.warning(f"⚠️ Missing SEO keywords: {seo_check['missing_keywords']}")
            
            # Generate title and meta from content
            soup = BeautifulSoup(post_content, 'html.parser')
            
            # Extract title from first h1 or h2
            title_element = soup.find(['h1', 'h2'])
            post_title = title_element.get_text().strip() if title_element else funding_data.get('title', 'Funding Opportunity')
            
            # Generate meta title (shorter version)
            meta_title = post_title[:57] + "..." if len(post_title) > 60 else post_title
            
            # Generate meta description from first paragraph
            first_p = soup.find('p')
            meta_description = ""
            if first_p:
                meta_text = first_p.get_text().strip()
                meta_description = meta_text[:157] + "..." if len(meta_text) > 160 else meta_text
            
            # Generate tags and categories
            tags = self.extract_suggested_tags(funding_data, seo_keywords)
            categories = self.extract_suggested_categories(funding_data)
            
            # Prepare response with validation metadata
            blog_data = {
                'post_title': post_title,
                'post_content': post_content,
                'meta_title': meta_title,
                'meta_description': meta_description,
                'tags': tags,
                'categories': categories,
                'word_count': word_count,
                'target_range': f"{min_words}-{max_words}",
                'seo_coverage': seo_check['coverage_percentage'],
                'missing_keywords': seo_check['missing_keywords'],
                'meets_word_count': word_count >= min_words * 0.8
            }
            
            logger.info(f"✅ Successfully generated blog post: {post_title[:50]}... ({word_count} words)")
            return blog_data
            
        except HTTPException:
            # Re-raise HTTP exceptions (already have proper user-friendly messages)
            raise
        except Exception as e:
            logger.error(f"🔴 Unexpected error in blog generation: {e}")
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

@router.get("/get-blog-post", response_model=GetBlogPostResponse)
async def get_blog_post(
    record_id: int,
    db: Session = Depends(get_db)
) -> GetBlogPostResponse:
    """
    Get existing saved blog post for a funding opportunity
    
    Args:
        record_id: Funding opportunity record ID
        db: Database session dependency
    
    Returns:
        GetBlogPostResponse: Existing blog post data or empty response
    """
    try:
        logger.info(f"🔍 Looking for existing blog post for record ID: {record_id}")
        
        # Check if blog post exists
        existing_blog_post = db.query(BlogPost).filter(
            BlogPost.record_id == record_id
        ).first()
        
        if existing_blog_post:
            logger.info(f"✅ Found existing blog post (ID: {existing_blog_post.id}) for record {record_id}")
            return GetBlogPostResponse(
                success=True,
                message="Existing blog post found",
                blog_post=SavedBlogPostResponse.from_orm(existing_blog_post),
                exists=True
            )
        else:
            logger.info(f"📝 No existing blog post found for record {record_id}")
            return GetBlogPostResponse(
                success=True,
                message="No existing blog post found",
                blog_post=None,
                exists=False
            )
            
    except Exception as e:
        logger.error(f"🔴 Error getting blog post for record {record_id}: {e}")
        return GetBlogPostResponse(
            success=False,
            message=f"Failed to get blog post: {str(e)}",
            blog_post=None,
            exists=False
        )

@router.post("/regenerate-blog-post", response_model=GeneratePostResponse)
async def regenerate_blog_post(
    request: RegenerateBlogPostRequest,
    db: Session = Depends(get_db)
) -> GeneratePostResponse:
    """
    Force regenerate blog post, overwriting existing saved post
    
    Args:
        request: Regeneration request with record_id and parameters
        db: Database session dependency
    
    Returns:
        GeneratePostResponse: Newly generated blog post content
    """
    try:
        logger.info(f"🔄 Force regenerating blog post for record ID: {request.record_id}")
        
        # Convert to standard GeneratePostRequest and call generate_post with force flag
        generate_request = GeneratePostRequest(
            record_id=request.record_id,
            seo_keywords=request.seo_keywords,
            tone=request.tone,
            length=request.length,
            extra_instructions=request.extra_instructions
        )
        
        # Call generate_post with force_regenerate=True
        return await generate_post(generate_request, db, force_regenerate=True)
        
    except Exception as e:
        logger.error(f"🔴 Error regenerating blog post for record {request.record_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate blog post: {str(e)}"
        )

@router.post("/generate-post", response_model=GeneratePostResponse)
async def generate_post(
    request: GeneratePostRequest,
    db: Session = Depends(get_db),
    force_regenerate: bool = False
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
        logger.info(f"🚀 Generating blog post for record ID: {request.record_id} (force_regenerate: {force_regenerate})")
        
        # Check for existing blog post first (unless force regenerating)
        existing_blog_post = None
        if not force_regenerate:
            existing_blog_post = db.query(BlogPost).filter(
                BlogPost.record_id == request.record_id
            ).first()
            
            if existing_blog_post:
                logger.info(f"✅ Found existing blog post (ID: {existing_blog_post.id}) for record {request.record_id}")
                
                # Return existing blog post
                return GeneratePostResponse(
                    success=True,
                    message=f"Using existing saved blog post (last updated: {existing_blog_post.updated_at.strftime('%Y-%m-%d %H:%M')})",
                    post_title=existing_blog_post.title,
                    post_content=existing_blog_post.content,
                    tags=existing_blog_post.tags or [],
                    categories=existing_blog_post.categories or [],
                    meta_title=existing_blog_post.meta_title,
                    meta_description=existing_blog_post.meta_description,
                    opportunity_url=None,  # Will be set below
                    record_id=request.record_id,
                    prompt_version=existing_blog_post.prompt_version,
                    blog_post_id=existing_blog_post.id,
                    is_existing=True,
                    last_updated=existing_blog_post.updated_at,
                    word_count=existing_blog_post.word_count
                )
        
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
        
        # Generate blog post using enhanced OpenAI method
        blog_data = generator.generate_blog_post(
            funding_data=funding_data,
            seo_keywords=request.seo_keywords,
            tone=request.tone or "professional",
            length=request.length or "medium",
            extra_instructions=request.extra_instructions
        )
        
        # Add prompt version to response for tracking
        blog_data['prompt_version'] = generator.CURRENT_PROMPT_VERSION
        
        # Fallback tag and category generation if OpenAI didn't provide them
        if not blog_data.get('tags'):
            blog_data['tags'] = generator.extract_suggested_tags(funding_data, request.seo_keywords)
        
        if not blog_data.get('categories'):
            blog_data['categories'] = generator.extract_suggested_categories(funding_data)
        
        # Create enhanced success message with validation info
        word_count = blog_data.get('word_count', 0)
        target_range = blog_data.get('target_range', 'unknown')
        seo_coverage = blog_data.get('seo_coverage', 0)
        meets_word_count = blog_data.get('meets_word_count', False)
        missing_keywords = blog_data.get('missing_keywords', [])
        
        # Build success message with quality indicators
        quality_indicators = []
        if meets_word_count:
            quality_indicators.append(f"✅ Word count: {word_count} (target: {target_range})")
        else:
            quality_indicators.append(f"⚠️ Word count: {word_count} (target: {target_range}) - shorter than expected")
        
        if seo_coverage >= 80:
            quality_indicators.append(f"✅ SEO coverage: {seo_coverage:.0f}%")
        else:
            quality_indicators.append(f"⚠️ SEO coverage: {seo_coverage:.0f}%")
            if missing_keywords:
                quality_indicators.append(f"Missing keywords: {', '.join(missing_keywords[:3])}")
        
        success_message = f"Successfully generated blog post for '{funding_data.get('title', 'Unknown Opportunity')}'. " + " | ".join(quality_indicators)
        
        # 💾 SAVE TO DATABASE: Create or update blog post in database
        try:
            # Check if this is an update (existing blog post from force regenerate)
            if force_regenerate and existing_blog_post:
                logger.info(f"📝 Updating existing blog post (ID: {existing_blog_post.id}) for record {request.record_id}")
                
                # Update existing blog post
                existing_blog_post.title = blog_data.get('post_title', '')
                existing_blog_post.content = blog_data.get('post_content', '')
                existing_blog_post.meta_title = blog_data.get('meta_title')
                existing_blog_post.meta_description = blog_data.get('meta_description')
                existing_blog_post.seo_keywords = request.seo_keywords
                existing_blog_post.tags = blog_data.get('tags', [])
                existing_blog_post.categories = blog_data.get('categories', [])
                existing_blog_post.tone = request.tone
                existing_blog_post.length = request.length
                existing_blog_post.extra_instructions = request.extra_instructions
                existing_blog_post.prompt_version = generator.CURRENT_PROMPT_VERSION
                existing_blog_post.word_count = blog_data.get('word_count')
                
                db.commit()
                db.refresh(existing_blog_post)
                
                blog_post_id = existing_blog_post.id
                last_updated = existing_blog_post.updated_at
                success_message += f" | Updated existing blog post (ID: {blog_post_id})"
                
            else:
                logger.info(f"💾 Saving new blog post to database for record {request.record_id}")
                
                # Create new blog post
                new_blog_post = BlogPost(
                    record_id=request.record_id,
                    title=blog_data.get('post_title', ''),
                    content=blog_data.get('post_content', ''),
                    meta_title=blog_data.get('meta_title'),
                    meta_description=blog_data.get('meta_description'),
                    seo_keywords=request.seo_keywords,
                    tags=blog_data.get('tags', []),
                    categories=blog_data.get('categories', []),
                    tone=request.tone or "professional",
                    length=request.length or "medium",
                    extra_instructions=request.extra_instructions,
                    prompt_version=generator.CURRENT_PROMPT_VERSION,
                    word_count=blog_data.get('word_count')
                )
                
                db.add(new_blog_post)
                db.commit()
                db.refresh(new_blog_post)
                
                blog_post_id = new_blog_post.id
                last_updated = new_blog_post.created_at
                success_message += f" | Saved to database (ID: {blog_post_id})"
                
        except Exception as db_error:
            logger.error(f"🔴 Failed to save blog post to database: {db_error}")
            # Don't fail the entire request if database save fails
            blog_post_id = None
            last_updated = None
            success_message += " | ⚠️ Generated successfully but failed to save to database"
        
        return GeneratePostResponse(
            success=True,
            message=success_message,
            post_title=blog_data.get('post_title'),
            post_content=blog_data.get('post_content'),
            tags=blog_data.get('tags', []),
            categories=blog_data.get('categories', []),
            meta_title=blog_data.get('meta_title'),
            meta_description=blog_data.get('meta_description'),
            opportunity_url=opportunity_url,
            record_id=request.record_id,
            prompt_version=generator.CURRENT_PROMPT_VERSION,
            blog_post_id=blog_post_id,
            is_existing=False,
            last_updated=last_updated,
            word_count=blog_data.get('word_count')
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