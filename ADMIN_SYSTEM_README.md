# 🔐 ReqAgent Admin System

A secure, role-based administrative interface for managing funding opportunities, generating content, and analyzing system performance.

## 🚀 Features

### Core Security Features
- ✅ **Bcrypt Password Hashing**: Industry-standard password security
- ✅ **Email-based Access Control**: Only authorized emails can access admin functions  
- ✅ **Session Management**: Secure token-based authentication with expiration
- ✅ **CSRF Protection**: Protection against cross-site request forgery attacks
- ✅ **Role-based Access**: Superuser and regular admin role support
- ✅ **Secure Cookies**: HttpOnly, SameSite protection

### Admin Interface Features
- 📊 **Comprehensive Dashboard**: Overview of system statistics and recent activity
- 📋 **QA Review System**: Review and approve parsed funding opportunities
- 📄 **Proposal Template Generator**: Create customized .docx proposal templates
- 🤖 **Blog Post Generator**: AI-powered content generation with SEO optimization
- 📝 **WordPress Publisher**: Direct publishing to WordPress as drafts
- 📊 **Feedback Analytics**: Track QA edits and system improvements
- ⚙️ **Settings Management**: System configuration (coming soon)

## 🏗️ Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file with:

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost/reqagent

# Security
SECRET_KEY=your-very-secure-secret-key
CSRF_SECRET_KEY=another-secure-key
AUTHORIZED_EMAILS=admin@yourorg.com,qa@yourorg.com,manager@yourorg.com

# Default Admin (optional)
DEFAULT_ADMIN_EMAIL=admin@yourorg.com
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=secure_password_123

# OpenAI (for content generation)
OPENAI_API_KEY=your-openai-api-key

# WordPress Integration (optional)
WP_API_URL=https://yoursite.com/wp-json/wp/v2
WP_USERNAME=your-wp-username
WP_APPLICATION_PASSWORD=your-wp-app-password
```

### 3. Set Up Database
```bash
# Run the FastAPI app to create tables
python main.py

# Or run database migration
python -c "from db import engine; from models import Base; Base.metadata.create_all(bind=engine)"
```

### 4. Create Your First Admin User
```bash
python setup_admin.py
```

Follow the interactive prompts to create your admin account.

### 5. Start the Application
```bash
uvicorn main:app --reload --port 8000
```

### 6. Access Admin Interface
Navigate to: `http://localhost:8000/admin/login`

## 🔑 Authentication System

### Email Authorization
Only emails listed in `AUTHORIZED_EMAILS` can create admin accounts:

```bash
AUTHORIZED_EMAILS=admin@company.com,qa-lead@company.com,manager@company.com
```

### User Roles
- **Regular Admin**: Can access all admin functions
- **Superuser**: Additional privileges for user management (future feature)

### Session Security
- Sessions expire after 24 hours
- Secure, signed tokens prevent tampering
- HttpOnly cookies prevent XSS attacks
- CSRF tokens protect against form attacks

## 📊 Admin Dashboard

The main dashboard provides:

### Statistics Overview
- Total funding opportunities
- Opportunities pending review
- Reviewed opportunities  
- Approved opportunities

### Recent Activity
- Latest parsed opportunities
- Status tracking
- Creation timestamps

### Quick Access Links
- QA Review interface
- Template generator
- Content creation tools
- Analytics dashboard

### System Status
- Implementation progress
- Feature availability
- TODO items

## 🛠️ Admin Functions

### 1. QA Review (`/admin/qa-review`)
**Purpose**: Review and approve AI-parsed funding opportunities

**Features**:
- View all raw opportunities needing review
- Edit extracted data inline
- Provide feedback on AI parsing accuracy
- Approve opportunities for content generation
- Track confidence scores and extraction warnings

**Workflow**:
1. View list of unreviewed opportunities
2. Click to expand and review details
3. Edit any incorrect information
4. Submit changes (automatically captures feedback)
5. Opportunity status changes to "reviewed"

### 2. Proposal Template Generator (`/admin/proposal-template/start`)
**Purpose**: Create customized .docx proposal templates

**Features**:
- Select from approved funding opportunities
- Define custom sections with headings and instructions
- Add funder-specific notes
- Generate professional .docx documents
- Download templates for proposal writing

**Usage**:
1. Select a funding opportunity
2. Add custom sections (heading + instruction text)
3. Include any special funder notes
4. Generate and download .docx template

### 3. Blog Post Generator (API-based)
**Purpose**: Generate SEO-optimized blog posts from funding opportunities

