# REBUILD_RECOMMENDATION.md — Repair vs Rebuild Assessment & Task Plan

**Date:** 2026-02-23
**Repository:** mycrivo/ngoinfo-requirement-agent
**Assessment based on:** AUDIT_REPORT.md and CONTENT_STANDARD.md

---

## 1. Verdict: Targeted Rebuild (Repair the Frame, Rebuild the Internals)

**Recommendation: REPAIR the project skeleton — REBUILD the core logic.**

The FastAPI application structure, database models, route organization, admin authentication, and WordPress publisher are architecturally sound. The problems are concentrated in:

1. **Deprecated dependencies** (OpenAI SDK, Pydantic v1)
2. **Wrong output schema** (current fields do not match CONTENT_STANDARD)
3. **Missing features** (quality gates, geography tags, structured HTML, SEO enforcement)
4. **Dead code** (entire `requirement-agent/` subfolder, broken test files)

A full rewrite would discard working components (WordPress publisher, feedback service, QA workflow, admin auth) for no benefit. A targeted rebuild preserves the ~40% of code that works and replaces the ~60% that doesn't.

### What to Keep (Repair)

| Component | Files | Effort |
|-----------|-------|--------|
| FastAPI app skeleton + routing | `main.py`, `routes/__init__.py` | Minor edits |
| Database connection | `db.py` | Remove debug prints |
| Admin authentication | `utils/auth.py` | Working as-is |
| Feedback service | `utils/feedback_service.py` | Working as-is |
| WordPress publisher class | `routes/publish.py` | Moderate edits (fix SEO, add validation gate) |
| Admin templates | `templates/` | Minor edits |
| Docker + Railway config | `Dockerfile`, `railway.json` | Minor edits |
| QA status workflow | `routes/qa_admin.py` | Minor edits |

### What to Rebuild

| Component | Files | Reason |
|-----------|-------|--------|
| SQLAlchemy models | `models.py` | Schema must match CONTENT_STANDARD |
| Pydantic schemas | `schemas.py` | Schema must match CONTENT_STANDARD |
| OpenAI parser | `utils/openai_parser.py` | Deprecated SDK, wrong prompt, wrong output schema |
| Blog post generator | `routes/generate_post.py` | Deprecated SDK, no quality gates, wrong HTML structure |
| Parsing route handler | `routes/requirement_agent.py` | Must support geography_tag, new schema, quality routing |
| requirements.txt | `requirements.txt` | Upgrade OpenAI SDK, Pydantic v2, fix encoding |

### What to Delete

| Item | Reason |
|------|--------|
| `requirement-agent/` (entire directory) | Dead code — older version with different API signatures |
| `test_admin_system.py` | Imports non-existent `AuthService` class — cannot run |
| `test_enhanced_parser.py` | Uses deprecated OpenAI SDK — must be rewritten |
| `setup_admin.py` | Imports non-existent `AuthService` class — cannot run |
| `create_blog_posts_table.py` | One-time migration script — tables created by app startup |
| `generate_password_hash.py` | Standalone utility with hardcoded email — security risk |
| `PARSER_IMPROVEMENTS.md` (in subfolder) | Documents deleted code |
| `ENHANCED_PARSER_SUMMARY.md` | Documents old parser — superseded by CONTENT_STANDARD |
| `ADMIN_SYSTEM_README.md` | Documents non-existent features (AuthService) |

---

## 2. Task Plan — Ordered Implementation Steps

### Phase 0: Cleanup & Dependency Upgrade (Foundation)

#### Task 0.1: Delete dead code
- **Delete:** `requirement-agent/` directory (entire subtree)
- **Delete:** `test_admin_system.py`, `test_enhanced_parser.py`, `setup_admin.py`
- **Delete:** `create_blog_posts_table.py`, `generate_password_hash.py`
- **Delete:** `ENHANCED_PARSER_SUMMARY.md`, `ADMIN_SYSTEM_README.md`
- **Acceptance:** `git status` shows only deletions. App still starts (no import errors from deleted files).

#### Task 0.2: Fix requirements.txt encoding and upgrade dependencies
- **Rewrite** `requirements.txt` in UTF-8 with upgraded versions:
  ```
  fastapi>=0.109.0,<1.0.0
  uvicorn[standard]>=0.25.0,<1.0.0
  openai>=1.12.0,<2.0.0          # New SDK with client instantiation
  sqlalchemy>=2.0.0,<3.0.0       # SQLAlchemy 2.x
  psycopg2-binary>=2.9.9,<3.0.0
  python-dotenv>=1.0.0,<2.0.0
  requests>=2.31.0,<3.0.0
  beautifulsoup4>=4.12.0,<5.0.0
  pydantic>=2.5.0,<3.0.0         # Pydantic v2
  httpx>=0.25.0,<1.0.0
  jinja2>=3.1.0,<4.0.0
  python-multipart>=0.0.6,<1.0.0
  itsdangerous>=2.1.0,<3.0.0
  playwright>=1.40.0,<2.0.0
  python-docx>=1.1.0,<2.0.0
  bcrypt>=4.1.0,<5.0.0
  ```
