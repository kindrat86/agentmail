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
