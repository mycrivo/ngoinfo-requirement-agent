import os
import time
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from utils.auth_enhanced import log_security_event, hash_ip_address

logger = logging.getLogger(__name__)

# Rate limiting configuration
DEFAULT_RATE_LIMITS = {
    "default": "5/second",
    "login": "5/minute",
    "admin": "10/second",
    "api": "20/second",
    "crawler": "2/second",
    "publisher": "5/minute"
}

# Parse rate limit configuration from environment
def parse_rate_limits() -> Dict[str, str]:
    """Parse rate limits from environment variable"""
    rate_limits_str = os.getenv("RATE_LIMITS", "")
    if not rate_limits_str:
        return DEFAULT_RATE_LIMITS
    
    try:
        limits = {}
        for limit_str in rate_limits_str.split(","):
            if "=" in limit_str:
                key, value = limit_str.strip().split("=", 1)
                limits[key.strip()] = value.strip()
            else:
                limits["default"] = limit_str.strip()
        return limits
    except Exception as e:
        logger.warning(f"Failed to parse RATE_LIMITS: {e}, using defaults")
        return DEFAULT_RATE_LIMITS

# Initialize rate limiter with in-memory storage for tests
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

if TEST_MODE:
    # Use in-memory storage for tests to avoid hanging
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
else:
    limiter = Limiter(key_func=get_remote_address)

RATE_LIMITS = parse_rate_limits()

def get_rate_limit_for_route(route_path: str, user_role: Optional[str] = None) -> str:
    """Get appropriate rate limit for a route"""
    # Admin routes get higher limits
    if route_path.startswith("/admin") and user_role == "admin":
        return RATE_LIMITS.get("admin", "10/second")
    
    # Login routes get strict limits
    if "login" in route_path:
        return RATE_LIMITS.get("login", "5/minute")
    
    # API routes get higher limits
    if route_path.startswith("/api"):
        return RATE_LIMITS.get("api", "20/second")
    
    # Crawler routes get strict limits
    if "crawler" in route_path or "parse" in route_path:
        return RATE_LIMITS.get("crawler", "2/second")
    
    # Publisher routes get moderate limits
    if "publish" in route_path or "wordpress" in route_path:
        return RATE_LIMITS.get("publisher", "5/minute")
    
    # Default rate limit
    return RATE_LIMITS.get("default", "5/second")

def rate_limit_dependency(route_path: str):
    """Create rate limit dependency for a specific route"""
    def dependency(request: Request):
        # Get user role for rate limit calculation
        user_role = None
        try:
            from utils.auth_enhanced import get_user_from_request
            user = get_user_from_request(request)
            user_role = user.get("role") if user else None
        except:
            pass
        
        # Get appropriate rate limit
        rate_limit = get_rate_limit_for_route(route_path, user_role)
        
        # Apply rate limiting
        try:
            limiter.limit(rate_limit)(lambda: None)()
        except RateLimitExceeded:
            # Log rate limit violation
            client_ip = get_remote_address(request)
            hashed_ip = hash_ip_address(client_ip)
            
            log_security_event(
                event_type="rate_limit_exceeded",
                user_email=user_role or "anonymous",
                ip_address=client_ip,
                details=f"Route: {route_path}, Limit: {rate_limit}",
                severity="warning"
            )
            
            # Raise rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {rate_limit}"
            )
    
        return True
    
    return dependency

def apply_rate_limits_to_router(router, base_path: str = ""):
    """Apply rate limits to all routes in a router"""
    for route in router.routes:
        if hasattr(route, 'endpoint'):
            # Add rate limiting to the endpoint
            route.endpoint = limiter.limit(
                get_rate_limit_for_route(base_path + route.path)
            )(route.endpoint)

# Rate limit decorators for specific limits
def rate_limit(limit: str):
    """Decorator to apply specific rate limit to a function"""
    return limiter.limit(limit)

def rate_limit_default():
    """Decorator to apply default rate limit"""
    return limiter.limit(RATE_LIMITS.get("default", "5/second"))

def rate_limit_login():
    """Decorator to apply login rate limit"""
    return limiter.limit(RATE_LIMITS.get("login", "5/minute"))

def rate_limit_admin():
    """Decorator to apply admin rate limit"""
    return limiter.limit(RATE_LIMITS.get("admin", "10/second"))

def rate_limit_api():
    """Decorator to apply API rate limit"""
    return limiter.limit(RATE_LIMITS.get("api", "20/second"))

def rate_limit_crawler():
    """Decorator to apply crawler rate limit"""
    return limiter.limit(RATE_LIMITS.get("crawler", "2/second"))

def rate_limit_publisher():
    """Decorator to apply publisher rate limit"""
    return limiter.limit(RATE_LIMITS.get("publisher", "5/minute"))

# Rate limit exceeded handler
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded events"""
    client_ip = get_remote_address(request)
    hashed_ip = hash_ip_address(client_ip)
    
    # Log the rate limit violation
    log_security_event(
        event_type="rate_limit_exceeded",
        user_email="anonymous",
        ip_address=client_ip,
        details=f"Route: {request.url.path}, Method: {request.method}",
        severity="warning"
    )
    
    # Return structured error response
    return {
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please try again later.",
        "retry_after": 60,
        "rate_limit": str(exc),
        "timestamp": time.time()
    }

# Rate limit statistics
class RateLimitStats:
    """Track rate limit statistics"""
    
    def __init__(self):
        self.violations = 0
        self.total_requests = 0
        self.last_violation = None
    
    def record_request(self):
        """Record a request"""
        self.total_requests += 1
    
    def record_violation(self):
        """Record a rate limit violation"""
        self.violations += 1
        self.last_violation = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limit statistics"""
        return {
            "total_requests": self.total_requests,
            "violations": self.violations,
            "violation_rate": (self.violations / self.total_requests * 100) if self.total_requests > 0 else 0,
            "last_violation": self.last_violation,
            "current_limits": RATE_LIMITS
        }

# Global rate limit statistics
rate_limit_stats = RateLimitStats()

def get_rate_limit_stats() -> Dict[str, Any]:
    """Get current rate limit statistics"""
    return rate_limit_stats.get_stats()

# Middleware to track rate limit statistics
async def rate_limit_stats_middleware(request: Request, call_next):
    """Middleware to track rate limit statistics"""
    rate_limit_stats.record_request()
    
    try:
        response = await call_next(request)
        return response
    except RateLimitExceeded:
        rate_limit_stats.record_violation()
        raise
    except HTTPException as e:
        if e.status_code == 429:
            rate_limit_stats.record_violation()
        raise
