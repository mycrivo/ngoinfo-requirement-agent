#!/usr/bin/env python3
"""
Generate bcrypt password hash for admin authentication

This script generates a bcrypt hash that should be set as the ADMIN_PASSWORD_HASH environment variable.
"""

import bcrypt
import getpass

def generate_password_hash():
    """Generate bcrypt hash for a password"""
    print("🔐 Admin Password Hash Generator")
    print("=" * 40)
    
    # Get password from user
    password = getpass.getpass("Enter admin password: ")
    if not password:
        print("❌ Password cannot be empty")
        return
    
    confirm_password = getpass.getpass("Confirm password: ")
    if password != confirm_password:
        print("❌ Passwords do not match")
        return
    
    # Generate bcrypt hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    hash_string = hashed.decode('utf-8')
    
    print("\n✅ Password hash generated successfully!")
    print(f"\nAdd this to your environment variables:")
    print(f"ADMIN_PASSWORD_HASH={hash_string}")
    
    print(f"\nFor Railway deployment, set:")
    print(f"ADMIN_EMAIL=mailps20@gmail.com")
    print(f"ADMIN_PASSWORD_HASH={hash_string}")
    
    print(f"\n🚀 After setting these environment variables, you can login with:")
    print(f"Email: mailps20@gmail.com")
    print(f"Password: [your chosen password]")

if __name__ == "__main__":
    generate_password_hash() 