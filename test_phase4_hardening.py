import unittest
import tempfile
import os
import json
import yaml
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the services we're testing
from services.site_profiles import SiteProfile, SiteProfileRegistry
from services.content_sanitizer import ContentSanitizer
from services.structured_logger import StructuredLogger, StructuredFormatter
from routes.admin_logs import _get_filtered_logs, _search_logs

class TestSiteProfiles(unittest.TestCase):
    """Test site profile registry functionality"""
    
    def setUp(self):
        self.test_config = {
            "default": {
                "selectors": {
                    "title": ["h1", ".title"],
                    "content": ["main", ".content"]
                },
                "pagination": {
                    "enabled": False,
                    "max_pages": 1
                },
                "waits": {
                    "page_load": 5000,
                    "element_wait": 2000
                },
                "retry": {
                    "max_attempts": 3,
                    "backoff_multiplier": 2.0,
                    "initial_delay": 1000
                },
                "rate_limit": {
                    "requests_per_second": 1.0,
                    "delay_between_requests": 1000
                },
                "user_agents": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ]
            },
            "gov.uk": {
                "selectors": {
                    "title": ["h1", ".gem-c-title__text"],
                    "content": ["main", ".govuk-main-wrapper"]
                },
                "pagination": {
                    "enabled": False,
                    "max_pages": 1
                },
                "waits": {
                    "page_load": 8000,
                    "element_wait": 3000
                },
                "retry": {
                    "max_attempts": 3,
                    "backoff_multiplier": 2.0,
                    "initial_delay": 2000
                },
                "rate_limit": {
                    "requests_per_second": 0.5,
                    "delay_between_requests": 2000
                }
            }
        }
        
        # Create temporary config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "sites.yml")
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_site_profile_creation(self):
        """Test SiteProfile creation and methods"""
        profile = SiteProfile(self.test_config["gov.uk"])
        
        self.assertEqual(profile.get_selector("title"), ["h1", ".gem-c-title__text"])
        self.assertEqual(profile.get_wait_time("page_load"), 8000)
        self.assertEqual(profile.get_retry_config()["max_attempts"], 3)
        self.assertEqual(profile.get_rate_limit_config()["requests_per_second"], 0.5)
        self.assertFalse(profile.should_paginate())
        self.assertEqual(profile.get_max_pages(), 1)
    
    def test_site_profile_registry_loading(self):
        """Test SiteProfileRegistry loading and profile retrieval"""
        with patch('services.site_profiles.CONFIG_PATH', self.config_path):
            registry = SiteProfileRegistry()
            
            # Test getting specific profile
            gov_profile = registry.get_profile("https://www.gov.uk/funding")
            self.assertEqual(gov_profile.get_selector("title"), ["h1", ".gem-c-title__text"])
            
            # Test fallback to default
            unknown_profile = registry.get_profile("https://unknown.com")
            self.assertEqual(unknown_profile.get_selector("title"), ["h1", ".title"])
    
    def test_rate_limit_enforcement(self):
        """Test rate limiting functionality"""
        with patch('services.site_profiles.CONFIG_PATH', self.config_path):
            registry = SiteProfileRegistry()
            
            # Test rate limiting
            start_time = datetime.now()
            registry.enforce_rate_limit("https://www.gov.uk/funding")
            end_time = datetime.now()
            
            # Should have some delay
            delay = (end_time - start_time).total_seconds()
            self.assertGreater(delay, 0)
    
    def test_retry_delay_calculation(self):
        """Test retry delay calculation with exponential backoff"""
        with patch('services.site_profiles.CONFIG_PATH', self.config_path):
            registry = SiteProfileRegistry()
            
            delay1 = registry.get_retry_delay(1, "https://www.gov.uk/funding")
            delay2 = registry.get_retry_delay(2, "https://www.gov.uk/funding")
            delay3 = registry.get_retry_delay(3, "https://www.gov.uk/funding")
            
            # Should increase exponentially
            self.assertLess(delay1, delay2)
            self.assertLess(delay2, delay3)
    
    def test_profile_validation(self):
        """Test profile validation"""
        with patch('services.site_profiles.CONFIG_PATH', self.config_path):
            registry = SiteProfileRegistry()
            
            # Test valid profile
            self.assertTrue(registry.validate_profile(registry.get_profile("https://www.gov.uk/funding")))
            
            # Test invalid profile (missing required fields)
            invalid_profile = SiteProfile({})
            self.assertFalse(registry.validate_profile(invalid_profile))

