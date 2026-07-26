# Multi-stage not needed — stdlib-only app. Python 3.11 slim.
FROM python:3.11-slim

# Non-root user for security
RUN useradd --create-home --uid 1000 agentmail
WORKDIR /home/agentmail/app

# Install the package + mcp extra
COPY pyproject.toml README.md LICENSE ./
COPY __init__.py core.py api.py cli.py mailtm.py otp.py mcp_server.py billing.py x402.py ./
COPY compliance/ ./compliance/
COPY sms/ ./sms/
COPY email_templates/ ./email_templates/
# Round-15 static pSEO pages (served by do_GET handler)
COPY vs/ ./vs/
COPY faq/ ./faq/
COPY learn/ ./learn/
COPY alternatives-to/ ./alternatives-to/
# Round 16 new page types
COPY penalties/ ./penalties/
COPY guides/ ./guides/
# Round 19 Isenberg pSEO (checklists, cost-of, best — templates not generated for this site)
COPY checklists/ ./checklists/
COPY cost-of/ ./cost-of/
COPY best/ ./best/
# Embeddable statistics hub page
COPY stats/ ./stats/
# Red-flags & scenario pSEO pages (problem-first conversion content)
COPY redflags/ ./redflags/
COPY scenarios/ ./scenarios/
# Scaled glossary pages (served via glossary static fall-through in api.py)
COPY glossary/ ./glossary/
# Round 21 pSEO — OFAC sanctions programs index
COPY programs/ ./programs/
# Interactive shareable tools (compliance-check, ai-spend-optimizer)
COPY tools/ ./tools/
# R17 UX system — shared design system across portfolio
COPY ux.css ux.js ./
# published CC BY dataset served by /ofac-enforcement-2026.csv (read from disk, not embedded)
COPY ofac-enforcement-2026.csv ./
# Public static assets (related-tools hub, network, answers, badge, verification files)
COPY public/ ./public/

# --- structured-data gate (~/.growth-engine/GUARDRAILS.md rule 3) ---
# Fails the image build — and so `flyctl deploy` — if any copied page carries
# unparsable JSON-LD. Placed after every static COPY so it sees exactly the
# page set do_GET will serve, and before the USER switch so it still runs as
# root. The gate is what was missing when "Unparsable structured data — Parsing
# error: Missing ',' or '}'" reached Search Console on voicelogpro.com.
# Python, not the portfolio's Node gate, deliberately: this is a python:slim
# image and validate_jsonld.py is stdlib-only, so gating costs no new dependency
# and no Node install. scripts/verify-jsonld.mjs runs in CI instead, where Node
# is free, for the extra corruption-signature checks.
COPY scripts/validate_jsonld.py /tmp/validate_jsonld.py
RUN python3 /tmp/validate_jsonld.py . && rm /tmp/validate_jsonld.py

RUN pip install --no-cache-dir ".[mcp]" && \
    cp /home/agentmail/app/api.py /usr/local/lib/python3.11/site-packages/agentmail/api.py && \
    cp /home/agentmail/app/core.py /usr/local/lib/python3.11/site-packages/agentmail/core.py && \
    cp /home/agentmail/app/billing.py /usr/local/lib/python3.11/site-packages/agentmail/billing.py && \
    cp /home/agentmail/app/x402.py /usr/local/lib/python3.11/site-packages/agentmail/x402.py

# Persistent volume for the registry + OFAC cache
RUN mkdir -p /home/agentmail/data && chown -R agentmail:agentmail /home/agentmail
ENV AGENTMAIL_HOME=/home/agentmail/data
VOLUME ["/home/agentmail/data"]
USER agentmail

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000 PYTHONPATH=/home/agentmail/app
# Hosted-mode knobs (override at deploy time):
# AGENTMAIL_REQUIRE_AUTH=true
# AGENTMAIL_API_KEYS=sk_live_xxx,sk_live_yyy
# AGENTMAIL_RATE_LIMIT=600
# AGENTMAIL_FREE_TIER_DAILY=100
# AGENTMAIL_AUDIT_LOG=/home/agentmail/data/audit.jsonl

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,json; urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=4).read()" || exit 1

CMD cd /home/agentmail/app && python -m agentmail.api
