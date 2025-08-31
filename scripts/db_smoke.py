#!/usr/bin/env python3
"""
Database connectivity smoke test
Tests database connection without modifying schema
"""
import os
import sys
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_config() -> Dict[str, str]:
    """Get database configuration from environment"""
    
    # Primary: DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return {"DATABASE_URL": database_url}
    
    # Fallback: individual components
    return {
        "PGHOST": os.getenv("PGHOST", "localhost"),
        "PGPORT": os.getenv("PGPORT", "5432"), 
        "PGDATABASE": os.getenv("PGDATABASE", "requirement_agent"),
        "PGUSER": os.getenv("PGUSER", "username"),
        "PGPASSWORD": os.getenv("PGPASSWORD", "")
    }

def test_sqlalchemy_connection() -> Dict[str, Any]:
    """Test SQLAlchemy connection"""
    result = {
        "method": "sqlalchemy",
        "success": False,
        "error": None,
        "driver_version": None,
        "server_version": None,
        "connection_info": {}
    }
    
    try:
        # Set test mode to avoid heavy init
        os.environ["TEST_MODE"] = "true"
        
        # Import database components
        from db import engine, DATABASE_URL
        from sqlalchemy import text
        
        result["connection_info"]["url_configured"] = DATABASE_URL is not None
        
        if DATABASE_URL:
            # Mask the URL for security
            if '@' in DATABASE_URL:
                masked_url = DATABASE_URL.split('@')[0].split('//')[1]
                masked_url = DATABASE_URL.replace(masked_url, '***:***')
            else:
                masked_url = DATABASE_URL[:20] + "..."
            result["connection_info"]["masked_url"] = masked_url
        
        # Test connection
        with engine.connect() as conn:
            # Simple query
            result_proxy = conn.execute(text("SELECT 1 as test"))
            row = result_proxy.fetchone()
            
            if row and row[0] == 1:
                result["success"] = True
            
            # Get database version
            try:
                version_result = conn.execute(text("SELECT version()"))
                version_row = version_result.fetchone()
                if version_row:
                    result["server_version"] = version_row[0][:50]  # Truncate for safety
            except Exception:
                pass
        
        # Get SQLAlchemy version
        try:
            import sqlalchemy
            result["driver_version"] = f"SQLAlchemy {sqlalchemy.__version__}"
        except Exception:
            pass
            
    except Exception as e:
        result["error"] = str(e)
    finally:
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]
    
    return result

def test_psycopg2_direct() -> Dict[str, Any]:
    """Test direct psycopg2 connection"""
    result = {
        "method": "psycopg2",
        "success": False,
        "error": None,
        "driver_version": None,
        "server_version": None,
        "connection_info": {}
    }
    
    try:
        import psycopg2
        result["driver_version"] = f"psycopg2 {psycopg2.__version__}"
        
        # Get connection parameters
        db_config = get_db_config()
        
        if "DATABASE_URL" in db_config:
            # Use DATABASE_URL
            conn = psycopg2.connect(db_config["DATABASE_URL"])
            result["connection_info"]["connection_method"] = "DATABASE_URL"
        else:
            # Use individual parameters
            conn = psycopg2.connect(
                host=db_config["PGHOST"],
                port=db_config["PGPORT"],
                database=db_config["PGDATABASE"],
                user=db_config["PGUSER"],
                password=db_config["PGPASSWORD"]
            )
            result["connection_info"]["connection_method"] = "individual_params"
            result["connection_info"]["host"] = db_config["PGHOST"]
            result["connection_info"]["port"] = db_config["PGPORT"]
            result["connection_info"]["database"] = db_config["PGDATABASE"]
        
        # Test query
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
            
            if row and row[0] == 1:
                result["success"] = True
            
            # Get server version
            try:
                cur.execute("SELECT version()")
                version_row = cur.fetchone()
                if version_row:
                    result["server_version"] = version_row[0][:50]
            except Exception:
                pass
        
        conn.close()
        
    except ImportError:
        result["error"] = "psycopg2 not available"
    except Exception as e:
        result["error"] = str(e)
    
    return result

def check_database_connectivity() -> Dict[str, Any]:
    """Main database connectivity check"""
    
    db_config = get_db_config()
    
    # Test both methods
    sqlalchemy_result = test_sqlalchemy_connection()
    psycopg2_result = test_psycopg2_direct()
    
    # Overall assessment
    any_success = sqlalchemy_result["success"] or psycopg2_result["success"]
    
    return {
        "db_config": {k: ("***" if "password" in k.lower() else v) for k, v in db_config.items()},
        "sqlalchemy_test": sqlalchemy_result,
        "psycopg2_test": psycopg2_result,
        "overall_success": any_success,
        "recommended_action": get_recommended_action(sqlalchemy_result, psycopg2_result)
    }