class TestContentSanitizer(unittest.TestCase):
    """Test content sanitization functionality"""
    
    def setUp(self):
        self.sanitizer = ContentSanitizer()
    
    def test_string_sanitization(self):
        """Test string sanitization"""
        # Test control character removal
        dirty_string = "Hello\x00World\x1f\n\r\t"
        clean_string = self.sanitizer.sanitize_string(dirty_string)
        self.assertEqual(clean_string, "Hello World")
        
        # Test whitespace normalization
        whitespace_string = "  Multiple    spaces\n\n\n"
        clean_whitespace = self.sanitizer.sanitize_string(whitespace_string)
        self.assertEqual(clean_whitespace, "Multiple spaces")
        
        # Test truncation
        long_string = "A" * 1000
        truncated = self.sanitizer.sanitize_string(long_string, max_length=100)
        self.assertEqual(len(truncated), 100)
    
    def test_html_sanitization(self):
        """Test HTML sanitization"""
        # Test allowed tags
        safe_html = "<p>Hello <strong>World</strong></p><ul><li>Item</li></ul>"
        sanitized = self.sanitizer.sanitize_html(safe_html, allow_html=True)
        self.assertIn("<p>", sanitized)
        self.assertIn("<strong>", sanitized)
        self.assertIn("<ul>", sanitized)
        
        # Test script removal
        unsafe_html = "<p>Hello</p><script>alert('xss')</script>"
        sanitized = self.sanitizer.sanitize_html(unsafe_html, allow_html=True)
        self.assertNotIn("<script>", sanitized)
        self.assertIn("<p>", sanitized)
        
        # Test complete HTML stripping
        stripped = self.sanitizer.sanitize_html(unsafe_html, allow_html=False)
        self.assertEqual(stripped, "Hello")
    
    def test_url_sanitization(self):
        """Test URL sanitization"""
        # Test HTTPS enforcement
        http_url = "http://example.com"
        https_url = self.sanitizer.sanitize_url(http_url)
        self.assertEqual(https_url, "https://example.com")
        
        # Test trailing slash removal
        slash_url = "https://example.com/"
        clean_url = self.sanitizer.sanitize_url(slash_url)
        self.assertEqual(clean_url, "https://example.com")
        
        # Test relative URL handling
        relative_url = "/path/to/resource"
        absolute_url = self.sanitizer.sanitize_url(relative_url, base_url="https://example.com")
        self.assertEqual(absolute_url, "https://example.com/path/to/resource")
    
    def test_date_normalization(self):
        """Test date normalization"""
        # Test various date formats
        test_cases = [
            ("2024-01-15", "2024-01-15"),
            ("15/01/2024", "15/01/2024"),
            ("January 15, 2024", "January 15, 2024"),
            ("", "To be confirmed"),
            ("Invalid date", "To be confirmed")
        ]
        
        for input_date, expected in test_cases:
            normalized = self.sanitizer.normalize_date(input_date)
            self.assertEqual(normalized, expected)
    
    def test_amount_normalization(self):
        """Test amount normalization"""
        # Test various amount formats
        test_cases = [
            ("$50,000", "$50,000"),
            ("£25,000 - £100,000", "£25,000 - £100,000"),
            ("50000", "$50,000"),
            ("", "To be confirmed"),
            ("TBD", "To be confirmed")
        ]
        
        for input_amount, expected in test_cases:
            normalized = self.sanitizer.normalize_amount(input_amount)
            self.assertEqual(normalized, expected)
    
    def test_funding_opportunity_sanitization(self):
        """Test complete funding opportunity sanitization"""
        dirty_opportunity = {
            "title": "Test\x00Opportunity",
            "description": "<p>Description</p><script>alert('xss')</script>",
            "url": "http://example.com/",
            "deadline": "2024-01-15",
            "amount": "50000",
            "themes": ["Theme 1", "Theme 2"],
            "eligibility": None,
            "contact": ""
        }
        
        sanitized = self.sanitizer.sanitize_funding_opportunity(dirty_opportunity)
        
        # Check sanitization
        self.assertEqual(sanitized["title"], "Test Opportunity")
        self.assertIn("<p>", sanitized["description"])
        self.assertNotIn("<script>", sanitized["description"])
        self.assertEqual(sanitized["url"], "https://example.com")
        self.assertEqual(sanitized["deadline"], "2024-01-15")
        self.assertEqual(sanitized["amount"], "$50,000")
        self.assertEqual(sanitized["themes"], ["Theme 1", "Theme 2"])
        self.assertEqual(sanitized["eligibility"], "To be confirmed")
        self.assertEqual(sanitized["contact"], "To be confirmed")
    
    def test_data_validation(self):
        """Test sanitized data validation"""
        sanitized_data = {
            "title": "Test Opportunity",
            "description": "Test description",
            "url": "https://example.com",
            "deadline": "2024-01-15",
            "amount": "$50,000",
            "themes": ["Theme 1"],
            "eligibility": "To be confirmed",
            "contact": "To be confirmed"
        }
        
        validated = self.sanitizer.validate_sanitized_data(sanitized_data)
        self.assertTrue(validated["is_valid"])
        self.assertEqual(validated["completeness_score"], 100.0)

