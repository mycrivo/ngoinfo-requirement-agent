"""
Analytics routes for Phase 8: Admin Analytics & Ops Dashboard
Provides API endpoints for pipeline metrics and security analytics
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any
import csv
import io
import os
from datetime import datetime, timedelta

from services.metrics import (
    get_pipeline_kpis, get_pipeline_trends, get_source_breakdown, get_qa_metrics,
    get_security_kpis, get_security_trends, get_security_breakdown
)
from utils.auth_enhanced import get_current_user, require_admin_role
from services.structured_logger import structured_logger
from services.feature_flags import check_analytics_enabled

router = APIRouter(prefix="/admin", tags=["admin-analytics"])
templates = Jinja2Templates(directory="templates")

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Analytics dashboard with Pipeline and Security tabs"""
    try:
        # Check feature flag
        check_analytics_enabled()
        
        # Get default date range (last 30 days)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        context = {
            "request": request,
            "user": current_user,
            "default_dates": {
                "start": start_date,
                "end": end_date
            }
        }
        
        structured_logger.info("📊 Analytics dashboard accessed", 
                              action="analytics_dashboard",
                              user=current_user.get("username", "unknown"))
        
        return templates.TemplateResponse("admin_analytics.html", context)
        
    except Exception as e:
        structured_logger.error(f"❌ Error loading analytics dashboard: {e}", 
                              action="analytics_dashboard",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load analytics dashboard"
        )

# Pipeline Analytics API Endpoints

@router.get("/api/analytics/pipeline/kpis")
async def get_pipeline_kpis_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get pipeline KPIs as JSON API"""
    try:
        check_analytics_enabled()
        kpis = get_pipeline_kpis(start=start, end=end)
        
        structured_logger.info("📊 Pipeline KPIs API requested", 
                              action="pipeline_kpis_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end)
        
        return kpis
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting pipeline KPIs: {e}", 
                              action="pipeline_kpis_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline KPIs"
        )

@router.get("/api/analytics/pipeline/trends")
async def get_pipeline_trends_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    interval: str = Query("daily", description="Interval: daily or weekly"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get pipeline trends as JSON API"""
    try:
        check_analytics_enabled()
        if interval not in ["daily", "weekly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be 'daily' or 'weekly'"
            )
        
        trends = get_pipeline_trends(start=start, end=end, interval=interval)
        
        structured_logger.info("📈 Pipeline trends API requested", 
                              action="pipeline_trends_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end, interval=interval)
        
        return trends
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting pipeline trends: {e}", 
                              action="pipeline_trends_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline trends"
        )

@router.get("/api/analytics/pipeline/sources")
async def get_pipeline_sources_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get pipeline source breakdown as JSON API"""
    try:
        check_analytics_enabled()
        sources = get_source_breakdown(start=start, end=end)
        
        structured_logger.info("🌐 Pipeline sources API requested", 
                              action="pipeline_sources_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end)
        
        return sources
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting pipeline sources: {e}", 
                              action="pipeline_sources_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline sources"
        )

@router.get("/api/analytics/pipeline/qa")
async def get_pipeline_qa_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get pipeline QA metrics as JSON API"""
    try:
        check_analytics_enabled()
        qa_metrics = get_qa_metrics(start=start, end=end)
        
        structured_logger.info("🔍 Pipeline QA metrics API requested", 
                              action="pipeline_qa_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end)
        
        return qa_metrics
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting pipeline QA metrics: {e}", 
                              action="pipeline_qa_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline QA metrics"
        )

# Security Analytics API Endpoints

@router.get("/api/analytics/security/kpis")
async def get_security_kpis_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get security KPIs as JSON API"""
    try:
        check_analytics_enabled()
        kpis = get_security_kpis(start=start, end=end)
        
        structured_logger.info("🔒 Security KPIs API requested", 
                              action="security_kpis_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end)
        
        return kpis
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting security KPIs: {e}", 
                              action="security_kpis_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get security KPIs"
        )

@router.get("/api/analytics/security/trends")
async def get_security_trends_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    interval: str = Query("daily", description="Interval: daily or weekly"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get security trends as JSON API"""
    try:
        check_analytics_enabled()
        if interval not in ["daily", "weekly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be 'daily' or 'weekly'"
            )
        
        trends = get_security_trends(start=start, end=end, interval=interval)
        
        structured_logger.info("📈 Security trends API requested", 
                              action="security_trends_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end, interval=interval)
        
        return trends
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting security trends: {e}", 
                              action="security_trends_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get security trends"
        )

