# Multi-stage not needed — stdlib-only app. Python 3.11 slim.
FROM python:3.11-slim

# Non-root user for security
RUN useradd --create-home --uid 1000 agentmail
WORKDIR /home/agentmail/app

# Install the package + mcp extra
COPY pyproject.toml README.md LICENSE ./
COPY __init__.py core.py api.py cli.py mailtm.py otp.py mcp_server.py ./
COPY compliance/ ./compliance/
COPY sms/ ./sms/

RUN pip install --no-cache-dir ".[mcp]"

# Persistent volume for the registry + OFAC cache
RUN mkdir -p /home/agentmail/data && chown -R agentmail:agentmail /home/agentmail
ENV AGENTMAIL_HOME=/home/agentmail/data
VOLUME ["/home/agentmail/data"]
USER agentmail

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000
# Hosted-mode knobs (override at deploy time):
# AGENTMAIL_REQUIRE_AUTH=true
# AGENTMAIL_API_KEYS=sk_live_xxx,sk_live_yyy
# AGENTMAIL_RATE_LIMIT=600
# AGENTMAIL_FREE_TIER_DAILY=100
# AGENTMAIL_AUDIT_LOG=/home/agentmail/data/audit.jsonl

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,json; urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=4).read()" || exit 1

CMD ["python", "-m", "agentmail.api"]