class TestStructuredLogger(unittest.TestCase):
    """Test structured logging functionality"""
    
    def setUp(self):
        self.logger = StructuredLogger()
        self.logger.clear_request_context()
    
    def test_request_context_management(self):
        """Test request context setting and clearing"""
        self.logger.set_request_context("req_123", "opp_456")
        
        # Test context is set
        self.logger.info("Test message")
        
        # Test context clearing
        self.logger.clear_request_context()
        self.logger.info("Another message")
    
    def test_log_levels(self):
        """Test different log levels"""
        with self.assertLogs('reqagent', level='INFO') as captured:
            self.logger.info("Info message")
            self.logger.warning("Warning message")
            self.logger.error("Error message")
            
            self.assertEqual(len(captured.records), 3)
    
    def test_timed_operation(self):
        """Test timed operation context manager"""
        with self.logger.timed_operation("test_operation", test_param="value") as operation_id:
            # Simulate some work
            import time
            time.sleep(0.1)
        
        # Should have logged start and completion
        # Note: In a real test, you'd capture and verify the logs
    
    def test_specialized_logging_methods(self):
        """Test specialized logging methods"""
        with self.assertLogs('reqagent', level='INFO') as captured:
            self.logger.log_crawler_activity("https://example.com", "started")
            self.logger.log_parser_activity("opp_123", "completed", confidence=0.95)
            self.logger.log_publisher_activity("opp_123", "published", platform="wordpress")
            self.logger.log_security_event("rate_limit_exceeded", "Too many requests", "medium")
            self.logger.log_performance_metric("response_time", 150, "ms")
            self.logger.log_data_quality("opp_123", "title", 0.9)
            self.logger.log_user_action("admin", "login", "dashboard")
            self.logger.log_system_event("startup", "Application started")
            
            self.assertEqual(len(captured.records), 8)
    
    def test_log_summary_and_export(self):
        """Test log summary and export functionality"""
        summary = self.logger.get_log_summary(hours=24)
        self.assertIn("period_hours", summary)
        self.assertIn("total_logs", summary)
        
        export_json = self.logger.export_logs(level="INFO", hours=24, format="json")
        self.assertIsInstance(export_json, str)
        self.assertIn("export_info", export_json)
        
        export_csv = self.logger.export_logs(level="INFO", hours=24, format="csv")
        self.assertIsInstance(export_csv, str)
        self.assertIn("timestamp,level,action,status,message", export_csv)

