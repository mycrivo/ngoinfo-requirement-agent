#!/usr/bin/env python3
"""
Database migration script to create the blog_posts table
Run this script once to add the new table to your existing database
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, BlogPost
from db import DATABASE_URL, engine

def create_blog_posts_table():
    """Create the blog_posts table in the database"""
    try:
        print(f"🔗 Using existing database connection...")
        print(f"🔧 Database URL: {DATABASE_URL[:30]}...") if DATABASE_URL else print("❌ No DATABASE_URL found")
        
        # Create the blog_posts table
        print("📝 Creating blog_posts table...")
        BlogPost.__table__.create(engine, checkfirst=True)
        
        print("✅ Successfully created blog_posts table!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating blog_posts table: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Blog Posts Table Migration")
    print("=" * 40)
    
    success = create_blog_posts_table()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("The blog_posts table has been added to your database.")
    else:
        print("\n💥 Migration failed!")
        print("Please check the error messages above and try again.")
    
    sys.exit(0 if success else 1) 