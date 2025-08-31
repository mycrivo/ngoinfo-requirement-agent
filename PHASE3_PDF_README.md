# 📚 **PHASE 3: PDF RFP INGESTION & PROCESSING**

## **🎯 Overview**

Phase 3 implements comprehensive PDF RFP ingestion capabilities for ReqAgent, enabling users to process funding opportunity documents through URL downloads or file uploads. The system automatically extracts text, parses content into the gold-standard schema, and integrates seamlessly with the existing QA review workflow.

## **🏗️ Architecture**

### **Core Components**

1. **PDF Extraction Service** (`services/pdf_extract.py`)
   - Native text extraction using PyMuPDF and pdfminer.six
   - Optional OCR fallback with multiple backends
   - Confidence scoring and quality assessment

2. **PDF-to-Gold Parser** (`services/pdf_to_gold.py`)
   - Converts extracted text to funding opportunity schema
   - OpenAI integration for intelligent parsing
   - Rule-based fallback parsing
   - Validation and quality metrics

3. **Document Ingestion API** (`routes/documents.py`)
   - URL and file upload endpoints
   - Security validation and rate limiting
   - Integration with existing database models

4. **Storage Integration**
   - Leverages Phase 2 StorageService
   - Persistent PDF and text storage
   - S3-compatible backend support

### **Data Flow**

```
PDF Input (URL/Upload) → Validation → Text Extraction → Gold Standard Parsing → Database Storage → QA Review
     ↓                    ↓              ↓                    ↓                    ↓              ↓
  Security Check    File Validation   Native/OCR        OpenAI/Rules        Funding Opp    Admin UI
```

## **🔧 Configuration**

### **Environment Variables**

```bash
# PDF Processing Configuration
MAX_UPLOAD_MB=20                    # Maximum PDF file size (MB)
MAX_PDF_PAGES=150                   # Maximum pages per PDF
PDF_DOWNLOAD_TIMEOUT=30             # URL download timeout (seconds)
PDF_MAX_REDIRECTS=5                 # Maximum redirects for URL downloads

# OCR Configuration (gated by environment)
OCR_BACKEND=none                    # Options: none, textract, vision, self_hosted
OCR_CONFIDENCE_THRESHOLD=0.7       # Minimum confidence for OCR results

# AWS Textract (if OCR_BACKEND=textract)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Google Cloud Vision (if OCR_BACKEND=vision)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GOOGLE_CLOUD_PROJECT=your-project-id
```

### **Dependencies**

```bash
# Core PDF Processing
PyMuPDF==1.23.8                    # Primary PDF text extraction
pdfminer.six==20231228             # Fallback text extraction
Pillow==10.1.0                     # Image processing for OCR

# Optional OCR Backends (uncomment as needed)
# textract==1.6.5                  # AWS Textract
# google-cloud-vision==3.4.4       # Google Cloud Vision
```

## **🚀 API Endpoints**

### **PDF URL Ingestion**

```http
POST /api/documents/ingest-url
Content-Type: application/x-www-form-urlencoded

url=https://example.com/funding-opportunity.pdf
funding_opportunity_id=123  # Optional: link to existing opportunity
```

**Response:**
```json
{
  "success": true,
  "message": "PDF successfully ingested and parsed",
  "document": {
    "document_id": 456,
    "sha256": "abc123...",
    "source": "url",
    "pages": 5,
    "ocr_status": "not_needed",
    "funding_opportunity_id": 123,
    "opportunity": {
      "id": 123,
      "title": "Education Innovation Grant",
      "status": "raw"
    }
  }
}
```

### **PDF File Upload**

```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: [PDF file]
funding_opportunity_id: 123  # Optional
```

**Response:** Same structure as URL ingestion

### **Document Metadata**

```http
GET /api/documents/{document_id}
Authorization: Bearer [admin_token]
```

### **Document Download**

```http
GET /api/documents/{document_id}/download
Authorization: Bearer [admin_token]
```

### **Extracted Text**

```http
GET /api/documents/{document_id}/text
Authorization: Bearer [admin_token]
```

## **🔒 Security Features**

### **Input Validation**
- **File Type**: Only PDF files accepted
- **File Size**: Configurable maximum (default: 20MB)
- **URL Security**: HTTPS only, no data/file URIs
- **Path Traversal**: Prevented through StorageService

### **Authentication & Authorization**
- **RBAC**: Admin-only access to all endpoints
- **Rate Limiting**: 
  - URL ingestion: 5/minute
  - File upload: 3/minute
- **Session Management**: Integrated with existing admin system

### **Audit Logging**
- User actions logged with timestamps
- IP address tracking
- Document processing metrics
- Error logging with context

## **📊 Processing Pipeline**

### **1. Text Extraction**

#### **Native Extraction (Primary)**
- **PyMuPDF**: High-quality text with positioning
- **pdfminer.six**: Fallback extraction
- **Confidence Scoring**: Based on text quality and key terms

#### **OCR Fallback (Optional)**
- **AWS Textract**: Cloud-based OCR with confidence scores
- **Google Vision**: Document text detection
- **Self-hosted Tesseract**: Local OCR processing

### **2. Content Parsing**

#### **OpenAI Integration**
- Uses existing parser prompts for consistency
- Structured JSON output
- Field validation and normalization

#### **Rule-based Fallback**
- Pattern matching for common fields
- Regular expression extraction
- Heuristic-based field identification

### **3. Quality Assessment**

