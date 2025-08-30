"""
Analytics service for Phase 8: Admin Analytics & Ops Dashboard
Provides pipeline metrics and security event analytics with caching
"""
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from sqlalchemy.sql import text

from db import get_db
from models import (
    FundingOpportunity, Document, ProposalTemplate, 
    IngestionRun, SecurityEvent, Source, ParsedDataFeedback
)

def check_analytics_enabled():
    """Check if analytics feature is enabled"""
    if os.getenv("ADMIN_ANALYTICS_ENABLED", "true").lower() != "true":
        raise Exception("Analytics feature is disabled")

# Simple in-process cache with TTL
_cache = {}
_cache_ttl = 60  # 60 seconds

def _get_cache_key(prefix: str, **kwargs) -> str:
    """Generate cache key from prefix and kwargs"""
    sorted_items = sorted(kwargs.items())
    return f"{prefix}:{':'.join(f'{k}={v}' for k, v in sorted_items)}"

def _get_cached(key: str) -> Optional[Any]:
    """Get cached value if not expired"""
    if os.getenv("TEST_MODE", "false").lower() == "true":
        return None  # Disable cache in test mode
    
    if key in _cache:
        value, timestamp = _cache[key]
        if time.time() - timestamp < _cache_ttl:
            return value
        else:
            del _cache[key]
    return None

def _set_cached(key: str, value: Any) -> None:
    """Set cached value with timestamp"""
    if os.getenv("TEST_MODE", "false").lower() == "true":
        return  # Disable cache in test mode
    
    _cache[key] = (value, time.time())

def _get_date_range(start: Optional[str] = None, end: Optional[str] = None) -> tuple:
    """Parse date range parameters"""
    if not start:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")
    
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)  # Include end date
    
    return start_dt, end_dt

