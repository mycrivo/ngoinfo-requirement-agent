"""
Migration utility for running Alembic migrations programmatically.
This is used during application startup to ensure the database schema is up to date.
"""

import os
import sys
import logging
from alembic import command
from alembic.config import Config
from pathlib import Path

logger = logging.getLogger(__name__)

def run_migrations():
    """
    Run Alembic migrations to upgrade the database to the latest version.
    
    Returns:
        bool: True if migrations succeeded, False otherwise
    """
    try:
        # Get the project root directory
        project_root = Path(__file__).parent.parent
        alembic_cfg = project_root / "alembic.ini"
        
        if not alembic_cfg.exists():
            logger.error(f"Alembic configuration file not found at {alembic_cfg}")
            return False
        
        # Create Alembic configuration
        config = Config(str(alembic_cfg))
        
        # Set the script location
        config.set_main_option("script_location", str(project_root / "migrations"))
        
        # Run the migration
        logger.info("Running database migrations...")
        command.upgrade(config, "head")
        logger.info("Database migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to run database migrations: {str(e)}")
        return False

def check_migration_status():
    """
    Check the current migration status without running migrations.
    
    Returns:
        dict: Migration status information
    """
    try:
        project_root = Path(__file__).parent.parent
        alembic_cfg = project_root / "alembic.ini"
        
        if not alembic_cfg.exists():
            return {"error": "Alembic configuration file not found"}
        
        config = Config(str(alembic_cfg))
        config.set_main_option("script_location", str(project_root / "migrations"))
        
        # Get current revision
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
        import sys
        import os
        
        # Add project root to path for imports
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from db import get_url
        
        engine = create_engine(get_url())
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            
        # Get head revision
        script_dir = ScriptDirectory.from_config(config)
        head_rev = script_dir.get_current_head()
        
        return {
            "current_revision": current_rev,
            "head_revision": head_rev,
            "is_up_to_date": current_rev == head_rev
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Allow running migrations from command line
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status = check_migration_status()
        print(f"Migration status: {status}")
    else:
        success = run_migrations()
        sys.exit(0 if success else 1)
