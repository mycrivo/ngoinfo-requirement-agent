# Phase 4: Hardening & Observability

## Overview

Phase 4 focuses on hardening ReqAgent's crawlers and parsers, implementing comprehensive content sanitization, improving WordPress publishing reliability, and adding structured logging and observability features.

## 🎯 Key Objectives

- **Crawler Hardening**: Implement retry policies, rate limiting, and site-specific configurations
- **Content Sanitization**: Ensure all outputs are safe and consistent
- **Publishing Reliability**: Add idempotency and retry logic to WordPress publishing
- **Observability**: Implement structured logging with request correlation and admin UI

## 🏗️ Architecture

### 1. Site Profile Registry (`configs/sites.yml`)

Centralized configuration for domain-specific crawling behavior:

```yaml
gov.uk:
  selectors:
    title: ["h1", ".gem-c-title__text", ".govuk-heading-xl"]
    content: ["main", ".govuk-main-wrapper", ".gem-c-govspeak"]
    deadline: ["[class*='deadline']", ".govuk-inset-text"]
    amount: ["[class*='amount']", ".govuk-summary-list"]
  
  pagination:
    enabled: false
    max_pages: 1
  
  waits:
    page_load: 8000
    element_wait: 3000
  
  retry:
    max_attempts: 3
    backoff_multiplier: 2.0
    initial_delay: 2000
  
  rate_limit:
    requests_per_second: 0.5
    delay_between_requests: 2000
```

**Features:**
- Domain-specific selector configurations
- Configurable wait times and timeouts
- Exponential backoff retry policies
- Polite rate limiting per domain
- User-Agent rotation

### 2. Content Sanitization (`services/content_sanitizer.py`)

Comprehensive sanitization for all content types:

```python
from services.content_sanitizer import content_sanitizer

# String sanitization
clean_text = content_sanitizer.sanitize_string("Dirty\x00text<script>alert('xss')</script>")

# HTML sanitization
safe_html = content_sanitizer.sanitize_html("<p>Hello <script>alert('xss')</script></p>", allow_html=True)

# URL sanitization
https_url = content_sanitizer.sanitize_url("http://example.com/")

# Date/amount normalization
normalized_date = content_sanitizer.normalize_date("2024-01-15")
normalized_amount = content_sanitizer.normalize_amount("50000")
```

**Security Features:**
- Control character removal
- HTML tag whitelisting (p, ul, li, a, strong, em, b, i)
- XSS prevention
- URL validation and HTTPS enforcement
- Consistent date/amount formatting

### 3. Structured Logging (`services/structured_logger.py`)

JSON-formatted logging with request correlation:

```python
from services.structured_logger import structured_logger

# Set request context
structured_logger.set_request_context("req_123", "opp_456")

# Log with context
structured_logger.info("Processing opportunity", action="parser", status="started")

# Timed operations
with structured_logger.timed_operation("crawler", url="https://example.com") as op_id:
    # ... crawling logic ...
    pass

# Specialized logging methods
structured_logger.log_crawler_activity("https://example.com", "completed")
structured_logger.log_parser_activity("opp_123", "completed", confidence=0.95)
structured_logger.log_publisher_activity("opp_123", "published", platform="wordpress")
```

**Features:**
- JSON-structured logs
- Request ID correlation
- Performance timing
- Specialized logging for different activities
- Thread-safe context management

### 4. Admin Logs UI (`/admin/logs`)

Web interface for log monitoring and analysis:

- **Real-time filtering** by level, action, and time range
- **Search functionality** across log entries
- **Export capabilities** (JSON/CSV)
- **Summary statistics** and metrics
- **Auto-refresh** every 30 seconds

### 5. WordPress Publishing Enhancements (`routes/publish.py`)

Improved reliability and idempotency:

```python
class WordPressPublisher:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2.0
    
    def _generate_idempotency_key(self, title: str, donor: str, deadline: str) -> str:
        """Generate unique key to prevent duplicate posts"""
        key_data = f"{title}:{donor}:{deadline}".lower().strip()
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()[:16]
    
    def _check_existing_post(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if post already exists"""
        # Implementation checks WordPress for existing posts
        pass
```

**Features:**
- **Idempotency**: Prevents duplicate posts using content hash
- **Retry Logic**: Exponential backoff on failures
- **SEO Integration**: Auto-fills Rank Math meta fields
- **Error Handling**: Specific `PublishError` exceptions

## 🔧 Configuration

### Environment Variables

