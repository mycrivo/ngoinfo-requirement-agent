# Changelog

## [0.8.0] - ReqAgent Phases 1–8 Release

### Added
- **Core FastAPI Application**: Complete web framework with async support
- **Playwright Web Scraping**: Automated funding opportunity discovery
- **OpenAI JSON Parsing**: AI-powered content extraction and validation
- **Alembic Database Migrations**: Normalized schema with funding_opportunities, blog_posts, feedback tables
- **Admin QA UI**: `/admin/qa-review` interface for content review
- **WordPress Draft Publishing**: Automated content publishing with SEO meta
- **Feedback Loop Tables**: Complete data collection and analysis pipeline
- **JWT Authentication**: Secure admin access with role-based permissions
- **Admin Analytics Dashboard**: Pipeline and security metrics with Chart.js visualizations
- **Security Hardening**: Rate limiting, CSP, security logging, IP hashing
- **Pytest Test Harness**: Comprehensive testing framework with guards for stable CI/CD

### Infrastructure
- **Docker Deployment**: Production-ready Dockerfile with multi-stage builds
- **Railway Integration**: One-click cloud deployment with health checks
- **Environment Configuration**: Secure credential management with .env.sample
- **Static Asset Management**: Self-hosted Chart.js and custom analytics components
- **Database Schema**: Complete migration chain from baseline to analytics tables

### Security Features
- **Rate Limiting**: Protection against abuse and DoS attacks
- **Security Event Logging**: Comprehensive audit trail for admin actions
- **IP Address Hashing**: Privacy-compliant security monitoring
- **Content Security Policy**: XSS and injection attack prevention
- **Input Validation**: Sanitization and validation throughout the pipeline

### API Endpoints
- `/health` - Application health monitoring
- `/admin/analytics` - Admin analytics dashboard
- `/api/analytics/*` - JSON endpoints for metrics and data export
- `/api/wordpress/*` - WordPress integration for content publishing
- `/api/requirement/*` - Core funding opportunity processing
- `/admin/qa-review` - Quality assurance review interface

### Deployment Ready
- Railway-compatible PORT binding in Dockerfile
- Comprehensive environment variable documentation
- Production health checks and monitoring
- Graceful error handling and logging
- Self-contained static assets (no external CDNs)

### Known Limitations
- Proposal template generation requires further testing
- Some test dependencies require manual installation for full CI/CD
- WordPress integration requires valid credentials for publishing features
