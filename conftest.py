import pytest
import os
import tempfile
from typing import Dict, Any
from unittest.mock import Mock, patch

# Set test environment defaults
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("OCR_BACKEND", "none")
os.environ.setdefault("PDF_ENGINE", "reportlab")
os.environ.setdefault("FILE_STORAGE_ROOT", "/tmp/reqagent-test")
os.environ.setdefault("SKIP_SECURITY_TESTS", "1")  # default skip locally
os.environ.setdefault("SKIP_SLOW_TESTS", "1")

@pytest.fixture(autouse=True)
def test_settings_env():
    """Set up test environment variables for all tests"""
    test_env = {
        "JWT_SECRET": "test-secret-key-12345",
        "API_KEYS": "testkey1,testkey2",
        "ADMIN_EMAIL_WHITELIST": "admin@test.com,qa@test.com",
        "RATE_LIMITS": "default=5/second,login=5/minute",
        "ALLOWED_ORIGINS": "http://localhost",
        "BCRYPT_ROUNDS": "4",
        "OCR_BACKEND": "none",
        "PDF_ENGINE": "reportlab",
        "FILE_STORAGE_ROOT": "/tmp/reqagent-test",
        "TEST_MODE": "true",
        "ENVIRONMENT": "development"
    }
    
    # Store original values
    original_env = {}
    for key in test_env:
        if key in os.environ:
            original_env[key] = os.environ[key]
    
    # Set test values
    for key, value in test_env.items():
        os.environ[key] = value
    
    yield test_env
    
    # Restore original values
    for key in test_env:
        if key in original_env:
            os.environ[key] = original_env[key]
        else:
            if key in os.environ:
                del os.environ[key]

@pytest.fixture
def mock_request():
    """Create a mock request object for testing"""
    request = Mock()
    request.headers = {}
    request.session = {}
    request.client = Mock()
    request.client.host = "127.0.0.1"
    request.url.path = "/test"
    request.url.query = ""
    request.method = "GET"
    return request

@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        "email": "test@example.com",
        "role": "qa",
        "password": "TestPass123"
    }

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix="reqagent-test-")
    yield temp_dir
    # Cleanup handled by OS

@pytest.fixture(autouse=True)
def disable_external_calls():
    """Disable external network calls during tests"""
    with patch('httpx.AsyncClient.post'), \
         patch('httpx.AsyncClient.get'), \
         patch('requests.post'), \
         patch('requests.get'):
        yield
