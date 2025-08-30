import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from pathlib import Path
import random
import time

logger = logging.getLogger(__name__)

class SiteProfile:
    """Configuration profile for a specific website domain"""
    
    def __init__(self, config: Dict[str, Any]):
        self.selectors = config.get("selectors", {})
        self.pagination = config.get("pagination", {})
        self.waits = config.get("waits", {})
        self.retry = config.get("retry", {})
        self.rate_limit = config.get("rate_limit", {})
        self.user_agents = config.get("user_agents", [])
    
    def get_selector(self, field: str) -> List[str]:
        """Get selectors for a specific field with fallback"""
        return self.selectors.get(field, [])
    
    def get_wait_time(self, wait_type: str) -> int:
        """Get wait time in milliseconds for a specific wait type"""
        return self.waits.get(wait_type, 2000)
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration"""
        return {
            "max_attempts": self.retry.get("max_attempts", 3),
            "backoff_multiplier": self.retry.get("backoff_multiplier", 2.0),
            "initial_delay": self.retry.get("initial_delay", 1000)
        }
    
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limiting configuration"""
        return {
            "requests_per_second": self.rate_limit.get("requests_per_second", 1.0),
            "delay_between_requests": self.rate_limit.get("delay_between_requests", 1000)
        }
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent from the pool"""
        if self.user_agents:
            return random.choice(self.user_agents)
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def should_paginate(self) -> bool:
        """Check if pagination is enabled for this site"""
        return self.pagination.get("enabled", False)
    
    def get_max_pages(self) -> int:
        """Get maximum number of pages to crawl"""
        return self.pagination.get("max_pages", 1)
    
    def get_next_button_selector(self) -> Optional[str]:
        """Get selector for next page button"""
        return self.pagination.get("next_button")

class SiteProfileRegistry:
    """Registry for managing site-specific crawling configurations"""
    
    def __init__(self):
        self.profiles: Dict[str, SiteProfile] = {}
        self.default_profile: Optional[SiteProfile] = None
        self.last_request_time: Dict[str, float] = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """Load site profiles from YAML configuration"""
        try:
            config_path = Path(__file__).parent.parent / "configs" / "sites.yml"
            
            if not config_path.exists():
                logger.warning(f"⚠️ Site profiles configuration not found at {config_path}")
                self._create_default_profile()
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Load default profile
            if "default" in config:
                self.default_profile = SiteProfile(config["default"])
                logger.info("✅ Default site profile loaded")
            
            # Load domain-specific profiles
            for domain, profile_config in config.items():
                if domain != "default":
                    self.profiles[domain] = SiteProfile(profile_config)
                    logger.info(f"✅ Site profile loaded for {domain}")
            
            logger.info(f"✅ Loaded {len(self.profiles)} site profiles")
            
        except Exception as e:
            logger.error(f"❌ Failed to load site profiles: {e}")
            self._create_default_profile()
    
    def _create_default_profile(self):
        """Create a default profile when configuration is missing"""
        default_config = {
            "selectors": {
                "title": ["h1", ".title", "[class*='title']", "title"],
                "content": ["main", ".content", "[class*='content']", "article", ".post"],
                "deadline": ["[class*='deadline']", "[class*='close']", "[class*='due']", "[class*='date']"],
                "amount": ["[class*='amount']", "[class*='budget']", "[class*='funding']", "[class*='grant']"],
                "eligibility": ["[class*='eligibility']", "[class*='criteria']", "[class*='requirements']"],
                "themes": ["[class*='themes']", "[class*='focus']", "[class*='priorities']", "[class*='sectors']"]
            },
            "pagination": {
                "enabled": False,
                "next_button": None,
                "max_pages": 1
            },
            "waits": {
                "page_load": 5000,
                "element_wait": 2000,
                "javascript": 3000
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
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        }
        
        self.default_profile = SiteProfile(default_config)
        logger.info("✅ Default site profile created")
    
    def get_profile(self, url: str) -> SiteProfile:
        """Get site profile for a specific URL"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Remove www. prefix for matching
            if domain.startswith("www."):
                domain = domain[4:]
            
            # Try to find exact domain match
            if domain in self.profiles:
                logger.debug(f"🎯 Using site profile for {domain}")
                return self.profiles[domain]
            
            # Try to find partial domain match (e.g., gov.uk for subdomain.gov.uk)
            for profile_domain in self.profiles.keys():
                if domain.endswith(profile_domain) or profile_domain.endswith(domain):
                    logger.debug(f"🎯 Using site profile for {profile_domain} (partial match for {domain})")
                    return self.profiles[profile_domain]
            
            # Fall back to default profile
            logger.debug(f"🎯 Using default site profile for {domain}")
            return self.default_profile
            
        except Exception as e:
            logger.error(f"❌ Error getting site profile for {url}: {e}")
            return self.default_profile
    
    def enforce_rate_limit(self, url: str):
        """Enforce rate limiting for a specific URL"""
        try:
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            
            profile = self.get_profile(url)
            rate_config = profile.get_rate_limit_config()
            
            current_time = time.time()
            last_request = self.last_request_time.get(domain, 0)
            
            # Calculate required delay
            min_interval = 1.0 / rate_config["requests_per_second"]
            time_since_last = current_time - last_request
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                logger.debug(f"⏱️ Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)
            
            # Update last request time
            self.last_request_time[domain] = time.time()
            
        except Exception as e:
            logger.error(f"❌ Error enforcing rate limit for {url}: {e}")
    
    def get_retry_delay(self, attempt: int, url: str) -> int:
        """Calculate retry delay for a specific attempt"""
        try:
            profile = self.get_profile(url)
            retry_config = profile.get_retry_config()
            
            if attempt >= retry_config["max_attempts"]:
                return 0
            
            delay = retry_config["initial_delay"] * (retry_config["backoff_multiplier"] ** attempt)
            
            # Cap maximum delay at 30 seconds
            max_delay = 30000
            delay = min(delay, max_delay)
            
            logger.debug(f"🔄 Retry attempt {attempt + 1}: waiting {delay}ms")
            return delay
            
        except Exception as e:
            logger.error(f"❌ Error calculating retry delay: {e}")
            return 2000  # Default 2 second delay
    
    def validate_profile(self, profile: SiteProfile) -> bool:
        """Validate that a site profile has required configuration"""
        try:
            required_fields = ["selectors", "waits", "retry", "rate_limit"]
            
            for field in required_fields:
                if not hasattr(profile, field):
                    logger.error(f"❌ Site profile missing required field: {field}")
                    return False
            
            # Validate selectors
            if not profile.selectors:
                logger.error("❌ Site profile missing selectors configuration")
                return False
            
            # Validate waits
            if not profile.waits:
                logger.error("❌ Site profile missing waits configuration")
                return False
            
            # Validate retry
            retry_config = profile.get_retry_config()
            if retry_config["max_attempts"] < 1:
                logger.error("❌ Site profile has invalid retry configuration")
                return False
            
            # Validate rate limit
            rate_config = profile.get_rate_limit_config()
            if rate_config["requests_per_second"] <= 0:
                logger.error("❌ Site profile has invalid rate limit configuration")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating site profile: {e}")
            return False
    
    def reload_profiles(self):
        """Reload site profiles from configuration"""
        logger.info("🔄 Reloading site profiles...")
        self.profiles.clear()
        self.last_request_time.clear()
        self._load_profiles()
        logger.info("✅ Site profiles reloaded")
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """Get summary of loaded profiles"""
        try:
            summary = {
                "total_profiles": len(self.profiles),
                "default_profile_loaded": self.default_profile is not None,
                "domains": list(self.profiles.keys()),
                "last_reload": getattr(self, '_last_reload_time', 'Unknown')
            }
            
            if self.default_profile:
                summary["default_profile"] = {
                    "selectors": list(self.default_profile.selectors.keys()),
                    "retry_max_attempts": self.default_profile.get_retry_config()["max_attempts"],
                    "rate_limit_rps": self.default_profile.get_rate_limit_config()["requests_per_second"]
                }
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting profile summary: {e}")
            return {"error": str(e)}

# Global registry instance
site_registry = SiteProfileRegistry()


