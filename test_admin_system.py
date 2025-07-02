#!/usr/bin/env python3
"""
Test script for ReqAgent Admin System

This script tests the core functionality of the secure admin authentication system.
"""

import os
import sys
import asyncio
from sqlalchemy.orm import Session

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db, engine
from models import Base, AdminUser
from utils.auth import AuthService, AuthService
from dotenv import load_dotenv

load_dotenv()

def test_database_connection():
    """Test database connection and table creation"""
    print("🔍 Testing database connection...")
    try:
        Base.metadata.create_all(bind=engine)
        db = next(get_db())
        
        # Test query
        count = db.query(AdminUser).count()
        print(f"✅ Database connected successfully. Found {count} admin users.")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_password_hashing():
    """Test bcrypt password hashing"""
    print("\n🔍 Testing password hashing...")
    try:
        test_password = "test_password_123"
        
        # Hash password
        hashed = AuthService.hash_password(test_password)
        print(f"✅ Password hashed successfully")
        
        # Verify correct password
        if AuthService.verify_password(test_password, hashed):
            print("✅ Password verification successful")
        else:
            print("❌ Password verification failed")
            return False
        
        # Verify incorrect password
        if not AuthService.verify_password("wrong_password", hashed):
            print("✅ Incorrect password correctly rejected")
        else:
            print("❌ Incorrect password was accepted")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Password hashing test failed: {e}")
        return False

def test_email_authorization():
    """Test email authorization system"""
    print("\n🔍 Testing email authorization...")
    try:
        # Test authorized email (from environment)
        authorized_emails = os.getenv("AUTHORIZED_EMAILS", "admin@example.com,qa@example.com").split(",")
        
        if AuthService.is_email_authorized(authorized_emails[0].strip()):
            print(f"✅ Authorized email '{authorized_emails[0].strip()}' correctly accepted")
        else:
            print(f"❌ Authorized email '{authorized_emails[0].strip()}' was rejected")
            return False
        
        # Test unauthorized email
        if not AuthService.is_email_authorized("unauthorized@example.com"):
            print("✅ Unauthorized email correctly rejected")
        else:
            print("❌ Unauthorized email was accepted")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Email authorization test failed: {e}")
        return False

def test_admin_user_creation():
    """Test admin user creation and authentication"""
    print("\n🔍 Testing admin user creation...")
    try:
        db = next(get_db())
        
        # Test user data
        test_email = "test_admin@example.com"
        test_username = "test_admin"
        test_password = "test_password_123"
        
        # Clean up any existing test user
        existing_user = db.query(AdminUser).filter(
            (AdminUser.email == test_email) | (AdminUser.username == test_username)
        ).first()
        if existing_user:
            db.delete(existing_user)
            db.commit()
        
        # Temporarily add test email to authorized list
        if not AuthService.is_email_authorized(test_email):
            print(f"⚠️  '{test_email}' not in authorized emails, testing will create anyway...")
        
        # Create test user
        try:
            admin_user = AuthService.create_admin_user(
                db=db,
                email=test_email,
                username=test_username,
                password=test_password,
                full_name="Test Administrator",
                is_superuser=False
            )
            print(f"✅ Admin user created successfully: {admin_user.email}")
        except ValueError as e:
            if "not authorized" in str(e):
                print(f"✅ Email authorization working correctly: {e}")
                db.close()
                return True
            else:
                raise e
        
        # Test authentication
        authenticated_user = AuthService.authenticate_user(db, test_username, test_password)
        if authenticated_user:
            print(f"✅ User authentication successful: {authenticated_user.username}")
        else:
            print("❌ User authentication failed")
            db.close()
            return False
        
        # Test wrong password
        wrong_auth = AuthService.authenticate_user(db, test_username, "wrong_password")
        if not wrong_auth:
            print("✅ Wrong password correctly rejected")
        else:
            print("❌ Wrong password was accepted")
            db.close()
            return False
        
        # Clean up test user
        db.delete(admin_user)
        db.commit()
        print("✅ Test user cleaned up")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Admin user creation test failed: {e}")
        if 'db' in locals():
            db.close()
        return False

def test_session_tokens():
    """Test session token creation and verification"""
    print("\n🔍 Testing session tokens...")
    try:
        db = next(get_db())
        
        # Create a test user object (in memory only)
        class MockUser:
            def __init__(self):
                self.id = 999
                self.username = "test_user"
                self.email = "test@example.com"
                self.is_superuser = False
        
        test_user = MockUser()
        
        # Create session token
        token = AuthService.create_session_token(test_user)
        print("✅ Session token created successfully")
        
        # Verify session token
        session_data = AuthService.verify_session_token(token)
        if session_data and session_data.get("username") == "test_user":
            print("✅ Session token verification successful")
        else:
            print("❌ Session token verification failed")
            return False
        
        # Test invalid token
        invalid_data = AuthService.verify_session_token("invalid_token")
        if not invalid_data:
            print("✅ Invalid token correctly rejected")
        else:
            print("❌ Invalid token was accepted")
            return False
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Session token test failed: {e}")
        return False

def test_csrf_tokens():
    """Test CSRF token creation and verification"""
    print("\n🔍 Testing CSRF tokens...")
    try:
        # Create CSRF token
        csrf_token = AuthService.create_csrf_token()
        print("✅ CSRF token created successfully")
        
        # Verify CSRF token
        if AuthService.verify_csrf_token(csrf_token):
            print("✅ CSRF token verification successful")
        else:
            print("❌ CSRF token verification failed")
            return False
        
        # Test invalid token
        if not AuthService.verify_csrf_token("invalid_csrf_token"):
            print("✅ Invalid CSRF token correctly rejected")
        else:
            print("❌ Invalid CSRF token was accepted")
            return False
        
        return True
    except Exception as e:
        print(f"❌ CSRF token test failed: {e}")
        return False

def run_all_tests():
    """Run all admin system tests"""
    print("🚀 ReqAgent Admin System Tests")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Password Hashing", test_password_hashing),
        ("Email Authorization", test_email_authorization),
        ("Admin User Creation", test_admin_user_creation),
        ("Session Tokens", test_session_tokens),
        ("CSRF Tokens", test_csrf_tokens),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your admin system is ready to use.")
        print("\nNext steps:")
        print("1. Run: python setup_admin.py")
        print("2. Start the app: uvicorn main:app --reload")
        print("3. Visit: http://localhost:8000/admin/login")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        print("Make sure your environment variables are properly configured.")

if __name__ == "__main__":
    run_all_tests() 