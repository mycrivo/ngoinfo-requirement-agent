from fastapi import APIRouter, HTTPException, status
import requests
import os
import logging
from typing import Dict, Any, List, Optional
import base64
from requests.auth import HTTPBasicAuth

from schemas import PublishToWordPressRequest, PublishToWordPressResponse

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["wordpress-publish"])

class WordPressPublisher:
    """WordPress REST API client for publishing posts"""
    
    def __init__(self):
        self.base_url = os.getenv('WP_API_URL')
        self.username = os.getenv('WP_USERNAME') 
        self.app_password = os.getenv('WP_APPLICATION_PASSWORD')
        
        if not all([self.base_url, self.username, self.app_password]):
            raise ValueError("WordPress credentials not properly configured. Please set WP_API_URL, WP_USERNAME, and WP_APPLICATION_PASSWORD environment variables.")
        
        # Remove trailing slash from base URL
        self.base_url = self.base_url.rstrip('/') if self.base_url else ''
        
        # Setup authentication (cast to satisfy type checker - we know they're not None)
        self.auth = HTTPBasicAuth(str(self.username), str(self.app_password))
        
        # Default headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to WordPress REST API"""
        url = f"{self.base_url}/wp-json/wp/v2/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                auth=self.auth,
                headers=self.headers,
                **kwargs
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"WordPress API request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to communicate with WordPress: {str(e)}"
            )
    
    def get_or_create_category(self, category_name: str) -> int:
        """Get category ID by name, create if it doesn't exist"""
        try:
            # Search for existing category
            response = self._make_request('GET', 'categories', params={'search': category_name})
            categories = response.json()
            
            # Check for exact match
            for category in categories:
                if category['name'].lower() == category_name.lower():
                    logger.info(f"Found existing category: {category_name} (ID: {category['id']})")
                    return category['id']
            
            # Create new category if not found
            logger.info(f"Creating new category: {category_name}")
            response = self._make_request('POST', 'categories', json={'name': category_name})
            new_category = response.json()
            return new_category['id']
            
        except Exception as e:
            logger.error(f"Failed to get/create category '{category_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to handle category '{category_name}'"
            )
    
    def get_or_create_tag(self, tag_name: str) -> int:
        """Get tag ID by name, create if it doesn't exist"""
        try:
            # Search for existing tag
            response = self._make_request('GET', 'tags', params={'search': tag_name})
            tags = response.json()
            
            # Check for exact match
            for tag in tags:
                if tag['name'].lower() == tag_name.lower():
                    logger.info(f"Found existing tag: {tag_name} (ID: {tag['id']})")
                    return tag['id']
            
            # Create new tag if not found
            logger.info(f"Creating new tag: {tag_name}")
            response = self._make_request('POST', 'tags', json={'name': tag_name})
            new_tag = response.json()
            return new_tag['id']
            
        except Exception as e:
            logger.error(f"Failed to get/create tag '{tag_name}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to handle tag '{tag_name}'"
            )
    
    def create_post(self, post_data: PublishToWordPressRequest) -> Dict[str, Any]:
        """Create a WordPress post as draft with SEO metadata"""
        try:
            # Get category IDs
            category_ids = []
            for category_name in post_data.categories:
                if category_name.strip():
                    category_ids.append(self.get_or_create_category(category_name.strip()))
            
            # Get tag IDs  
            tag_ids = []
            for tag_name in post_data.tags:
                if tag_name.strip():
                    tag_ids.append(self.get_or_create_tag(tag_name.strip()))
            
            # Prepare post payload
            wp_post_data = {
                'title': post_data.title,
                'content': post_data.content,
                'status': 'draft',
                'categories': category_ids,
                'tags': tag_ids,
                'meta': {
                    # Custom field for opportunity URL
                    'opportunity_url': post_data.opportunity_url,
                    
                    # Rank Math SEO fields
                    'rank_math_title': post_data.meta_title,
                    'rank_math_description': post_data.meta_description,
                    'rank_math_focus_keyword': '',  # Can be enhanced later
                    'rank_math_robots': ['index', 'follow'],
                    
                    # Additional SEO meta fields that Rank Math might use
                    '_yoast_wpseo_title': post_data.meta_title,  # Fallback for Yoast compatibility
                    '_yoast_wpseo_metadesc': post_data.meta_description,
                }
            }
            
            # Create the post
            logger.info(f"Creating WordPress post: {post_data.title}")
            response = self._make_request('POST', 'posts', json=wp_post_data)
            post_response = response.json()
            
            logger.info(f"Successfully created WordPress post ID: {post_response.get('id')}")
            return post_response
            
        except Exception as e:
            logger.error(f"Failed to create WordPress post: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create WordPress post: {str(e)}"
            )

@router.post("/wordpress/publish", response_model=PublishToWordPressResponse)
async def publish_to_wordpress(post_data: PublishToWordPressRequest) -> PublishToWordPressResponse:
    """
    Publish a blog post to WordPress as a draft via REST API
    
    Args:
        post_data: Blog post data including title, content, tags, categories, and SEO metadata
    
    Returns:
        PublishToWordPressResponse: WordPress API response with post details
    """
    try:
        logger.info(f"🚀 Publishing blog post to WordPress: {post_data.title}")
        
        # Initialize WordPress publisher
        wp_publisher = WordPressPublisher()
        
        # Create the post
        wordpress_response = wp_publisher.create_post(post_data)
        
        # Extract post details
        post_id = wordpress_response.get('id')
        post_url = wordpress_response.get('link')
        
        return PublishToWordPressResponse(
            success=True,
            message=f"Successfully created WordPress post as draft (ID: {post_id})",
            wordpress_response=wordpress_response,
            post_id=post_id,
            post_url=post_url
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as they already have proper error details
        raise
    except Exception as e:
        logger.error(f"Unexpected error in publish_to_wordpress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/wordpress/test-connection")
async def test_wordpress_connection():
    """Test WordPress API connection and authentication"""
    try:
        wp_publisher = WordPressPublisher()
        
        # Test connection by fetching site info
        response = wp_publisher._make_request('GET', '../', timeout=10)
        site_info = response.json()
        
        return {
            "success": True,
            "message": "WordPress connection successful",
            "site_name": site_info.get('name', 'Unknown'),
            "site_url": site_info.get('url', 'Unknown'),
            "api_url": wp_publisher.base_url
        }
        
    except Exception as e:
        logger.error(f"WordPress connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"WordPress connection failed: {str(e)}"
        ) 