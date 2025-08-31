# Phase 8: Analytics & Ops Dashboard

## Overview

Phase 8 extends the existing Admin UI with a comprehensive Analytics & Ops Dashboard, providing pipeline metrics and security event analytics. The dashboard is admin-only and integrates seamlessly with the existing admin interface.

## Features

### 🚀 Pipeline Analytics (Ops)
- **KPIs**: Total ingested, QA-approved, published, templates generated, error rate
- **Trends**: Time-series charts (daily/weekly) for ingested, published, and templates
- **Source Breakdown**: Top 10 providers/domains by ingested/published volume
- **QA Metrics**: Average edits per record, most corrected fields, template success ratio

### 🔒 Security Analytics
- **KPIs**: Login successes/failures, rate-limit hits, forbidden (403) events
- **Trends**: Line charts for login success vs failure over time
- **Top Offenders**: IPs/emails with most failures (hashed/anonymized)
- **Role Usage**: Breakdown of admin vs QA vs editor logins

### 📊 Dashboard Features
- **Interactive Tabs**: Switch between Pipeline and Security analytics
- **Date Range Filters**: Customizable start/end dates with interval selection
- **Real-time Charts**: Chart.js powered visualizations
- **CSV Export**: Download comprehensive reports for both analytics types
- **Responsive Design**: Mobile-friendly interface

## Architecture

### Database Changes
- **New Table**: `security_events` for persistent security analytics
- **Indexes**: Optimized for analytics queries with TTL (90 days)
- **Migration**: `0004_add_security_events_table.py`

### Service Layer
- **Location**: `services/analytics.py`
- **Caching**: In-process dict with 60s TTL (disabled in TEST_MODE)
- **Functions**:
  - `get_pipeline_kpis()` - Core pipeline metrics
  - `get_pipeline_trends()` - Time-series data
  - `get_source_breakdown()` - Provider/domain analysis
  - `get_qa_metrics()` - QA performance metrics
  - `get_security_kpis()` - Security event counts
  - `get_security_trends()` - Security time-series
  - `get_security_breakdown()` - Security offender analysis

### API Endpoints
All endpoints require admin authentication:

```
GET /admin/analytics                    # Dashboard UI
GET /api/admin/analytics/pipeline/kpis  # Pipeline KPIs
GET /api/admin/analytics/pipeline/trends # Pipeline trends
GET /api/admin/analytics/pipeline/sources # Source breakdown
GET /api/admin/analytics/pipeline/qa     # QA metrics
GET /api/admin/analytics/security/kpis   # Security KPIs
GET /api/admin/analytics/security/trends # Security trends
GET /api/admin/analytics/security/breakdown # Security breakdown
GET /api/admin/analytics/export          # CSV export
```

### Frontend
- **Template**: `templates/admin_analytics.html`
- **Charts**: Chart.js (CDN) for interactive visualizations
- **Navigation**: Integrated into existing admin navbar
- **Responsive**: Mobile-friendly CSS Grid layout

## Security Features

### Data Privacy
- **IP Anonymization**: IP addresses are hashed before storage
- **No PII Exposure**: Raw IPs/emails never exposed in UI
- **Role-based Access**: Admin-only access to all analytics

### Input Validation
- **Date Parameters**: Validated date format (YYYY-MM-DD)
- **Interval Validation**: Only "daily" or "weekly" allowed
- **SQL Injection Protection**: Parameterized queries via SQLAlchemy

### Audit Logging
- **Structured Logging**: All analytics access logged
- **User Tracking**: Username recorded for all API calls
- **Security Events**: Persistent storage in `security_events` table

## Performance Optimizations

### Caching Strategy
- **In-Process Cache**: 60-second TTL for all analytics queries
- **Test Mode**: Cache disabled when `TEST_MODE=true`
- **Cache Keys**: Deterministic based on parameters

### Database Indexes
```sql
-- Core analytics indexes
CREATE INDEX ix_security_events_event_type_created_at ON security_events (event_type, created_at);
CREATE INDEX ix_security_events_ip_hashed_created_at ON security_events (ip_hashed, created_at);
CREATE INDEX ix_security_events_user_email_created_at ON security_events (user_email, created_at);

-- TTL index for automatic cleanup
CREATE INDEX ix_security_events_ttl ON security_events (created_at) 
WHERE created_at < NOW() - INTERVAL '90 days';
```

### Query Optimization
- **Date Truncation**: Efficient time-series grouping
- **JOIN Optimization**: Minimal joins for source breakdown
- **Aggregation**: Pre-calculated counts and ratios

## Installation & Setup

