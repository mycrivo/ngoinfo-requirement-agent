from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import bcrypt
import os
import secrets
from typing import Optional
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Environment-based admin credentials
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

def verify_admin_credentials(email: str, password: str) -> bool:
    """
    Verify admin credentials against environment variables
    """
    try:
        # Check email match
        if email.lower().strip() != ADMIN_EMAIL.lower().strip():
            logger.warning(f"Failed login attempt - email mismatch: {email}")
            return False
        
        # Check if password hash is configured
        if not ADMIN_PASSWORD_HASH:
            logger.error("ADMIN_PASSWORD_HASH environment variable not set")
            return False
        
        # Verify password using bcrypt
        if bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD_HASH.encode('utf-8')):
            logger.info(f"Successful admin login for: {email}")
            return True
        else:
            logger.warning(f"Failed login attempt - password mismatch for: {email}")
            return False
            
    except Exception as e:
        logger.error(f"Error during credential verification: {e}")
        return False

def is_logged_in(request: Request) -> bool:
    """
    Check if user is logged in by checking session
    """
    try:
        session_data = request.session.get("admin_session", {})
        return session_data.get("logged_in", False) and session_data.get("email") == ADMIN_EMAIL
    except Exception as e:
        logger.debug(f"Session check error: {e}")
        return False

def create_admin_session(request: Request) -> None:
    """
    Create admin session after successful login
    """
    request.session["admin_session"] = {
        "logged_in": True,
        "email": ADMIN_EMAIL,
        "login_time": str(os.times().elapsed)  # Simple timestamp
    }

def clear_admin_session(request: Request) -> None:
    """
    Clear admin session on logout
    """
    request.session.pop("admin_session", None)

def require_login(request: Request):
    """
    Dependency to require admin login for protected routes
    """
    if not is_logged_in(request):
        logger.warning(f"Unauthorized access attempt to {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/admin/login"}
        )
    return True

def get_current_admin(request: Request) -> Optional[str]:
    """
    Get current admin email if logged in
    """
    if is_logged_in(request):
        return ADMIN_EMAIL
    return None

# CSRF Protection Functions
def create_csrf_token() -> str:
    """
    Create simple CSRF token
    """
    return secrets.token_urlsafe(32)

def verify_csrf_token(request: Request, token: str) -> bool:
    """
    Verify CSRF token (simple implementation)
    """
    stored_token = request.session.get("csrf_token")
    return stored_token and stored_token == token

def get_csrf_token(request: Request) -> str:
    """
    Get or create CSRF token for forms
    """
    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        csrf_token = create_csrf_token()
        request.session["csrf_token"] = csrf_token
    return csrf_token

# Utility function to generate password hash (for setup)
def generate_password_hash(password: str) -> str:
    """
    Generate bcrypt hash for a password - use this to create ADMIN_PASSWORD_HASH
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# Legacy compatibility functions (keep for existing code that might reference these)
def require_admin_auth(request: Request):
    """Legacy function - redirect to new require_login"""
    return require_login(request)

def get_session_user(request: Request) -> Optional[str]:
    """Legacy function - use get_current_admin instead"""
    return get_current_admin(request)

def verify_session_token(token: str) -> Optional[dict]:
    """Legacy function - always returns None since we use sessions now"""
    return None

def create_session_token(username: str) -> str:
    """Legacy function - returns empty string since we use sessions now"""
    return "" 