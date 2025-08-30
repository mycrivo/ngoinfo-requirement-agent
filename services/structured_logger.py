import os
import json
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextlib import contextmanager
import threading

# Configure logging format
class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage()
        }
        
        # Add request correlation if available
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, 'opportunity_id'):
            log_entry["opportunity_id"] = record.opportunity_id
        
        # Add performance metrics if available
        if hasattr(record, 'duration_ms'):
            log_entry["duration_ms"] = record.duration_ms
        
        if hasattr(record, 'action'):
            log_entry["action"] = record.action
        
        if hasattr(record, 'status'):
            log_entry["status"] = record.status
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1])
            }
        
        return json.dumps(log_entry)

class StructuredLogger:
    """Structured logging service for ReqAgent"""
    
    def __init__(self):
        self.logger = logging.getLogger('reqagent')
        self.request_id = None
        self.opportunity_id = None
        self.start_time = None
        
        # Set up formatter
        formatter = StructuredFormatter()
        
        # Configure handlers
        self._setup_handlers(formatter)
        
        # Set log level from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Thread-local storage for request context
        self._local = threading.local()
    
    def _setup_handlers(self, formatter):
        """Set up logging handlers"""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Console handler (for development)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (optional)
        log_file = os.getenv('LOG_FILE')
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not set up file logging: {e}")
        
        # Disable propagation to root logger
        self.logger.propagate = False
    
    def set_request_context(self, request_id: str, opportunity_id: Optional[str] = None):
        """Set request context for correlation"""
        self._local.request_id = request_id
        self._local.opportunity_id = opportunity_id
    
    def clear_request_context(self):
        """Clear request context"""
        self._local.request_id = None
        self._local.opportunity_id = None
    
    def _get_request_context(self) -> Dict[str, Any]:
        """Get current request context"""
        context = {}
        
        if hasattr(self._local, 'request_id') and self._local.request_id:
            context['request_id'] = self._local.request_id
        
        if hasattr(self._local, 'opportunity_id') and self._local.opportunity_id:
            context['opportunity_id'] = self._local.opportunity_id
        
        return context
    
    def _log_with_context(self, level: str, message: str, **kwargs):
        """Log message with request context"""
        # Create log record with extra fields
        extra_fields = self._get_request_context()
        extra_fields.update(kwargs)
        
        # Add timestamp
        extra_fields['timestamp'] = datetime.utcnow().isoformat()
        
        # Create custom log record
        record = logging.LogRecord(
            name=self.logger.name,
            level=getattr(logging, level.upper()),
            pathname='',
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.extra_fields = extra_fields
        
        # Log the record
        self.logger.handle(record)
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self._log_with_context('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self._log_with_context('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self._log_with_context('ERROR', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self._log_with_context('DEBUG', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        self._log_with_context('CRITICAL', message, **kwargs)
    
    @contextmanager
    def timed_operation(self, action: str, **kwargs):
        """Context manager for timing operations"""
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]
        
        try:
            # Log operation start
            self.info(f"🚀 Operation started: {action}", 
                     action=action, 
                     operation_id=operation_id,
                     status="started",
                     **kwargs)
            
            yield operation_id
            
            # Log operation success
            duration_ms = (time.time() - start_time) * 1000
            self.info(f"✅ Operation completed: {action}", 
                     action=action, 
                     operation_id=operation_id,
                     status="completed",
                     duration_ms=round(duration_ms, 2),
                     **kwargs)
            
        except Exception as e:
            # Log operation failure
            duration_ms = (time.time() - start_time) * 1000
            self.error(f"❌ Operation failed: {action}", 
                      action=action, 
                      operation_id=operation_id,
                      status="failed",
                      duration_ms=round(duration_ms, 2),
                      error=str(e),
                      **kwargs)
            raise
    
    def log_crawler_activity(self, url: str, status: str, **kwargs):
        """Log crawler activity"""
        self.info(f"🕷️ Crawler activity: {status}", 
                 action="crawler",
                 url=url,
                 status=status,
                 **kwargs)
    
    def log_parser_activity(self, opportunity_id: str, status: str, confidence: float = None, **kwargs):
        """Log parser activity"""
        log_data = {
            "action": "parser",
            "opportunity_id": opportunity_id,
            "status": status
        }
        
        if confidence is not None:
            log_data["confidence"] = confidence
        
        log_data.update(kwargs)
        
        self.info(f"🔍 Parser activity: {status}", **log_data)
    
    def log_publisher_activity(self, opportunity_id: str, status: str, platform: str = "wordpress", **kwargs):
        """Log publisher activity"""
        self.info(f"📝 Publisher activity: {status}", 
                 action="publisher",
                 opportunity_id=opportunity_id,
                 status=status,
                 platform=platform,
                 **kwargs)
    
    def log_security_event(self, event_type: str, details: str, severity: str = "medium", **kwargs):
        """Log security events"""
        self.warning(f"🔒 Security event: {event_type}", 
                    action="security",
                    event_type=event_type,
                    details=details,
                    severity=severity,
                    **kwargs)
    
    def log_performance_metric(self, metric_name: str, value: Union[int, float], unit: str = "ms", **kwargs):
        """Log performance metrics"""
        self.info(f"📊 Performance metric: {metric_name} = {value}{unit}", 
                 action="performance",
                 metric_name=metric_name,
                 value=value,
                 unit=unit,
                 **kwargs)
    
    def log_data_quality(self, opportunity_id: str, field: str, quality_score: float, **kwargs):
        """Log data quality metrics"""
        self.info(f"🎯 Data quality: {field} = {quality_score:.2f}", 
                 action="data_quality",
                 opportunity_id=opportunity_id,
                 field=field,
                 quality_score=quality_score,
                 **kwargs)
    
    def log_user_action(self, user: str, action: str, target: str = None, **kwargs):
        """Log user actions"""
        self.info(f"👤 User action: {user} {action}", 
                 action="user_action",
                 user=user,
                 user_action=action,
                 target=target,
                 **kwargs)
    
    def log_system_event(self, event_type: str, details: str, **kwargs):
        """Log system events"""
        self.info(f"⚙️ System event: {event_type}", 
                 action="system",
                 event_type=event_type,
                 details=details,
                 **kwargs)
    
    def get_log_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get log summary for the specified time period"""
        try:
            # This is a simplified summary - in production, you'd query a log aggregation service
            summary = {
                "period_hours": hours,
                "total_logs": 0,
                "by_level": {},
                "by_action": {},
                "by_status": {},
                "errors": [],
                "warnings": [],
                "performance_metrics": []
            }
            
            # In a real implementation, you'd query your logs here
            # For now, return a placeholder
            self.info("📋 Log summary requested", action="log_summary", hours=hours)
            
            return summary
            
        except Exception as e:
            self.error(f"❌ Error getting log summary: {e}")
            return {"error": str(e)}
    
    def export_logs(self, level: str = "INFO", hours: int = 24, format: str = "json") -> str:
        """Export logs in specified format"""
        try:
            # This is a simplified export - in production, you'd query a log aggregation service
            export_data = {
                "export_info": {
                    "level": level,
                    "hours": hours,
                    "format": format,
                    "exported_at": datetime.utcnow().isoformat()
                },
                "logs": []
            }
            
            # In a real implementation, you'd query and format your logs here
            self.info("📤 Log export requested", action="log_export", level=level, hours=hours, format=format)
            
            if format == "json":
                return json.dumps(export_data, indent=2)
            elif format == "csv":
                # Convert to CSV format
                return "timestamp,level,action,status,message\n"
            else:
                return str(export_data)
                
        except Exception as e:
            self.error(f"❌ Error exporting logs: {e}")
            return f"Error: {str(e)}"

# Global logger instance
structured_logger = StructuredLogger()

# Convenience functions for backward compatibility
def get_logger(name: str = None) -> StructuredLogger:
    """Get structured logger instance"""
    return structured_logger

def log_info(message: str, **kwargs):
    """Log info message"""
    structured_logger.info(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Log warning message"""
    structured_logger.warning(message, **kwargs)

def log_error(message: str, **kwargs):
    """Log error message"""
    structured_logger.error(message, **kwargs)

def log_debug(message: str, **kwargs):
    """Log debug message"""
    structured_logger.debug(message, **kwargs)