#### **Validation Metrics**
- Required field completeness
- Data quality scoring
- Confidence thresholds
- Extraction engine tracking

## **💾 Storage Strategy**

### **File Organization**
```
storage/
├── pdfs/
│   ├── ab/
│   │   ├── abc123...pdf
│   │   └── abc123...txt
│   └── cd/
│       ├── cde456...pdf
│       └── cde456...txt
└── previews/
    └── abc123-p1.png
```

### **Storage Backends**
- **Local Filesystem**: Development and testing
- **S3-compatible**: Production persistence
- **Automatic Fallback**: Seamless backend switching

## **🧪 Testing**

### **Run Phase 3 Tests**
```bash
# Run comprehensive test suite
make test-phase3

# Or run directly
python test_phase3_pdf.py
```

### **Test Coverage**
- PDF validation and security
- Text extraction accuracy
- OCR backend capabilities
- API endpoint functionality
- Error handling and edge cases
- Integration scenarios

## **📈 Performance & Scalability**

### **Optimization Features**
- **Async Processing**: Non-blocking PDF operations
- **Caching**: Reuse existing document hashes
- **Batch Processing**: Multiple PDFs in sequence
- **Resource Limits**: Configurable timeouts and size limits

### **Railway/Docker Considerations**
- **Lightweight Dependencies**: Minimal system packages
- **OCR Gating**: Optional heavy dependencies
- **Ephemeral Filesystem**: S3 backend recommended
- **Resource Monitoring**: Memory and CPU usage tracking

## **🔍 Monitoring & Observability**

### **Health Checks**
- PDF processing pipeline status
- OCR backend availability
- Storage backend connectivity
- API endpoint responsiveness

### **Metrics & Logging**
- Processing time per document
- Success/failure rates
- OCR usage statistics
- Storage utilization
- Error frequency and types

## **🚨 Error Handling**

### **Common Scenarios**
- **Invalid PDF**: File format validation
- **Download Failures**: Network timeout handling
- **OCR Failures**: Graceful fallback to native extraction
- **Storage Errors**: Retry logic and error reporting
- **Parsing Failures**: Rule-based fallback

### **Error Responses**
```json
{
  "error": "PDF validation failed",
  "detail": "File does not appear to be a valid PDF",
  "status_code": 400
}
```

## **🔧 Development & Debugging**

### **Local Development**
```bash
# Install dependencies
make install

# Run tests
make test-phase3

# Start development server
make run

# Check health
make health-check
```

### **Debug Mode**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
uvicorn main:app --reload --log-level debug
```

## **📚 Usage Examples**

### **Python Client**
```python
import requests

# Ingest PDF from URL
response = requests.post(
    "http://localhost:8000/api/documents/ingest-url",
    data={
        "url": "https://example.com/grant-opportunity.pdf",
        "funding_opportunity_id": 123
    },
    headers={"Authorization": "Bearer admin_token"}
)

# Upload PDF file
with open("grant.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/documents/upload",
        files={"file": f},
        data={"funding_opportunity_id": 123},
        headers={"Authorization": "Bearer admin_token"}
    )
```

### **cURL Examples**
```bash
# URL ingestion
curl -X POST "http://localhost:8000/api/documents/ingest-url" \
  -H "Authorization: Bearer admin_token" \
  -d "url=https://example.com/grant.pdf"

# File upload
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "Authorization: Bearer admin_token" \
  -F "file=@grant.pdf"
```

## **🔮 Future Enhancements**

### **Planned Features**
- **Batch Processing**: Multiple PDFs in single request
- **Advanced OCR**: Layout analysis and table extraction
- **Template Recognition**: Funding opportunity template detection
- **Multi-language Support**: International PDF processing
- **Real-time Processing**: WebSocket progress updates

### **Integration Opportunities**
- **Email Integration**: PDF attachment processing
- **Webhook Support**: External system notifications
- **API Rate Limiting**: Per-user quotas and billing
- **Advanced Analytics**: Processing metrics and insights

## **📋 Troubleshooting**

### **Common Issues**

#### **PDF Extraction Fails**
- Check file format and size
- Verify OCR backend configuration
- Review extraction logs for errors

#### **OCR Not Working**
- Verify backend dependencies installed
- Check API credentials and permissions
- Review OCR configuration in environment

#### **Storage Errors**
- Verify storage backend configuration
- Check disk space and permissions
- Review S3 credentials if using cloud storage

#### **API Authentication**
- Verify admin user setup
- Check session configuration
- Review CORS and security headers

### **Debug Commands**
```bash
# Check PDF processing capabilities
python -c "from services.pdf_extract import pdf_extractor; print(pdf_extractor.ocr_backend)"

# Test storage service
python -c "from services.storage import storage_service; print(storage_service.backend_type)"

# Verify database connectivity
python -c "from db import engine; print(engine.execute('SELECT 1').scalar())"
```

## **📞 Support**

### **Getting Help**
- **Documentation**: Check this README and API docs
- **Logs**: Review application logs for error details
- **Tests**: Run test suite to verify functionality
- **Issues**: Report bugs with detailed error information

### **Contributing**
- Follow existing code patterns
- Add comprehensive tests for new features
- Update documentation for API changes
- Use conventional commit messages

---

**🎉 Phase 3 PDF Processing is now production-ready!**

The system provides robust, secure, and scalable PDF ingestion capabilities while maintaining compatibility with existing ReqAgent infrastructure. Users can now process funding opportunity documents through multiple channels with automatic text extraction, intelligent parsing, and seamless integration into the QA review workflow.





