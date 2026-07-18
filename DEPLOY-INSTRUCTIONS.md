# Deploy Instructions — sanctionsai.dev AI Discoverability Assets

## Overview

All 11 AI-discoverability assets have been added to the `~/workspace/agentmail` repo (the app that powers sanctionsai.dev).
Most assets are served inline from `api.py` (stdlib HTTP server routes). A few are static files on disk.

Deploy with a single Fly.io deployment — no config changes needed.

---

## Files Created / Modified

### Inline routes in `api.py` (deployed with code — deploy any time):

| Route | What | Status |
|-------|------|--------|
| `/llms.txt` | Already existed (`_llms_txt` method). Expanded with full tools and data sources. **No change needed.** | ✅ Already live |
| `/llms-full.txt` | Already existed (`_llms_full_txt` method). Full doc for RAG ingestion. **No change needed.** | ✅ Already live |
| `/robots.txt` | **🔥 UPGRADED.** Now AI-bot-friendly: explicitly allows all AI crawlers to `/docs`, `/api`, `/blog/`, `/guides/`, `/llms.txt`, `/agents.md`, `/openapi.json`, `/.well-known/`, `/feed.xml`. Only blocks `/checkout/`, `/dashboard`, `/start`, `/squeeze`, `/keys/`, `/webhooks/`. | ✅ Updated |
| `/agents.md` | **🔥 NEW.** Root-level agent entry point. Describes all 4 tools, quick start, plans, and links. | ✨ Added |
| `/.well-known/agent-card.json` | Already existed (A2A protocol card). **No change needed.** | ✅ Already live |
| `/.well-known/mcp.json` | Already existed (MCP server manifest). **No change needed.** | ✅ Already live |
| `/.well-known/ai-plugin.json` | Already existed (ChatGPT plugin manifest). **No change needed.** | ✅ Already live |
| `/.well-known/agents.md` | Already existed (public agents.md). **No change needed.** | ✅ Already live |
| `/manifest.webmanifest` | Already existed (PWA manifest). **No change needed.** | ✅ Already live |
| `/feed.xml` and `/rss.xml` | **🔥 NEW.** RSS 2.0 feed with 5 items: OFAC penalties guide, wallet screening guide, KYA explainer, x402 compliance, agent compliance checklist. Both routes serve the same feed. | ✨ Added |
| `/openapi.json` | Already existed (OpenAPI 3.0 spec). **No change needed.** | ✅ Already live |

### Static files on disk (placed at project root for reference):

| File | Purpose |
|------|---------|
| `~/workspace/agentmail/llms.txt` | Updated from stub to full content matching `_llms_txt()` handler |
| `/87aaa199acaf7d14c812e974ce115e32.txt` (route) | IndexNow key — served dynamically by `api.py` (`_serve_text`), **not** a file on disk; submit to IndexNow after deploy |

---

## Deploy Steps

```bash
# 1. Change to the app directory
cd ~/workspace/agentmail

# 2. Deploy to Fly.io
flyctl deploy

# 3. Verify the new endpoints respond
curl -sI https://sanctionsai.dev/agents.md | head -1
curl -sI https://sanctionsai.dev/robots.txt | head -3
curl -sI https://sanctionsai.dev/feed.xml | head -1
curl -sI https://sanctionsai.dev/rss.xml | head -1

# 4. Submit IndexNow
# IndexNow tells search engines (Bing, Yandex, etc.) to reindex immediately
curl -X POST "https://api.indexnow.org/IndexNow" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sanctionsai.dev",
    "key": "87aaa199acaf7d14c812e974ce115e32",
    "keyLocation": "https://sanctionsai.dev/87aaa199acaf7d14c812e974ce115e32.txt",
    "urlList": [
      "https://sanctionsai.dev/",
      "https://sanctionsai.dev/llms.txt",
      "https://sanctionsai.dev/agents.md",
      "https://sanctionsai.dev/robots.txt",
      "https://sanctionsai.dev/openapi.json",
      "https://sanctionsai.dev/feed.xml",
      "https://sanctionsai.dev/rss.xml",
      "https://sanctionsai.dev/.well-known/agent-card.json",
      "https://sanctionsai.dev/.well-known/mcp.json",
      "https://sanctionsai.dev/.well-known/ai-plugin.json",
      "https://sanctionsai.dev/.well-known/agents.md",
      "https://sanctionsai.dev/manifest.webmanifest"
    ]
  }'

# 5. (Optional) Also submit via Bing Webmaster Tools
# Go to https://www.bing.com/webmaster/ and verify sanctionsai.dev
# Then use the "URL Submission" tool with the IndexNow key
```

---

## Verification Checklist

After deploy, confirm each endpoint returns the correct content type:

```bash
echo "=== robots.txt ==="
curl -s https://sanctionsai.dev/robots.txt | head -5

echo "=== agents.md ==="
curl -s https://sanctionsai.dev/agents.md | head -5

echo "=== feed.xml ==="
curl -s https://sanctionsai.dev/feed.xml | head -5

echo "=== rss.xml ==="
curl -s https://sanctionsai.dev/rss.xml | head -5

echo "=== IndexNow key ==="
curl -s https://sanctionsai.dev/87aaa199acaf7d14c812e974ce115e32.txt

echo "=== Existing assets (should still work) ==="
curl -sI https://sanctionsai.dev/.well-known/agent-card.json | grep content-type
curl -sI https://sanctionsai.dev/.well-known/mcp.json | grep content-type
curl -sI https://sanctionsai.dev/.well-known/ai-plugin.json | grep content-type
curl -sI https://sanctionsai.dev/.well-known/agents.md | grep content-type
curl -sI https://sanctionsai.dev/manifest.webmanifest | grep content-type
curl -sI https://sanctionsai.dev/openapi.json | grep content-type
```

---

## Rollback

If something goes wrong, the previous deploy is still on Fly.io:

```bash
flyctl deploy --local-only  # re-deploy from last working commit
# OR
flyctl releases rollback    # roll back to the last release
```
