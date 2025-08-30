import os
from typing import List, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

# Security configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",") if os.getenv("ALLOWED_ORIGINS") else ["*"]
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "false").lower() == "true"
CSP_POLICY = os.getenv("CSP_POLICY", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self'")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = CSP_POLICY
        
        # Strict Transport Security (only if enabled and behind TLS)
        if ENABLE_HSTS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Remove server information
        if "server" in response.headers:
            del response.headers["server"]
        
        # Add security info header
        response.headers["X-Security-Info"] = "ReqAgent Security Enabled"
        
        return response

def create_cors_middleware():
    """Create CORS middleware with security configuration"""
    return CORSMiddleware(
        app=None,  # Will be set when added to FastAPI app
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Requested-With"
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ]
    )

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate and sanitize requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Validate request size
        content_length = request.headers.get("content-length")
        if content_length:
            max_size = int(os.getenv("MAX_REQUEST_SIZE_MB", "10")) * 1024 * 1024
            if int(content_length) > max_size:
                logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
                return Response(
                    status_code=413,
                    content="Request too large",
                    media_type="text/plain"
                )
        
        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT"]:
            content_type = request.headers.get("content-type", "")
            if not content_type:
                logger.warning(f"Missing content-type header from {request.client.host}")
                return Response(
                    status_code=400,
                    content="Missing content-type header",
                    media_type="text/plain"
                )
        
        # Block suspicious user agents
        user_agent = request.headers.get("user-agent", "")
        suspicious_agents = ["bot", "crawler", "spider", "scraper"]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            logger.info(f"Suspicious user agent: {user_agent} from {request.client.host}")
            # Don't block, just log for monitoring
        
        response = await call_next(request)
        return response

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log security-relevant request information"""
    
    async def dispatch(self, request: Request, call_next):
        # Log security-relevant information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        referer = request.headers.get("referer", "none")
        
        # Log suspicious patterns
        if self._is_suspicious_request(request, client_ip):
            logger.warning(f"Suspicious request: {request.method} {request.url.path} from {client_ip}")
        
        response = await call_next(request)
        
        # Log security events
        if response.status_code in [401, 403, 429]:
            logger.info(f"Security event: {response.status_code} for {request.method} {request.url.path} from {client_ip}")
        
        return response
    
    def _is_suspicious_request(self, request: Request, client_ip: str) -> bool:
        """Check if request shows suspicious patterns"""
        # Check for common attack patterns
        path = request.url.path.lower()
        query = str(request.url.query).lower()
        
        suspicious_patterns = [
            "..",  # Path traversal
            "script",  # XSS attempts
            "javascript:",  # XSS attempts
            "data:",  # Data URI attacks
            "vbscript:",  # VBScript attacks
            "onload=",  # Event handler injection
            "onerror=",  # Event handler injection
            "eval(",  # Code injection
            "document.cookie",  # Cookie theft attempts
        ]
        
        return any(pattern in path or pattern in query for pattern in suspicious_patterns)

def create_security_middleware_stack():
    """Create a stack of security middleware"""
    return [
        SecurityHeadersMiddleware,
        RequestValidationMiddleware,
        SecurityLoggingMiddleware
    ]

# Security configuration validation
def validate_security_config():
    """Validate security configuration"""
    warnings = []
    
    if ALLOWED_ORIGINS == ["*"]:
        warnings.append("ALLOWED_ORIGINS is set to '*' - consider restricting to specific domains")
    
    if not ENABLE_HSTS:
        warnings.append("HSTS is disabled - consider enabling for production")
    
    if len(CSP_POLICY) < 50:
        warnings.append("CSP policy seems too short - review security policy")
    
    if warnings:
        for warning in warnings:
            logger.warning(f"Security configuration warning: {warning}")
    else:
        logger.info("✅ Security configuration validated")

# Initialize security configuration
validate_security_config()
