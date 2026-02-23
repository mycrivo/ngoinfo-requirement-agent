# CONTENT_STANDARD.md — Target JSON Schema & Quality Rules

**Version:** 1.0
**Date:** 2026-02-23
**Applies to:** All AI-generated funding opportunity posts and blog posts published to WordPress

---

## 1. Funding Opportunity JSON Schema

Every funding opportunity parsed from a donor URL **must** produce a JSON object conforming to this schema before it can be published to WordPress.

```json
{
  "title": "string — REQUIRED — Full official name of the funding opportunity",
  "slug": "string — REQUIRED — URL-safe slug derived from title (lowercase, hyphens, max 80 chars)",
  "donor": "string — REQUIRED — Organization, foundation, or agency providing funding",
  "summary": "string — REQUIRED — 2-4 sentence overview of purpose, scope, and impact (150-300 chars)",
  "amount_raw": "string — REQUIRED — Original amount text exactly as stated on the donor page",
  "amount_min": "number|null — Minimum funding amount in base currency units (e.g. 10000 not 10k)",
  "amount_max": "number|null — Maximum funding amount in base currency units",
  "currency": "string — REQUIRED — ISO 4217 currency code: USD, GBP, EUR, etc. Use 'UNSPECIFIED' if unknown",
  "deadline": "string — REQUIRED — ISO 8601 date (YYYY-MM-DD) or 'Rolling' or 'TBD'",
  "deadline_raw": "string — Original deadline text as stated on the donor page",
  "location": ["string — REQUIRED — List of eligible geographies (countries, regions, or 'Global')"],
  "eligibility": ["string — REQUIRED — List of eligible entity types and criteria"],
  "themes": ["string — REQUIRED — List of thematic focus areas / sectors"],
  "duration": "string|null — Project length or funding period (e.g. '12 months', '2-3 years')",
  "how_to_apply": "string|null — Application process summary",
  "published_date": "string|null — ISO 8601 date when the opportunity was announced",
  "contact_info": "string|null — Contact details for inquiries",
  "evaluation_criteria": ["string|null — List of criteria used to evaluate applications"],
  "required_documents": ["string|null — List of documents applicants must submit"],
  "opportunity_url": "string — REQUIRED — Source URL of the original funding page",
  "geography_tag": "string — REQUIRED — Primary geographic classification: one of [Africa, Asia, Europe, Americas, MENA, Global, Pacific]",
  "post_content_html": "string — REQUIRED — Full HTML blog post body (see Section 2)",
  "seo_focus_keyword": "string — REQUIRED — Primary keyword for RankMath (2-5 words)",
  "seo_title": "string — REQUIRED — SEO-optimized title, max 60 chars, includes focus keyword",
  "seo_description": "string — REQUIRED — Meta description, 120-155 chars, includes focus keyword",
  "seo_keywords": ["string — List of 5-10 secondary SEO keywords"],
  "tags": ["string — WordPress tags derived from themes and donor"],
  "categories": ["string — WordPress categories (e.g. 'NGO Grants and Funds', 'Scholarships')"],

  "_confidence_score": "number — 0-100 extraction confidence",
  "_missing_required": ["string — List of required field names that could not be extracted"],
  "_low_quality_fields": ["string — List of fields with uncertain or placeholder values"],
  "_extraction_warning": "string|null — Human-readable warning for QA team",
  "_prompt_version": "string — Version of the extraction prompt used",
  "_parsed_at": "string — ISO 8601 timestamp of when extraction occurred"
}
```

