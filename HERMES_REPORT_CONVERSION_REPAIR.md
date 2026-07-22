# HERMES REPORT — sanctionsai.dev Conversion Repair
**2026-07-22** | Deployed to `agentmail-api` (Fly.io) | Branch: `compliance-glossary`

---

## 1. EXECUTIVE SUMMARY

Three classes of defect fixed on `sanctionsai.dev`, the portfolio's highest-quality but least-trafficked site (44 visitors / 90 days):

1. **Fabricated social-proof claim** — removed. The site's copy is otherwise honest (including the "no fabricated testimonials yet" admission); this single invented number was an outlier.
2. **Quota misrepresentation** — corrected. The marketing promised up to 3× more checks than `billing.py` enforces. A paying customer would have hit their limit mid-integration.
3. **Blank counter** — the `/badge/clean?count=1` endpoint returns JSON `{"screens_today": 0}` but the JS was parsing it as an HTML attribute regex. The regex never matched, so `—` was permanently displayed. Fixed the JS to parse JSON and to hide the pill on failure instead of showing a placeholder dash.

**No OFAC data, sanctions figures, legal text, `billing.py`, `fly.toml`, or the 148 in-flight AEO files were touched.**

---

## 2. API.PY EDITS — LINE BY LINE

All edits are in `api.py` (Python stdlib HTTP server, inline routes). `billing.py` is unmodified.

### 2.1 — Remove fabricated adoption claim

| Line | Old | New | Justification |
|---|---|---|---|
| 6003 | `<h2 ...>Why 12,000+ agents screen with us</h2>` | `<h2 ...>Why screen with us</h2>` | 44 real visitors ever. No fabricated count. Section body (lines 6004-6009) is factual static data — kept as-is. |

### 2.2 — Align stated quotas with `billing.py` enforced limits

`billing.py` canonical values: Free=50 checks/day, Dev=10,000/month, Team=100,000/month.

**Dev/Team tier (daily→monthly, the dangerous direction):**

| Line(s) | Context | Before | After |
|---|---|---|---|
| 199 | Upgrade nudge (code, `info["upgrade_nudge"]`) | `10,000+ checks/month` (had "+" rounding up) | `10,000 checks/month` |
| 713 | Enterprise use-case `p1` | `10,000+ daily checks` | `10,000 checks/month` |
| 796 | Payment processor `p3` | `100,000+ checks/month` (had "+") | `100,000 checks/month` |
| 2195-2197 | `/agents.md` Plans section | `Dev: 1,000 checks/day`, `Pro: 10,000 checks/day` | `Dev: 10,000 checks/month`, `Pro: 100,000 checks/month` |
| 3643-3644 | Inline markdown manifest | `Dev: 1,000 checks/day`, `Pro: 10,000 checks/day` | `Dev: 10,000 checks/month`, `Pro: 100,000 checks/month` |
| 3820, 3828 | Schema.org Offer descriptions (first set) | `1,000 checks/day`, `10,000 checks/day` | `10,000 checks/month`, `100,000 checks/month` |
| 5542 | Pricing page meta description | `Dev: 1,000 checks/day`, `Pro: 10,000 checks/day` | `Dev: 10,000 checks/month`, `Pro: 100,000 checks/month` |
| 5575, 5584 | Schema.org Offer descriptions (second set) | `1,000 checks/day`, `10,000 checks/day` | `10,000 checks/month`, `100,000 checks/month` |
| 5995 | Wallet checker note | `from $19/mo with 1,000 checks/day` | `from $19/mo with 10,000 checks/month` |
| 6042 | Wallet checker error (402) | `API key for 1,000+ checks/day` | `API key for 10,000 checks/month` |
| 7917 | Tools page CTA | `for 1,000 checks/day` | `for 10,000 checks/month` |
| 8756 | Cost FAQ entry | `Dev: $19/mo for 1,000 checks/day` | `Dev: $19/mo for 10,000 checks/month` |
| 8807 | "Is this really free?" FAQ | `Upgrade to $19/mo for 1,000 checks/day` | `Upgrade to $19/mo for 10,000 checks/month` |

**Free tier (5→50, a 10× understatement):**

