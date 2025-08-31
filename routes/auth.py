from fastapi import APIRouter, HTTPException, status, Depends, Request, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from utils.auth_enhanced import (
    verify_password,
    validate_email_allowlist,
    create_jwt_token,
    log_security_event,
    hash_ip_address,
    require_auth,
    ROLE_ADMIN,
    ROLE_QA,
    ROLE_EDITOR
)
from utils.rate_limiter import rate_limit_login
from db import get_db
from models import AdminUser
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

class TokenValidationResponse(BaseModel):
    valid: bool
    user: Optional[Dict[str, Any]] = None
    expires_at: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class UserInfoResponse(BaseModel):
    email: str
    role: str
    full_name: Optional[str] = None
    is_active: bool
    last_login: Optional[str] = None

@router.post("/login", response_model=LoginResponse)
@rate_limit_login()
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    """
    try:
        client_ip = request.client.host if request.client else "unknown"
        hashed_ip = hash_ip_address(client_ip)
        
        # Validate email against allowlist
        if not validate_email_allowlist(login_data.email):
            log_security_event(
                event_type="login_failure",
                user_email=login_data.email,
                ip_address=client_ip,
                details="Email not in allowlist",
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Find user in database
        user = db.query(AdminUser).filter(
            AdminUser.email == login_data.email.lower(),
            AdminUser.is_active == True
        ).first()
        
        if not user:
            log_security_event(
                event_type="login_failure",
                user_email=login_data.email,
                ip_address=client_ip,
                details="User not found or inactive",
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            log_security_event(
                event_type="login_failure",
                user_email=login_data.email,
                ip_address=client_ip,
                details="Invalid password",
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create JWT token
        user_data = {
            "email": user.email,
            "role": user.role if hasattr(user, 'role') else ROLE_QA,
            "user_id": user.id
        }
        
        token = create_jwt_token(user_data)
        
        # Log successful login
        log_security_event(
            event_type="login_success",
            user_email=login_data.email,
            ip_address=client_ip,
            details=f"Role: {user_data['role']}",
            severity="info"
        )
        
        return LoginResponse(
            access_token=token,
            expires_in=3600,  # 1 hour
            user={
                "email": user.email,
                "role": user_data["role"],
                "full_name": user.full_name,
                "is_active": user.is_active
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        log_security_event(
            event_type="login_error",
            user_email=login_data.email,
            ip_address=client_ip,
            details=f"System error: {str(e)}",
            severity="error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(
    request: Request,
    token: str = Form(...)
):
    """
    Validate JWT token and return user information
    """
    try:
        from utils.auth_enhanced import verify_jwt_token
        
        payload = verify_jwt_token(token)
        
        return TokenValidationResponse(
            valid=True,
            user={
                "email": payload["sub"],
                "role": payload["role"]
            },
            expires_at=datetime.fromtimestamp(payload["exp"]).isoformat()
        )
        
    except Exception as e:
        return TokenValidationResponse(valid=False)

@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(require_auth())
):
    """
    Get current user information from JWT token
    """
    return UserInfoResponse(
        email=current_user["email"],
        role=current_user["role"],
        full_name=current_user.get("full_name"),
        is_active=True,
        last_login=current_user.get("last_login")
    )

@router.post("/refresh")
async def refresh_token(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_auth())
):
    """
    Refresh JWT token
    """
    try:
        # Create new token with same user data
        user_data = {
            "email": current_user["email"],
            "role": current_user["role"],
            "user_id": current_user.get("user_id")
        }
        
        new_token = create_jwt_token(user_data)
        
        log_security_event(
            event_type="token_refresh",
            user_email=current_user["email"],
            ip_address=request.client.host if request.client else "unknown",
            details="Token refreshed successfully",
            severity="info"
        )
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 3600
        }
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/logout")
async def logout(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_auth())
):
    """
    Logout user (client should discard token)
    """
    client_ip = request.client.host if request.client else "unknown"
    
    log_security_event(
        event_type="logout",
        user_email=current_user["email"],
        ip_address=client_ip,
        details="User logged out",
        severity="info"
    )
    
    return {"message": "Logged out successfully"}

@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: Dict[str, Any] = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """
    Change user password
    """
    try:
        client_ip = request.client.host if request.client else "unknown"
        
        # Find user
        user = db.query(AdminUser).filter(
            AdminUser.email == current_user["email"]
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not verify_password(password_data.current_password, user.password_hash):
            log_security_event(
                event_type="password_change_failure",
                user_email=current_user["email"],
                ip_address=client_ip,
                details="Current password incorrect",
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        from utils.auth_enhanced import hash_password
        new_password_hash = hash_password(password_data.new_password)
        
        # Update password
        user.password_hash = new_password_hash
        user.updated_at = datetime.utcnow()
        db.commit()
        
        log_security_event(
            event_type="password_change_success",
            user_email=current_user["email"],
            ip_address=client_ip,
            details="Password changed successfully",
            severity="info"
        )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@router.get("/roles")
async def get_available_roles(
    current_user: Dict[str, Any] = Depends(require_auth(required_role=ROLE_ADMIN))
):
    """
    Get available roles (admin only)
    """
    return {
        "roles": [
            {"id": ROLE_ADMIN, "name": "Administrator", "description": "Full system access"},
            {"id": ROLE_QA, "name": "QA Reviewer", "description": "Review and approve funding opportunities"},
            {"id": ROLE_EDITOR, "name": "Editor", "description": "Publish content to WordPress"}
        ]
    }

@router.get("/health")
async def auth_health_check():
    """
    Authentication service health check
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "JWT authentication",
            "Role-based access control",
            "Rate limiting",
            "Security logging"
        ]
    }