### Field Rules

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `title` | string | Yes | 10-200 chars. Must not be "Unknown" or empty. |
| `slug` | string | Yes | Lowercase, hyphens only, max 80 chars. Auto-generated from title. |
| `donor` | string | Yes | Must not be "Unknown". Organization name only, no URLs. |
| `summary` | string | Yes | 150-300 chars. No HTML. No AI filler phrases (see Section 4). |
| `amount_raw` | string | Yes | Exact text from donor page. |
| `amount_min` | number\|null | No | Positive integer. Null if not determinable. |
| `amount_max` | number\|null | No | Positive integer. >= amount_min. Null if not determinable. |
| `currency` | string | Yes | ISO 4217 code. "UNSPECIFIED" if truly unknown. |
| `deadline` | string | Yes | ISO 8601 (YYYY-MM-DD), "Rolling", or "TBD". |
| `deadline_raw` | string | No | Exact text from donor page. |
| `location` | list[string] | Yes | >= 1 item. Use "Global" if no geographic restriction. |
| `eligibility` | list[string] | Yes | >= 1 item. Each item is a complete eligibility criterion. |
| `themes` | list[string] | Yes | >= 1 item. Each item is a thematic area. |
| `duration` | string\|null | No | Free text. Null if not stated. |
| `how_to_apply` | string\|null | No | Free text, max 500 chars. |
| `published_date` | string\|null | No | ISO 8601 date. |
| `contact_info` | string\|null | No | Email, phone, or URL. |
| `evaluation_criteria` | list[string]\|null | No | Each item is one criterion. |
| `required_documents` | list[string]\|null | No | Each item is one document type. |
| `opportunity_url` | string | Yes | Valid URL. Must match the input URL. |
| `geography_tag` | string | Yes | One of: Africa, Asia, Europe, Americas, MENA, Global, Pacific. |
| `post_content_html` | string | Yes | Valid HTML. See Section 2 for structure. |
| `seo_focus_keyword` | string | Yes | 2-5 words. Must appear in `seo_title`, `seo_description`, and `post_content_html`. |
| `seo_title` | string | Yes | Max 60 chars. Contains focus keyword. |
| `seo_description` | string | Yes | 120-155 chars. Contains focus keyword. |
| `seo_keywords` | list[string] | No | 5-10 keywords. |
| `tags` | list[string] | No | 3-8 tags. |
| `categories` | list[string] | No | 1-3 WordPress categories. |

---

## 2. `post_content_html` Structure

The `post_content_html` field **must** follow this exact section structure. All sections are required unless marked optional.

```html
<h2>Overview</h2>
<p>[2-3 paragraphs summarizing the opportunity, its purpose, and impact. 150-250 words.]</p>

<h2>Funding Details</h2>
<ul>
  <li><strong>Amount:</strong> [amount_raw or formatted range]</li>
  <li><strong>Currency:</strong> [currency]</li>
  <li><strong>Duration:</strong> [duration or "Not specified"]</li>
  <li><strong>Deadline:</strong> [deadline in human-readable format]</li>
</ul>

<h2>Eligibility Criteria</h2>
<ul>
  <li>[One eligibility criterion per list item]</li>
</ul>

<h2>Thematic Focus Areas</h2>
<ul>
  <li>[One theme per list item]</li>
</ul>

<h2>How to Apply</h2>
<p>[Application process description. If required_documents exist, list them here.]</p>

<!-- OPTIONAL: Only include if evaluation_criteria is non-empty -->
<h2>Evaluation Criteria</h2>
<ol>
  <li>[One criterion per list item]</li>
</ol>

<h2>Key Dates</h2>
<ul>
  <li><strong>Deadline:</strong> [deadline in human-readable format]</li>
  <li><strong>Published:</strong> [published_date or "Not specified"]</li>
</ul>

<h2>About the Donor</h2>
<p>[1-2 sentences about the donor organization. Sourced from the donor page, not fabricated.]</p>

<h2>Apply Now</h2>
<p>For full details and to submit your application, visit the official opportunity page: <a href="[opportunity_url]" target="_blank" rel="noopener">[donor name] — [short title]</a>.</p>
```

### HTML Rules

- Use only `<h2>`, `<h3>`, `<p>`, `<ul>`, `<ol>`, `<li>`, `<strong>`, `<em>`, `<a>` tags.
- No `<h1>` tags (WordPress uses the post title as `<h1>`).
- No inline styles or class attributes.
- No `<div>`, `<span>`, `<table>`, `<script>`, or `<iframe>` tags.
- All links must have `target="_blank" rel="noopener"`.
- Minimum total word count: 800 words.
- Maximum total word count: 2500 words.

---

## 3. Blog Post JSON Schema (Standalone)

Standalone blog posts (not tied to a specific funding opportunity) follow the same publication flow but use a simpler input schema:

```json
{
  "title": "string — REQUIRED",
  "slug": "string — REQUIRED",
  "seo_focus_keyword": "string — REQUIRED",
  "seo_title": "string — REQUIRED — max 60 chars",
  "seo_description": "string — REQUIRED — 120-155 chars",
  "seo_keywords": ["string"],
  "post_content_html": "string — REQUIRED — Minimum 1200 words",
  "tags": ["string"],
  "categories": ["string"],
  "tone": "string — One of: professional, persuasive, informal",
  "extra_instructions": "string|null",

  "_prompt_version": "string",
  "_word_count": "number",
  "_generated_at": "string — ISO 8601"
}
```

### Blog Post `post_content_html` Rules

- Minimum 1200 words, target 1500 words.
- Must include the `seo_focus_keyword` in the first 100 words.
- Must include the `seo_focus_keyword` in at least one `<h2>` heading.
- Must have at least 4 `<h2>` sections.
- Must include at least one internal link placeholder: `[INTERNAL_LINK:topic]`.
- Must end with a call-to-action section.