def get_recommended_action(sqlalchemy_result: Dict[str, Any], psycopg2_result: Dict[str, Any]) -> str:
    """Get recommended action based on test results"""
    
    if sqlalchemy_result["success"] and psycopg2_result["success"]:
        return "✅ Database connectivity is working properly"
    
    if sqlalchemy_result["success"] and not psycopg2_result["success"]:
        return "⚠️ SQLAlchemy works but direct psycopg2 fails - check connection parameters"
    
    if not sqlalchemy_result["success"] and psycopg2_result["success"]:
        return "⚠️ Direct psycopg2 works but SQLAlchemy fails - check db.py configuration"
    
    # Both failed
    sqlalchemy_error = sqlalchemy_result.get("error", "")
    psycopg2_error = psycopg2_result.get("error", "")
    
    if "not available" in psycopg2_error:
        return f"❌ Database connection failed: {sqlalchemy_error}"
    
    if "could not connect" in sqlalchemy_error.lower() or "connection refused" in sqlalchemy_error.lower():
        return "❌ Database server is not reachable - check host, port, and network"
    
    if "authentication failed" in sqlalchemy_error.lower() or "password" in sqlalchemy_error.lower():
        return "❌ Database authentication failed - check username and password"
    
    if "database" in sqlalchemy_error.lower() and "does not exist" in sqlalchemy_error.lower():
        return "❌ Database does not exist - create the database first"
    
    return f"❌ Database connection failed: {sqlalchemy_error}"

def generate_db_report(results: Dict[str, Any]) -> str:
    """Generate markdown report of database connectivity"""
    report = []
    
    report.append("## Database Connectivity Smoke Test\n")
    
    # Configuration
    report.append("### Configuration\n")
    for key, value in results["db_config"].items():
        report.append(f"- **{key}**: {value}")
    report.append("")
    
    # SQLAlchemy test
    sqlalchemy = results["sqlalchemy_test"]
    report.append("### SQLAlchemy Test\n")
    report.append("| Property | Value |")
    report.append("|----------|-------|")
    report.append(f"| Success | {'✅' if sqlalchemy['success'] else '❌'} |")
    report.append(f"| Driver Version | {sqlalchemy.get('driver_version', 'Unknown')} |")
    report.append(f"| Server Version | {sqlalchemy.get('server_version', 'Unknown')} |")
    
    if sqlalchemy.get("connection_info"):
        for key, value in sqlalchemy["connection_info"].items():
            report.append(f"| {key.replace('_', ' ').title()} | {value} |")
    
    if sqlalchemy.get("error"):
        report.append(f"| Error | {sqlalchemy['error']} |")
    
    report.append("")
    
    # psycopg2 test
    psycopg2 = results["psycopg2_test"]
    report.append("### Direct psycopg2 Test\n")
    report.append("| Property | Value |")
    report.append("|----------|-------|")
    report.append(f"| Success | {'✅' if psycopg2['success'] else '❌'} |")
    report.append(f"| Driver Version | {psycopg2.get('driver_version', 'Unknown')} |")
    report.append(f"| Server Version | {psycopg2.get('server_version', 'Unknown')} |")
    
    if psycopg2.get("connection_info"):
        for key, value in psycopg2["connection_info"].items():
            report.append(f"| {key.replace('_', ' ').title()} | {value} |")
    
    if psycopg2.get("error"):
        report.append(f"| Error | {psycopg2['error']} |")
    
    report.append("")
    
    # Overall result
    report.append("### Overall Result\n")
    report.append(f"**Status**: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
    report.append(f"**Recommendation**: {results['recommended_action']}\n")
    
    return '\n'.join(report)

if __name__ == "__main__":
    print("🔍 Testing database connectivity...")
    
    results = check_database_connectivity()
    
    print(f"\n🗄️ DATABASE CONNECTIVITY SMOKE TEST")
    print(f"===================================")
    
    # Configuration
    print(f"Configuration:")
    for key, value in results["db_config"].items():
        print(f"   {key}: {value}")
    
    # Results
    sqlalchemy = results["sqlalchemy_test"]
    psycopg2 = results["psycopg2_test"]
    
    print(f"\nSQLAlchemy Test: {'✅' if sqlalchemy['success'] else '❌'}")
    if sqlalchemy.get("error"):
        print(f"   Error: {sqlalchemy['error']}")
    if sqlalchemy.get("driver_version"):
        print(f"   Driver: {sqlalchemy['driver_version']}")
    
    print(f"\npsycopg2 Test: {'✅' if psycopg2['success'] else '❌'}")
    if psycopg2.get("error"):
        print(f"   Error: {psycopg2['error']}")
    if psycopg2.get("driver_version"):
        print(f"   Driver: {psycopg2['driver_version']}")
    
    print(f"\nOverall: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
    print(f"Recommendation: {results['recommended_action']}")
    
    # Generate report
    report = generate_db_report(results)
    print(f"\n📋 DETAILED REPORT")
    print(f"==================")
    print(report)

