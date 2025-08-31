import re
import logging
import bleach
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from urllib.parse import urlparse, urljoin
import html

logger = logging.getLogger(__name__)

class ContentSanitizer:
    """Comprehensive content sanitization service for ReqAgent"""
    
    def __init__(self):
        # HTML tag whitelist for WordPress publishing
        self.allowed_html_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
        ]
        
        # HTML attribute whitelist
        self.allowed_html_attrs = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'title'],
            '*': ['class', 'id']  # Allow class and id on any element
        }
        
        # Control character patterns to remove
        self.control_char_pattern = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
        
        # URL schemes to allow
        self.allowed_url_schemes = ['http', 'https', 'mailto']
        
        # Date patterns for normalization
        self.date_patterns = [
            # DD/MM/YYYY or MM/DD/YYYY
            re.compile(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})'),
            # Month name patterns
            re.compile(r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{2,4})', re.I),
            # ISO date
            re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
            # Full month names
            re.compile(r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{2,4})', re.I)
        ]
        
        # Amount patterns for normalization
        self.amount_patterns = [
            # Currency with numbers
            re.compile(r'[\$£€](\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'),
            # Numbers with currency words
            re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(dollars?|pounds?|euros?|usd|gbp|eur)', re.I),
            # Range patterns
            re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*-\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'),
            # Up to patterns
            re.compile(r'up\s+to\s+[\$£€]?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', re.I)
        ]
    
    def sanitize_string(self, text: Any, max_length: Optional[int] = None) -> str:
        """Sanitize a string by removing control characters and normalizing whitespace"""
        try:
            if text is None:
                return ""
            
            # Convert to string if needed
            text = str(text)
            
            # Remove control characters (except newlines and tabs)
            text = self.control_char_pattern.sub('', text)
            
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Strip leading/trailing whitespace
            text = text.strip()
            
            # Truncate if max length specified
            if max_length and len(text) > max_length:
                text = text[:max_length] + "... [truncated]"
                logger.warning(f"⚠️ String truncated to {max_length} characters")
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing string: {e}")
            return "[sanitization_error]"
    
    def sanitize_html(self, html_content: str, allow_html: bool = False) -> str:
        """Sanitize HTML content to prevent XSS attacks"""
        try:
            if not html_content:
                return ""
            
            # Convert to string if needed
            html_content = str(html_content)
            
            if not allow_html:
                # Strip all HTML tags and return plain text
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                return self.sanitize_string(clean_text)
            
            # Use bleach to sanitize HTML with whitelist
            clean_html = bleach.clean(
                html_content,
                tags=self.allowed_html_tags,
                attributes=self.allowed_html_attrs,
                strip=True
            )
            
            # Additional safety: escape any remaining potentially dangerous content
            clean_html = html.escape(clean_html)
            
            # Re-apply allowed tags (bleach will have stripped them)
            # This is a simplified approach - in production, consider using a more sophisticated HTML parser
            
            logger.debug(f"✅ HTML sanitized: {len(html_content)} -> {len(clean_html)} characters")
            return clean_html
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing HTML: {e}")
            # Return plain text version as fallback
            return self.sanitize_string(html_content, allow_html=False)
    
    def sanitize_url(self, url: str, base_url: Optional[str] = None) -> str:
        """Sanitize and validate URL"""
        try:
            if not url:
                return ""
            
            url = str(url).strip()
            
            # Parse URL
            parsed = urlparse(url)
            
            # Check if URL has a scheme
            if not parsed.scheme:
                if base_url:
                    # Make relative URL absolute
                    url = urljoin(base_url, url)
                    parsed = urlparse(url)
                else:
                    # Add https as default scheme
                    url = f"https://{url}"
                    parsed = urlparse(url)
            
            # Validate scheme
            if parsed.scheme.lower() not in self.allowed_url_schemes:
                logger.warning(f"⚠️ Disallowed URL scheme: {parsed.scheme}")
                return ""
            
            # Remove trailing slashes from path
            clean_path = parsed.path.rstrip('/')
            if not clean_path:
                clean_path = '/'
            
            # Reconstruct clean URL
            clean_url = f"{parsed.scheme}://{parsed.netloc}{clean_path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            if parsed.fragment:
                clean_url += f"#{parsed.fragment}"
            
            logger.debug(f"✅ URL sanitized: {url} -> {clean_url}")
            return clean_url
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing URL: {e}")
            return ""
    
    def normalize_date(self, date_text: str) -> str:
        """Normalize date strings to consistent format"""
        try:
            if not date_text:
                return "To be confirmed"
            
            date_text = str(date_text).strip().lower()
            
            # Check for common "unknown" or "TBC" patterns
            if any(pattern in date_text for pattern in ['unknown', 'tbc', 'tba', 'to be confirmed', 'to be announced']):
                return "To be confirmed"
            
            # Try to parse various date formats
            for pattern in self.date_patterns:
                match = pattern.search(date_text)
                if match:
                    try:
                        # Extract components and attempt to create a date
                        if len(match.groups()) == 3:
                            # This is a simplified date parsing - in production, use dateutil.parser
                            # For now, return the matched text as-is
                            return date_text
                    except:
                        continue
            
            # If no pattern matched, return as-is but sanitized
            return self.sanitize_string(date_text, max_length=100)
            
        except Exception as e:
            logger.error(f"❌ Error normalizing date: {e}")
            return "To be confirmed"
    
    def normalize_amount(self, amount_text: str) -> str:
        """Normalize amount strings to consistent format"""
        try:
            if not amount_text:
                return "To be confirmed"
            
            amount_text = str(amount_text).strip()
            
            # Check for common "unknown" patterns
            if any(pattern in amount_text.lower() for pattern in ['unknown', 'tbc', 'tba', 'to be confirmed', 'to be announced']):
                return "To be confirmed"
            
            # Try to extract and normalize amount patterns
            for pattern in self.amount_patterns:
                match = pattern.search(amount_text)
                if match:
                    try:
                        # Extract the matched amount
                        if match.groups():
                            # Return the matched amount as-is for now
                            # In production, this could be converted to a standard format
                            return amount_text
                    except:
                        continue
            
            # If no pattern matched, return as-is but sanitized
            return self.sanitize_string(amount_text, max_length=100)
            
        except Exception as e:
            logger.error(f"❌ Error normalizing amount: {e}")
            return "To be confirmed"
    
    def sanitize_list(self, items: Union[List, str], max_items: int = 10) -> List[str]:
        """Sanitize a list of items"""
        try:
            if not items:
                return []
            
            # Convert string to list if needed
            if isinstance(items, str):
                # Try to split by common delimiters
                if ',' in items:
                    items = [item.strip() for item in items.split(',')]
                elif ';' in items:
                    items = [item.strip() for item in items.split(';')]
                elif '\n' in items:
                    items = [item.strip() for item in items.split('\n')]
                else:
                    items = [items]
            
            # Ensure it's a list
            if not isinstance(items, list):
                items = [str(items)]
            
            # Sanitize each item
            sanitized_items = []
            for item in items:
                if item:
                    sanitized_item = self.sanitize_string(item, max_length=200)
                    if sanitized_item and sanitized_item not in sanitized_items:
                        sanitized_items.append(sanitized_item)
            
            # Limit number of items
            if len(sanitized_items) > max_items:
                sanitized_items = sanitized_items[:max_items]
                logger.warning(f"⚠️ List truncated to {max_items} items")
            
            return sanitized_items
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing list: {e}")
            return []
    
    def sanitize_funding_opportunity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a complete funding opportunity data structure"""
        try:
            sanitized_data = {}
            
            # Required fields with sanitization
            required_fields = {
                'title': lambda x: self.sanitize_string(x, max_length=500),
                'donor': lambda x: self.sanitize_string(x, max_length=200),
                'summary': lambda x: self.sanitize_string(x, max_length=2000),
                'amount': lambda x: self.normalize_amount(x),
                'deadline': lambda x: self.normalize_date(x),
                'location': lambda x: self.sanitize_list(x, max_items=5),
                'eligibility': lambda x: self.sanitize_list(x, max_items=10),
                'themes': lambda x: self.sanitize_list(x, max_items=8)
            }
            
            # Sanitize required fields
            for field, sanitizer in required_fields.items():
                value = data.get(field)
                sanitized_value = sanitizer(value) if value is not None else self._get_default_value(field)
                sanitized_data[field] = sanitized_value
                
                # Log if field was sanitized
                if value != sanitized_value:
                    logger.info(f"🔄 Field '{field}' sanitized: {str(value)[:50]}... -> {str(sanitized_value)[:50]}...")
            
            # Optional fields with sanitization
            optional_fields = {
                'duration': lambda x: self.sanitize_string(x, max_length=100),
                'how_to_apply': lambda x: self.sanitize_string(x, max_length=1000),
                'opportunity_url': lambda x: self.sanitize_url(x),
                'published_date': lambda x: self.normalize_date(x),
                'contact_info': lambda x: self.sanitize_string(x, max_length=500)
            }
            
            # Sanitize optional fields
            for field, sanitizer in optional_fields.items():
                value = data.get(field)
                if value is not None:
                    sanitized_value = sanitizer(value)
                    sanitized_data[field] = sanitized_value
                    
                    # Log if field was sanitized
                    if value != sanitized_value:
                        logger.info(f"🔄 Optional field '{field}' sanitized: {str(value)[:50]}... -> {str(sanitized_value)[:50]}...")
            
            # Add sanitization metadata
            sanitized_data['_sanitized_at'] = datetime.utcnow().isoformat()
            sanitized_data['_sanitization_version'] = '1.0'
            
            logger.info(f"✅ Funding opportunity data sanitized: {len(data)} fields processed")
            return sanitized_data
            
        except Exception as e:
            logger.error(f"❌ Error sanitizing funding opportunity: {e}")
            # Return minimal safe data
            return {
                'title': 'Funding Opportunity',
                'donor': 'Unknown',
                'summary': 'Details to be confirmed',
                'amount': 'To be confirmed',
                'deadline': 'To be confirmed',
                'location': ['To be confirmed'],
                'eligibility': ['To be confirmed'],
                'themes': ['To be confirmed'],
                '_sanitization_error': str(e),
                '_sanitized_at': datetime.utcnow().isoformat()
            }
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for required fields"""
        defaults = {
            'title': 'Funding Opportunity',
            'donor': 'Unknown',
            'summary': 'Details to be confirmed',
            'amount': 'To be confirmed',
            'deadline': 'To be confirmed',
            'location': ['To be confirmed'],
            'eligibility': ['To be confirmed'],
            'themes': ['To be confirmed']
        }
        return defaults.get(field, 'Unknown')
    
    def validate_sanitized_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that sanitized data meets requirements"""
        try:
            validation_result = {
                'is_valid': True,
                'missing_required': [],
                'low_quality_fields': [],
                'warnings': []
            }
            
            # Check required fields
            required_fields = ['title', 'donor', 'summary', 'amount', 'deadline', 'location', 'eligibility', 'themes']
            
            for field in required_fields:
                value = data.get(field)
                
                if not value:
                    validation_result['missing_required'].append(field)
                    validation_result['is_valid'] = False
                elif isinstance(value, str) and value.lower() in ['unknown', 'to be confirmed', 'details to be confirmed']:
                    validation_result['low_quality_fields'].append(field)
                elif isinstance(value, list) and len(value) == 0:
                    validation_result['missing_required'].append(field)
                    validation_result['is_valid'] = False
            
            # Check for potential issues
            if data.get('amount') == 'To be confirmed':
                validation_result['warnings'].append('Amount information is missing or unclear')
            
            if data.get('deadline') == 'To be confirmed':
                validation_result['warnings'].append('Deadline information is missing or unclear')
            
            # Log validation results
            if validation_result['missing_required']:
                logger.warning(f"⚠️ Missing required fields: {validation_result['missing_required']}")
            
            if validation_result['low_quality_fields']:
                logger.warning(f"⚠️ Low quality fields: {validation_result['low_quality_fields']}")
            
            if validation_result['warnings']:
                for warning in validation_result['warnings']:
                    logger.warning(f"⚠️ {warning}")
            
            if validation_result['is_valid']:
                logger.info("✅ Sanitized data validation passed")
            else:
                logger.warning("⚠️ Sanitized data validation failed")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"❌ Error validating sanitized data: {e}")
            return {
                'is_valid': False,
                'missing_required': ['validation_error'],
                'low_quality_fields': [],
                'warnings': [f'Validation error: {str(e)}']
            }

# Global sanitizer instance
content_sanitizer = ContentSanitizer()





