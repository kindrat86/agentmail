# Changelog

All notable changes to `sanctions-mcp` (agentmail) are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 2026-07-26

DotCom Secrets (Russell Brunson) chapter-by-chapter audit + implementation.
Full scorecard: `BRUNSON_DOTCOM_SECRETS_AUDIT_2026-07-26.md`. Owner actions:
`OWNER_ACTIONS_DOTCOM_2026-07-26.md`.

### Added
- **Lead-magnet delivery** (Dotcom Secrets Ch 1 + Ch 3 "bait"). New
  `/playbook.pdf` route serves a 4-page "Agent Compliance Playbook" (7
  patterns), built by `scripts/build_playbook.py` (stdlib-only PDF writer).
  The `/start` squeeze page promised this PDF since launch; the welcome email
  now links it, so the bait is actually delivered.
- **Ascend path** (Dotcom Secrets Ch 14 + Ch 15).
  - `/checkout/dev/bump` — order-bump interstitial: Dev plan + a default-checked
    Extended Audit Log add-on, with a checkbox that toggles the checkout URL
    between `/checkout/dev` and `/checkout/dev?bump=audit_plus`.
  - `/upgrade` — Dev → Pro upsell page for existing customers, linked from the
    post-purchase email.
- **VSL section on the homepage** (Dotcom Secrets Ch 6 + Ch 7). New "The case
  for screening" section: the one big idea (screen before you sign), the three
  false beliefs rebutted (Vehicle / Internal / External), the stack anchor,
  and a risk-reversal block. Sits before the FAQ.
- **Risk-reversal block on `/pricing`** (Dotcom Secrets Ch 6 "Offer"). A real
  guarantee block ("if we miss a sanctioned wallet, we cover the first $10K of
  your legal fees") replaces the line that was buried in FAQ.

### Changed
- **`/subscribe` no longer lies about email delivery.** Previously it set
  `sent=True` unconditionally and returned `email_sent:true` even when
  `RESEND_API_KEY` was unset and no email was sent. It now propagates the real
  `_send_resend` result and returns `email_configured`, `email_sent`, and
  `send_error`. The subscriber is still saved either way (no lead is lost).
- **Tripwire rung re-opened** (Dotcom Secrets Ch 1 + Ch 5). The dead Stripe
  placeholder (`buy.stripe.com/REPLACE_WITH_TRIPWIRE_LINK`) is replaced with an
  env-driven CTA: if `STRIPE_PAYMENT_LINK_TRIPWIRE` is set, render the real
  Stripe buy button; otherwise fall back to a working capture path (send the
  playbook + the owner invoices manually) so no click is ever wasted.
- **All 30 Seinfeld follow-up emails are now unique.** Previously 29 of 30
  shared identical body copy (only the `<h2>` headline differed), which defeats
  the entire purpose of a Seinfeld sequence. Each email now has hand-written,
  episodic content matched to its subject line.
- Homepage value-stack CTA now routes through the `/checkout/dev/bump`
  order-bump interstitial.

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