class TestAdminLogs(unittest.TestCase):
    """Test admin logs functionality"""
    
    def test_filtered_logs(self):
        """Test log filtering functionality"""
        logs = _get_filtered_logs(
            level="INFO",
            action="crawler",
            hours=24,
            page=1,
            per_page=10
        )
        
        self.assertIsInstance(logs, list)
        if logs:
            self.assertIsInstance(logs[0], dict)
            self.assertIn("timestamp", logs[0])
            self.assertIn("level", logs[0])
    
    def test_log_search(self):
        """Test log search functionality"""
        search_results = _search_logs(
            query="crawler",
            level="INFO",
            action="crawler",
            hours=24,
            limit=10
        )
        
        self.assertIsInstance(search_results, list)
        if search_results:
            self.assertIsInstance(search_results[0], dict)
            self.assertIn("timestamp", search_results[0])

class TestIntegration(unittest.TestCase):
    """Test integration between components"""
    
    def test_sanitization_in_logging(self):
        """Test that sanitization works with logging"""
        sanitizer = ContentSanitizer()
        logger = StructuredLogger()
        
        # Test logging sanitized data
        dirty_data = "Test\x00Data<script>alert('xss')</script>"
        clean_data = sanitizer.sanitize_string(dirty_data)
        
        with self.assertLogs('reqagent', level='INFO') as captured:
            logger.info("Sanitized data", data=clean_data)
            
            self.assertEqual(len(captured.records), 1)
            self.assertNotIn("\x00", str(captured.records[0]))
            self.assertNotIn("<script>", str(captured.records[0]))
    
    def test_site_profiles_with_sanitization(self):
        """Test site profiles working with sanitization"""
        sanitizer = ContentSanitizer()
        
        # Create a test profile
        test_config = {
            "selectors": {
                "title": ["h1", ".title"],
                "content": ["main", ".content"]
            },
            "pagination": {"enabled": False, "max_pages": 1},
            "waits": {"page_load": 5000, "element_wait": 2000},
            "retry": {"max_attempts": 3, "backoff_multiplier": 2.0, "initial_delay": 1000},
            "rate_limit": {"requests_per_second": 1.0, "delay_between_requests": 1000},
            "user_agents": ["Test User Agent"]
        }
        
        profile = SiteProfile(test_config)
        
        # Test that profile data can be sanitized
        profile_data = {
            "url": "http://example.com/",
            "selectors": str(profile.get_selector("title")),
            "wait_time": str(profile.get_wait_time("page_load"))
        }
        
        sanitized = sanitizer.sanitize_funding_opportunity(profile_data)
        
        self.assertEqual(sanitized["url"], "https://example.com")
        self.assertIsInstance(sanitized["selectors"], str)
        self.assertIsInstance(sanitized["wait_time"], str)

if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_suite.addTest(unittest.makeSuite(TestSiteProfiles))
    test_suite.addTest(unittest.makeSuite(TestContentSanitizer))
    test_suite.addTest(unittest.makeSuite(TestStructuredLogger))
    test_suite.addTest(unittest.makeSuite(TestAdminLogs))
    test_suite.addTest(unittest.makeSuite(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Phase 4 Testing Complete")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"  ❌ {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"  ❌ {test}: {traceback}")
    
    if not result.failures and not result.errors:
        print(f"\n🎉 All tests passed! Phase 4 implementation is working correctly.")
    
    print(f"{'='*60}")