- **Acceptance:** `pip install -r requirements.txt` succeeds. No encoding errors.

#### Task 0.3: Create .env.example
- Create `.env.example` documenting all required environment variables with placeholder values.
- **Acceptance:** File lists every env var referenced in the codebase.

---

### Phase 1: Schema Upgrade (Database + Pydantic)

#### Task 1.1: Rewrite models.py to match CONTENT_STANDARD
- Update `FundingOpportunity` model:
  - Add columns: `slug`, `donor`, `summary`, `amount_raw`, `amount_min`, `amount_max`, `currency`, `deadline`, `deadline_raw`, `geography_tag`, `post_content_html`, `seo_focus_keyword`, `seo_title`, `seo_description`, `confidence_score`
  - Keep: `id`, `source_url` (unique), `json_data` (full JSON backup), `status`, `created_at`
  - Convert `editable_text` to `post_content_html`
- Update `BlogPost` model:
  - Add: `slug`, `seo_focus_keyword`, ensure `word_count` is populated
  - Keep existing fields that align with CONTENT_STANDARD
- Migrate Pydantic v1 `orm_mode = True` to Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- **Acceptance:** `Base.metadata.create_all()` succeeds. Models match CONTENT_STANDARD schema.

#### Task 1.2: Rewrite schemas.py to match CONTENT_STANDARD
- Replace `FundingData` with `FundingOpportunitySchema` matching CONTENT_STANDARD fields
- Add `FundingOpportunityCreateRequest` with `url: HttpUrl` and `geography_tag: str`
- Add `ContentValidationResult` schema for quality gate responses
- Update all request/response models to use Pydantic v2 syntax
- **Acceptance:** All schemas validate against CONTENT_STANDARD field rules.

---

### Phase 2: Parser Rebuild (OpenAI Integration)

#### Task 2.1: Rewrite utils/openai_parser.py with new OpenAI SDK
- Replace `openai.ChatCompletion.create()` with `OpenAI().chat.completions.create()`
- Use client instantiation pattern: `client = OpenAI(api_key=...)`
- Update model from `gpt-3.5-turbo` to `gpt-4o-mini` (better extraction, lower cost than GPT-4)
- Rewrite extraction prompt to output CONTENT_STANDARD JSON schema
- Add `geography_tag` extraction (infer from location + donor)
- Split amount into `amount_raw`, `amount_min`, `amount_max`, `currency`
- Extract new fields: `evaluation_criteria`, `required_documents`, `slug`
- Keep: Playwright scraping, sectioned content extraction, validation framework
- **Acceptance:** Parsing a test URL produces JSON conforming to CONTENT_STANDARD. All required fields populated or flagged.

#### Task 2.2: Add content quality validation module
- Create `utils/content_validator.py`:
  - `validate_banned_phrases(html: str) -> list[str]` — returns found banned phrases
  - `validate_html_structure(html: str) -> list[str]` — checks required sections, allowed tags
  - `validate_seo_fields(data: dict) -> list[str]` — checks keyword presence, char limits
  - `validate_word_count(html: str, min_words: int) -> bool`
  - `validate_schema_completeness(data: dict) -> list[str]` — checks all required fields
  - `run_all_validations(data: dict) -> ContentValidationResult`
- **Acceptance:** Validator correctly rejects content with banned phrases, missing sections, or insufficient word count.

---

### Phase 3: Blog Generator Rebuild

#### Task 3.1: Rewrite routes/generate_post.py with new OpenAI SDK
- Replace deprecated `openai.ChatCompletion.create()` with new client pattern
- Rewrite `BlogPostGenerator.create_enhanced_blog_prompt()` to:
  - Enforce CONTENT_STANDARD section structure (Section 2 of CONTENT_STANDARD.md)
  - Include banned phrase list in system prompt ("Never use these phrases: ...")
  - Generate `seo_focus_keyword` from funding data
  - Ensure focus keyword appears in title, description, and first 100 words
- Add post-generation validation:
  - Run `content_validator.run_all_validations()` before saving
  - Retry generation (max 2 retries) if validation fails
  - Return validation errors to caller if all retries exhausted
- **Acceptance:** Generated blog posts pass all validation checks in CONTENT_STANDARD Section 4.

#### Task 3.2: Add `post_content_html` generation to the parsing flow
- After parsing a funding opportunity, auto-generate `post_content_html` using the blog generator
- Store `post_content_html` in the `FundingOpportunity` record
- Implement confidence-based routing:
  - Score >= 80: Generate content and create WP draft automatically
  - Score 60-79: Generate content, save as draft with `[QA-REVIEW]` tag
  - Score < 60: Save to QA dashboard, do not generate content
- **Acceptance:** Parsing a URL with high confidence produces a complete record with `post_content_html` ready for WordPress.

---

### Phase 4: WordPress Publisher Fixes

#### Task 4.1: Fix WordPress publisher SEO and validation
- Fix `rank_math_focus_keyword` — populate from `seo_focus_keyword` field (currently hardcoded empty)
- Add pre-publish validation gate:
  - Run `content_validator.run_all_validations()` before sending to WordPress
  - Block publish if any required validation fails
  - Return detailed error messages