---

## 4. Quality Rejection Rules (Banned Phrases & Validation)

### 4.1 Banned AI Filler Phrases

The following phrases (case-insensitive) must **not** appear in any published content. If detected, the content must be rejected and regenerated:

```
"In today's world"
"In an ever-changing"
"It's worth noting"
"It is important to note"
"In conclusion"
"As we navigate"
"In the realm of"
"Dive into"
"Dive deep"
"Unlock the potential"
"Unlock new"
"Harness the power"
"Game-changer"
"Groundbreaking"
"Revolutionize"
"Cutting-edge"
"Synergy"
"Leverage" (as a verb in marketing context)
"Empower" (when used generically without specific context)
"Holistic approach"
"Paradigm shift"
"Best-in-class"
"World-class"
"Seamlessly"
"Robust" (when describing non-technical concepts)
"Comprehensive guide"
"Everything you need to know"
"Without further ado"
"Let's delve"
"Let's explore"
```

### 4.2 Content Validation Checks

Before publishing to WordPress, every post must pass these checks:

| Check | Rule | Action on Failure |
|-------|------|-------------------|
| **Word count** | `post_content_html` >= 800 words (opportunity) or >= 1200 words (blog) | Reject — regenerate |
| **Banned phrases** | None of the phrases in 4.1 appear | Reject — regenerate |
| **HTML validity** | Only allowed tags (Section 2). No unclosed tags. | Reject — fix HTML |
| **SEO keyword presence** | `seo_focus_keyword` appears in title, description, and content | Reject — regenerate |
| **Section structure** | All required `<h2>` sections present (Section 2) | Reject — regenerate |
| **No placeholder text** | No `[TODO]`, `[PLACEHOLDER]`, `[INSERT]`, `Lorem ipsum` | Reject — regenerate |
| **Link validity** | `opportunity_url` is a valid, reachable URL | Warn — allow with warning |
| **Character limits** | `seo_title` <= 60 chars, `seo_description` 120-155 chars | Reject — fix |
| **Empty required fields** | All REQUIRED fields in schema are non-empty and non-"Unknown" | Reject — cannot publish |
| **Confidence threshold** | `_confidence_score` >= 60 for auto-publish, < 60 requires manual QA | Route to QA |

### 4.3 Confidence Score Thresholds

| Score Range | Action |
|-------------|--------|
| 80-100 | Auto-publish as WordPress draft |
| 60-79 | Publish as draft with `[QA-REVIEW]` tag |
| 40-59 | Route to QA dashboard — do not publish |
| 0-39 | Route to QA dashboard — flag as low quality |

---

## 5. WordPress Publication Mapping

How JSON schema fields map to WordPress REST API fields:

| Schema Field | WordPress Field | Notes |
|-------------|----------------|-------|
| `title` | `title` | Plain text |
| `slug` | `slug` | Auto-generated URL slug |
| `post_content_html` | `content` | Full HTML body |
| `categories` | `categories` | Array of category IDs (resolve by name) |
| `tags` | `tags` | Array of tag IDs (create if not exist) |
| `seo_title` | `meta.rank_math_title` | RankMath SEO title |
| `seo_description` | `meta.rank_math_description` | RankMath meta description |
| `seo_focus_keyword` | `meta.rank_math_focus_keyword` | RankMath focus keyword |
| `opportunity_url` | `meta.opportunity_source_url` | Custom field |
| `geography_tag` | `meta.geography_tag` | Custom field |
| `donor` | `meta.donor_name` | Custom field |
| `deadline` | `meta.deadline` | Custom field |
| `amount_raw` | `meta.funding_amount` | Custom field |
| — | `status` | Always `"draft"` |

---

## 6. Differences from Current Implementation

| Aspect | Current State | Target State |
|--------|--------------|--------------|
| Amount field | Single `amount` string | Split: `amount_raw`, `amount_min`, `amount_max`, `currency` |
| Location field | String (joined from list) | Always `list[string]` |
| Eligibility/Themes | Sometimes string, sometimes list | Always `list[string]` |
| Geography tag | Not implemented | Required: one of 7 regions |
| `post_content_html` | Free-form AI HTML | Enforced section structure (Section 2) |
| SEO focus keyword | Hardcoded empty string | Required, validated in title/desc/content |
| Slug | Not generated | Required, auto-generated from title |
| Evaluation criteria | Not extracted | New optional field |
| Required documents | Not extracted | New optional field |
| Banned phrase check | Not implemented | Required pre-publish gate |
| Word count validation | Approximate, no rejection | Strict, with rejection |
| Confidence routing | Logged but not acted on | Determines publish vs QA routing |
| Blog post structure | No enforced sections | Required section template |
