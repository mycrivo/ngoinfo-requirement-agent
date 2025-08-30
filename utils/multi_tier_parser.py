"""
Multi-tier funding opportunity parser utilities.
This module provides functions to detect funding tiers, parse application windows,
extract delivery periods, and build OpportunityVariant objects from HTML content.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, time
from bs4 import BeautifulSoup, Tag
from schemas import (
    OpportunityVariant, 
    ApplicationWindow, 
    ApplicationRound, 
    DeliveryPeriod
)


class MultiTierParser:
    """Parser for multi-tier funding opportunities"""
    
    # Money patterns for tier detection
    MONEY_PATTERNS = [
        r'up to\s*[£$€]?\s*([\d,]+(?:\.\d{2})?)',  # "up to £5,000"
        r'over\s*[£$€]?\s*([\d,]+(?:\.\d{2})?)',   # "over £5,000"
        r'[£$€]\s*([\d,]+(?:\.\d{2})?)',            # "£5,000"
        r'([\d,]+(?:\.\d{2})?)\s*[£$€]',            # "5,000 £"
        r'([\d,]+(?:\.\d{2})?)\s*(?:pounds?|euros?|dollars?)',  # "5,000 pounds"
    ]
    
    # Tier indicator phrases
    TIER_PHRASES = [
        'small grants', 'large grants', 'micro grants', 'major grants',
        'tier 1', 'tier 2', 'level 1', 'level 2', 'category a', 'category b',
        'round 1', 'round 2', 'phase 1', 'phase 2'
    ]
    
    # Date patterns for UK format
    DATE_PATTERNS = [
        # "1st September 2024" or "1 September 2024"
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        # "22 Sep 2025" or "22 Sep 25"
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})',
        # "2024-09-01" or "01/09/2024"
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{1,2})/(\d{1,2})/(\d{4})',
    ]
    
    # Time patterns
    TIME_PATTERNS = [
        r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)',  # "5:00 PM"
        r'(\d{1,2})\s*(AM|PM|am|pm)',          # "5 PM"
        r'midday|noon',                         # "midday" or "noon"
        r'midnight',                            # "midnight"
    ]
    
    # Month names for parsing
    MONTHS = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    def __init__(self):
        self.money_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.MONEY_PATTERNS]
        self.date_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.DATE_PATTERNS]
        self.time_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.TIME_PATTERNS]
    
    def detect_tiers(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Detect funding tiers in the HTML content.
        
        Args:
            soup: BeautifulSoup object of the HTML content
            
        Returns:
            List of tier information dictionaries
        """
        tiers = []
        
        # Look for h2/h3 sections that might contain tier information
        for heading in soup.find_all(['h2', 'h3']):
            heading_text = heading.get_text().strip()
            
            # Check if heading contains tier indicators
            if self._is_tier_heading(heading_text):
                tier_info = self._extract_tier_from_section(heading, heading_text)
                if tier_info:
                    tiers.append(tier_info)
        
        # If no tiers found, create a single default tier
        if not tiers:
            tiers.append(self._create_default_tier(soup))
        
        return tiers
    
    def _is_tier_heading(self, text: str) -> bool:
        """Check if a heading text indicates a funding tier"""
        text_lower = text.lower()
        
        # Check for money patterns
        for regex in self.money_regexes:
            if regex.search(text):
                return True
        
        # Check for tier phrases
        for phrase in self.TIER_PHRASES:
            if phrase in text_lower:
                return True
        
        return False
    
    def _extract_tier_from_section(self, heading: Tag, heading_text: str) -> Optional[Dict[str, Any]]:
        """Extract tier information from a section starting with a heading"""
        tier_info = {
            'title': heading_text,
            'grant_min': None,
            'grant_max': None,
            'currency': 'GBP',  # Default to GBP for UK councils
            'application_window': None,
            'application_rounds': [],
            'delivery_period': None,
            'application_link': None,
            'notes': ''
        }
        
        # Extract grant amounts from heading first
        amounts = self._extract_grant_amounts(heading_text)
        
        # Look for content in the section
        section_content = self._get_section_content(heading)
        
        # If no amounts found in heading, try to extract from content
        if not amounts:
            amounts = self._extract_grant_amounts(section_content)
        
        if amounts:
            tier_info['grant_min'] = amounts.get('min')
            tier_info['grant_max'] = amounts.get('max')
        
        # Extract application window
        tier_info['application_window'] = self._extract_application_window(section_content)
        
        # Extract application rounds
        tier_info['application_rounds'] = self._extract_application_rounds(section_content)
        
        # Extract delivery period
        tier_info['delivery_period'] = self._extract_delivery_period(section_content)
        
        # Extract application link
        tier_info['application_link'] = self._extract_application_link(section_content)
        
        # Extract additional notes
        tier_info['notes'] = self._extract_notes(section_content)
        
        return tier_info
    
    def _extract_grant_amounts(self, text: str) -> Optional[Dict[str, float]]:
        """Extract grant amounts from text"""
        amounts = {}
        
        for regex in self.money_regexes:
            matches = regex.findall(text)
            if matches:
                # Convert to float, removing commas
                amount = float(matches[0].replace(',', ''))
                
                if 'up to' in text.lower():
                    amounts['max'] = amount
                elif 'over' in text.lower():
                    amounts['min'] = amount
                elif 'from' in text.lower() and 'to' in text.lower():
                    # Handle ranges like "from £5,000 to £25,000"
                    range_match = re.search(r'from\s*[£$€]?\s*([\d,]+(?:\.\d{2})?)\s*to\s*[£$€]?\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
                    if range_match:
                        amounts['min'] = float(range_match.group(1).replace(',', ''))
                        amounts['max'] = float(range_match.group(2).replace(',', ''))
                else:
                    # Single amount
                    amounts['max'] = amount
        
        return amounts if amounts else None
    
    def _get_section_content(self, heading: Tag) -> str:
        """Get the content of a section starting with a heading"""
        content_parts = []
        
        # Get the heading text
        content_parts.append(heading.get_text().strip())
        
        # Get following siblings until next heading
        current = heading.next_sibling
        max_iterations = 100  # Safety limit
        iteration = 0
        
        while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and iteration < max_iterations:
            if hasattr(current, 'get_text'):
                text = current.get_text().strip()
                if text:
                    content_parts.append(text)
            current = current.next_sibling
            iteration += 1
        
        if iteration >= max_iterations:
            print(f"⚠️ Warning: Section content extraction hit max iterations for heading: {heading.get_text()}")
        
        return ' '.join(content_parts)
    
    def _extract_application_window(self, content: str) -> Optional[ApplicationWindow]:
        """Extract application window from content"""
        # Look for application window patterns
        open_patterns = [
            r'open\s+from\s+(.+?)(?:\s+and\s+close|\s+until|\s+to)',
            r'applications?\s+open\s+(.+?)(?:\s+and\s+close|\s+until|\s+to)',
        ]
        
        close_patterns = [
            r'close\s+on\s+(.+?)(?:\s+at|\s+by|\s+until)',
            r'closes?\s+(.+?)(?:\s+at|\s+by|\s+until)',
            r'deadline\s+(.+?)(?:\s+at|\s+by|\s+until)',
        ]
        
        open_date = None
        close_date = None
        timezone = None
        
        # Extract open date
        for pattern in open_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                open_date = self._parse_date(match.group(1))
                break
        
        # Extract close date
        for pattern in close_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                close_date = self._parse_date(match.group(1))
                break
        
        # Extract time if present
        time_match = re.search(r'at\s+(.+?)(?:\s+([A-Z]{3,4})|$)', content, re.IGNORECASE)
        if time_match:
            time_str = time_match.group(1).strip()
            timezone_str = time_match.group(2) if time_match.group(2) else None
            
            # Parse time
            parsed_time = self._parse_time(time_str)
            if parsed_time and close_date:
                # Combine date and time
                close_date = datetime.combine(close_date, parsed_time)
            
            if timezone_str:
                timezone = timezone_str
        
        if open_date or close_date:
            return ApplicationWindow(
                open_date=open_date,
                close_date=close_date,
                timezone=timezone
            )
        
        return None
    
    def _extract_application_rounds(self, content: str) -> List[ApplicationRound]:
        """Extract application rounds from content"""
        rounds = []
        
        # Look for round patterns
        round_patterns = [
            r'round\s+(\d+):\s*(.+?)(?=round|\s*$)',  # "Round 1: Opens in Nov, closes in Jan"
            r'phase\s+(\d+):\s*(.+?)(?=phase|\s*$)',  # "Phase 1: Opens in Nov, closes in Jan"
        ]
        
        for pattern in round_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                round_num = match.group(1)
                round_content = match.group(2)
                
                # Extract month and year information
                month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', round_content, re.IGNORECASE)
                year_match = re.search(r'(\d{4})', round_content)
                
                if month_match:
                    month = month_match.group(1)
                    year = int(year_match.group(1)) if year_match else None
                    
                    rounds.append(ApplicationRound(
                        round_name=f"Round {round_num}",
                        apply_open_month=month,
                        apply_open_year_estimate=year,
                        apply_close_date=None  # Will be filled if specific date found
                    ))
        
        return rounds
    
    def _extract_delivery_period(self, content: str) -> Optional[DeliveryPeriod]:
        """Extract delivery period from content"""
        # Look for delivery period patterns
        delivery_patterns = [
            r'between\s+(.+?)\s+and\s+(.+?)(?:\s+$|\.)',
            r'from\s+(.+?)\s+to\s+(.+?)(?:\s+$|\.)',
            r'must\s+be\s+completed\s+between\s+(.+?)\s+and\s+(.+?)(?:\s+$|\.)',
            r'completion\s+by\s+(.+?)(?:\s+$|\.)',
        ]
        
        for pattern in delivery_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                start_date = self._parse_date(match.group(1))
                end_date = self._parse_date(match.group(2)) if match.group(2) else None
                
                if start_date or end_date:
                    return DeliveryPeriod(
                        start_date=start_date,
                        end_date=end_date
                    )
        
        return None
    
    def _extract_application_link(self, content: str) -> Optional[str]:
        """Extract application link from content"""
        # Look for apply links in the section
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find links with apply-related text
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().lower()
            href = link['href']
            
            if any(word in link_text for word in ['apply', 'application', 'form', 'submit']):
                # Prefer external application portals
                if 'apply.' in href or 'portal.' in href or 'external.' in href:
                    return href
                elif href.startswith('http'):
                    return href
        
        return None
    
    def _extract_notes(self, content: str) -> str:
        """Extract additional notes from content"""
        # Remove HTML tags and clean up
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        date_str = date_str.strip()
        
        # Try different date patterns
        for regex in self.date_regexes:
            match = regex.search(date_str)
            if match:
                if len(match.groups()) == 3:
                    if len(match.group(3)) == 4:  # Full year
                        if match.group(2).isdigit():  # ISO format
                            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                        else:  # Month name format
                            month = self.MONTHS.get(match.group(2).lower())
                            if month:
                                return date(int(match.group(3)), month, int(match.group(1)))
                    else:  # Short year
                        year = int(match.group(3))
                        if year < 50:  # Assume 20xx
                            year += 2000
                        else:  # Assume 19xx
                            year += 1900
                        month = self.MONTHS.get(match.group(2).lower())
                        if month:
                            return date(year, month, int(match.group(1)))
        
        return None
    
    def _parse_time(self, time_str: str) -> Optional[datetime.time]:
        """Parse time string to time object"""
        time_str = time_str.strip().lower()
        
        # Handle special cases
        if time_str in ['midday', 'noon']:
            return time(12, 0)
        elif time_str == 'midnight':
            return time(0, 0)
        
        # Parse standard time formats
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(AM|PM|am|pm)?', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            
            if ampm and ampm.upper() == 'PM' and hour != 12:
                hour += 12
            elif ampm and ampm.upper() == 'AM' and hour == 12:
                hour = 0
            
            return time(hour, minute)
        
        return None
    
    def _create_default_tier(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Create a default tier when no tiers are detected"""
        return {
            'title': 'Main Grant',
            'grant_min': None,
            'grant_max': None,
            'currency': 'GBP',
            'application_window': None,
            'application_rounds': [],
            'delivery_period': None,
            'application_link': None,
            'notes': 'Default tier created from main content'
        }
    
    def build_variants(self, soup: BeautifulSoup) -> List[OpportunityVariant]:
        """
        Build OpportunityVariant objects from detected tiers.
        
        Args:
            soup: BeautifulSoup object of the HTML content
            
        Returns:
            List of OpportunityVariant objects
        """
        tiers = self.detect_tiers(soup)
        variants = []
        
        for i, tier in enumerate(tiers):
            variant = OpportunityVariant(
                variant_title=tier['title'],
                grant_min=tier['grant_min'],
                grant_max=tier['grant_max'],
                currency=tier['currency'],
                funding_type=None,  # Could be extracted in future
                application_window=tier['application_window'],
                application_rounds=tier['application_rounds'],
                delivery_period=tier['delivery_period'],
                application_link=tier['application_link'],
                notes=tier['notes'],
                is_primary=(i == 0)  # First tier is primary by default
            )
            variants.append(variant)
        
        return variants


def parse_multi_tier_opportunity(html_content: str, url: str) -> List[OpportunityVariant]:
    """
    Parse multi-tier funding opportunity from HTML content.
    
    Args:
        html_content: Raw HTML content
        url: Source URL for context
        
    Returns:
        List of OpportunityVariant objects
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    parser = MultiTierParser()
    return parser.build_variants(soup)
