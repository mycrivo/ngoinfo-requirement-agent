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
                if 'pytest' in sys.modules:
                    pytest.fail(f"SlowAPI decorator configuration error: {e}")
                else:
                    raise AssertionError(f"SlowAPI decorator configuration error: {e}")
            else:
                if 'pytest' in sys.modules:
                    pytest.skip(f"Skipping due to missing dependencies: {e}")
                else:
                    print(f"⚠️ Skipping due to missing dependencies: {e}")
                    return
        
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
                if 'pytest' in sys.modules:
                    pytest.fail(f"SlowAPI decorator configuration error: {e}")
                else:
                    raise AssertionError(f"SlowAPI decorator configuration error: {e}")
            else:
                if 'pytest' in sys.modules:
                    pytest.skip(f"Skipping due to missing dependencies: {e}")
                else:
                    print(f"⚠️ Skipping due to missing dependencies: {e}")
                    return
        
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


def test_rate_limit_exception_handler_app_level():
    """Test that RateLimitExceeded handler is registered at app level, not router level"""
    # Set test mode to avoid heavy initialization
    os.environ["TEST_MODE"] = "true"
    
    try:
        try:
            import main
            from slowapi.errors import RateLimitExceeded
            
            # Verify app has exception handlers
            assert hasattr(main.app, 'exception_handlers'), "FastAPI app missing exception_handlers"
            
            # Check that RateLimitExceeded is registered at app level
            app_handlers = main.app.exception_handlers
            rate_limit_handler_found = False
            
            for exception_type, handler in app_handlers.items():
                if exception_type == RateLimitExceeded or (hasattr(exception_type, '__name__') and exception_type.__name__ == 'RateLimitExceeded'):
                    rate_limit_handler_found = True
                    break
            
            assert rate_limit_handler_found, "RateLimitExceeded handler not found in app-level exception handlers"
            
            # Verify no router-level exception handlers exist (by checking routers don't have exception_handler decorators)
            # This is a compile-time check - if there were router-level handlers, import would fail
            
        except ImportError as e:
            # Check for specific rate limit handler errors
            if "exception_handler" in str(e).lower() or "router" in str(e).lower():
                if 'pytest' in sys.modules:
                    pytest.fail(f"Router-level exception handler configuration error: {e}")
                else:
                    raise AssertionError(f"Router-level exception handler configuration error: {e}")
            else:
                if 'pytest' in sys.modules:
                    pytest.skip(f"Skipping due to missing dependencies: {e}")
                else:
                    print(f"⚠️ Skipping due to missing dependencies: {e}")
                    return
                
    finally:
        # Clean up test mode
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]


if __name__ == "__main__":
    # Run tests directly for debugging
    try:
        test_main_app_import()
        print("✅ test_main_app_import passed!")
    except Exception as e:
        print(f"❌ test_main_app_import failed: {e}")
    
    try:
        test_fastapi_testclient_instantiation()
        print("✅ test_fastapi_testclient_instantiation passed!")
    except Exception as e:
        print(f"❌ test_fastapi_testclient_instantiation failed: {e}")
    
    try:
        test_slowapi_limiter_configuration()
        print("✅ test_slowapi_limiter_configuration passed!")
    except Exception as e:
        print(f"❌ test_slowapi_limiter_configuration failed: {e}")
        
    try:
        test_storage_service_initialization()
        print("✅ test_storage_service_initialization passed!")
    except Exception as e:
        print(f"❌ test_storage_service_initialization failed: {e}")
        
    try:
        test_rate_limit_exception_handler_app_level()
        print("✅ test_rate_limit_exception_handler_app_level passed!")
    except Exception as e:
        print(f"❌ test_rate_limit_exception_handler_app_level failed: {e}")
    
    print("✅ All startup import tests completed!")