### 1. Database Migration
```bash
# Run the new migration
alembic upgrade head
```

### 2. Verify Models
Ensure `SecurityEvent` model is imported in `models.py`

### 3. Register Routes
Analytics router is automatically included in `main.py`

### 4. Access Dashboard
Navigate to `/admin/analytics` (admin role required)

## Configuration

### Environment Variables
```bash
# Disable caching in test mode
TEST_MODE=true

# Security events retention (90 days default)
SECURITY_EVENTS_TTL_DAYS=90
```

### Chart.js Configuration
- **CDN Source**: `https://cdn.jsdelivr.net/npm/chart.js`
- **Responsive**: Auto-resize charts
- **Theme**: Consistent with admin UI colors

## Testing

### Run Analytics Tests
```bash
# Unit tests
pytest tests/test_phase8_analytics.py::TestAnalyticsService -v

# Integration tests
pytest tests/test_phase8_analytics.py::TestAnalyticsIntegration -v

# API tests
pytest tests/test_phase8_analytics.py::TestAnalyticsAPI -v

# All analytics tests
pytest tests/test_phase8_analytics.py -v
```

### Test Coverage
- **Service Functions**: All analytics calculations
- **API Endpoints**: Request/response validation
- **Cache Behavior**: TTL and test mode handling
- **Error Handling**: Database and validation errors

## Usage Examples

### Pipeline Analytics
1. Navigate to `/admin/analytics`
2. Select "Pipeline Analytics" tab
3. Adjust date range and interval
4. View KPIs, trends, and breakdowns
5. Export data as CSV

### Security Analytics
1. Select "Security Analytics" tab
2. Monitor login patterns and security events
3. Identify top offending IPs/emails
4. Track role usage patterns
5. Export security reports

### Custom Date Ranges
- **Last 7 days**: Quick performance review
- **Last 30 days**: Monthly reporting
- **Custom range**: Specific incident analysis

## Monitoring & Maintenance

### Data Retention
- **Security Events**: 90-day TTL with automatic cleanup
- **Analytics Cache**: 60-second TTL for real-time data
- **Database Size**: Monitor `security_events` table growth

### Performance Monitoring
- **Query Performance**: Monitor slow analytics queries
- **Cache Hit Rate**: Track cache effectiveness
- **Memory Usage**: Monitor in-process cache size

### Alerting (Optional)
- **High Error Rates**: Pipeline error rate > 20%
- **Security Anomalies**: >10 failed logins/hour
- **Performance Issues**: Analytics response time > 2s

## Troubleshooting

### Common Issues

#### Charts Not Loading
- Check Chart.js CDN availability
- Verify JavaScript console for errors
- Ensure admin role permissions

#### Slow Analytics
- Check database indexes
- Monitor query performance
- Verify cache is working

#### Missing Data
- Check date range filters
- Verify security events are being logged
- Check database connectivity

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Disable cache for testing
export TEST_MODE=true
```

## Future Enhancements

### Phase 9+ Considerations
- **Real-time Updates**: WebSocket integration for live data
- **Advanced Charts**: More chart types (pie, bar, heatmaps)
- **Custom Dashboards**: User-configurable widget layouts
- **Alert Integration**: Slack/Teams webhook notifications
- **Data Export**: Additional formats (JSON, Excel)

### Performance Improvements
- **Redis Caching**: Distributed cache for production
- **Background Jobs**: Async analytics calculation
- **Data Warehousing**: Historical analytics storage
- **CDN Integration**: Static asset optimization

## Contributing

### Code Style
- **Type Hints**: All functions include type annotations
- **Docstrings**: Comprehensive function documentation
- **Error Handling**: Graceful degradation for failures
- **Testing**: 90%+ test coverage target

### Pull Request Process
1. **Feature Branch**: Create from `main`
2. **Tests**: Ensure all tests pass
3. **Documentation**: Update README and docstrings
4. **Review**: Admin review required for analytics changes

## Security Considerations

### Access Control
- **Admin Only**: All analytics endpoints require admin role
- **Session Validation**: Verify user session on each request
- **Rate Limiting**: Prevent analytics API abuse

### Data Protection
- **No PII**: Never expose raw IPs or sensitive data
- **Audit Trail**: Log all analytics access
- **Data Minimization**: Only collect necessary metrics

### Compliance
- **GDPR**: Right to be forgotten for security events
- **Data Retention**: Automatic cleanup after 90 days
- **Access Logs**: Maintain audit trail for compliance

---

**Phase 8 Status**: ✅ Complete  
**Last Updated**: January 2024  
**Maintainer**: Backend Team





