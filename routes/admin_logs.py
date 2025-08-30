from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict, Any
import os
from datetime import datetime, timedelta

from services.structured_logger import structured_logger
from utils.auth import get_current_user, require_admin_role

router = APIRouter(prefix="/admin", tags=["admin-logs"])
templates = Jinja2Templates(directory="templates")

@router.get("/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    level: Optional[str] = Query(None, description="Filter by log level"),
    action: Optional[str] = Query(None, description="Filter by action"),
    hours: int = Query(24, description="Hours to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=10, le=100, description="Logs per page"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Admin logs dashboard"""
    try:
        # Get log summary
        summary = structured_logger.get_log_summary(hours=hours)
        
        # Get filtered logs (this would query your actual log storage in production)
        logs = _get_filtered_logs(level, action, hours, page, per_page)
        
        # Calculate pagination
        total_logs = len(logs)  # In production, this would be the total count
        total_pages = (total_logs + per_page - 1) // per_page
        
        # Prepare context
        context = {
            "request": request,
            "user": current_user,
            "logs": logs,
            "summary": summary,
            "filters": {
                "level": level,
                "action": action,
                "hours": hours
            },
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_logs": total_logs,
                "has_prev": page > 1,
                "has_next": page < total_pages
            },
            "log_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "log_actions": ["crawler", "parser", "publisher", "security", "performance", "data_quality", "user_action", "system"]
        }
        
        return templates.TemplateResponse("admin_logs.html", context)
        
    except Exception as e:
        structured_logger.error(f"❌ Error loading admin logs: {e}", 
                              action="admin_logs",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load logs"
        )

@router.get("/api/logs/summary")
async def get_logs_summary(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Get logs summary as JSON API"""
    try:
        summary = structured_logger.get_log_summary(hours=hours)
        
        structured_logger.info("📋 Log summary API requested", 
                              action="log_summary_api",
                              user=current_user.get("username", "unknown"),
                              hours=hours)
        
        return summary
        
    except Exception as e:
        structured_logger.error(f"❌ Error getting log summary: {e}", 
                              action="log_summary_api",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get log summary"
        )

@router.get("/api/logs/export")
async def export_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    format: str = Query("json", description="Export format (json, csv)"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Export logs in specified format"""
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be 'json' or 'csv'"
            )
        
        exported_data = structured_logger.export_logs(
            level=level,
            hours=hours,
            format=format
        )
        
        structured_logger.info("📤 Log export requested", 
                              action="log_export",
                              user=current_user.get("username", "unknown"),
                              level=level,
                              hours=hours,
                              format=format)
        
        # Set appropriate content type
        content_type = "application/json" if format == "json" else "text/csv"
        filename = f"reqagent_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        from fastapi.responses import Response
        return Response(
            content=exported_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        structured_logger.error(f"❌ Error exporting logs: {e}", 
                              action="log_export",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export logs"
        )

@router.get("/api/logs/search")
async def search_logs(
    query: str = Query(..., description="Search query"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    action: Optional[str] = Query(None, description="Filter by action"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    limit: int = Query(100, ge=10, le=1000, description="Maximum results"),
    current_user: Dict[str, Any] = Depends(require_admin_role)
):
    """Search logs with filters"""
    try:
        # In production, this would use a proper search engine
        # For now, return a placeholder
        search_results = _search_logs(query, level, action, hours, limit)
        
        structured_logger.info("🔍 Log search performed", 
                              action="log_search",
                              user=current_user.get("username", "unknown"),
                              query=query,
                              level=level,
                              action=action,
                              hours=hours,
                              results_count=len(search_results))
        
        return {
            "query": query,
            "filters": {"level": level, "action": action, "hours": hours},
            "results": search_results,
            "total": len(search_results),
            "limit": limit
        }
        
    except Exception as e:
        structured_logger.error(f"❌ Error searching logs: {e}", 
                              action="log_search",
                              user=current_user.get("username", "unknown"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search logs"
        )

def _get_filtered_logs(level: Optional[str], action: Optional[str], hours: int, page: int, per_page: int) -> List[Dict[str, Any]]:
    """Get filtered logs (placeholder implementation)"""
    # In production, this would query your actual log storage
    # For now, return sample data
    
    sample_logs = [
        {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "action": "crawler",
            "message": "🕷️ Crawler activity: started",
            "url": "https://example.com",
            "status": "started",
            "request_id": "req_12345",
            "opportunity_id": "opp_67890"
        },
        {
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "level": "WARNING",
            "action": "parser",
            "message": "🔍 Parser activity: low_confidence",
            "opportunity_id": "opp_67890",
            "status": "low_confidence",
            "confidence": 0.65,
            "request_id": "req_12345"
        },
        {
            "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
            "level": "ERROR",
            "action": "publisher",
            "message": "❌ Publisher activity: failed",
            "opportunity_id": "opp_67890",
            "status": "failed",
            "platform": "wordpress",
            "error": "Connection timeout",
            "request_id": "req_12345"
        }
    ]
    
    # Apply filters
    filtered_logs = sample_logs
    
    if level:
        filtered_logs = [log for log in filtered_logs if log.get("level") == level.upper()]
    
    if action:
        filtered_logs = [log for log in filtered_logs if log.get("action") == action]
    
    # Apply pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return filtered_logs[start_idx:end_idx]

def _search_logs(query: str, level: Optional[str], action: Optional[str], hours: int, limit: int) -> List[Dict[str, Any]]:
    """Search logs (placeholder implementation)"""
    # In production, this would use a proper search engine
    # For now, return sample data
    
    sample_results = [
        {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "action": "crawler",
            "message": f"🕷️ Crawler activity: {query} found",
            "url": "https://example.com",
            "status": "completed",
            "request_id": "req_12345",
            "opportunity_id": "opp_67890"
        }
    ]
    
    return sample_results[:limit]


