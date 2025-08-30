# Phase 2: Production-Ready Proposal Templates

## Overview

Phase 2 of ReqAgent implements production-ready proposal template generation with deterministic output, persistent storage, and comprehensive admin integration. This phase transforms the basic template generation into a robust, scalable system suitable for production deployment on Railway.

## 🚀 Key Features

### 1. **Storage Abstraction Layer**
- **Local Storage**: Configurable via `FILE_STORAGE_ROOT` environment variable
- **S3-Compatible Storage**: Automatic fallback to local if S3 credentials unavailable
- **Path Validation**: Prevents path traversal attacks and ensures security
- **Railway Optimized**: Handles ephemeral filesystem gracefully

### 2. **Deterministic Template Engine**
- **Content Model**: Structured data model with consistent sections
- **Hash-Based Deduplication**: SHA256 hashing prevents duplicate generation
- **DOCX Generation**: Professional Word documents with consistent styling
- **PDF Generation**: Dual-engine approach (WeasyPrint + ReportLab fallback)

### 3. **Secure API Endpoints**
- **RBAC Protection**: Admin-only access to all endpoints
- **Rate Limiting**: 10 requests/minute for generation, 5/minute for regeneration
- **Input Validation**: Comprehensive validation and sanitization
- **Audit Logging**: Full request tracking and error logging

### 4. **Admin UI Integration**
- **QA Review Integration**: Template generation directly from funding opportunity review
- **Real-time Status**: Live updates during generation process
- **Download Management**: Direct access to DOCX and PDF files
- **Regeneration Support**: Force regeneration with new content hash

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Admin UI      │    │  Template API    │    │  Storage Layer  │
│   (QA Review)   │◄──►│  (/api/templates)│◄──►│  (Local/S3)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Template Service │
                       │ (Business Logic) │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Content Model    │
                       │ + Hash Engine    │
                       └──────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ DOCX/PDF Gen     │
                       │ (python-docx +   │
                       │  ReportLab)      │
                       └──────────────────┘
```

## 📁 File Structure

```
services/
├── __init__.py
├── storage.py              # Storage abstraction layer
└── template_generator.py   # Template generation engine

routes/
├── templates.py            # New secure API endpoints
└── proposal_template.py    # Legacy admin routes (kept for compatibility)

templates/
└── qa_review.html         # Enhanced with template generation UI
```

## 🔧 Configuration

### Environment Variables

```bash
# Storage Configuration
FILE_STORAGE_ROOT=/mnt/data/generated
PDF_ENGINE=reportlab  # Options: reportlab, weasyprint

# S3 Configuration (Optional)
S3_ENDPOINT=https://your-s3-endpoint.com
S3_BUCKET=your-bucket-name
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

### Railway Considerations

- **Ephemeral Filesystem**: Local storage is temporary across deploys
- **S3 Recommended**: Use S3-compatible storage for production persistence
- **Font Dependencies**: ReportLab uses system fonts (DejaVu recommended)

## 📋 API Endpoints

### Template Generation
```http
POST /api/templates/generate
Content-Type: application/json

{
  "record_id": 123,
  "sections": [
    {
      "heading": "Executive Summary",
      "instruction": "Provide overview of proposal"
    }
  ],
  "funder_notes": "Optional funder requirements"
}
```

### Template Download
```http
GET /api/templates/{id}/download?format=docx
GET /api/templates/{id}/download?format=pdf
```

### Template Metadata
```http
GET /api/templates/{id}
```

### Force Regeneration
```http
POST /api/templates/{id}/regenerate
```

## 🎯 Content Model

### Standard Sections
1. **Executive Summary** - Proposal overview
2. **Organization Background** - NGO capabilities
3. **Problem Statement** - Need identification
4. **Objectives & Outcomes** - Project goals
5. **Activities & Workplan** - Implementation timeline
6. **Monitoring & Evaluation** - Success metrics
7. **Budget Summary** - Financial overview
8. **Sustainability & Risk** - Long-term viability

### Content Hashing
- **Deterministic**: Same input always produces same hash
- **Deduplication**: Prevents duplicate template generation
- **Version Control**: Tracks content changes over time

## 🔒 Security Features

### Authentication & Authorization
- **Session-based Auth**: Admin-only access to all endpoints
- **RBAC**: Role-based access control enforced
- **Rate Limiting**: Prevents abuse and DoS attacks

### Input Validation
- **Path Sanitization**: Prevents directory traversal
- **Content Validation**: Sanitizes all user inputs
- **File Type Validation**: Restricts to safe formats

### Storage Security
- **Path Validation**: All storage paths validated and sanitized
- **S3 Encryption**: Server-side encryption when available
- **Access Control**: Secure file access patterns

## 🧪 Testing

### Test Script
```bash
python test_phase2_templates.py
```

### Test Coverage
- ✅ Storage service functionality
- ✅ Template generation engine
- ✅ Content model and hashing
- ✅ Storage integration
- ✅ PDF generation fallbacks

## 🚀 Deployment

### Railway Deployment
1. **Environment Setup**: Configure storage and S3 variables
2. **Dependencies**: All required packages in requirements.txt
3. **Health Checks**: /health endpoint remains functional
4. **Graceful Degradation**: PDF generation fails gracefully

### Docker Considerations
- **Minimal Dependencies**: No heavy system packages
- **Font Support**: Include DejaVu fonts for PDF generation
- **Storage Mounts**: Use persistent volumes for local storage

## 📊 Monitoring & Observability

### Logging
- **Structured JSON**: Machine-readable log format
- **Request Tracking**: Correlation IDs for debugging
- **Error Classification**: Clear error categories and messages

### Health Checks
- **Storage Health**: Verify storage backend availability
- **PDF Engine**: Check PDF generation capabilities
- **Database**: Template persistence verification

## 🔄 Migration from Phase 1

### Backward Compatibility
- **Legacy Routes**: `/admin/proposal-template/*` routes maintained
- **Database Schema**: No breaking changes to existing tables
- **File Formats**: Same DOCX output format

### New Features
- **Persistent Storage**: Templates saved to database and storage
- **PDF Output**: Additional PDF format support
- **Admin Integration**: Seamless QA review integration
- **API Access**: RESTful API for external integrations

## 🎉 Success Criteria

- [x] Admin can generate templates from QA review page
- [x] Templates persist across application restarts
- [x] Deduplication prevents unnecessary regeneration
- [x] PDF generation works with fallback engines
- [x] All endpoints properly secured and rate-limited
- [x] Comprehensive error handling and logging
- [x] Railway deployment ready with S3 support

## 🚧 Future Enhancements

### Phase 3 Considerations
- **Template Customization**: User-defined section templates
- **Batch Processing**: Bulk template generation
- **Advanced PDF**: Enhanced styling and branding
- **Template Versioning**: Full version control system
- **Collaboration**: Multi-user template editing

### Performance Optimizations
- **Async Generation**: Background template processing
- **Caching**: Template result caching
- **CDN Integration**: Template file distribution
- **Compression**: Optimized file storage

## 📚 Additional Resources

- **API Documentation**: FastAPI auto-generated docs at `/docs`
- **Admin Interface**: `/admin/qa-review` for template management
- **Migration Guide**: See MIGRATIONS.md for database changes
- **Testing**: Run `test_phase2_templates.py` for verification

---

**Phase 2 Status**: ✅ **COMPLETE** - Production-ready proposal template system implemented and tested.

