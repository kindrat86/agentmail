# Changelog

All notable changes to `sanctions-mcp` (agentmail) are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — 2026-07-18

### Added
- **agentmail Sanctions Exposure Index (SEI)** — proprietary 5-factor framework for quantifying an AI agent's OFAC sanctions exposure. Velocity (30%), Jurisdiction overlap (25%), Asset class (20%), Screening posture (15%), Disclosure readiness (10%). Published in the [2026 Agent-Payment Sanctions Exposure Report](https://sanctionsai.dev/research/agent-payment-sanctions-exposure-2026).
- **Interactive SEI Calculator** at https://sanctionsai.dev/tools/sei-calculator — computes SEI scores in real-time.
- 36 hallucinated-URL 301 redirects (AI-guessed slugs now resolve to real pages).
- 8 section-index pages for AEO crawlability (`/for`, `/compare`, `/integrations`, `/glossary`, `/tools`, `/vs`, `/how-to`, `/cost`).
- PostHog AI-referral auto-capture — fires `ai_referral_detected` events when visitors arrive from ChatGPT/Perplexity/Gemini/Claude/Copilot/DeepSeek/Grok + 10 more AI sources.
- Self-reported attribution survey on `/start` squeeze page (14 options including 6 AI sources).
- `Dataset` + `Article` schema for the SEI research report.

### Changed
- `knowledge-graph.json` `SoftwareApplication.alternateName` expanded with `SanctionsAI`, `sanctions-mcp`, `agentmail API` for entity consolidation.
- `pyproject.toml` keywords now include `sei`, `sanctions-exposure-index`, `x402`.
- Homepage now at `sanctionsai.dev` (was `github.com/kindrat86/agentmail`).
- Documentation and Changelog URLs added to PyPI metadata.

### Fixed
- `robots.txt` no longer advertises 404 section-index paths.
- Sitemap no longer contains `/integrations/eliza` (removed; 301 to `/integrations/elizaos`).
- Founder `Person` schema cleaned — removed fabricated-looking `givenName`/`familyName`/`alumniOf`/dead LinkedIn URL.

## [0.4.0] — 2026-06-28

- Initial PyPI release.
- OFAC sanctions screening (`sanctions_check`), transaction risk scoring (`risk_score`), Know-Your-Agent verification (`kya_verify`), dispute management (`dispute_open`).
- MCP server, HTTP API, and CLI interfaces.
- Free tier: 5 checks/day, no API key.
