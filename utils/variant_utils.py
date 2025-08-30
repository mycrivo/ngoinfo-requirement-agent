"""
Utility functions for handling opportunity variants and primary variant selection.
This module provides functions to select the primary variant from a list of variants
and map its fields to the top-level opportunity fields for backward compatibility.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from schemas import OpportunityVariant


def select_primary_variant(variants: List[OpportunityVariant]) -> Optional[OpportunityVariant]:
    """
    Select the primary variant from a list of variants using deterministic rules.
    
    Rules (in order of priority):
    1. If any variant has is_primary=True, pick it
    2. Else pick the one with a specific application_window.apply_close_date
    3. Else pick the one with the higher grant_max (if comparable)
    4. Else pick the first variant
    
    Args:
        variants: List of opportunity variants
        
    Returns:
        The selected primary variant, or None if variants list is empty
    """
    if not variants:
        return None
    
    # Rule 1: Check for explicitly marked primary variant
    for variant in variants:
        if variant.is_primary:
            return variant
    
    # Rule 2: Check for variant with specific close date
    variants_with_close_date = []
    for variant in variants:
        if (variant.application_window and 
            variant.application_window.close_date):
            variants_with_close_date.append(variant)
    
    if variants_with_close_date:
        # If multiple have close dates, pick the one with earliest close date
        return min(variants_with_close_date, 
                  key=lambda v: v.application_window.close_date)
    
    # Rule 3: Compare grant_max values (if comparable)
    variants_with_grant_max = []
    for variant in variants:
        if variant.grant_max is not None:
            variants_with_grant_max.append(variant)
    
    if variants_with_grant_max:
        # Pick the one with highest grant_max
        return max(variants_with_grant_max, 
                  key=lambda v: v.grant_max or 0)
    
    # Rule 4: Fall back to first variant
    return variants[0]


def apply_primary_to_top_level(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply primary variant fields to top-level opportunity fields for backward compatibility.
    
    This function ensures that when variants exist, the top-level fields are derived
    from the primary variant, maintaining the existing API contract.
    
    Args:
        opportunity: Dictionary containing opportunity data with variants
        
    Returns:
        Updated opportunity dictionary with top-level fields mapped from primary variant
    """
    if not opportunity.get('variants'):
        return opportunity
    
    variants = opportunity['variants']
    primary_variant = select_primary_variant(variants)
    
    if not primary_variant:
        return opportunity
    
    # Map primary variant fields to top-level fields
    updated_opportunity = opportunity.copy()
    
    # Map grant amounts and currency
    if primary_variant.grant_min is not None:
        updated_opportunity['grant_min'] = primary_variant.grant_min
    if primary_variant.grant_max is not None:
        updated_opportunity['grant_max'] = primary_variant.grant_max
    if primary_variant.currency:
        updated_opportunity['currency'] = primary_variant.currency
    
    # Map application link
    if primary_variant.application_link:
        updated_opportunity['application_link'] = primary_variant.application_link
    
    # Map deadline from application window
    if (primary_variant.application_window and 
        primary_variant.application_window.close_date):
        updated_opportunity['deadline'] = primary_variant.application_window.close_date
    else:
        # If no specific close date, leave deadline as None
        # This will render as "Varies, check official website" in blog
        updated_opportunity['deadline'] = None
    
    return updated_opportunity


def get_variant_summary(variants: List[OpportunityVariant]) -> Dict[str, Any]:
    """
    Generate a summary of variants for admin/QA display.
    
    Args:
        variants: List of opportunity variants
        
    Returns:
        Dictionary containing variant summary information
    """
    if not variants:
        return {"count": 0, "summary": "No variants"}
    
    summary = {
        "count": len(variants),
        "has_primary": any(v.is_primary for v in variants),
        "variants": []
    }
    
    for variant in variants:
        variant_summary = {
            "title": variant.variant_title,
            "is_primary": variant.is_primary,
            "grant_range": None,
            "application_window": None,
            "delivery_period": None,
            "application_link": variant.application_link
        }
        
        # Format grant range
        if variant.grant_min is not None or variant.grant_max is not None:
            if variant.grant_min == variant.grant_max:
                grant_range = f"{variant.grant_min}"
            elif variant.grant_min and variant.grant_max:
                grant_range = f"{variant.grant_min} - {variant.grant_max}"
            elif variant.grant_min:
                grant_range = f"Min: {variant.grant_min}"
            else:
                grant_range = f"Max: {variant.grant_max}"
            
            if variant.currency:
                grant_range += f" {variant.currency}"
            
            variant_summary["grant_range"] = grant_range
        
        # Format application window
        if variant.application_window:
            window_info = []
            if variant.application_window.open_date:
                window_info.append(f"Opens: {variant.application_window.open_date.strftime('%Y-%m-%d')}")
            if variant.application_window.close_date:
                window_info.append(f"Closes: {variant.application_window.close_date.strftime('%Y-%m-%d')}")
            if variant.application_window.timezone:
                window_info.append(f"TZ: {variant.application_window.timezone}")
            
            if window_info:
                variant_summary["application_window"] = " | ".join(window_info)
        
        # Format delivery period
        if variant.delivery_period:
            period_info = []
            if variant.delivery_period.start_date:
                period_info.append(f"Start: {variant.delivery_period.start_date.strftime('%Y-%m-%d')}")
            if variant.delivery_period.end_date:
                period_info.append(f"End: {variant.delivery_period.end_date.strftime('%Y-%m-%d')}")
            
            if period_info:
                variant_summary["delivery_period"] = " | ".join(period_info)
        
        summary["variants"].append(variant_summary)
    
    return summary