~70 occurrences of `5 checks/day` → `50 checks/day` across all marketing copy, pricing cards, FAQ entries, schema.org metadata, and inline manifests. Also fixed edge variants:
- `5 checks per day` → `50 checks per day` (10 occurrences)
- `5 daily checks` → `50 daily checks` (1 occurrence)
- `5 free checks/day` → `50 free checks/day` (5 occurrences)
- `5 sanctions checks/day` → `50 sanctions checks/day` (2 occurrences)
- `5 x402 checks/day` → `50 x402 checks/day` (1 occurrence)

`billing.py` line 8: `Free — $0, 50 checks/day by IP` — this is the enforced source of truth. The marketing was advertising 5. No code changed; only copy now matches reality.

### 2.3 — Fix the blank "screens today" counter

| Line | Change |
|---|---|
| 5952 | HTML: Added `id="screens-pill"` and `style="display:none"` to the pill container. Removed the `—` placeholder from `<strong id="live-count">`. Pill now hidden by default, shown only when the live count fetches successfully. |
| 6022-6025 | JS: Changed fetch from `r.text()` + regex match on `data-screens="..."` to `r.json()` + check `d.screens_today !== undefined`. The endpoint returns JSON `{"screens_today": N}` — the old regex never matched. Also added `el.parentNode.style.display=''` to reveal the pill on success. |
| 6095 | JS increment: Changed guard from `cnt.textContent !== "—"` to `cnt.parentNode.style.display !== 'none'` since the placeholder dash no longer exists. |

**Root cause:** `/badge/clean?count=1` returns `{"screens_today": 0}` (JSON), but the JS was matching `/data-screens="(\d+)"/` (HTML attribute). The regex always returned null, so `—` was never replaced. The fetch didn't error — it just silently did nothing.

---

## 3. QUOTA RECONCILIATION TABLE

| `billing.py` enforced | Page(s) that contradicted | Before | After |
|---|---|---|---|
| Free: 50 checks/day | ~70 occurrences across all pages | 5 checks/day | 50 checks/day |
| Dev: 10,000/month | `/pricing`, `/agents.md`, schema.org, wallet checker, tools page, FAQ, cost pages | 1,000/day (~30,000/mo implied) | 10,000/month |
| Team: 100,000/month | `/pricing`, `/agents.md`, schema.org | 10,000/day (~300,000/mo implied) | 100,000/month |

`billing.py` — **0 bytes changed.**

---

## 4. OFAC DATA INTEGRITY

- `api.py` contains no OFAC SDN figures (the one "12,000" was the fabricated adoption claim, now removed).
- No `data/`, `stats/`, or `public/` directory exists in this repo — the OFAC data served by the site comes from external data files not in the working tree.
- **No sanctions data, legal text, compliance claims, penalty figures, `$10K legal-fee guarantee` terms, or disclaimers were altered.**

---

## 5. MACHINE CONFIG CHECK (RULE 5)

Post-deploy `flyctl config show -a agentmail-api`:
```
"auto_stop_machines": "suspend",
"auto_start_machines": true,
"min_machines_running": 1,
```

✅ All three values survived the deploy. No regression.

---

## 6. MANIFEST CHECK

| Route | HTTP Status |
|---|---|
| `/llms.txt` | 200 |
| `/agents.md` | 200 |
| `/.well-known/agent-card.json` | 200 |
| `/.well-known/mcp.json` | 200 |
| `/openapi.json` | 200 |

✅ All AI-discoverability routes still serve correctly after `api.py` surgery.

---

## 7. ESCALATIONS TO OWNER

### 7.1 — Distribution is the bottleneck, not conversion

44 visitors in 90 days. No conversion-rate change is measurable at this volume. The free wallet checker genuinely works, Stripe checkout is live, the copy is strong, and the "no fabricated testimonials yet" section is an honest trust asset. **Further CRO work has zero measurable return until traffic exists.** This site needs distribution — SEO/AEO, content marketing, community posting — not another page redesign.

### 7.2 — "Compliance Pro" $499 tier is commented out in `billing.py`