def get_pipeline_kpis(start: Optional[str] = None, end: Optional[str] = None, 
                      filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get pipeline KPIs for the specified date range"""
    cache_key = _get_cache_key("pipeline_kpis", start=start, end=end, filters=str(filters))
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Basic counts
        total_ingested = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        total_qa_approved = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.status == "approved",
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        total_published = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.status == "approved",
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        total_templates = db.query(ProposalTemplate).filter(
            and_(
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).count()
        
        # Error rate calculation
        total_errors = db.query(IngestionRun).filter(
            and_(
                IngestionRun.started_at >= start_dt,
                IngestionRun.started_at < end_dt
            )
        ).with_entities(
            func.sum(func.jsonb_array_length(IngestionRun.errors))
        ).scalar() or 0
        
        total_runs = db.query(IngestionRun).filter(
            and_(
                IngestionRun.started_at >= start_dt,
                IngestionRun.started_at < end_dt
            )
        ).count()
        
        error_rate = (total_errors / max(total_runs, 1)) * 100 if total_runs > 0 else 0
        
        result = {
            "total_ingested": total_ingested,
            "total_qa_approved": total_qa_approved,
            "total_published": total_published,
            "total_templates": total_templates,
            "error_rate": round(error_rate, 2),
            "total_errors": total_errors,
            "total_runs": total_runs,
            "period": {
                "start": start_dt.strftime("%Y-%m-%d"),
                "end": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            }
        }
        
        _set_cached(cache_key, result)
        return result

def get_pipeline_trends(start: Optional[str] = None, end: Optional[str] = None, 
                       interval: str = "daily", filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get pipeline trends over time"""
    cache_key = _get_cache_key("pipeline_trends", start=start, end=end, interval=interval, filters=str(filters))
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        if interval == "daily":
            date_format = "%Y-%m-%d"
            date_trunc = func.date_trunc('day', FundingOpportunity.created_at)
        else:  # weekly
            date_format = "%Y-W%U"
            date_trunc = func.date_trunc('week', FundingOpportunity.created_at)
        
        # Ingested trends
        ingested_trends = db.query(
            date_trunc.label('date'),
            func.count(FundingOpportunity.id).label('count')
        ).filter(
            and_(
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        # Published trends
        published_trends = db.query(
            date_trunc.label('date'),
            func.count(FundingOpportunity.id).label('count')
        ).filter(
            and_(
                FundingOpportunity.status == "approved",
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        # Template trends
        template_trends = db.query(
            date_trunc.label('date'),
            func.count(ProposalTemplate.id).label('count')
        ).filter(
            and_(
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        result = {
            "ingested": [{"date": t.date.strftime(date_format), "count": t.count} for t in ingested_trends],
            "published": [{"date": t.date.strftime(date_format), "count": t.count} for t in published_trends],
            "templates": [{"date": t.date.strftime(date_format), "count": t.count} for t in template_trends],
            "interval": interval
        }
        
        _set_cached(cache_key, result)
        return result

def get_source_breakdown(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get source/domain breakdown for pipeline analytics"""
    cache_key = _get_cache_key("source_breakdown", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Top providers by ingested
        top_providers = db.query(
            Source.provider,
            func.count(FundingOpportunity.id).label('count')
        ).join(
            IngestionRun, Source.id == IngestionRun.source_id
        ).join(
            FundingOpportunity, FundingOpportunity.created_at >= start_dt
        ).filter(
            and_(
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).group_by(Source.provider).order_by(desc('count')).limit(10).all()
        
        # Top domains by published
        top_domains = db.query(
            Source.domain,
            func.count(FundingOpportunity.id).label('count')
        ).join(
            IngestionRun, Source.id == IngestionRun.source_id
        ).join(
            FundingOpportunity, FundingOpportunity.created_at >= start_dt
        ).filter(
            and_(
                FundingOpportunity.status == "approved",
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).group_by(Source.domain).order_by(desc('count')).limit(10).all()
        
        result = {
            "top_providers": [{"provider": p.provider, "count": p.count} for p in top_providers],
            "top_domains": [{"domain": d.domain, "count": d.count} for d in top_domains if d.domain]
        }
        
        _set_cached(cache_key, result)
        return result

def get_qa_metrics(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get QA metrics for pipeline analytics"""
    cache_key = _get_cache_key("qa_metrics", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Average edits per record
        total_feedback = db.query(ParsedDataFeedback).filter(
            and_(
                ParsedDataFeedback.created_at >= start_dt,
                ParsedDataFeedback.created_at < end_dt
            )
        ).count()
        
        total_records = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        avg_edits = total_feedback / max(total_records, 1) if total_records > 0 else 0
        
        # Most corrected fields
        field_corrections = db.query(
            ParsedDataFeedback.field_name,
            func.count(ParsedDataFeedback.id).label('count')
        ).filter(
            and_(
                ParsedDataFeedback.created_at >= start_dt,
                ParsedDataFeedback.created_at < end_dt
            )
        ).group_by(ParsedDataFeedback.field_name).order_by(desc('count')).limit(5).all()
        
        # Template success ratio
        total_templates = db.query(ProposalTemplate).filter(
            and_(
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).count()
        
        successful_templates = db.query(ProposalTemplate).filter(
            and_(
                ProposalTemplate.status == "ready",
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).count()
        
        template_success_ratio = (successful_templates / max(total_templates, 1)) * 100 if total_templates > 0 else 0
        
        result = {
            "avg_edits_per_record": round(avg_edits, 2),
            "total_feedback": total_feedback,
            "total_records": total_records,
            "most_corrected_fields": [{"field": f.field_name, "count": f.count} for f in field_corrections],
            "template_success_ratio": round(template_success_ratio, 2),
            "total_templates": total_templates,
            "successful_templates": successful_templates
        }
        
        _set_cached(cache_key, result)
        return result

def get_security_kpis(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get security KPIs for the specified date range"""
    cache_key = _get_cache_key("security_kpis", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Count by event type
        event_counts = db.query(
            SecurityEvent.event_type,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.event_type).all()
        
        # Convert to dict
        event_counts_dict = {event.event_type: event.count for event in event_counts}
        
        result = {
            "login_successes": event_counts_dict.get("login_success", 0),
            "login_failures": event_counts_dict.get("login_failure", 0),
            "rate_limit_hits": event_counts_dict.get("rate_limit_exceeded", 0),
            "forbidden_events": event_counts_dict.get("forbidden_access", 0),
            "total_events": sum(event_counts_dict.values()),
            "period": {
                "start": start_dt.strftime("%Y-%m-%d"),
                "end": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            }
        }
        
        _set_cached(cache_key, result)
        return result

def get_security_trends(start: Optional[str] = None, end: Optional[str] = None, 
                        interval: str = "daily") -> Dict[str, Any]:
    """Get security trends over time"""
    cache_key = _get_cache_key("security_trends", start=start, end=end, interval=interval)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        if interval == "daily":
            date_format = "%Y-%m-%d"
            date_trunc = func.date_trunc('day', SecurityEvent.created_at)
        else:  # weekly
            date_format = "%Y-W%U"
            date_trunc = func.date_trunc('week', SecurityEvent.created_at)
        
        # Login trends (success vs failure)
        login_trends = db.query(
            date_trunc.label('date'),
            SecurityEvent.event_type,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.event_type.in_(["login_success", "login_failure"]),
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(date_trunc, SecurityEvent.event_type).order_by(date_trunc).all()
        
        # Group by date
        trends_by_date = {}
        for trend in login_trends:
            date_str = trend.date.strftime(date_format)
            if date_str not in trends_by_date:
                trends_by_date[date_str] = {"success": 0, "failure": 0}
            trends_by_date[date_str][trend.event_type.replace("login_", "")] = trend.count
        
        # Convert to lists for Chart.js
        dates = sorted(trends_by_date.keys())
        success_counts = [trends_by_date[date]["success"] for date in dates]
        failure_counts = [trends_by_date[date]["failure"] for date in dates]
        
        result = {
            "dates": dates,
            "success": success_counts,
            "failure": failure_counts,
            "interval": interval
        }
        
        _set_cached(cache_key, result)
        return result

def get_security_breakdown(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get security breakdown analytics"""
    cache_key = _get_cache_key("security_breakdown", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Top offenders by IP (hashed)
        top_ips = db.query(
            SecurityEvent.ip_hashed,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.event_type.in_(["login_failure", "rate_limit_exceeded", "forbidden_access"]),
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.ip_hashed).order_by(desc('count')).limit(10).all()
        
        # Top offenders by email
        top_emails = db.query(
            SecurityEvent.user_email,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.event_type.in_(["login_failure", "forbidden_access"]),
                SecurityEvent.user_email.isnot(None),
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.user_email).order_by(desc('count')).limit(10).all()
        
        # Role usage breakdown
        role_usage = db.query(
            SecurityEvent.role,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.event_type == "login_success",
                SecurityEvent.role.isnot(None),
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.role).order_by(desc('count')).all()
        
        result = {
            "top_offending_ips": [{"ip_hash": ip.ip_hashed, "count": ip.count} for ip in top_ips],
            "top_offending_emails": [{"email": email.user_email, "count": email.count} for email in top_emails],
            "role_usage": [{"role": role.role, "count": role.count} for role in role_usage]
        }
        
        _set_cached(cache_key, result)
        return result

def clear_cache() -> None:
    """Clear all cached data (useful for testing)"""
    global _cache
    _cache.clear()

