"""
Test startup import compatibility
Tests that the main application can be imported and instantiated without errors,
catching SlowAPI decorator issues and other import-time problems early.
"""
import os
import sys
import pytest

# Add project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_main_app_import():
    """Test that main:app can be imported without decorator errors"""
    # Set test mode to avoid heavy initialization
    os.environ["TEST_MODE"] = "true"
    
    try:
        # Import main module - this will catch SlowAPI decorator issues
        try:
            import main
            
            # Verify the app instance exists
            assert hasattr(main, 'app'), "FastAPI app instance not found"
            assert main.app is not None, "FastAPI app instance is None"
            
            # Basic app attributes check
            assert hasattr(main.app, 'title'), "FastAPI app missing title attribute"
            assert main.app.title == "ReqAgent - Funding Opportunity Management"
            
        except ImportError as e:
            # If we're missing dependencies, that's expected in dev environment
            # Just check that it's not a SlowAPI decorator issue
            if "No 'request' or 'websocket' argument" in str(e):
                pytest.fail(f"SlowAPI decorator configuration error: {e}")
            else:
                pytest.skip(f"Skipping due to missing dependencies: {e}")
        
    finally:
        # Clean up test mode
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]


def test_fastapi_testclient_instantiation():
    """Test that TestClient can be instantiated without crashing"""
    # Set test mode to avoid heavy initialization
    os.environ["TEST_MODE"] = "true"
    
    try:
        try:
            from fastapi.testclient import TestClient
            import main
            
            # This will catch SlowAPI middleware and decorator configuration issues
            client = TestClient(main.app)
            
            # Verify client is created successfully
            assert client is not None, "TestClient instantiation failed"
            
            # Basic connectivity test (without actual requests to avoid DB dependencies)
            assert hasattr(client, 'get'), "TestClient missing HTTP methods"
            
        except ImportError as e:
            if "No 'request' or 'websocket' argument" in str(e):
                pytest.fail(f"SlowAPI decorator configuration error: {e}")
            else:
                pytest.skip(f"Skipping due to missing dependencies: {e}")
        
    finally:
        # Clean up test mode
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]


def test_slowapi_limiter_configuration():
    """Test that SlowAPI limiter is properly configured"""
    # Set test mode to avoid heavy initialization
    os.environ["TEST_MODE"] = "true"
    
    try:
        import main
        from utils.rate_limiter import limiter
        
        # Verify limiter is attached to app state
        assert hasattr(main.app, 'state'), "FastAPI app missing state"
        assert hasattr(main.app.state, 'limiter'), "FastAPI app state missing limiter"
        assert main.app.state.limiter is limiter, "Limiter not properly attached to app state"
        
        # Verify SlowAPI middleware is in the middleware stack
        middleware_classes = [middleware.cls.__name__ for middleware in main.app.user_middleware]
        assert 'SlowAPIMiddleware' in middleware_classes, "SlowAPIMiddleware not found in middleware stack"
        
    finally:
        # Clean up test mode
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]


def test_storage_service_initialization():
    """Test that storage service initializes without errors"""
    # Set test mode and safe storage path
    os.environ["TEST_MODE"] = "true"
    os.environ["REQAGENT_STORAGE_DIR"] = "/tmp/reqagent_test_storage"
    
    try:
        from services.storage import StorageService
        
        # This should not raise any exceptions
        storage = StorageService()
        
        # Verify initialization
        assert storage is not None, "StorageService instantiation failed"
        assert storage.backend_type in ["local", "s3"], f"Unexpected backend type: {storage.backend_type}"
        
        if storage.backend_type == "local":
            assert storage.base_path is not None, "Local storage base_path not set"
            # Should use our test directory or fallback to /tmp
            assert "/tmp" in str(storage.base_path), f"Storage path not in /tmp: {storage.base_path}"
        
    finally:
        # Clean up test environment
        for key in ["TEST_MODE", "REQAGENT_STORAGE_DIR"]:
            if key in os.environ:
                del os.environ[key]


if __name__ == "__main__":
    # Run tests directly for debugging
    test_main_app_import()
    test_fastapi_testclient_instantiation() 
    test_slowapi_limiter_configuration()
    test_storage_service_initialization()
    print("✅ All startup import tests passed!")