**API Endpoints**:
```bash
# Generate blog post
POST /api/generate-post
{
  "record_id": 123,
  "seo_keywords": ["nonprofit funding", "grants"],
  "tone": "professional",
  "length": "medium",
  "extra_instructions": "Focus on small nonprofits"
}

# Test record data
GET /api/generate-post/test/{record_id}
```

### 4. WordPress Publisher (API-based)
**Purpose**: Publish generated content directly to WordPress

**API Endpoints**:
```bash
# Publish to WordPress
POST /api/wordpress/publish
{
  "post_title": "New Funding Opportunity",
  "post_content": "<h2>Overview</h2><p>Content...</p>",
  "tags": ["funding", "grants"],
  "categories": ["Funding Opportunities"],
  "meta_title": "SEO Title",
  "meta_description": "SEO description",
  "opportunity_url": "https://funder.com/opportunity"
}

# Test connection
GET /api/wordpress/test-connection
```

### 5. Feedback Analytics (`/admin/feedback/stats`)
**Purpose**: Analyze QA feedback patterns to improve AI parsing

**Features**:
- Track most frequently edited fields
- Monitor parsing accuracy trends
- Identify common AI mistakes
- Export feedback data for training

## 🔒 Security Best Practices

### Environment Variables
- Use strong, unique secret keys
- Rotate keys regularly
- Never commit secrets to version control

### Email Configuration
- Limit authorized emails to trusted personnel
- Use corporate email addresses
- Regularly review access list

### Password Policy
- Minimum 8 characters
- Include special characters, numbers
- Avoid common passwords
- Regular password updates

### Production Deployment
```bash
# Set secure cookies in production
SECURE_COOKIES=true

# Use HTTPS
SSL_REDIRECT=true

# Monitor sessions
SESSION_MONITORING=true
```

## 🛡️ CSRF Protection

All admin forms include CSRF protection:

```html
<!-- Forms automatically include CSRF tokens -->
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

JavaScript requests:
```javascript
// Get CSRF token
function getCSRFToken() {
    return document.getElementById('csrf-token').value;
}

// Include in requests
fetch('/api/endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCSRFToken()
    },
    body: JSON.stringify(data)
});
```

## 📊 Database Schema

### AdminUser Table
```sql
CREATE TABLE admin_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    username VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 🔧 API Integration

### Authentication Headers
For API access, include session cookie or token:

```bash
# Cookie-based (from browser)
Cookie: admin_session=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...

# Header-based (for scripts)
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Error Handling
```json
{
    "error": "Authentication required",
    "status_code": 401,
    "redirect": "/admin/login"
}
```

## 📱 Mobile Responsiveness

The admin interface is fully responsive:
- Mobile-friendly navigation
- Touch-optimized controls
- Responsive grid layouts
- Mobile form inputs

## 🚀 Future Enhancements

### Planned Features
- [ ] Advanced user management UI
- [ ] Role-based permission system
- [ ] Audit logging system
- [ ] Two-factor authentication
- [ ] API key management
- [ ] Advanced analytics dashboard
- [ ] Automated backup system
- [ ] Integration management UI

### Settings Panel (Coming Soon)
- User management
- System configuration
- Integration settings
- Security settings
- Backup management

## 🛠️ Troubleshooting

### Common Issues

**Login fails with "unauthorized email"**
- Check `AUTHORIZED_EMAILS` environment variable
- Ensure email is spelled correctly
- Restart application after changing environment variables

**Database connection errors**
- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL is running
- Check database permissions

**CSRF token errors**
- Clear browser cookies
- Ensure JavaScript is enabled
- Check if CSRF tokens are being included in forms

**Session expires quickly**
- Check system clock accuracy
- Verify `SECRET_KEY` hasn't changed
- Clear old sessions

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug mode
uvicorn main:app --reload --log-level debug
```

### Reset Admin Access
```bash
# If locked out, reset via script
python setup_admin.py

# Or directly via database
psql $DATABASE_URL -c "UPDATE admin_users SET is_active = true WHERE email = 'your@email.com';"
```

## 📞 Support

For issues with the admin system:

1. Check this documentation
2. Review application logs
3. Check database connectivity
4. Verify environment variables
5. Test with a fresh admin user

## 🔄 Updates and Maintenance

### Regular Tasks
- [ ] Review authorized email list monthly
- [ ] Update dependencies quarterly
- [ ] Rotate secret keys annually
- [ ] Backup database weekly
- [ ] Monitor failed login attempts
- [ ] Review admin user activity

### Security Updates
- Monitor for security patches
- Update dependencies regularly
- Review access logs
- Audit user permissions

---

**🎉 Congratulations!** You now have a secure, feature-rich admin interface for managing your ReqAgent system. 