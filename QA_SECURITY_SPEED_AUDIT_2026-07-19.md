# sanctionsai.dev — QA / Security / Speed Audit
**Date:** 2026-07-19 · **Target:** sanctionsai.dev (Python stdlib `http.server` on Fly.io)
**Scope:** Security headers (all response paths) · Broken links · HTTPS/HSTS · robots.txt AI-bot block
**Method:** `curl -sI` against live host + source review of `api.py`. No dep audit, no Lighthouse, no deploy.

---

## Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| **QA** | **92/100** | 234-URL sitemap clean; 3 `/compare/*` entries list redirecting (not canonical) URLs; `/dashboard` returns 403 (correct, but listed in sitemap) |
| **Speed** | **95/100** | TTFB 155–220 ms globally; gzip active (82 KB→21 KB, 74%); proper `Vary: Accept-Encoding`, long `max-age` on static assets, `Link: rel=preconnect` |
| **Security** | **89/100** | Strong baseline (HSTS preload, CSP, COOP/COEP not needed); gaps on redirect responses and a few non-HTML paths (see below) |

---

## 1. Security Headers — Per Response Path

All paths probed via `curl -sI https://sanctionsai.dev<path>`. Legend: ✅ present · ❌ missing · ➖ N/A.

| Path | Status | CT | XCTO | HSTS | CSP | PERM-POL | XFO | REF-POL | CC | Notes |
|------|--------|----|------|------|-----|----------|-----|---------|----|----|
| `/` (HTML) | 200 | ✅ | ✅ | ✅ preload | ✅ strong | ✅ | ✅ SAMEORIGIN | ✅ | ✅ max-age=60 | Gold-standard. Also X-Robots-Tag, Link preconnect, Accept-CH |
| `/check` (HTML) | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Same as `/` |
| `/pricing`, `/faq`, `/docs`, `/about` etc. (HTML) | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All HTML pages share `_send_html()` — uniform |
| `/this-page-does-not-exist` (HTML 404) | 404 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 404 uses same `_send_html` — **good**, no header regression on errors |
| `/openapi.json` (JSON API) | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ DENY | ✅ | ✅ no-store | CSP missing on JSON — acceptable (CSP is HTML-only) |
| `/health` (JSON) | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ DENY | ✅ | ✅ no-store | Same as above |
| `/dashboard/export` (CSV) | 403* | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ no-store | **Gap:** CSV path omits Permissions-Policy + X-Frame-Options |
| `/dashboard/logs` (JSON 403) | 403 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ DENY | ✅ | ✅ | Via `_json()` — fine |
| `/llms.txt` (text) | 200 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ DENY | ✅ | ✅ max-age=3600 | Permissions-Policy missing on `_serve_text` |
| `/robots.txt` (text) | 200 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ DENY | ✅ | ✅ max-age=3600 | Same |
| `/sitemap.xml` (XML) | 200 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ DENY | ✅ | ✅ max-age=3600 | Same |
| `/feed.xml` (RSS) | 200 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ DENY | ✅ | ✅ max-age=3600 | Same |
| `/og.png` (PNG) | 200 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ max-age=86400 | XFO + PERM-POL missing on `_send_png` |
| `/checkout/dev` (302 → Stripe) | 302 | ➖ | ❌ | ✅ | ➖ | ➖ | ❌ | ✅ | ❌ | **Gap:** 302 redirect omits XCTO, XFO, Cache-Control |
| `/compare/chainalysis` (301 redirect) | 301 | ➖ | ❌ | ❌ | ➖ | ➖ | ❌ | ❌ | ✅ | **Gap:** `HALLUCINATED_REDIRECTS` 301 omits HSTS, XCTO, Referrer-Policy |
| `www.sanctionsai.dev` (301 → apex) | 301 | ➖ | ❌ | ✅ | ➖ | ➖ | ❌ | ❌ | ❌ | HSTS present (good), but XCTO + Referrer-Policy missing |
| `http://sanctionsai.dev` (301 → HTTPS) | 301 | ➖ | ❌ | ❌ | ➖ | ➖ | ❌ | ❌ | ❌ | **Gap:** HTTP→HTTPS 301 omits HSTS (Fly edge handles it, but defense-in-depth missing) |

\* `/dashboard/export` returns 403 without auth (correct). Headers shown are from the 403 response via `_json()`. The **200 CSV path** (code lines 6380–6388) also omits Permissions-Policy and X-Frame-Options — see source review.

### Security header gaps — summary

