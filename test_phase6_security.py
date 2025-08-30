import os
import pytest

# Skip security tests locally by default
if os.getenv("SKIP_SECURITY_TESTS", "1") == "1":
    pytest.skip("Skipping Phase-6 security tests locally; run in CI", allow_module_level=True)

# Mark slow tests for local skipping
skip_local = os.getenv("SKIP_SLOW_TESTS", "1") == "1"
slow = pytest.mark.skipif(skip_local, reason="Skipped locally; runs in CI")

import tempfile
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import jwt
import bcrypt

# Import the security services we're testing
from utils.auth_enhanced import (
    validate_configuration,
    validate_password_strength,
    hash_password,
    verify_password,
    validate_email_allowlist,
    create_jwt_token,
    verify_jwt_token,
    verify_api_key,
    get_user_from_request,
    require_auth,
    require_admin,
    require_qa_or_above,
    require_editor_or_above,
    hash_ip_address,
    log_security_event,
    ROLE_ADMIN,
    ROLE_QA,
    ROLE_EDITOR
)

from utils.rate_limiter import (
    parse_rate_limits,
    get_rate_limit_for_route,
    rate_limit_dependency,
    get_rate_limit_stats
)

from utils.security_middleware import (
    ALLOWED_ORIGINS,
    ENABLE_HSTS,
    CSP_POLICY,
    validate_security_config
)

@pytest.mark.unit
class TestAuthentication:
    """Test authentication functionality"""
    
    def test_configuration_validation(self):
        """Test security configuration validation"""
        # Should pass with valid config
        validate_configuration()
        
        # Should fail with missing JWT_SECRET
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception):
                validate_configuration()
    
    def test_password_strength_validation(self):
        """Test password strength validation"""
        # Valid password
        assert validate_password_strength("StrongPass123") is True
        
        # Too short
        assert validate_password_strength("Weak") is False
        
        # Missing uppercase
        assert validate_password_strength("weakpass123") is False
        
        # Missing lowercase
        assert validate_password_strength("WEAKPASS123") is False
        
        # Missing digit
        assert validate_password_strength("WeakPass") is False
    
    def test_password_hashing_and_verification(self):
        """Test password hashing and verification"""
        password = "TestPassword123"
        
        # Hash password
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert password != hashed
        
        # Verify password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False
    
    def test_email_allowlist_validation(self):
        """Test email allowlist validation"""
        # Valid emails
        assert validate_email_allowlist("admin@test.com") is True
        assert validate_email_allowlist("QA@TEST.COM") is True  # Case insensitive
        
        # Invalid emails
        assert validate_email_allowlist("hacker@evil.com") is False
        assert validate_email_allowlist("") is False
    
    def test_jwt_token_creation_and_verification(self):
        """Test JWT token creation and verification"""
        user_data = {
            "email": "test@example.com",
            "role": ROLE_QA
        }
        
        # Create token
        token = create_jwt_token(user_data)
        assert isinstance(token, str)
        
        # Verify token
        payload = verify_jwt_token(token)
        assert payload["sub"] == user_data["email"]
        assert payload["role"] == user_data["role"]
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload
    
    @slow
    def test_jwt_token_expiry(self):
        """Test JWT token expiry handling"""
        # Create token with short expiry
        with patch('utils.auth_enhanced.JWT_EXPIRY_HOURS', 0.0001):  # Very short expiry
            user_data = {"email": "test@example.com", "role": ROLE_QA}
            token = create_jwt_token(user_data)
            
            # Wait for token to expire
            time.sleep(0.1)
            
            # Should fail verification
            with pytest.raises(Exception):
                verify_jwt_token(token)
    
    def test_api_key_verification(self):
        """Test API key verification"""
        # Valid keys
        assert verify_api_key("testkey1") is True
        assert verify_api_key("testkey2") is True
        
        # Invalid keys
        assert verify_api_key("invalid") is False
        assert verify_api_key("") is False
    
    def test_ip_address_hashing(self):
        """Test IP address hashing for privacy"""
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"
        
        hash1 = hash_ip_address(ip1)
        hash2 = hash_ip_address(ip2)
        
        # Should be different for different IPs
        assert hash1 != hash2
        
        # Should be consistent for same IP
        assert hash1 == hash_ip_address(ip1)
        
        # Should be 8 characters long
        assert len(hash1) == 8
        assert len(hash2) == 8

