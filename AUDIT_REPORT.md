# NGOInfo Requirement Agent — Full Repository Audit

**Date:** 2026-02-23
**Auditor:** Technical Architect Review
**Repository:** mycrivo/ngoinfo-requirement-agent
**Branch audited:** master (all files)

---

## 1.1 What the Original Agent Was Trying to Do

### Intended Workflow

The agent is a **FastAPI web service** (deployed on Railway via Docker) that:

1. **Accepts a donor grant page URL** via `POST /api/requirement/parse`
2. **Scrapes the page** using Playwright (headless Chromium) with intelligent DOM section extraction
3. **Sends the scraped content to OpenAI** (GPT-3.5-turbo, using the legacy `openai==0.28.1` SDK) with a structured extraction prompt
4. **Returns a JSON object** with standardised funding opportunity fields (title, donor, summary, amount, deadline, location, eligibility, themes, etc.)
5. **Stores the result in PostgreSQL** (via SQLAlchemy) with a status workflow: `raw → reviewed → approved → rejected`
6. **Provides a QA admin dashboard** (Jinja2 HTML templates) where a human reviewer can inspect, edit, and approve parsed opportunities
7. **Generates blog posts** from approved opportunities using OpenAI GPT-4 (`POST /api/generate-post`)
8. **Publishes to WordPress** as a draft post via the REST API (`POST /api/wordpress/publish`), including RankMath SEO meta fields
9. **Generates .docx proposal templates** from approved opportunities (`POST /admin/proposal-template/generate`)
10. **Captures QA feedback** on AI-generated content to track editing patterns over time

### Trigger Mechanism

- **Manual/API-driven**: No scheduler, no cron, no webhook listener. Every action is triggered by a human hitting an API endpoint or using the admin dashboard.
- There is no automated pipeline — a human must call each step sequentially.

### APIs/Tools Called

| Tool | Usage | File |
|------|-------|------|
| **Playwright** (headless Chromium) | Web scraping with DOM section extraction | `utils/openai_parser.py` |
| **OpenAI GPT-3.5-turbo** | Funding opportunity data extraction from scraped text | `utils/openai_parser.py` |
| **OpenAI GPT-4** | Blog post generation from structured funding data | `routes/generate_post.py` |
| **WordPress REST API** | Publishing draft posts with RankMath SEO fields | `routes/publish.py` |
| **PostgreSQL** (via SQLAlchemy) | Storing opportunities, blog posts, feedback, admin users | `db.py`, `models.py` |
| **BeautifulSoup** | HTML word counting, response sanitisation | `routes/generate_post.py` |
| **python-docx** | Generating .docx proposal templates | `routes/proposal_template.py` |
| **bcrypt** | Admin password hashing | `utils/auth.py` |
| **httpx** | Legacy web fetching (in `requirement-agent/` subfolder only) | `requirement-agent/utils/openai_parser.py` |

### Output Produced

- A JSON object with ~15 funding opportunity fields stored in PostgreSQL
- An HTML blog post (generated via OpenAI) stored in the `blog_posts` table
- A WordPress draft post with RankMath SEO metadata
- A downloadable .docx proposal template

---

## 1.2 What Is Broken and Why

### Critical Breaks

#### 1. OpenAI SDK Version Lock (FATAL)

**Files:** `utils/openai_parser.py:519-528`, `routes/generate_post.py:281-295`, `requirement-agent/utils/openai_parser.py:140-151`

The entire repo pins `openai==0.28.1` and uses the **deprecated** `openai.ChatCompletion.create()` API. This SDK version:
- Is no longer maintained
- Does not support the current OpenAI API response format
- Will fail at runtime if the OpenAI API has deprecated the v1/chat/completions endpoint for this client version
- Cannot use newer models (GPT-4-turbo, GPT-4o, o1, o3)
- Uses `openai.api_key = os.getenv()` global state instead of client instantiation

**Impact:** Blog generation and URL parsing both call this deprecated API. Both will fail.

#### 2. Pydantic v1 Pinned (BREAKING with FastAPI)