```bash
# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/reqagent.log

# Sanitization
SANITIZE_ALLOW_TAGS=p,ul,li,a,strong,em,b,i
SANITIZE_MAX_STRING_LENGTH=10000
SANITIZE_MAX_LIST_ITEMS=50

# Site Profiles
SITE_PROFILES_CONFIG=configs/sites.yml
SITE_PROFILES_RELOAD_INTERVAL=300

# Crawler
CRAWLER_MAX_RETRIES=3
CRAWLER_RATE_LIMIT_DEFAULT=1.0
CRAWLER_TIMEOUT_PAGE_LOAD=10000
CRAWLER_TIMEOUT_ELEMENT_WAIT=5000

# WordPress
WP_PUBLISH_MAX_RETRIES=3
WP_PUBLISH_RETRY_DELAY=2.0
WP_ENABLE_IDEMPOTENCY=true
WP_SEO_AUTO_FILL=true

# Error Reporting (Optional)
SENTRY_DSN=your-sentry-dsn-here
```

### Site Profile Configuration

Create `configs/sites.yml` with domain-specific settings:

```yaml
default:
  selectors:
    title: ["h1", ".title", "h1.title"]
    content: ["main", ".content", ".main-content"]
    deadline: ["[class*='deadline']", ".deadline", "[data-deadline]"]
    amount: ["[class*='amount']", ".amount", "[data-amount]"]
  
  pagination:
    enabled: false
    max_pages: 1
  
  waits:
    page_load: 5000
    element_wait: 2000
  
  retry:
    max_attempts: 3
    backoff_multiplier: 2.0
    initial_delay: 1000
  
  rate_limit:
    requests_per_second: 1.0
    delay_between_requests: 1000
  
  user_agents:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
```

## 🚀 Usage

### 1. Site Profile Management

```python
from services.site_profiles import site_registry

# Get profile for specific domain
profile = site_registry.get_profile("https://www.gov.uk/funding")

# Apply rate limiting
site_registry.enforce_rate_limit("https://www.gov.uk/funding")

# Get retry delay for attempt
delay = site_registry.get_retry_delay(2, "https://www.gov.uk/funding")
```

### 2. Content Sanitization

```python
from services.content_sanitizer import content_sanitizer

# Sanitize complete funding opportunity
clean_opportunity = content_sanitizer.sanitize_funding_opportunity(raw_data)

# Validate sanitized data
validation = content_sanitizer.validate_sanitized_data(clean_opportunity)
if validation["is_valid"]:
    print(f"Data quality: {validation['completeness_score']}%")
```

### 3. Structured Logging

```python
from services.structured_logger import structured_logger

# Set request context
structured_logger.set_request_context("req_123", "opp_456")

# Log activities
structured_logger.log_crawler_activity("https://example.com", "started")
structured_logger.log_parser_activity("opp_123", "completed", confidence=0.95)

# Clear context when done
structured_logger.clear_request_context()
```

### 4. Admin Logs Interface

Access the logs dashboard at `/admin/logs`:

- **Filter by level**: INFO, WARNING, ERROR, CRITICAL, DEBUG
- **Filter by action**: crawler, parser, publisher, security, etc.
- **Time range**: Last hour to last week
- **Search**: Full-text search across log entries
- **Export**: Download logs in JSON or CSV format

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Test Phase 4 functionality
make test-phase4