@router.get("/api/analytics/security/breakdown")
async def get_security_breakdown_api(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get security breakdown as JSON API"""
    try:
        check_analytics_enabled()
        breakdown = get_security_breakdown(start=start, end=end)
        
        structured_logger.info("🔍 Security breakdown API requested", 
                              action="security_breakdown_api",
                              user=current_user.get("username", "unknown"),
                              start=start, end=end)
        
        return breakdown
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting security breakdown: {e}", 
                              action="security_breakdown_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get security breakdown"
        )

# Health Endpoint

@router.get("/api/analytics/health")
async def analytics_health(
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Health check for analytics endpoints"""
    try:
        check_analytics_enabled()
        
        structured_logger.info("🏥 Analytics health check requested", 
                              action="analytics_health",
                              user=current_user.get("username", "unknown"))
        
        return {
            "ok": True,
            "features": ["pipeline", "security"],
            "timestamp": datetime.now().isoformat(),
            "cache_enabled": os.getenv("TEST_MODE", "false").lower() != "true"
        }
        
    except Exception as e:
        structured_logger.error(f"❌ Analytics health check failed: {e}", 
                              action="analytics_health",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics health check failed"
        )

# Export Endpoints

@router.get("/api/analytics/export")
async def export_analytics(
    type: str = Query(..., description="Export type: pipeline or security"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Export analytics data as CSV"""
    try:
        check_analytics_enabled()
        if type not in ["pipeline", "security"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Type must be 'pipeline' or 'security'"
            )
        
        # Generate CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        if type == "pipeline":
            # Pipeline export
            writer.writerow(["Metric", "Value", "Period"])
            
            kpis = get_pipeline_kpis(start=start, end=end)
            writer.writerow(["Total Ingested", kpis["total_ingested"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Total QA Approved", kpis["total_qa_approved"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Total Published", kpis["total_published"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Total Templates", kpis["total_templates"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Error Rate (%)", kpis["error_rate"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            
            # Add trends
            trends = get_pipeline_trends(start=start, end=end, interval="daily")
            writer.writerow([])
            writer.writerow(["Date", "Ingested", "Published", "Templates"])
            for i, date in enumerate(trends["ingested"]):
                ingested_count = trends["ingested"][i]["count"] if i < len(trends["ingested"]) else 0
                published_count = trends["published"][i]["count"] if i < len(trends["published"]) else 0
                template_count = trends["templates"][i]["count"] if i < len(trends["templates"]) else 0
                writer.writerow([date["date"], ingested_count, published_count, template_count])
                
        else:
            # Security export
            writer.writerow(["Metric", "Value", "Period"])
            
            kpis = get_security_kpis(start=start, end=end)
            writer.writerow(["Login Successes", kpis["login_successes"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Login Failures", kpis["login_failures"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Rate Limit Hits", kpis["rate_limit_hits"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Forbidden Events", kpis["forbidden_events"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            writer.writerow(["Total Events", kpis["total_events"], f"{kpis['period']['start']} to {kpis['period']['end']}"])
            
            # Add trends
            trends = get_security_trends(start=start, end=end, interval="daily")
            writer.writerow([])
            writer.writerow(["Date", "Login Success", "Login Failure"])
            for i, date in enumerate(trends["dates"]):
                success_count = trends["success"][i] if i < len(trends["success"]) else 0
                failure_count = trends["failure"][i] if i < len(trends["failure"]) else 0
                writer.writerow([date, success_count, failure_count])
        
        output.seek(0)
        
        structured_logger.info(f"📊 Analytics export requested: {type}", 
                              action="analytics_export",
                              user=current_user.get("username", "unknown"),
                              type=type, start=start, end=end)
        
        filename = f"analytics_{type}_{start or 'all'}_{end or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        structured_logger.error(f"❌ Error exporting analytics: {e}", 
                              action="analytics_export",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analytics"
        )