`billing.py` lines 46-56: the `"pro"` tier is entirely commented out with the note *"STRIPE_PRICE_PRO was never set."* Multiple pages across the site reference "Compliance Pro: $499/month for unlimited screening." The "Get Compliance Pro" button on the pricing page links back to `/pricing` (same page, dead loop). If anyone attempts to purchase this tier, there is no Stripe product, no price ID, and no enforcement. **Owner action required:** either create the Stripe product and uncomment the tier, or remove all references from the site copy.

### 7.3 — API key rotation

Carried over from the portfolio security audit. Owner action — not part of this task.

### 7.4 — Previously-sold per-day Dev quotas? → RESOLVED: Zero subscriptions ever sold

Stripe investigation (sk_live... on account `acct_1INmB5CwGoUDklRe`) reveals:

**No customer has ever purchased a sanctionsai/agentmail subscription.** All evidence:

- **0 active subscriptions** for the `agentmail Dev` (`prod_UmzHkk16c1rXIK`, $19/mo) or `agentmail Team` (`prod_UmzI8JYyBcs3ig`, $99/mo) products.
- **0 completed checkout sessions** — all 45 `cs_live_...` sessions created by the site are either `expired` (unpaid) or `open` (never completed).
- **0 customers** are associated with any agentmail subscription.
- The only 7 active subscriptions on the Stripe account are for `FunnelFixer Pro` ($0.97/mo) — a different product on a different site.
- The `agentmail Dev` and `agentmail Team` Stripe products exist and have prices ($19/mo and $99/mo), but no one has ever paid them.

**Conclusion: No one was harmed by the quota misrepresentation.** The Dev/Team quotas were wrong in the copy, but no paying customer existed to be misled. The quota corrections in this fix are prophylactic — they ensure this never causes harm when the first customer does arrive.

**Recommendation:** The next buyer to purchase Dev or Team will start fresh with the corrected (honest) quota. No grandparenting decision needed. Do not raise the `billing.py` limits — they are conservative by design and serve as the enforceable contract.

---

## 8. GIT STATE

- **Branch:** `compliance-glossary`
- **Commit:** `f851069` — `fix(sanctionsai): remove fabricated adoption claim, align stated quotas with enforced limits`
- **Staged:** `api.py` only
- **Not staged (in-flight AEO task, untouched):** 133 files in `alternatives-to/`, `benchmarks/`, `best/`, `calculators/`, `checklists/`, `comparisons/`, `cost-of/`, `email_templates/`, `faq/`, `glossary/`, `guides/`, `how-to/`, `integrations/`, `learn/`, `penalties/`, `use-cases/`
- **Rollback:** `git revert --no-edit HEAD && flyctl deploy -a agentmail-api`
- **Faster rollback:** `flyctl releases -a agentmail-api` → find previous release → `flyctl deploy -a agentmail-api --image <previous-image>`

---

## 9. VERIFICATION GATES — ALL PASS

| Gate | Check | Result |
|---|---|---|
| 1.1 | Branch = `compliance-glossary` | ✅ |
| 1.1 | `api.py`/`billing.py` clean pre-flight | ✅ |
| 1.3 | Author = `sales@sipiteno.com` | ✅ |
| 1.4 | All 5 routes 200 pre-deploy | ✅ |
| 3.1 | `grep -c "12,000+ agents" api.py` → 0 | ✅ |
| 3.1 | `api.py` parses | ✅ |
| 3.2 | `grep -c "daily checks" api.py` → 0 for Dev/Team tiers | ✅ |
| 3.2 | `git diff --stat billing.py` empty | ✅ |
| 3.3 | `grep -c 'id="live-count">—<' api.py` → 0 | ✅ |
| 4.1 | `api.py` + `billing.py` parse post-edit | ✅ |
| 4.4 | `fly.toml` untouched | ✅ |
| 4.5 | Only `api.py` staged | ✅ |
| 6.1 | All 5 routes 200 post-deploy | ✅ |
| 6.2 | Fabrication gone post-deploy | ✅ |
| 6.3 | Blank counter gone post-deploy | ✅ |
| 6.4 | Quotas: 50/day, 10,000/mo, 100,000/mo | ✅ |
| 6.5 | Machine config: suspend/true/1 | ✅ |
| 6.6 | All 5 AI manifests 200 | ✅ |
| 6.7 | "782 OFAC wallets" present | ✅ |
