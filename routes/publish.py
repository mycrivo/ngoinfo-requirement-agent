from fastapi import APIRouter, HTTPException, status
import requests
import os
import logging
import hashlib
import json
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
import time

from schemas import PublishToWordPressRequest, PublishToWordPressResponse
from services.content_sanitizer import content_sanitizer

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["wordpress-publish"])

class PublishError(Exception):
    """Custom exception for publishing failures"""
    pass

class WordPressPublisher:
    """Enhanced WordPress REST API client with idempotency and retry logic"""
    
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
        
        # Clean up base URL
        self.base_url = self.base_url.rstrip('/') if self.base_url else ''
        logger.info(f"✅ WordPress publisher initialized for: {self.base_url}")
        
        # Authentication
        self.auth = requests.auth.HTTPBasicAuth(self.username, self.app_password)
        
        # Headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ReqAgent/2.0.0"
        }
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
    
    def _generate_idempotency_key(self, title: str, donor: str, deadline: str) -> str:
        """Generate idempotency key from content"""
        try:
            # Create a hash from key identifying fields
            key_data = f"{title}:{donor}:{deadline}".lower().strip()
            return hashlib.sha256(key_data.encode('utf-8')).hexdigest()[:16]
        except Exception as e:
            logger.error(f"❌ Error generating idempotency key: {e}")
            # Fallback to timestamp-based key
            return f"reqagent_{int(time.time())}"
    
    def _check_existing_post(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if a post with the same idempotency key already exists"""
        try:
            # Search for posts with the idempotency key in meta
            search_url = f"{self.base_url}/wp-json/wp/v2/posts"
            params = {
                'search': idempotency_key,
                'per_page': 10
            }
            
            response = requests.get(
                search_url,
                auth=self.auth,
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                posts = response.json()
                
                # Check if any post has our idempotency key
                for post in posts:
                    # Check meta fields for idempotency key
                    meta_url = f"{self.base_url}/wp-json/wp/v2/posts/{post['id']}"
                    meta_response = requests.get(
                        meta_url,
                        auth=self.auth,
                        headers=self.headers,
                        timeout=30
                    )
                    
                    if meta_response.status_code == 200:
                        post_data = meta_response.json()
                        meta = post_data.get('meta', {})
                        
                        if meta.get('reqagent_idempotency_key') == idempotency_key:
                            logger.info(f"🔄 Found existing post with idempotency key: {post['id']}")
                            return post_data
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error checking for existing post: {e}")
            return None
    
    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make WordPress API request with retry logic and exponential backoff"""
        request_id = f"wp_{int(time.time() * 1000)}"
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"🚀 [{request_id}] WordPress API request attempt {attempt + 1}/{self.max_retries + 1}")
                
                url = f"{self.base_url}/wp-json/wp/v2/{endpoint}"
                
                # Make the request
                response = requests.request(
                    method=method,
                    url=url,
                    auth=self.auth,
                    headers=self.headers,
                    timeout=30,
                    **kwargs
                )
                
                # Log response details (excluding sensitive content)
                logger.info(f"📥 [{request_id}] WordPress API Response:")
                logger.info(f"   Status: {response.status_code} {response.reason}")
                logger.info(f"   URL: {url}")
                logger.info(f"   Method: {method}")
                
                # Log response headers (excluding sensitive ones)
                safe_headers = {k: v for k, v in response.headers.items() 
                              if k.lower() not in ['authorization', 'cookie', 'set-cookie']}
                logger.info(f"   Response headers: {safe_headers}")
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    self._handle_http_error(response, request_id)
                
                # Success - return response
                logger.info(f"✅ [{request_id}] WordPress API request successful")
                return response
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ [{request_id}] WordPress API request failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"🔄 [{request_id}] Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    logger.error(f"❌ [{request_id}] All retry attempts failed")
                    raise PublishError(f"WordPress API request failed after {self.max_retries + 1} attempts: {str(e)}")
            
            except Exception as e:
                logger.error(f"❌ [{request_id}] Unexpected error: {e}")
                raise PublishError(f"Unexpected error during WordPress API request: {str(e)}")
    
    def _handle_http_error(self, response: requests.Response, request_id: str):
        """Handle HTTP errors from WordPress API"""
        try:
            error_detail = "Unknown error"
            
            # Try to extract error details from response
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_detail = error_data.get('message', error_data.get('error', 'Unknown error'))
            except:
                error_detail = response.text[:500] if response.text else 'No error details'
            
            # Log error details (excluding sensitive information)
            logger.error(f"❌ [{request_id}] WordPress API HTTP error:")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   URL: {response.url}")
            logger.error(f"   Error: {error_detail}")
            
            # Raise appropriate HTTP exception
            if response.status_code == 401:
                raise PublishError("WordPress authentication failed. Please check your credentials.")
            elif response.status_code == 403:
                raise PublishError("WordPress access denied. Please check your permissions.")
            elif response.status_code == 404:
                raise PublishError("WordPress endpoint not found. Please check your API URL.")
            elif response.status_code == 429:
                raise PublishError("WordPress rate limit exceeded. Please try again later.")
            elif response.status_code >= 500:
                raise PublishError(f"WordPress server error ({response.status_code}). Please try again later.")
            else:
                raise PublishError(f"WordPress API error ({response.status_code}): {error_detail}")
                
        except PublishError:
            raise
        except Exception as e:
            logger.error(f"❌ [{request_id}] Error handling HTTP error: {e}")
            raise PublishError(f"WordPress API error ({response.status_code}): {response.text[:200]}")
    
    def _create_seo_meta(self, post_data: PublishToWordPressRequest) -> Dict[str, Any]:
        """Create SEO meta fields for Rank Math or similar plugins"""
        try:
            # Generate focus keyword from title and themes
            focus_keywords = []
            if post_data.title:
                # Extract key terms from title
                title_words = post_data.title.lower().split()
                focus_keywords.extend([word for word in title_words if len(word) > 3])
            
            if post_data.themes:
                focus_keywords.extend(post_data.themes[:3])
            
            # Create meta description
            meta_description = ""
            if post_data.summary:
                meta_description = post_data.summary[:160] + "..." if len(post_data.summary) > 160 else post_data.summary
            elif post_data.title:
                meta_description = f"Funding opportunity: {post_data.title}"
            
            # Create meta title
            meta_title = post_data.title
            if post_data.donor and post_data.donor != "Unknown":
                meta_title = f"{post_data.title} - {post_data.donor}"
            
            seo_meta = {
                "rank_math_title": meta_title,
                "rank_math_description": meta_description,
                "rank_math_focus_keyword": ", ".join(focus_keywords[:3]),
                "rank_math_robots": "index,follow",
                "rank_math_advanced_robots": "noindex,nofollow"
            }
            
            logger.info(f"✅ SEO meta fields created: {len(seo_meta)} fields")
            return seo_meta
            
        except Exception as e:
            logger.error(f"❌ Error creating SEO meta: {e}")
            return {}
    
    def create_post(self, post_data: PublishToWordPressRequest) -> Dict[str, Any]:
        """Create a WordPress post with idempotency and enhanced features"""
        post_creation_id = f"post_{int(time.time() * 1000)}"
        
        try:
            logger.info(f"🚀 [{post_creation_id}] Creating WordPress post: {post_data.title}")
            
            # Generate idempotency key
            idempotency_key = self._generate_idempotency_key(
                post_data.title, 
                post_data.donor, 
                post_data.deadline
            )
            
            # Check for existing post
            existing_post = self._check_existing_post(idempotency_key)
            if existing_post:
                logger.info(f"🔄 [{post_creation_id}] Post already exists, returning existing data")
                return existing_post
            
            # Sanitize content for WordPress
            sanitized_title = content_sanitizer.sanitize_string(post_data.title, max_length=100)
            sanitized_content = content_sanitizer.sanitize_html(post_data.content, allow_html=True)
            
            # Create WordPress post data
            wp_post_data = {
                "title": sanitized_title,
                "content": sanitized_content,
                "status": "draft",  # Always create as draft for safety
                "excerpt": post_data.summary[:200] + "..." if len(post_data.summary) > 200 else post_data.summary,
                "categories": [1],  # Default category
                "tags": post_data.tags[:10] if post_data.tags else [],
                "meta": {
                    "reqagent_idempotency_key": idempotency_key,
                    "reqagent_source": "ReqAgent",
                    "reqagent_published_at": datetime.utcnow().isoformat(),
                    "funding_amount": post_data.amount,
                    "funding_deadline": post_data.deadline,
                    "funding_location": ", ".join(post_data.location) if post_data.location else "Unknown"
                }
            }
            
            # Add SEO meta fields
            seo_meta = self._create_seo_meta(post_data)
            wp_post_data["meta"].update(seo_meta)
            
            # Log post creation details
            logger.info(f"📝 [{post_creation_id}] Post data prepared:")
            logger.info(f"   Title: {sanitized_title[:50]}...")
            logger.info(f"   Content length: {len(sanitized_content)} characters")
            logger.info(f"   Status: draft")
            logger.info(f"   Idempotency key: {idempotency_key}")
            logger.info(f"   SEO meta: {len(seo_meta)} fields")
            
            # Create the post with retry logic
            response = self._make_request_with_retry('POST', 'posts', json=wp_post_data)
            post_response = response.json()
            
            post_id = post_response.get('id')
            post_url = post_response.get('link')
            
            logger.info(f"✅ [{post_creation_id}] Successfully created WordPress post:")
            logger.info(f"   Post ID: {post_id}")
            logger.info(f"   Post URL: {post_url}")
            logger.info(f"   Status: {post_response.get('status')}")
            logger.info(f"   Idempotency key: {idempotency_key}")
            
            return post_response
            
        except PublishError:
            raise
        except Exception as e:
            logger.error(f"🔴 [{post_creation_id}] Failed to create WordPress post: {e}")
            logger.error(f"   Full exception: {traceback.format_exc()}")
            raise PublishError(f"Failed to create WordPress post: {str(e)}")

