import os
import bcrypt
import jwt
import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Security configuration
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "1"))
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
ADMIN_EMAIL_WHITELIST = os.getenv("ADMIN_EMAIL_WHITELIST", "").split(",") if os.getenv("ADMIN_EMAIL_WHITELIST") else []

# Password policy
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
PASSWORD_REQUIRE_UPPER = os.getenv("PASSWORD_REQUIRE_UPPER", "true").lower() == "true"
PASSWORD_REQUIRE_LOWER = os.getenv("PASSWORD_REQUIRE_LOWER", "true").lower() == "true"
PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "false").lower() == "true"

# Test mode detection
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "4" if TEST_MODE else "12"))

# Role definitions
ROLE_ADMIN = "admin"
ROLE_QA = "qa"
ROLE_EDITOR = "editor"

# Security token scheme
security = HTTPBearer(auto_error=False)

class AuthError(Exception):
    """Custom authentication error"""
    pass

class InsufficientPrivilegesError(Exception):
    """Custom authorization error"""
    pass

def validate_configuration():
    """Validate that all required security configuration is present"""
    missing_configs = []
    
    if not JWT_SECRET:
        missing_configs.append("JWT_SECRET")
    
    if not ADMIN_EMAIL_WHITELIST:
        missing_configs.append("ADMIN_EMAIL_WHITELIST")
    
    if missing_configs:
        raise AuthError(f"Missing required security configuration: {', '.join(missing_configs)}")
    
    logger.info("✅ Security configuration validated")

def validate_password_strength(password: str) -> bool:
    """Validate password meets security requirements"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False
    
    if PASSWORD_REQUIRE_UPPER and not any(c.isupper() for c in password):
        return False
    
    if PASSWORD_REQUIRE_LOWER and not any(c.islower() for c in password):
        return False
    
    if PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False
    
    if PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False
    
    return True

def hash_password(password: str) -> str:
    """Hash password using bcrypt with configurable rounds"""
    if not validate_password_strength(password):
        raise AuthError(f"Password does not meet security requirements (min length: {MIN_PASSWORD_LENGTH})")
    
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def validate_email_allowlist(email: str) -> bool:
    """Check if email is in admin allowlist"""
    if not ADMIN_EMAIL_WHITELIST:
        logger.warning("No admin email allowlist configured")
        return False
    
    return email.lower().strip() in [e.lower().strip() for e in ADMIN_EMAIL_WHITELIST]

def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """Create JWT token with user claims"""
    if not JWT_SECRET:
        raise AuthError("JWT_SECRET not configured")
    
    payload = {
        "sub": user_data.get("email"),
        "role": user_data.get("role", ROLE_QA),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16)  # JWT ID for uniqueness
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    if not JWT_SECRET:
        raise AuthError("JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}")

def verify_api_key(api_key: str) -> bool:
    """Verify API key against configured keys"""
    if not API_KEYS:
        return False
    
    return api_key.strip() in [key.strip() for key in API_KEYS if key.strip()]

def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Extract user information from request (JWT or session)"""
    # Try JWT token first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = verify_jwt_token(token)
            return {
                "email": payload["sub"],
                "role": payload["role"],
                "auth_method": "jwt"
            }
        except AuthError:
            logger.warning("Invalid JWT token in request")
            return None
    
    # Try API key
    api_key = request.headers.get("X-API-Key")
    if api_key and verify_api_key(api_key):
        return {
            "email": "system",
            "role": ROLE_EDITOR,
            "auth_method": "api_key"
        }
    
    # Try session-based auth (for admin UI)
    session_data = request.session.get("admin_session", {})
    if session_data.get("logged_in") and session_data.get("email"):
        return {
            "email": session_data["email"],
            "role": session_data.get("role", ROLE_ADMIN),
            "auth_method": "session"
        }
    
    return None

def require_auth(required_role: Optional[str] = None):
    """Dependency to require authentication and optionally specific role"""
    def auth_dependency(request: Request):
        user = get_user_from_request(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if required_role and user["role"] != required_role:
            logger.warning(f"Access denied: {user['email']} (role: {user['role']}) attempted to access {required_role}-only route")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges"
            )
        
        return user
    
    return auth_dependency

def require_admin():
    """Dependency to require admin role"""
    return require_auth(required_role=ROLE_ADMIN)

def require_qa_or_above():
    """Dependency to require QA role or higher"""
    def qa_dependency(request: Request):
        user = get_user_from_request(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if user["role"] not in [ROLE_ADMIN, ROLE_QA]:
            logger.warning(f"Access denied: {user['email']} (role: {user['role']}) attempted to access QA+ route")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="QA role or higher required"
            )
        
        return user
    
    return qa_dependency

def require_editor_or_above():
    """Dependency to require editor role or higher"""
    def editor_dependency(request: Request):
        user = get_user_from_request(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if user["role"] not in [ROLE_ADMIN, ROLE_QA, ROLE_EDITOR]:
            logger.warning(f"Access denied: {user['email']} (role: {user['role']}) attempted to access editor+ route")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Editor role or higher required"
            )
        
        return user
    
    return editor_dependency

def hash_ip_address(ip: str) -> str:
    """Hash IP address for privacy in logs"""
    return hashlib.sha256(ip.encode()).hexdigest()[:8]

def log_security_event(event_type: str, user_email: str, ip_address: str, details: str = "", severity: str = "info"):
    """Log security events with structured data"""
    hashed_ip = hash_ip_address(ip_address)
    
    log_data = {
        "event_type": event_type,
        "user_email": user_email,
        "ip_hash": hashed_ip,
        "details": details,
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if severity == "error":
        logger.error(f"🔒 Security Event: {event_type} - {user_email} ({hashed_ip}) - {details}")
    elif severity == "warning":
        logger.warning(f"🔒 Security Event: {event_type} - {user_email} ({hashed_ip}) - {details}")
    else:
        logger.info(f"🔒 Security Event: {event_type} - {user_email} ({hashed_ip}) - {details}")

# Convenience functions for backward compatibility
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from request (backward compatibility)"""
    return get_user_from_request(request)

def require_admin_role(request: Request):
    """Require admin role (backward compatibility)"""
    return require_admin()(request)

# Initialize configuration validation (only in production)
if os.getenv("ENVIRONMENT", "development") == "production":
    try:
        validate_configuration()
    except AuthError as e:
        logger.error(f"❌ Security configuration error: {e}")
        raise
else:
    logger.info("🔧 Development mode: Skipping strict security validation")