1. **301 redirects (`HALLUCINATED_REDIRECTS`, lines 1852–1862)** — missing HSTS, X-Content-Type-Options, Referrer-Policy. The 301 response body is empty so XSS risk is nil, but HSTS on redirects is defense-in-depth best practice (a MITM could strip the redirect on first hop).
2. **302 checkout redirect (line 2680–2684)** — missing X-Content-Type-Options, X-Frame-Options, Cache-Control (low risk; redirects to Stripe which has its own headers).
3. **CSV export path (`_wrap_dashboard_export`, line 6380)** — missing Permissions-Policy and X-Frame-Options (the `_json()` helper sets them, but the CSV path writes headers manually and skips them).
4. **`_serve_text` and `_send_png`** — missing Permissions-Policy. X-Frame-Options also missing on PNG. Low risk (text/PNG aren't framable in a dangerous way), but inconsistent with HTML paths.
5. **HTTP→HTTPS 301** — Fly edge issues this without HSTS. HSTS on the plain-HTTP response is non-functional anyway (browsers ignore it on HTTP), so this is informational only.

### What's done well
- **HSTS** with `preload` + `includeSubDomains` on all HTTP/2 responses ✅
- **CSP** is strong: `default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, Stripe/PostHog allowlisted narrowly ✅
- **Permissions-Policy** disables camera, mic, geolocation, payment, USB, browsing-topics, interest-cohort ✅
- **X-Content-Type-Options: nosniff** on every path ✅
- **Referrer-Policy: strict-origin-when-cross-origin** on every path ✅
- **No `Server` version leak** (Fly proxy stamps `Fly/6cc1c2f7c8` — build hash, not Python version) ✅
- **404 pages inherit full security headers** via shared `_send_html()` ✅

---

## 2. Broken Links

**Method:** Extracted all 234 `<loc>` URLs from `/sitemap.xml`, checked each with `curl -s -o /dev/null -w "%{http_code}"`. Also checked 25 internal links from homepage HTML + 4 external links.

### Internal links (homepage nav) — **all good**
Every `href` in the homepage resolves to 200 (or 301→200 for `/compare/*`).

### Sitemap sweep — 234 URLs, 6 flagged, **0 truly broken**

| URL | Status | Verdict |
|-----|--------|---------|
| `/compare/chainalysis` | 301 → `/vs/chainalysis` → 200 | **Sitemap should list `/vs/chainalysis` (canonical), not the redirecting `/compare/` URL.** SEO minor. |
| `/compare/elliptic` | 301 → `/vs/elliptic` → 200 | Same |
| `/compare/complyadvantage` | 301 → `/vs/complyadvantage` → 200 | Same |
| `/compare` | 301 → `/vs/chainalysis` | Same (and `/compare` bare shouldn't be in sitemap) |
| `/cost-of/refinitiv-worldcheck-pricing` | 000 (timeout once) → 200 on retry | Transient, not broken |
| `/dashboard` | 403 | **Correctly auth-gated.** But robots.txt already `Disallow: /dashboard` — sitemap should not list a disallowed URL. SEO contradiction. |

### External links — **all 200**
- `github.com/kindrat86/agentmail` ✅
- `pypi.org/project/sanctions-mcp/` ✅
- `agentmail-api.fly.dev/health` ✅
- `agentmail-api.fly.dev` ✅

**Action:** Update sitemap to (a) replace 4 `/compare/*` entries with `/vs/*` canonicals, (b) remove `/dashboard` (it's robots-disallowed and 403s for crawlers).

---

## 3. HTTPS / HSTS

| Check | Result |
|-------|--------|
| HTTPS valid cert | ✅ Fly managed cert |
| HTTP → HTTPS redirect | ✅ `http://sanctionsai.dev` → 301 → `https://sanctionsai.dev` |
| www → apex redirect | ✅ `www.sanctionsai.dev` → 301 → `https://sanctionsai.dev/` |
| HSTS header | ✅ `max-age=63072000; includeSubDomains; preload` (2 years + preload) |
| HSTS on all paths | ✅ Present on every 200/403/404 (missing only on some 301s — see §1) |
| HSTS preload eligibility | ✅ `max-age` ≥ 1 year, `includeSubDomains`, `preload` keyword all present |

**Verdict:** HTTPS/HSTS is production-grade. Only nit: HSTS not echoed on `HALLUCINATED_REDIRECTS` 301s (defense-in-depth).

---

## 4. robots.txt — FacebookBot + Applebot Block

**Current state:** The deployed `/robots.txt` is **served dynamically** by `api.py` lines 1882–1955 (the static `robots.txt` file on disk at repo root is **not used** — it's stale). The dynamic robots.txt explicitly allowlists 22 AI crawlers but **does NOT include `FacebookBot` or `Applebot`**.

### What's there (deployed)
The robots.txt lists `Applebot-Extended` and `Meta-ExternalAgent`, which are the **training** crawlers for Apple and Meta respectively. The **indexing** crawlers (`Applebot`, `FacebookBot`) are not named. Under `User-agent: *`, only `/checkout/`, `/dashboard`, `/start`, `/squeeze`, `/keys/`, `/webhooks/` are disallowed — so FacebookBot/Applebot technically *can* crawl under the catch-all. **However**, explicit `Disallow:` allowlisting is the strong signal AI crawlers look for, and these two are absent.

### Impact
- **FacebookBot** (Meta's web crawler for link previews / AI training) — not explicitly invited
- **Applebot** (Apple's indexer for Siri/Spotlight/AI overviews) — not explicitly invited. `Applebot-Extended` is a *different* UA (training-only); Apple's indexing bot is just `Applebot`.

### Exact fix
Add these two blocks to the dynamically-served robots.txt in `api.py` (after the `Applebot-Extended` / `Meta-ExternalAgent` entries, around line 1949):

```diff
 User-agent: Applebot-Extended
 Disallow:
+
+User-agent: Applebot
+Disallow:
+
 User-agent: Bingbot
 Disallow:
 User-agent: DuckAssistBot
 Disallow:
 User-agent: Amazonbot
 Disallow:
 User-agent: Bytespider
 Disallow:
 User-agent: Meta-ExternalAgent
 Disallow:
+
+User-agent: FacebookBot
+Disallow:
+
 User-agent: cohere-ai
 Disallow:
 User-agent: YouBot
 Disallow:
```

**File to edit:** `~/workspace/agentmail/api.py` — the `_serve_text("""...robots.txt...""")` block starting at line 1883. Do **not** edit the static `robots.txt` file at repo root (it's dead code).

---

## Appendix — Response Time (Speed)

| Path | TTFB | Size (uncompressed) | Size (gzip) |
|------|------|---------------------|-------------|
| `/` | 218 ms | 82 KB | 21 KB (74% savings) |
| `/pricing` | 217 ms | 13 KB | 3.8 KB |
| `/tools/wallet-checker` | 217 ms | 7.8 KB | — |
| `/llms.txt` | 155 ms | 1.9 KB | — |
| `/openapi.json` | 156 ms | 2.8 KB | — |
| `/sitemap.xml` | 208 ms | 42 KB | — |
| `/check` | 217 ms | 9.1 KB | — |

**Speed notes:**
- TTFB 155–220 ms is excellent for a single-region Fly.io deployment (edge in AMS).
- Gzip conditional on `Accept-Encoding` and only for >1 KB bodies — correct (avoids compressing tiny responses).
- `Vary: Accept-Encoding` present on all HTML ✅ (prevents cache poisoning).
- Static assets (`/og.png`, `/ux.css`, `/ux.js`) cached 24 h ✅.
- `Link: <…>; rel=preconnect` for PostHog + API origin ✅.
- No render-blocking third-party JS visible in headers (Stripe/PostHog loaded async per CSP).
- **Minor:** `/sitemap.xml` (42 KB) and `/feed.xml` could be gzipped for faster transfer — currently served identity. Low priority.

---

## Priority Action List

| # | Issue | Severity | Effort |
|---|-------|----------|--------|
| 1 | Add `FacebookBot` + `Applebot` to robots.txt (dynamic, in `api.py`) | **High** (AI visibility) | 2 lines |
| 2 | Add HSTS + X-Content-Type-Options to `HALLUCINATED_REDIRECTS` 301s | Medium (defense-in-depth) | 2 lines |
| 3 | Add Permissions-Policy + X-Frame-Options to CSV export path (`_wrap_dashboard_export`) | Medium | 2 lines |
| 4 | Fix sitemap: replace `/compare/*` with `/vs/*`, remove `/dashboard` | Low (SEO hygiene) | sitemap builder edit |
| 5 | Add Permissions-Policy to `_serve_text` and `_send_png` for consistency | Low | 2 lines × 2 functions |
| 6 | Gzip `/sitemap.xml` + `/feed.xml` | Low (speed) | small |