**File:** `requirements.txt` (line 10: `pydantic==1.10.13`)

`pydantic==1.10.13` is pinned alongside `fastapi==0.103.2`. While FastAPI 0.103.2 supports Pydantic v1, this creates a hard ceiling — upgrading FastAPI or any dependency that requires Pydantic v2 is impossible. The code uses `orm_mode = True` (Pydantic v1) instead of `model_config` (Pydantic v2).

**Impact:** Dependency upgrade path is blocked. Any new library requiring Pydantic v2 will conflict.

#### 3. requirements.txt is UTF-16 Encoded

**File:** `requirements.txt`

The file contains null bytes between every character (visible in the raw read: `f a s t a p i = = 0 . 1 0 3 . 2`). This is UTF-16 encoding. `pip install -r requirements.txt` will fail on most systems because pip expects UTF-8.

**Impact:** The Docker build (`pip install --no-cache-dir -r requirements.txt`) will fail or install nothing, making the container non-functional.

#### 4. Duplicate Codebase (Confusing)

**Directory:** `requirement-agent/` (subfolder)

There is a complete older version of the parser inside `requirement-agent/`. It has its own `utils/openai_parser.py` (using httpx instead of Playwright) and its own `routes/requirement_agent.py`. This older version uses different function signatures (`parse_funding_opportunity(text)` with 1 arg vs `parse_funding_opportunity(text, url)` with 2 args).

The root-level code imports from the root-level `utils/`, not from `requirement-agent/`. The subfolder is dead code that creates confusion.

**Impact:** Developers cannot tell which is the "real" code. The subfolder's `test_parser.py` imports from `utils.openai_parser` but would resolve differently depending on working directory.

#### 5. test_admin_system.py References Non-Existent `AuthService` Class

**File:** `test_admin_system.py:19` — `from utils.auth import AuthService, AuthService`

The current `utils/auth.py` has no `AuthService` class. It exposes standalone functions (`verify_admin_credentials`, `require_login`, etc.). The test file imports a class that does not exist and will crash on import.

**Impact:** All admin system tests are non-functional.

#### 6. setup_admin.py References Non-Existent `AuthService` Class

**File:** `setup_admin.py:22` — `from utils.auth import AuthService`

Same issue. The admin setup script cannot run.

#### 7. No .env File or .env.example

There is no `.env.example` or documentation of required environment variables in the repo. The required variables (scattered across code) are:

