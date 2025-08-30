# ReqAgent - Funding Opportunity Management System

AI-powered funding opportunity discovery and management system with enhanced security features.

## Local Testing

By default, Phase-6 security tests are skipped locally (`SKIP_SECURITY_TESTS=1`).

To run them: `SKIP_SECURITY_TESTS=0 pytest -vv tests/test_phase6_security.py --timeout=30`.

## Development

See individual phase READMEs for detailed implementation information:

- [Phase 2: Template Generation](PHASE2_TEMPLATES_README.md)
- [Phase 3: PDF Processing](PHASE3_PDF_README.md) 
- [Phase 4: Hardening & Observability](PHASE4_HARDENING_README.md)
- [Phase 6: Enhanced Security](PHASE6_SECURITY_README.md)
- [Phase 8: Analytics & Ops Dashboard](PHASE8_ANALYTICS_README.md)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (skips security tests by default)
pytest -q

# Run security tests locally
SKIP_SECURITY_TESTS=0 pytest tests/test_phase6_security.py

# Run analytics tests
pytest tests/test_phase8_analytics.py -v
```

## Analytics Dashboard

The admin analytics dashboard (`/admin/analytics`) provides:

- **Pipeline Analytics**: Monitor ingestion, QA approval, publishing, and template generation metrics
- **Security Analytics**: Track login attempts, rate limiting, and security events
- **Export Functionality**: Download CSV reports for both pipeline and security data
- **Real-time Charts**: Interactive charts powered by Chart.js for trend visualization

Access requires admin role and is available at `/admin/analytics`.

## Phase 8 Analytics Runbook

### Feature Flag

Analytics features are controlled by the `ADMIN_ANALYTICS_ENABLED` environment variable:

```bash
# Enable analytics (default)
ADMIN_ANALYTICS_ENABLED=true

# Disable analytics (returns 404)
ADMIN_ANALYTICS_ENABLED=false
```

### API Endpoints

All endpoints require admin role authentication:

**Pipeline Analytics:**
- `GET /admin/api/analytics/pipeline/kpis` - Pipeline KPIs
- `GET /admin/api/analytics/pipeline/trends` - Pipeline trends (daily/weekly)
- `GET /admin/api/analytics/pipeline/sources` - Source breakdown
- `GET /admin/api/analytics/pipeline/qa` - QA metrics

**Security Analytics:**
- `GET /admin/api/analytics/security/kpis` - Security KPIs
- `GET /admin/api/analytics/security/trends` - Security trends (daily/weekly)
- `GET /admin/api/analytics/security/breakdown` - Security breakdown

**Health & Export:**
- `GET /admin/api/analytics/health` - Health check
- `GET /admin/api/analytics/export?type=pipeline&format=csv` - CSV export

### CSV Export

Server-side CSV generation with privacy controls:
- Anonymized IP addresses (hashed, first 8 chars displayed)
- No raw PII beyond role/timestamp
- Date range filtering supported
- Separate exports for pipeline and security data

### Security Notes

- All routes protected by admin RBAC
- IP addresses are SHA256 hashed in database
- Security events table auto-prunes after 90 days
- CSP-compliant (no external CDNs, self-hosted Chart.js)
- Input validation on all query parameters

### Cache Configuration

- In-process cache with 60-second TTL
- Automatically disabled in test mode (`TEST_MODE=true`)
- Efficient SQLAlchemy queries with proper indexing

### Enabling Phase-8 Tests

Analytics tests are gated by default. To enable:

```bash
# Enable Phase-8 tests
export SKIP_PHASE8_TESTS=0

# Run analytics tests
pytest tests/test_phase8_analytics.py -v

# Run with other tests
SKIP_PHASE8_TESTS=0 pytest -v
```

