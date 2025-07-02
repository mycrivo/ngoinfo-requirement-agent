#!/usr/bin/env python3
"""
Setup script for creating initial admin users in ReqAgent

This script helps you create admin users for the secure authentication system.
Run this script to set up your first admin user or add additional users.

Usage:
    python setup_admin.py
"""

import os
import sys
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db, engine
from models import Base, AdminUser
from utils.auth import AuthService

load_dotenv()

def create_tables():
    """Create database tables if they don't exist"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False

def setup_admin_user():
    """Interactive setup for admin user"""
    print("\n🔐 ReqAgent Admin User Setup")
    print("=" * 40)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check if any admin users exist
        admin_count = db.query(AdminUser).count()
        
        if admin_count > 0:
            print(f"ℹ️  Found {admin_count} existing admin user(s)")
            choice = input("Do you want to create another admin user? (y/N): ").lower().strip()
            if choice not in ['y', 'yes']:
                print("Exiting setup.")
                return
        
        print("\nEnter details for the new admin user:")
        
        # Get user details
        email = input("Email address: ").strip()
        if not email:
            print("❌ Email is required")
            return
        
        username = input("Username: ").strip()
        if not username:
            print("❌ Username is required")
            return
        
        import getpass
        password = getpass.getpass("Password: ")
        if not password:
            print("❌ Password is required")
            return
        
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("❌ Passwords do not match")
            return
        
        full_name = input("Full name (optional): ").strip() or None
        
        is_superuser = input("Grant superuser privileges? (y/N): ").lower().strip() in ['y', 'yes']
        
        # Validate email authorization
        if not AuthService.is_email_authorized(email):
            print(f"\n⚠️  Warning: Email '{email}' is not in the authorized emails list")
            print("Current authorized emails:")
            authorized_emails = os.getenv("AUTHORIZED_EMAILS", "admin@example.com,qa@example.com").split(",")
            for auth_email in authorized_emails:
                print(f"  - {auth_email.strip()}")
            
            print(f"\nTo authorize this email, add it to the AUTHORIZED_EMAILS environment variable:")
            print(f"AUTHORIZED_EMAILS={','.join(authorized_emails + [email])}")
            
            choice = input("\nDo you want to proceed anyway? (y/N): ").lower().strip()
            if choice not in ['y', 'yes']:
                print("Setup cancelled.")
                return
        
        # Create the user
        try:
            admin_user = AuthService.create_admin_user(
                db=db,
                email=email,
                username=username,
                password=password,
                full_name=full_name,
                is_superuser=is_superuser
            )
            
            print(f"\n✅ Successfully created admin user!")
            print(f"   Email: {admin_user.email}")
            print(f"   Username: {admin_user.username}")
            print(f"   Full Name: {admin_user.full_name or 'Not provided'}")
            print(f"   Superuser: {'Yes' if admin_user.is_superuser else 'No'}")
            print(f"   Created: {admin_user.created_at}")
            
            print(f"\n🚀 You can now login at: http://localhost:8000/admin/login")
            
        except ValueError as e:
            print(f"❌ Error creating user: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            
    finally:
        db.close()

def list_admin_users():
    """List all existing admin users"""
    print("\n👥 Existing Admin Users")
    print("=" * 40)
    
    db = next(get_db())
    
    try:
        users = db.query(AdminUser).all()
        
        if not users:
            print("No admin users found.")
            return
        
        for user in users:
            print(f"\n📧 {user.email}")
            print(f"   Username: {user.username}")
            print(f"   Full Name: {user.full_name or 'Not provided'}")
            print(f"   Active: {'Yes' if user.is_active else 'No'}")
            print(f"   Superuser: {'Yes' if user.is_superuser else 'No'}")
            print(f"   Last Login: {user.last_login or 'Never'}")
            print(f"   Created: {user.created_at}")
            
    except Exception as e:
        print(f"❌ Error listing users: {e}")
    finally:
        db.close()

def main():
    """Main setup function"""
    print("🚀 ReqAgent Admin Setup")
    print("=" * 40)
    
    # Check database connection
    if not create_tables():
        print("❌ Cannot proceed without database connection")
        return
    
    while True:
        print("\nWhat would you like to do?")
        print("1. Create new admin user")
        print("2. List existing admin users")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            setup_admin_user()
        elif choice == "2":
            list_admin_users()
        elif choice == "3":
            print("Goodbye! 👋")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main() 