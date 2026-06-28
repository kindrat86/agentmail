# Deployment & Distribution Guide

Step-by-step to take agentmail from "works on my machine" to live and discoverable.
Each section is independent — do them in any order.

---

## 1. Deploy hosted API (Fly.io) — ~10 min, ~$2/mo

The hosted API is what you charge for. Self-host is free; hosted = uptime + audit log + rate limits.

### Prerequisites
```bash
# Install flyctl (macOS)
brew install flyctl
# OR: curl -L https://fly.io/install.sh | sh

# Login (opens browser)
flyctl auth login
```

### Deploy
```bash
cd ~/workspace/agentmail

# Create the app (one-time)
flyctl apps create agentmail

# Create persistent volume for OFAC cache + audit log (one-time)
flyctl volumes create agentmail_data --region fra --size 1

# Set secrets (generates a random API key for yourself)
flyctl secrets set AGENTMAIL_REQUIRE_AUTH=1
flyctl secrets set AGENTMAIL_API_KEYS=$(python3 -c "import secrets; print('sk_live_' + secrets.token_hex(24))")
flyctl secrets set AGENTMAIL_RATE_LIMIT=600
flyctl secrets set AGENTMAIL_FREE_TIER_DAILY=50
flyctl secrets set AGENTMAIL_AUDIT_LOG=/data/audit.jsonl

# Save your API key! (flyctl secrets set doesn't echo it back)
# To see it again: flyctl secrets list (shows names, not values)

# Deploy
flyctl deploy

# Verify
curl https://agentmail.fly.dev/health
curl -H "X-API-Key: YOUR_KEY" https://agentmail.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96
```

### Cost
- `shared-cpu-1x` + 512MB = ~$1.94/mo
- `auto_stop_machines=true` = scales to zero when idle (saves ~70% if low traffic)
- 1GB volume = $0.15/mo
- **Total: ~$2/mo**, break-even at **1 paying customer ($19/mo)**

---

## 2. Register on MCP directories — ~15 min, free

### Smithery (most important — the "npm for MCP")
1. Go to https://smithery.ai/new
2. Sign in with GitHub
3. Paste repo URL: `https://github.com/kindrat86/agentmail`
4. Smithery reads `smithery.yaml` automatically
5. Click Publish
6. Your server appears at `smithery.ai/server/@kindrat86/agentmail`

### mcp.so
1. Go to https://mcp.so/submit
2. Fill: name, repo URL, description, category (Security)
3. Submit

### Glama.ai
1. Go to https://glama.ai/mcp/servers/submit
2. Sign in with GitHub
3. Submit repo URL + description
4. Your badge URL appears: `glama.ai/mcp/servers/kindrat86/agentmail/badges/score.svg`

---

## 3. Publish on PyPI — ~5 min, free

This makes `pip install agentmail` work globally (not just from GitHub).

### Prerequisites
```bash
pip install build twine
# Create PyPI account: https://pypi.org/account/register/
# Create API token: https://pypi.org/manage/account/token/ (scope: "Entire account")
```

### Build + publish
```bash
cd ~/workspace/agentmail

# Clean build
rm -rf dist/ build/ *.egg-info
python -m build

# Check
twine check dist/*

# Upload (paste PyPI token when prompted, username = __token__)
twine upload dist/*

# Verify
pip install agentmail
python -c "import agentmail; print(agentmail.__version__)"
```

After this, update README install line from `git clone + pip install -e .` to just `pip install agentmail[mcp]`.

---

## 4. GitHub Release — ~2 min, free

Makes the repo look maintained and enables version tracking.

```bash
cd ~/workspace/agentmail
git tag -a v0.4.0 -m "v0.4.0: OFAC sanctions + KYA + risk + email/SMS for AI agents"
git push origin v0.4.0

# Then on GitHub: Releases → "Draft a new release" → select tag v0.4.0
# Paste the changelog from git log as release notes
```

Or via CLI:
```bash
gh release create v0.4.0 --repo kindrat86/agentmail \
  --title "v0.4.0 — Compliance toolkit for AI agents" \
  --notes "First public release. Real OFAC sanctions data (782 wallets + 19,086 names), KYA, transaction risk scoring, disposable email/SMS. MCP + HTTP + CLI."
```

---

## 5. Post launches (after registries + deploy)

See `docs/LAUNCH_POSTS.md` for ready-to-paste Show HN + Reddit drafts.

**Timing:**
1. Wait for awesome-mcp-servers PR to merge (so search visitors find you)
2. Wait for hosted API to be live (so "is there a hosted version?" has an answer)
3. Post Tue–Thu, 8–10am ET (best HN front-page odds)
4. Reply to every comment within 2 hours

---

## Quick status checklist

- [x] Public GitHub repo with README
- [x] OSINT compliance provider (real OFAC data)
- [x] Hosted API code (auth + rate limit + audit)
- [x] Dockerfile + fly.toml
- [x] smithery.yaml
- [x] PR to awesome-mcp-servers (#8881)
- [x] Launch post drafts
- [ ] Fly.io deploy (needs `flyctl auth login` — browser)
- [ ] Smithery publish (needs GitHub OAuth — browser)
- [ ] mcp.so submit (needs form — browser)
- [ ] Glama submit (needs GitHub OAuth — browser)
- [ ] PyPI publish (needs `twine upload` — token)
- [ ] GitHub release tag
- [ ] Show HN + Reddit posts