@pytest.mark.unit
class TestAuthorization:
    """Test authorization and role-based access control"""
    
    def test_role_based_access_control(self, mock_request):
        """Test role-based access control"""
        # Test admin access
        admin_user = {"email": "admin@test.com", "role": ROLE_ADMIN}
        with patch('utils.auth_enhanced.get_user_from_request', return_value=admin_user):
            # Admin should access admin routes
            admin_dep = require_admin()
            result = admin_dep(mock_request)
            assert result == admin_user
            
            # Admin should access QA routes
            qa_dep = require_qa_or_above()
            result = qa_dep(mock_request)
            assert result == admin_user
            
            # Admin should access editor routes
            editor_dep = require_editor_or_above()
            result = editor_dep(mock_request)
            assert result == admin_user
        
        # Test QA access
        qa_user = {"email": "qa@test.com", "role": ROLE_QA}
        with patch('utils.auth_enhanced.get_user_from_request', return_value=qa_user):
            # QA should not access admin routes
            admin_dep = require_admin()
            with pytest.raises(Exception):
                admin_dep(mock_request)
            
            # QA should access QA routes
            qa_dep = require_qa_or_above()
            result = qa_dep(mock_request)
            assert result == qa_user
            
            # QA should access editor routes
            editor_dep = require_editor_or_above()
            result = editor_dep(mock_request)
            assert result == qa_user
        
        # Test editor access
        editor_user = {"email": "editor@test.com", "role": ROLE_EDITOR}
        with patch('utils.auth_enhanced.get_user_from_request', return_value=editor_user):
            # Editor should not access admin routes
            admin_dep = require_admin()
            with pytest.raises(Exception):
                admin_dep(mock_request)
            
            # Editor should not access QA routes
            qa_dep = require_qa_or_above()
            with pytest.raises(Exception):
                qa_dep(mock_request)
            
            # Editor should access editor routes
            editor_dep = require_editor_or_above()
            result = editor_dep(mock_request)
            assert result == editor_user

@pytest.mark.unit
class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limit_parsing(self):
        """Test rate limit configuration parsing"""
        # Test default limits
        limits = parse_rate_limits()
        assert "default" in limits
        assert "login" in limits
        
        # Test custom limits
        with patch.dict(os.environ, {"RATE_LIMITS": "default=10/second,login=3/minute"}):
            limits = parse_rate_limits()
            assert limits["default"] == "10/second"
            assert limits["login"] == "3/minute"
        
        # Test invalid format
        with patch.dict(os.environ, {"RATE_LIMITS": "invalid-format"}):
            limits = parse_rate_limits()
            assert "default" in limits  # Should fall back to defaults
    
    def test_rate_limit_for_routes(self):
        """Test rate limit assignment for different routes"""
        # Admin routes
        limit = get_rate_limit_for_route("/admin/dashboard", "admin")
        assert "second" in limit
        
        # Login routes
        limit = get_rate_limit_for_route("/admin/login")
        assert "minute" in limit
        
        # API routes
        limit = get_rate_limit_for_route("/api/requirement/parse")
        assert "second" in limit
        
        # Crawler routes
        limit = get_rate_limit_for_route("/api/crawler/start")
        assert "second" in limit
        
        # Publisher routes
        limit = get_rate_limit_for_route("/api/wordpress/publish")
        assert "minute" in limit
    
    def test_rate_limit_statistics(self):
        """Test rate limit statistics tracking"""
        stats = get_rate_limit_stats()
        assert "total_requests" in stats
        assert "violations" in stats
        assert "current_limits" in stats

@pytest.mark.unit
class TestSecurityMiddleware:
    """Test security middleware functionality"""
    
    def test_security_configuration_validation(self):
        """Test security configuration validation"""
        # Should pass with default config
        validate_security_config()
        
        # Test warnings for insecure config
        with patch('utils.security_middleware.ALLOWED_ORIGINS', ["*"]):
            with patch('utils.security_middleware.ENABLE_HSTS', False):
                with patch('utils.security_middleware.CSP_POLICY', "short"):
                    validate_security_config()  # Should log warnings but not fail
    
    def test_cors_middleware_creation(self):
        """Test CORS middleware creation"""
        from utils.security_middleware import create_cors_middleware
        
        cors_middleware = create_cors_middleware()
        assert cors_middleware is not None
        
        # Test with custom origins
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://example.com,https://test.com"}):
            cors_middleware = create_cors_middleware()
            assert cors_middleware is not None

@pytest.mark.unit
class TestSecurityLogging:
    """Test security event logging"""
    
    def test_security_event_logging(self):
        """Test security event logging functionality"""
        # Test different event types
        event_types = [
            "login_success",
            "login_failure", 
            "rate_limit_exceeded",
            "forbidden_access",
            "password_change",
            "token_refresh"
        ]
        
        for event_type in event_types:
            # Should not raise exception
            log_security_event(
                event_type=event_type,
                user_email="test@example.com",
                ip_address="192.168.1.1",
                details="Test event",
                severity="info"
            )

@pytest.mark.integration
class TestIntegration:
    """Test integration between security components"""
    
    def test_auth_with_rate_limiting(self):
        """Test authentication with rate limiting integration"""
        # Create user data
        user_data = {
            "email": "admin@test.com",
            "role": ROLE_ADMIN
        }
        
        # Create JWT token
        token = create_jwt_token(user_data)
        
        # Verify token
        payload = verify_jwt_token(token)
        assert payload["sub"] == user_data["email"]
        assert payload["role"] == user_data["role"]
        
        # Test rate limiting
        limits = parse_rate_limits()
        assert "default" in limits
        assert "login" in limits
    
    def test_security_configuration_integration(self):
        """Test security configuration integration"""
        # Validate auth config
        validate_configuration()
        
        # Validate security config
        validate_security_config()
        
        # Validate rate limiting config
        limits = parse_rate_limits()
        assert isinstance(limits, dict)
        assert len(limits) > 0

if __name__ == '__main__':
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])