- `OPENAI_API_KEY`
- `DATABASE_URL` (or `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`)
- `WP_API_URL`, `WP_USERNAME`, `WP_APPLICATION_PASSWORD`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`
- `SECRET_KEY`
- `AUTHORIZED_EMAILS` (referenced in test code but not in auth.py)

**Impact:** No developer can set up the project without reading every source file.

#### 8. CORS Wildcard in Production

**File:** `main.py:44` — `allow_origins=["*"]`

This allows any domain to call the API. Combined with session-based auth, this is a security vulnerability.

### Architectural Issues (Design Problems)

#### 9. No Content Quality Gate Before WordPress Publish

The WordPress publish endpoint (`POST /api/wordpress/publish`) accepts any title and HTML content. There is zero validation that the content meets any quality standard — no word count check, no banned phrase scan, no schema validation. A malformed or empty post can be pushed to WordPress.

#### 10. No Automation / Pipeline Orchestration

Every step (parse → review → generate → publish) requires a separate manual API call. There is no end-to-end pipeline, no scheduler, and no webhook integration. This means the agent cannot operate autonomously.

#### 11. Blog Generation Schema Does Not Match Target

The `BlogPostGenerator` in `routes/generate_post.py` generates free-form HTML with an OpenAI prompt. It does **not** produce structured JSON matching any defined schema. The output is raw HTML with no guaranteed section structure, no SEO field validation, and no post_content_html structure enforcement.

#### 12. RankMath Focus Keyword is Empty

**File:** `routes/publish.py:431` — `'rank_math_focus_keyword': ''`

The focus keyword is hardcoded to an empty string. This defeats the purpose of SEO integration.

#### 13. No Slack Notification

There is no Slack integration anywhere in the codebase.

#### 14. No Google Sheets Logging

There is no Google Sheets integration anywhere in the codebase.

#### 15. Scraper is Playwright-Only (Heavy, Fragile)

The scraper launches a full headless Chromium browser for every URL. This:
- Requires ~400MB of browser binaries in the Docker image
- Takes 5-15 seconds per page
- Fails on many sites that require JavaScript interaction beyond simple page load
- Cannot handle PDFs, which many grant pages link to

#### 16. db.py Prints Credentials to stdout

**File:** `db.py:12-17` — Loops through all environment variables starting with `PG` or `DATABASE` and prints them. While passwords are masked, this is a security anti-pattern in production logs.

---

## 1.3 What Is Salvageable

### HIGH Value — Worth Keeping

| Component | File | What It Does | Reuse Notes |
|-----------|------|-------------|-------------|
| **WordPress Publisher class** | `routes/publish.py:20-484` | Well-structured WP REST API client with auth, validation, error handling, URL construction logic, category lookup | Needs: empty focus keyword fixed, schema validation added before publish. ~80% reusable. |
| **Database models** | `models.py` | Clean SQLAlchemy models for FundingOpportunity, BlogPost, Feedback tables | Needs: schema fields expanded to match new CONTENT_STANDARD. ~60% reusable. |
| **QA status workflow** | `models.py:6-9` + `routes/requirement_agent.py` | `raw → reviewed → approved → rejected` lifecycle. Duplicate detection by URL. | Directly reusable. |
| **Feedback capture service** | `utils/feedback_service.py` | Tracks field-level diffs between original AI output and QA edits | Directly reusable for prompt improvement loop. |
| **Admin auth (concept)** | `utils/auth.py` | bcrypt hashing, session management, CSRF tokens | Implementation is functional but `AuthService` class was removed — needs cleanup. |

### MEDIUM Value — Partially Reusable

| Component | File | What It Does | Reuse Notes |
|-----------|------|-------------|-------------|
| **Extraction prompt structure** | `utils/openai_parser.py:372-398` | Structured field extraction prompt with confidence scoring | Prompt text is generic. Needs complete rewrite to match CONTENT_STANDARD schema. The *approach* (sectioned extraction → LLM → validation) is sound. |
| **Post-LLM validation logic** | `utils/openai_parser.py:402-459, 552-629` | Field completeness checking, confidence scoring, retry logic for low-quality fields | The validation *pattern* is good. Implementation needs rewrite for new schema. |
| **Blog post prompt** | `routes/generate_post.py:143-253` | Detailed prompt for generating blog posts with word count targets, tone instructions, SEO keywords | Prompt quality is mediocre — produces generic AI content. Needs complete rewrite per CONTENT_STANDARD. |
| **Input sanitisation** | `routes/generate_post.py:29-78` | Strips control characters from strings before sending to OpenAI | Utility functions are clean and reusable as-is. |
| **Pydantic schemas** | `schemas.py` | Request/response models for all endpoints | Needs significant expansion for new JSON schema. ~30% reusable. |

### LOW Value — Delete

| Component | File | Reason |
|-----------|------|--------|
| `requirement-agent/` entire subfolder | All files within | Dead code. Older version with different API. Causes confusion. |
| `test_admin_system.py` | Root | Imports non-existent `AuthService`. Cannot run. |
| `setup_admin.py` | Root | Imports non-existent `AuthService`. Cannot run. |
| `test_enhanced_parser.py` | Root | Tests are useful conceptually but call deprecated OpenAI API. |
| `requirement-agent/test_parser.py` | Subfolder | Dead code. |
| `requirement-agent/validate_env_encoding.py` | Subfolder | Utility script, not part of app. |
| `requirement-agent/validate_openai_setup.py` | Subfolder | Tests deprecated OpenAI SDK. |
| `generate_password_hash.py` | Root | One-time utility. Leaks admin email in source code (line 38: `mailps20@gmail.com`). |
| `ADMIN_SYSTEM_README.md` | Root | Documents features that don't fully exist (e.g., `AuthService` class). |
| `ENHANCED_PARSER_SUMMARY.md` | Root | Documents the old parser version. |
| `PARSER_IMPROVEMENTS.md` | Subfolder | Documents the even older parser version. |
| `create_blog_posts_table.py` | Root | One-time migration script. Should be handled by proper migrations. |

---

## 1.4 Gap Analysis Against Target Workflow

### Funding Opportunity Post Flow

| Step | Required | Status in Current Repo | Notes |
|------|----------|----------------------|-------|
| **INPUT**: Donor grant URL + geography tag | URL accepted, **no geography tag parameter** | PARTIAL | `ParseRequirementRequest` only has `url: HttpUrl`. No geography field. |
| **STEP 1**: Scrape donor URL, extract clean content | Playwright scraping exists | PRESENT BUT FRAGILE | Works but slow (full browser), no PDF support, no Firecrawl integration. Section extraction is CSS-selector-based and brittle. |
| **STEP 2**: Rewrite into CONTENT_STANDARD JSON schema | OpenAI extraction exists | PRESENT BUT WRONG SCHEMA | Current schema has ~13 flat fields. Target schema has 25+ fields including `amount_min`, `amount_max`, `currency`, `evaluation_criteria`, `required_documents`, `post_content_html`, SEO fields, etc. No overlap on structure. |
| **STEP 3**: POST to WordPress as draft | WordPress publisher exists | PRESENT AND MOSTLY WORKING | Needs: focus keyword fix, schema validation gate, slug generation. |
| **STEP 4**: Set RankMath SEO fields | RankMath meta fields set in WP post | PRESENT BUT INCOMPLETE | `rank_math_focus_keyword` is hardcoded empty. `rank_math_title` and `rank_math_description` are set. |
| **STEP 5**: Log to Google Sheets or database | PostgreSQL logging exists, **no Google Sheets** | PARTIAL | DB logging works. Google Sheets integration is entirely missing. |
| **STEP 6**: Slack notification | **Not implemented** | MISSING | Zero Slack code anywhere. |

### Blog Post Flow

| Step | Required | Status in Current Repo | Notes |
|------|----------|----------------------|-------|
| **INPUT**: Keyword + content brief | Accepts `seo_keywords`, `tone`, `length`, `extra_instructions` | PARTIAL | No explicit "keyword + content brief" input model. The current input is tied to an existing `record_id` (funding opportunity), not a standalone keyword. |
| **STEP 1**: Generate 1200+ word SEO blog post | OpenAI GPT-4 generation exists | PRESENT BUT LOW QUALITY | Uses deprecated OpenAI SDK. Prompt produces generic AI content with no voice/tone control per CONTENT_STANDARD. Word count validation exists but is approximate. |
| **STEP 2**: POST to WordPress with RankMath | WordPress publisher exists | PRESENT | Same publisher, same RankMath gaps. |
| **STEP 3**: Log and notify | PostgreSQL logging exists, **no notification** | PARTIAL | Blog post saved to DB. No Slack/email notification. |

### Summary of Gaps

| Capability | Status |
|-----------|--------|
| Geography tag input | MISSING |
| CONTENT_STANDARD JSON schema | MISSING (completely different schema) |
| `post_content_html` with enforced section structure | MISSING |
| `amount_min` / `amount_max` / `currency` split fields | MISSING |
| `evaluation_criteria` array | MISSING |
| `required_documents` array | MISSING |
| `seo_focus_keyword` generation | MISSING (hardcoded empty) |
| Quality rejection gate (banned phrases, char limits, HTML validation) | MISSING |
| Standalone blog post generation from keyword (not tied to funding opp) | MISSING |
| Google Sheets logging | MISSING |
| Slack notification | MISSING |
| Firecrawl or modern scraping | MISSING |
| End-to-end pipeline automation | MISSING |
| PDF grant page support | MISSING |

---

## 2. Rebuild vs Repair Recommendation

See **REBUILD_RECOMMENDATION.md** (written separately below).

## 3. Task Plan

See **REBUILD_RECOMMENDATION.md** (written separately below).
