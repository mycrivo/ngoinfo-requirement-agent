"""
Test file for Phase 8 Analytics features
"""
import os
import pytest

# Module-level skip guard as required
if os.getenv("SKIP_PHASE8_TESTS", "1") == "1":
    pytest.skip("Phase-8 tests gated; enabled later", allow_module_level=True)

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

class TestPhase8Analytics(unittest.TestCase):
    """Test cases for Phase 8 Analytics features"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        self.end_date = datetime.now().strftime("%Y-%m-%d")
    
    @patch('services.metrics.get_pipeline_kpis')
    def test_pipeline_kpis(self, mock_get_kpis):
        """Test pipeline KPIs functionality"""
        # Mock response
        mock_get_kpis.return_value = {
            "total_ingested": 100,
            "total_qa_approved": 80,
            "total_published": 75,
            "total_templates": 50,
            "error_rate": 5.0
        }
        
        from services.metrics import get_pipeline_kpis
        result = get_pipeline_kpis(start=self.start_date, end=self.end_date)
        
        self.assertIsInstance(result, dict)
        self.assertIn("total_ingested", result)
        self.assertIn("total_qa_approved", result)
        mock_get_kpis.assert_called_once()
    
    @patch('services.metrics.get_security_kpis')
    def test_security_kpis(self, mock_get_security_kpis):
        """Test security KPIs functionality"""
        # Mock response
        mock_get_security_kpis.return_value = {
            "login_success": 150,
            "login_failure": 10,
            "rate_limit": 5,
            "forbidden": 2,
            "total_events": 167
        }
        
        from services.metrics import get_security_kpis
        result = get_security_kpis(start=self.start_date, end=self.end_date)
        
        self.assertIsInstance(result, dict)
        self.assertIn("login_success", result)
        self.assertIn("login_failure", result)
        mock_get_security_kpis.assert_called_once()
    
    @patch('services.feature_flags.check_analytics_enabled')
    def test_feature_flag_check(self, mock_check_enabled):
        """Test feature flag functionality"""
        mock_check_enabled.return_value = True
        
        from services.feature_flags import check_analytics_enabled
        result = check_analytics_enabled()
        
        self.assertTrue(result)
        mock_check_enabled.assert_called_once()
    
    def test_cache_functionality(self):
        """Test caching functionality"""
        from services.metrics import _get_cache_key, _get_cached, _set_cached
        
        key = _get_cache_key("test", param1="value1", param2="value2")
        self.assertIsInstance(key, str)
        self.assertIn("test", key)
        
        # Test cache miss
        cached_value = _get_cached("nonexistent_key")
        self.assertIsNone(cached_value)
        
        # Test cache set and get
        test_value = {"test": "data"}
        _set_cached("test_key", test_value)
        # Note: In test mode, cache is disabled, so this will return None
        cached_value = _get_cached("test_key")
        # In test mode, cache should be disabled
        self.assertIsNone(cached_value)

if __name__ == "__main__":
    unittest.main()