# Or run directly
python test_phase4_hardening.py
```

**Test Coverage:**
- Site profile loading and validation
- Content sanitization (strings, HTML, URLs, dates, amounts)
- Structured logging and context management
- Admin logs filtering and search
- Integration between components

## 📊 Monitoring & Observability

### 1. Log Correlation

All logs include correlation fields:
- `request_id`: Links related operations
- `opportunity_id`: Tracks specific opportunities
- `action`: Operation type (crawler, parser, publisher)
- `status`: Operation status (started, completed, failed)
- `duration_ms`: Performance metrics

### 2. Performance Metrics

Track system performance:
- Response times
- Success/failure rates
- Data quality scores
- Crawler performance per domain

### 3. Security Monitoring

Monitor security events:
- Rate limit violations
- Authentication failures
- Input validation errors
- XSS/SQL injection attempts

## 🔒 Security Features

### 1. Input Sanitization

- **Control Characters**: Removed from all strings
- **HTML Injection**: Whitelist-based sanitization
- **URL Validation**: HTTPS enforcement, trailing slash removal
- **Data Normalization**: Consistent formatting with fallbacks

### 2. Rate Limiting

- **Per-domain limits**: Configurable requests per second
- **Exponential backoff**: Intelligent retry strategies
- **User-Agent rotation**: Avoid detection and blocking

### 3. Error Handling

- **Structured errors**: Consistent error formats
- **No stack traces**: Production-safe error messages
- **Audit logging**: Track all security events

## 🐳 Docker & Railway Considerations

### 1. Lightweight Dependencies

- **Pure Python**: No heavy system packages
- **Configurable backends**: Graceful fallbacks
- **Memory efficient**: Conservative retry limits

### 2. Logging Strategy

- **JSON output**: Structured logs to stdout
- **Railway capture**: Automatic log aggregation
- **Optional Sentry**: Error reporting service

### 3. Configuration Management

- **Environment-based**: No hardcoded values
- **Hot reloading**: Site profiles update without restart
- **Validation**: Configuration validation on startup

## 📈 Performance Optimizations

### 1. Crawler Efficiency

- **Smart retries**: Exponential backoff prevents hammering
- **Rate limiting**: Polite crawling behavior
- **Timeout management**: Configurable page and element waits

### 2. Logging Performance

- **Async operations**: Non-blocking log writes
- **Context caching**: Efficient request correlation
- **Export optimization**: Streaming for large log exports

### 3. Memory Management

- **String limits**: Configurable max lengths
- **List limits**: Prevent memory bloat
- **Cleanup**: Automatic context clearing

## 🔄 Migration & Deployment

### 1. Backward Compatibility

- **Existing APIs**: No breaking changes
- **Gradual rollout**: Enable features incrementally
- **Fallback modes**: Graceful degradation

### 2. Configuration Migration

```bash
# Copy example configuration
cp configs/sites.yml.example configs/sites.yml

# Update environment variables
cp env.example .env
# Edit .env with your settings

# Restart application
make restart
```

### 3. Monitoring Setup

1. **Enable structured logging**: Set `LOG_FORMAT=json`
2. **Configure site profiles**: Create `configs/sites.yml`
3. **Set sanitization rules**: Configure `SANITIZE_*` variables
4. **Test admin logs**: Access `/admin/logs` interface

## 🚨 Troubleshooting

### Common Issues

1. **Site profiles not loading**
   - Check `configs/sites.yml` syntax
   - Verify file permissions
   - Check `SITE_PROFILES_CONFIG` path

2. **Sanitization too aggressive**
   - Adjust `SANITIZE_ALLOW_TAGS`
   - Check `SANITIZE_MAX_STRING_LENGTH`
   - Review sanitization logs

3. **Logs not appearing**
   - Verify `LOG_LEVEL` setting
   - Check `LOG_FILE` permissions
   - Ensure structured logging is enabled

4. **WordPress publishing failures**
   - Check `WP_PUBLISH_MAX_RETRIES`
   - Verify idempotency settings
   - Review retry delay configuration

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
DEBUG=true
```

### Health Checks

Monitor system health:

```bash
# Check application health
make health-check

# View recent logs
make show-logs LEVEL=ERROR

# Test specific functionality
make test-phase4
```

## 🔮 Future Enhancements

### 1. Advanced Monitoring

- **Metrics dashboard**: Real-time performance metrics
- **Alerting**: Automated notifications for issues
- **Trend analysis**: Historical performance tracking

### 2. Enhanced Security

- **Threat detection**: ML-based anomaly detection
- **Advanced sanitization**: Context-aware content cleaning
- **Security scoring**: Automated security assessments

### 3. Performance Optimization

- **Caching layer**: Redis-based caching
- **Async processing**: Background job processing
- **Load balancing**: Multi-instance deployment

## 📚 Additional Resources

- **Site Profile Examples**: `configs/sites.yml`
- **Configuration Reference**: `env.example`
- **API Documentation**: `/docs` endpoint
- **Test Suite**: `test_phase4_hardening.py`
- **Admin Interface**: `/admin/logs`

## 🤝 Contributing

When contributing to Phase 4:

1. **Follow security-first approach**: All inputs must be sanitized
2. **Maintain observability**: Log all important events
3. **Test thoroughly**: Run full test suite
4. **Document changes**: Update README and inline docs
5. **Performance conscious**: Monitor memory and CPU usage

## 📄 License

This implementation follows the same license as the main ReqAgent project.

---

**Phase 4 Status**: ✅ Complete  
**Last Updated**: December 2024  
**Version**: 4.0.0




