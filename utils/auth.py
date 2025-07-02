from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature
import bcrypt
import os
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

from db import get_db
from models import AdminUser

load_dotenv()
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", secrets.token_urlsafe(32))
SESSION_MAX_AGE = 86400  # 24 hours

# Authorized email addresses (can be environment variable)
AUTHORIZED_EMAILS = os.getenv("AUTHORIZED_EMAILS", "admin@example.com,qa@example.com").split(",")

# Session and CSRF serializers
session_serializer = URLSafeTimedSerializer(SECRET_KEY)
csrf_serializer = URLSafeTimedSerializer(CSRF_SECRET_KEY)

# Security scheme
security = HTTPBearer(auto_error=False)

class AuthService:
    """Enhanced authentication service with bcrypt and email-based access"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def is_email_authorized(email: str) -> bool:
        """Check if email is in authorized list"""
        return email.lower().strip() in [e.lower().strip() for e in AUTHORIZED_EMAILS]
    
    @staticmethod
    def create_admin_user(
        db: Session, 
        email: str, 
        username: str, 
        password: str, 
        full_name: str = None,
        is_superuser: bool = False
    ) -> AdminUser:
        """Create a new admin user"""
        # Check if email is authorized
        if not AuthService.is_email_authorized(email):
            raise ValueError(f"Email {email} is not authorized for admin access")
        
        # Check if user already exists
        existing_user = db.query(AdminUser).filter(
            (AdminUser.email == email) | (AdminUser.username == username)
        ).first()
        
        if existing_user:
            raise ValueError("User with this email or username already exists")
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Create user
        admin_user = AdminUser(
            email=email,
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            is_superuser=is_superuser,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        logger.info(f"Created admin user: {email}")
        return admin_user
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[AdminUser]:
        """Authenticate user by username/email and password"""
        # Find user by username or email
        user = db.query(AdminUser).filter(
            ((AdminUser.username == username) | (AdminUser.email == username)) &
            (AdminUser.is_active == True)
        ).first()
        
        if not user:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return None
        
        if not AuthService.verify_password(password, user.password_hash):
            logger.warning(f"Failed login attempt for user: {username}")
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"Successful login for user: {username}")
        return user
    
    @staticmethod
    def create_session_token(user: AdminUser) -> str:
        """Create a signed session token"""
        data = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_superuser": user.is_superuser,
            "created_at": datetime.utcnow().isoformat()
        }
        return session_serializer.dumps(data)
    
    @staticmethod
    def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode session token"""
        try:
            data = session_serializer.loads(token, max_age=SESSION_MAX_AGE)
            return data
        except Exception as e:
            logger.debug(f"Session token verification failed: {e}")
            return None
    
    @staticmethod
    def create_csrf_token() -> str:
        """Create CSRF token"""
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "nonce": secrets.token_urlsafe(16)
        }
        return csrf_serializer.dumps(data)
    
    @staticmethod
    def verify_csrf_token(token: str) -> bool:
        """Verify CSRF token"""
        try:
            csrf_serializer.loads(token, max_age=3600)  # 1 hour expiry
            return True
        except Exception:
            return False

# Session management functions
def get_session_user(request: Request, db: Session = None) -> Optional[Dict[str, Any]]:
    """Get the current authenticated user from session"""
    session_token = request.cookies.get("admin_session")
    if not session_token:
        return None
    
    session_data = AuthService.verify_session_token(session_token)
    if not session_data:
        return None
    
    # Optional: Verify user still exists and is active
    if db:
        user = db.query(AdminUser).filter(
            AdminUser.id == session_data.get("user_id"),
            AdminUser.is_active == True
        ).first()
        if not user:
            return None
    
    return session_data

def require_admin_auth(request: Request):
    """Dependency to require admin authentication"""
    user = get_session_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/admin/login"}
        )
    return user

def require_superuser_auth(request: Request):
    """Dependency to require superuser authentication"""
    user = get_session_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/admin/login"}
        )
    
    if not user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required"
        )
    return user

def get_csrf_token(request: Request) -> str:
    """Get CSRF token for forms"""
    return AuthService.create_csrf_token()

def verify_csrf_token(request: Request, token: str) -> bool:
    """Verify CSRF token from form"""
    return AuthService.verify_csrf_token(token)

# Database setup functions
def ensure_admin_users_exist(db: Session):
    """Ensure at least one admin user exists"""
    try:
        # Check if any admin users exist
        admin_count = db.query(AdminUser).count()
        
        if admin_count == 0:
            logger.info("No admin users found, creating default admin user")
            
            # Create default admin from environment or defaults
            default_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
            default_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
            
            if default_email not in AUTHORIZED_EMAILS:
                AUTHORIZED_EMAILS.append(default_email)
            
            AuthService.create_admin_user(
                db=db,
                email=default_email,
                username=default_username,
                password=default_password,
                full_name="Default Administrator",
                is_superuser=True
            )
            
            logger.info(f"Created default admin user: {default_email}")
        
    except Exception as e:
        logger.error(f"Error ensuring admin users exist: {e}")

# Legacy compatibility functions (for existing code)
def verify_admin_credentials(username: str, password: str, db: Session = None) -> bool:
    """Legacy function - use authenticate_user instead"""
    if not db:
        return False
    
    user = AuthService.authenticate_user(db, username, password)
    return user is not None

def create_session_token(username: str) -> str:
    """Legacy function - use AuthService.create_session_token instead"""
    # This is a simplified version for backward compatibility
    data = {"username": username, "created_at": datetime.utcnow().isoformat()}
    return session_serializer.dumps(data)

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Legacy function - use AuthService.verify_session_token instead"""
    return AuthService.verify_session_token(token) 