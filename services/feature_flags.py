"""
Feature flags service for controlling application features
"""
import os

def check_analytics_enabled(feature_type: str = None):
    """Check if analytics feature is enabled"""
    if os.getenv("ADMIN_ANALYTICS_ENABLED", "true").lower() != "true":
        raise Exception("Analytics feature is disabled")
    return True
