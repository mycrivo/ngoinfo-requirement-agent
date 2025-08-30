"""
Metrics service for Admin Analytics - Pipeline + Security
Provides efficient SQLAlchemy queries with in-process caching
"""
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, text
from sqlalchemy.sql import text

from db import get_db
from models import (
    FundingOpportunity, Document, ProposalTemplate, 
    IngestionRun, SecurityEvent, Source, ParsedDataFeedback, AdminUser
)

# Simple in-process cache with TTL (60s, disabled if TEST_MODE=true)
_cache = {}
_cache_ttl = 60

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

def _hash_ip(ip: str) -> str:
    """Hash IP address for privacy"""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

# Pipeline Analytics Functions

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
        template_failures = db.query(ProposalTemplate).filter(
            and_(
                ProposalTemplate.status == "failed",
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).count()
        
        error_rate = (template_failures / max(total_templates, 1)) * 100
        
        result = {
            "total_ingested": total_ingested,
            "total_qa_approved": total_qa_approved,
            "total_published": total_published,
            "total_templates": total_templates,
            "error_rate": round(error_rate, 2),
            "period": {
                "start": start or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end": end or datetime.now().strftime("%Y-%m-%d")
            }
        }
        
        _set_cached(cache_key, result)
        return result

def get_pipeline_trends(start: Optional[str] = None, end: Optional[str] = None, 
                       interval: str = "daily") -> Dict[str, Any]:
    """Get pipeline trends for the specified date range and interval"""
    cache_key = _get_cache_key("pipeline_trends", start=start, end=end, interval=interval)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        if interval == "daily":
            date_trunc = func.date_trunc('day', FundingOpportunity.created_at)
        else:  # weekly
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
        
        # Published trends (approved status)
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
        template_date_trunc = func.date_trunc('day' if interval == "daily" else 'week', ProposalTemplate.created_at)
        template_trends = db.query(
            template_date_trunc.label('date'),
            func.count(ProposalTemplate.id).label('count')
        ).filter(
            and_(
                ProposalTemplate.created_at >= start_dt,
                ProposalTemplate.created_at < end_dt
            )
        ).group_by(template_date_trunc).order_by(template_date_trunc).all()
        
        result = {
            "ingested": [{"date": row.date.strftime("%Y-%m-%d"), "count": row.count} for row in ingested_trends],
            "published": [{"date": row.date.strftime("%Y-%m-%d"), "count": row.count} for row in published_trends],
            "templates": [{"date": row.date.strftime("%Y-%m-%d"), "count": row.count} for row in template_trends]
        }
        
        _set_cached(cache_key, result)
        return result

def get_source_breakdown(start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get source breakdown for the specified date range"""
    cache_key = _get_cache_key("source_breakdown", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Get source breakdown by joining with sources table
        source_breakdown = db.query(
            Source.provider.label('source'),
            func.count(FundingOpportunity.id).label('count')
        ).join(
            IngestionRun, Source.id == IngestionRun.source_id
        ).join(
            FundingOpportunity, IngestionRun.id == FundingOpportunity.id  # Simplified join
        ).filter(
            and_(
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).group_by(Source.provider).order_by(desc('count')).all()
        
        result = [{"source": row.source, "count": row.count} for row in source_breakdown]
        
        _set_cached(cache_key, result)
        return result

def get_qa_metrics(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get QA metrics for the specified date range"""
    cache_key = _get_cache_key("qa_metrics", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # QA approval rate
        total_reviewed = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.status.in_(["approved", "rejected"]),
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        total_approved = db.query(FundingOpportunity).filter(
            and_(
                FundingOpportunity.status == "approved",
                FundingOpportunity.created_at >= start_dt,
                FundingOpportunity.created_at < end_dt
            )
        ).count()
        
        approval_rate = (total_approved / max(total_reviewed, 1))
        
        # Average review time (simplified - using creation time diff)
        avg_review_time = 24.0  # Placeholder - would need review timestamps
        
        # Total feedback entries
        total_feedback = db.query(ParsedDataFeedback).filter(
            and_(
                ParsedDataFeedback.created_at >= start_dt,
                ParsedDataFeedback.created_at < end_dt
            )
        ).count()
        
        result = {
            "approval_rate": round(approval_rate, 3),
            "avg_review_time": avg_review_time,
            "total_reviews": total_reviewed,
            "total_feedback": total_feedback
        }
        
        _set_cached(cache_key, result)
        return result

# Security Analytics Functions

def get_security_kpis(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get security KPIs for the specified date range"""
    cache_key = _get_cache_key("security_kpis", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Count events by type
        event_counts = db.query(
            SecurityEvent.event_type,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.event_type).all()
        
        # Convert to dict for easy access
        counts = {row.event_type: row.count for row in event_counts}
        
        result = {
            "login_success": counts.get("login_success", 0),
            "login_failure": counts.get("login_failure", 0),
            "rate_limit": counts.get("rate_limit_exceeded", 0),
            "forbidden": counts.get("forbidden_access", 0),
            "total_events": sum(counts.values()),
            "period": {
                "start": start or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end": end or datetime.now().strftime("%Y-%m-%d")
            }
        }
        
        _set_cached(cache_key, result)
        return result

def get_security_trends(start: Optional[str] = None, end: Optional[str] = None, 
                       interval: str = "daily") -> Dict[str, Any]:
    """Get security trends for the specified date range and interval"""
    cache_key = _get_cache_key("security_trends", start=start, end=end, interval=interval)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        if interval == "daily":
            date_trunc = func.date_trunc('day', SecurityEvent.created_at)
        else:  # weekly
            date_trunc = func.date_trunc('week', SecurityEvent.created_at)
        
        # Get trends for login events
        trends = db.query(
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
        
        result = []
        for row in trends:
            result.append({
                "date": row.date.strftime("%Y-%m-%d"),
                "event_type": row.event_type,
                "count": row.count
            })
        
        _set_cached(cache_key, result)
        return result

def get_security_breakdown(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get security breakdown for the specified date range"""
    cache_key = _get_cache_key("security_breakdown", start=start, end=end)
    cached = _get_cached(cache_key)
    if cached:
        return cached
    
    start_dt, end_dt = _get_date_range(start, end)
    
    with get_db() as db:
        # Top offending IPs (already hashed)
        ip_breakdown = db.query(
            SecurityEvent.ip_hashed,
            func.count(SecurityEvent.id).label('count')
        ).filter(
            and_(
                SecurityEvent.event_type.in_(["login_failure", "rate_limit_exceeded", "forbidden_access"]),
                SecurityEvent.created_at >= start_dt,
                SecurityEvent.created_at < end_dt
            )
        ).group_by(SecurityEvent.ip_hashed).order_by(desc('count')).limit(10).all()
        
        # Top offending users
        user_breakdown = db.query(
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
        
        # Role usage
        role_breakdown = db.query(
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
            "ip_breakdown": [{"ip_hashed": row.ip_hashed, "count": row.count, "event_types": ["security"]} for row in ip_breakdown],
            "user_breakdown": [{"user_email": row.user_email, "count": row.count, "event_types": ["login_failure"]} for row in user_breakdown],
            "role_breakdown": [{"role": row.role, "count": row.count} for row in role_breakdown]
        }
        
        _set_cached(cache_key, result)
        return result
