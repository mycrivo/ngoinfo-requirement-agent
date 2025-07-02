from fastapi import APIRouter, HTTPException, status
import requests
import os
import logging
from typing import Dict, Any, List, Optional
import base64
from requests.auth import HTTPBasicAuth
import json
import traceback
from datetime import datetime

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
            logger.error("🔴 WordPress credentials not configured properly:")
            logger.error(f"   WP_API_URL: {'✅ Set' if self.base_url else '❌ Missing'}")
            logger.error(f"   WP_USERNAME: {'✅ Set' if self.username else '❌ Missing'}")
            logger.error(f"   WP_APPLICATION_PASSWORD: {'✅ Set' if self.app_password else '❌ Missing'}")
            raise ValueError("WordPress credentials not properly configured. Please set WP_API_URL, WP_USERNAME, and WP_APPLICATION_PASSWORD environment variables.")
        
        # Remove trailing slash from base URL
        self.base_url = self.base_url.rstrip('/') if self.base_url else ''
        
        # Setup authentication (cast to satisfy type checker - we know they're not None)
        self.auth = HTTPBasicAuth(str(self.username), str(self.app_password))
        
        # Default headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'ReqAgent/1.0 WordPress Publisher'
        }
        
        logger.info(f"📡 WordPress Publisher initialized - API URL: {self.base_url}")
    
    def validate_content(self, content: str) -> Dict[str, Any]:
        """Validate content before sending to WordPress"""
        validation_result = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Check content length
        content_length = len(content)
        if content_length > 1000000:  # 1MB limit
            validation_result['errors'].append(f"Content too large: {content_length} characters (max: 1,000,000)")
            validation_result['valid'] = False
        elif content_length > 500000:  # 500KB warning
            validation_result['warnings'].append(f"Large content: {content_length} characters")
        
        # Check for problematic characters
        problematic_chars = ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08', '\x0b', '\x0c', '\x0e', '\x0f']
        for char in problematic_chars:
            if char in content:
                validation_result['errors'].append(f"Contains invalid control character: {repr(char)}")
                validation_result['valid'] = False
        
        # Log validation results
        if validation_result['warnings']:
            logger.warning(f"⚠️ Content validation warnings: {'; '.join(validation_result['warnings'])}")
        if validation_result['errors']:
            logger.error(f"🔴 Content validation errors: {'; '.join(validation_result['errors'])}")
        
        return validation_result
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to WordPress REST API with comprehensive logging"""
        url = f"{self.base_url}/wp-json/wp/v2/{endpoint}"
        request_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
        
        # 🔍 ENHANCED DEBUGGING: Log full WordPress request details
        logger.info(f"🔍 WP PUBLISH: URL = {url}")
        logger.info(f"🔍 WP PUBLISH: METHOD = {method}")
        logger.info(f"🔍 WP PUBLISH: HEADERS = {json.dumps(dict(self.headers), indent=2)}")
        logger.info(f"🔍 WP PUBLISH: BASE_URL = {self.base_url}")
        logger.info(f"🔍 WP PUBLISH: ENDPOINT = {endpoint}")
        logger.info(f"🔍 WP PUBLISH: FULL_URL_CONSTRUCTION = {self.base_url} + /wp-json/wp/v2/ + {endpoint}")
        
        # Log authentication details (without exposing credentials)
        logger.info(f"🔍 WP PUBLISH: AUTH_USERNAME = {self.username}")
        logger.info(f"🔍 WP PUBLISH: AUTH_TYPE = HTTPBasicAuth")
        logger.info(f"🔍 WP PUBLISH: HAS_PASSWORD = {'Yes' if self.app_password else 'No'}")
        
        # Log request payload if present
        if 'json' in kwargs:
            payload = kwargs['json']
            logger.info(f"🔍 WP PUBLISH: PAYLOAD = {json.dumps(payload, indent=2, default=str)}")
            logger.info(f"🔍 WP PUBLISH: PAYLOAD_SIZE = {len(json.dumps(payload)) if payload else 0} characters")
        
        if 'params' in kwargs:
            logger.info(f"🔍 WP PUBLISH: QUERY_PARAMS = {json.dumps(kwargs['params'], indent=2)}")
        
        # Log additional request details
        logger.info(f"🔍 WP PUBLISH: TIMEOUT = 30 seconds")
        logger.info(f"🔍 WP PUBLISH: REQUEST_ID = {request_id}")
        
        try:
            logger.info(f"🚀 [{request_id}] Making WordPress API request...")
            
            response = requests.request(
                method=method,
                url=url,
                auth=self.auth,
                headers=self.headers,
                timeout=30,  # Add 30 second timeout
                **kwargs
            )
            
            # Log response details
            logger.info(f"📥 [{request_id}] WordPress API Response:")
            logger.info(f"   Status: {response.status_code} {response.reason}")
            logger.info(f"   Response headers: {dict(response.headers)}")
            
            # Log response body
            try:
                response_json = response.json()
                logger.info(f"   Response body: {json.dumps(response_json, indent=2, default=str)}")
            except (ValueError, json.JSONDecodeError):
                response_text = response.text[:1000]
                logger.info(f"   Response body (text): {response_text}")
            
            # Check for HTTP errors
            if not response.ok:
                self._handle_http_error(response, request_id)
            
            return response
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔴 [{request_id}] Connection failed to WordPress API: {e}")
            logger.error(f"   URL: {url}")
            logger.error(f"   Check if WordPress site is accessible and API URL is correct")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot connect to WordPress API. Please check if the site is accessible and the API URL is correct. (Error: {str(e)})"
            )
        except requests.exceptions.Timeout as e:
            logger.error(f"🔴 [{request_id}] WordPress API request timed out: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="WordPress API request timed out. The site may be slow or experiencing issues."
            )
        except requests.exceptions.RequestException as e:
            # 🔍 ENHANCED ERROR LOGGING: Capture complete failure details
            logger.error(f"❌ WordPress API request failed: {e}")
            logger.error(f"❌ [{request_id}] WordPress API error details:")
            
            # Log the response details if available
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"❌ WP RESPONSE STATUS: {e.response.status_code}")
                logger.error(f"❌ WP RESPONSE HEADERS: {json.dumps(dict(e.response.headers), indent=2)}")
                logger.error(f"❌ WP RESPONSE TEXT: {e.response.text}")
                logger.error(f"❌ WP RESPONSE URL: {e.response.url}")
                logger.error(f"❌ WP RESPONSE REASON: {e.response.reason}")
                
                # Try to parse JSON error from WordPress
                try:
                    error_json = e.response.json()
                    logger.error(f"❌ WP RESPONSE JSON: {json.dumps(error_json, indent=2)}")
                except (ValueError, json.JSONDecodeError):
                    logger.error("❌ Could not parse WordPress error response as JSON")
            else:
                logger.error(f"❌ No response object available in exception")
                logger.error(f"❌ Exception type: {type(e)}")
                logger.error(f"❌ Exception args: {e.args}")
            
            # Log the original request details for comparison
            logger.error(f"❌ FAILED REQUEST URL: {url}")
            logger.error(f"❌ FAILED REQUEST METHOD: {method}")
            logger.error(f"❌ Full exception traceback: {traceback.format_exc()}")
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to communicate with WordPress: {str(e)}"
            )
    
    def _handle_http_error(self, response: requests.Response, request_id: str):
        """Handle specific HTTP error codes from WordPress API"""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_code = error_data.get('code', 'unknown_error')
            error_message = error_data.get('message', 'Unknown error')
            error_details = error_data.get('data', {})
        except (ValueError, json.JSONDecodeError):
            error_code = 'parse_error'
            error_message = 'Could not parse error response'
            error_details = {'raw_response': response.text[:500]}
        
        logger.error(f"🔴 [{request_id}] WordPress API Error {status_code}:")
        logger.error(f"   Error code: {error_code}")
        logger.error(f"   Error message: {error_message}")
        logger.error(f"   Error details: {json.dumps(error_details, indent=2, default=str)}")
        
        # Handle specific error cases
        if status_code == 401:
            logger.error("🔐 Authentication failed - check WordPress credentials")
            logger.error("   - Verify WP_USERNAME and WP_APPLICATION_PASSWORD are correct")
            logger.error("   - Check if Application Password is enabled in WordPress")
            logger.error("   - Ensure user has proper permissions")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"WordPress authentication failed. Please check credentials. (WordPress error: {error_message})"
            )
        elif status_code == 403:
            logger.error("🚫 Permission denied - user lacks required permissions")
            logger.error("   - Check if user can create/edit posts")
            logger.error("   - Verify user role and capabilities")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. User lacks required WordPress permissions. (WordPress error: {error_message})"
            )
        elif status_code == 404:
            logger.error("🔍 WordPress API endpoint not found")
            logger.error("   - Check if WordPress REST API is enabled")
            logger.error("   - Verify API URL is correct")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WordPress API endpoint not found. Check if REST API is enabled. (WordPress error: {error_message})"
            )
        elif status_code == 500:
            logger.error("💥 WordPress server error")
            logger.error("   - Check WordPress site health")
            logger.error("   - Review WordPress error logs")
            logger.error("   - Check for plugin conflicts")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WordPress server error. Check site health and error logs. (WordPress error: {error_message})"
            )
        else:
            logger.error(f"❓ Unexpected WordPress API error: {status_code}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WordPress API error {status_code}: {error_message}"
            )
    
    def get_default_category_id(self) -> Optional[int]:
        """Get the default 'NGO Grants and Funds' category ID, return None if not found"""
        default_category_slug = "ngo-grants-and-funds"
        default_category_name = "NGO Grants and Funds"
        
        try:
            logger.info(f"🏷️ Looking for default category: {default_category_name} (slug: {default_category_slug})")
            
            # Search for category by slug (more reliable than name)
            response = self._make_request('GET', 'categories', params={'slug': default_category_slug})
            categories = response.json()
            
            if categories and len(categories) > 0:
                category_id = categories[0]['id']
                logger.info(f"✅ Found default category: {default_category_name} (ID: {category_id})")
                return category_id
            
            # Category not found by slug, try by name as fallback
            logger.info(f"🔍 Category not found by slug, trying name search...")
            response = self._make_request('GET', 'categories', params={'search': default_category_name})
            categories = response.json()
            
            # Check for exact name match
            for category in categories:
                if category['name'].lower() == default_category_name.lower():
                    category_id = category['id']
                    logger.info(f"✅ Found default category by name: {default_category_name} (ID: {category_id})")
                    return category_id
            
            # Category not found at all
            logger.warning(f"⚠️ Default category '{default_category_name}' not found. Publishing without category.")
            return None
            
        except HTTPException:
            # Don't fail the entire post creation if category lookup fails
            logger.warning(f"⚠️ Failed to lookup default category due to API error. Publishing without category.")
            return None
        except Exception as e:
            logger.warning(f"⚠️ Failed to lookup default category '{default_category_name}': {e}")
            logger.warning("   Publishing without category to avoid blocking post creation.")
            return None
    

    
    def create_post(self, post_data: PublishToWordPressRequest) -> Dict[str, Any]:
        """Create a WordPress post as draft with SEO metadata"""
        post_creation_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
        
        try:
            logger.info(f"📝 [{post_creation_id}] Creating WordPress post: {post_data.title}")
            
            # Validate post content
            validation_result = self.validate_content(post_data.content)
            if not validation_result['valid']:
                logger.error(f"🔴 [{post_creation_id}] Content validation failed:")
                for error in validation_result['errors']:
                    logger.error(f"   - {error}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content validation failed: {'; '.join(validation_result['errors'])}"
                )
            
            # Validate required fields
            if not post_data.title or not post_data.title.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Post title is required and cannot be empty"
                )
            
            if not post_data.content or not post_data.content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Post content is required and cannot be empty"
                )
            
            # Get default category ID (NGO Grants and Funds)
            logger.info(f"🏷️ [{post_creation_id}] Setting up default category")
            default_category_id = self.get_default_category_id()
            category_ids = [default_category_id] if default_category_id else []
            
            # Note: Tags are not processed - posts use default category only
            tag_ids = []
            
            # Prepare post payload (always draft status, default category only)
            wp_post_data = {
                'title': post_data.title.strip(),
                'content': post_data.content,
                'status': 'draft',  # Always draft, never publish
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
            
            # Only include categories if we have a valid default category
            if category_ids:
                wp_post_data['categories'] = category_ids
                logger.info(f"📂 [{post_creation_id}] Using default category (ID: {category_ids[0]})")
            else:
                logger.info(f"📂 [{post_creation_id}] Publishing without category (default category not available)")
            
            logger.info(f"📊 [{post_creation_id}] Post data summary:")
            logger.info(f"   Title: {post_data.title}")
            logger.info(f"   Content length: {len(post_data.content)} characters")
            logger.info(f"   Status: draft (always)")
            logger.info(f"   Default category: {'Applied' if category_ids else 'Not available'}")
            logger.info(f"   Meta title: {post_data.meta_title}")
            logger.info(f"   Meta description length: {len(post_data.meta_description) if post_data.meta_description else 0}")
            
            # Create the post
            logger.info(f"🚀 [{post_creation_id}] Sending post creation request to WordPress...")
            response = self._make_request('POST', 'posts', json=wp_post_data)
            post_response = response.json()
            
            post_id = post_response.get('id')
            post_url = post_response.get('link')
            
            logger.info(f"✅ [{post_creation_id}] Successfully created WordPress post:")
            logger.info(f"   Post ID: {post_id}")
            logger.info(f"   Post URL: {post_url}")
            logger.info(f"   Status: {post_response.get('status')}")
            
            return post_response
            
        except HTTPException:
            # Re-raise HTTP exceptions as they already have proper error details
            raise
        except Exception as e:
            logger.error(f"🔴 [{post_creation_id}] Failed to create WordPress post: {e}")
            logger.error(f"   Full exception: {traceback.format_exc()}")
            logger.error(f"   Post data summary:")
            logger.error(f"     Title: {getattr(post_data, 'title', 'N/A')}")
            logger.error(f"     Content length: {len(getattr(post_data, 'content', ''))}")
            logger.error(f"     Status: draft (always)")
            logger.error(f"     Default category attempted: {default_category_id is not None}")
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