- Add slug support — send `slug` field to WordPress REST API
- Add custom meta fields mapping per CONTENT_STANDARD Section 5
- Resolve tags by name (create if not exist) instead of ignoring them
- **Acceptance:** Published WordPress draft has correct RankMath fields, slug, tags, and categories.

#### Task 4.2: Update publish endpoint schema
- Update `PublishToWordPressRequest` to accept CONTENT_STANDARD fields
- Add response field for validation results (pass/fail with details)
- **Acceptance:** API request/response matches CONTENT_STANDARD WordPress mapping.

---

### Phase 5: Route Handler Updates

#### Task 5.1: Update requirement_agent.py parsing endpoint
- Add `geography_tag` parameter to `POST /api/requirement/parse`
- Update response to return CONTENT_STANDARD-conforming JSON
- Add validation result in response (which checks passed/failed)
- Update `enrich_extracted_data()` to handle new fields
- **Acceptance:** `POST /api/requirement/parse` with URL + geography_tag returns CONTENT_STANDARD JSON.

#### Task 5.2: Update QA review routes
- Update `qa_admin.py` to display new schema fields in QA review
- Add geography_tag display and editing
- Add validation status display (which checks pass/fail)
- **Acceptance:** QA reviewer can see and edit all CONTENT_STANDARD fields.

---

### Phase 6: Security & Operational Fixes

#### Task 6.1: Fix CORS configuration
- Replace `allow_origins=["*"]` with environment variable `ALLOWED_ORIGINS`
- Default to `["http://localhost:3000", "http://localhost:8000"]` for development
- **Acceptance:** CORS only allows configured origins.

#### Task 6.2: Remove credential logging in db.py
- Remove the loop that prints `PG*` and `DATABASE*` environment variables
- Keep only the safe log: `"Database URL configured: postgresql://****@host/db"`
- **Acceptance:** No credentials appear in application logs.

#### Task 6.3: Fix auth.py deprecated time function
- Replace `os.times().elapsed` with `time.time()` for timestamp generation
- **Acceptance:** No deprecation warnings at runtime.

---

### Phase 7: Testing

#### Task 7.1: Create integration test suite
- Create `tests/` directory with:
  - `test_content_validator.py` — unit tests for all validation functions
  - `test_schemas.py` — test Pydantic models validate/reject correctly
  - `test_parser_output.py` — test that parser output matches CONTENT_STANDARD schema
  - `test_wordpress_mapping.py` — test WordPress field mapping
- Add `pytest` and `pytest-asyncio` to requirements.txt
- **Acceptance:** `pytest tests/` passes with >= 80% coverage of new code.

#### Task 7.2: Create test fixtures
- Create `tests/fixtures/` with:
  - `sample_donor_page.html` — realistic donor page HTML
  - `expected_output.json` — expected CONTENT_STANDARD JSON for sample page
  - `invalid_content.json` — content that should fail validation
- **Acceptance:** Fixtures used in test suite, all tests pass.

---

## 3. Implementation Priority & Dependencies

```
Phase 0  ─── (cleanup, deps)
  │
  ▼
Phase 1  ─── (schema: models + pydantic)
  │
  ├──▶ Phase 2  ─── (parser rebuild) ──▶ Phase 3  ─── (blog generator)
  │                                            │
  │                                            ▼
  │                                      Phase 4  ─── (WordPress fixes)
  │
  ├──▶ Phase 5  ─── (route handlers — depends on Phase 1 + 2)
  │
  ├──▶ Phase 6  ─── (security fixes — independent)
  │
  └──▶ Phase 7  ─── (testing — depends on all above)
```

**Critical path:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4

**Parallelizable:** Phase 6 can be done at any time. Phase 5 can start after Phase 1.

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OpenAI SDK upgrade breaks parsing | Medium | High | Test with sample URLs before deploying. Keep old prompt text for reference. |
| Pydantic v2 migration breaks FastAPI | Low | High | FastAPI >= 0.109 fully supports Pydantic v2. Test each endpoint. |
| SQLAlchemy 2.x breaks queries | Low | Medium | Queries are simple. SA 2.x is backward-compatible for basic ORM usage. |
| Database migration loses data | Medium | High | Run `alembic` migration or manual ALTER TABLE. Never DROP TABLE. |
| WordPress REST API changes | Low | Low | WP REST API is stable. Publisher has good error handling. |
| Playwright scraping breaks on site changes | High | Medium | Fallback to body text extraction exists. Consider adding Firecrawl as backup. |

---

## 5. Out of Scope (Future Work)

These features are referenced in the audit but are **not** part of this rebuild plan:

- Google Sheets logging integration
- Slack notification integration
- Firecrawl or alternative scraping integration
- PDF document parsing
- End-to-end pipeline automation (scheduler/cron)
- Admin user management UI
- Alembic database migration framework
- Rate limiting on API endpoints
- Two-factor authentication

These should be addressed in subsequent phases after the core rebuild is stable and tested.