@router.post("/wordpress/publish", response_model=PublishToWordPressResponse)
async def publish_to_wordpress(post_data: PublishToWordPressRequest) -> PublishToWordPressResponse:
    """
    Publish a blog post to WordPress as a draft via REST API with idempotency
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
        
    except PublishError as e:
        logger.error(f"❌ WordPress publishing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error in publish_to_wordpress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/wordpress/test-connection")
async def test_wordpress_connection():
    """Test WordPress API connection and authentication"""
    try:
        logger.info("🔍 Testing WordPress API connection...")
        
        wp_publisher = WordPressPublisher()
        
        # Test basic connectivity
        response = wp_publisher._make_request_with_retry('GET', 'posts?per_page=1')
        
        if response.status_code == 200:
            logger.info("✅ WordPress API connection successful")
            return {
                "success": True,
                "message": "WordPress API connection successful",
                "status_code": response.status_code,
                "base_url": wp_publisher.base_url
            }
        else:
            logger.error(f"❌ WordPress API connection failed: {response.status_code}")
            return {
                "success": False,
                "message": f"WordPress API connection failed: {response.status_code}",
                "status_code": response.status_code,
                "base_url": wp_publisher.base_url
            }
            
    except Exception as e:
        logger.error(f"❌ WordPress API connection test failed: {e}")
        return {
            "success": False,
            "message": f"WordPress API connection test failed: {str(e)}",
            "error": str(e)
        }

@router.get("/wordpress/status")
async def get_wordpress_status():
    """Get WordPress site status and configuration"""
    try:
        logger.info("🔍 Getting WordPress site status...")
        
        wp_publisher = WordPressPublisher()
        
        # Get site info
        response = wp_publisher._make_request_with_retry('GET', '')
        site_info = response.json()
        
        # Get posts count
        posts_response = wp_publisher._make_request_with_retry('GET', 'posts?per_page=1')
        posts_count = int(posts_response.headers.get('X-WP-Total', 0))
        
        status_info = {
            "success": True,
            "site_name": site_info.get('name', 'Unknown'),
            "site_description": site_info.get('description', ''),
            "site_url": site_info.get('url', ''),
            "api_url": wp_publisher.base_url,
            "total_posts": posts_count,
            "api_version": site_info.get('version', 'Unknown'),
            "features": site_info.get('features', []),
            "authentication": "configured" if wp_publisher.username and wp_publisher.app_password else "missing"
        }
        
        logger.info(f"✅ WordPress status retrieved: {status_info['site_name']}")
        return status_info
        
    except Exception as e:
        logger.error(f"❌ Failed to get WordPress status: {e}")
        return {
            "success": False,
            "message": f"Failed to get WordPress status: {str(e)}",
            "error": str(e)
        } 