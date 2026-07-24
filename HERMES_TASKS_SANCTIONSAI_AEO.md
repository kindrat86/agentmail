# Hermes Autonomous Execution Brief — sanctionsai.dev AEO/SEO Remediation

**Target repo:** `~/workspace/agentmail` (branch `main`, HEAD at time of writing: `71d2618`) — **not** `~/sanctionsai-dashboard`, which is a separate, dashboard-only repo that does not serve the live site.
**Live domain:** https://sanctionsai.dev, served entirely by a single-file Python server (`api.py`, ~835KB) running as Fly.io app `agentmail-api` (region `fra`), **not Vercel**.
**Deploy command:** `flyctl deploy` from `~/workspace/agentmail` (app name is set in `fly.toml`, no `-a` flag needed if run from this directory).
**Source audit:** 10-site portfolio AEO/SEO audit, 2026-07-21, sanctionsai.dev scored 76/100, 0 critical + 1 high + 2 medium + 1 low finding.
**Executor:** Hermes Agent (autonomous, DeepSeek v4 Pro). This document is your complete task spec — do not improvise scope beyond what's written here.

**Important methodology note:** every task below was re-verified directly against the current repo before being written into this brief, including reading the actual live `/knowledge-graph.json` and `/qa.jsonl` response bodies inside `api.py` (not just the audit's summary of them). Some of the source audit's specific claims did **not** match what's actually being served and have been corrected or reframed — see §3. Trust the file/line citations and exact string counts in this document; re-verify yourself if HEAD has moved since `71d2618`.

---

## 0. Read this whole section before touching anything

### 0.1 Collision check — mandatory first step, every run, and unusually important on this repo right now

```bash
ps aux | grep -i hermes | grep -v grep
cd ~/workspace/agentmail && git status --short | head -20 && git log -1 --format='%H %ci'
```

**At the time this brief was written, this repo's working tree had 130+ modified files and several new untracked directories uncommitted** — a large in-progress bulk edit touching dozens of pSEO page twins plus `ux.js`/`ux.css` (looked like an in-flight growth-engine UX-script upgrade, R15→R18). This is very likely either the `portfolio-traffic-rotation` Hermes cron or a growth-engine cycle actively mid-flight. **Do not assume a clean tree.** Before doing anything:

- If `git status --short` shows any modified/untracked files, **do not run `git add -A` or any broad-stage command** — you could commit someone else's half-finished work under your commit message. Only ever `git add` the exact files each task below names.
- If a Hermes process is running against `~/workspace/agentmail`, or `fly releases -a agentmail-api | head -5` shows a deploy in the last ~30 minutes, wait and re-check every 10 minutes before starting.
- Confirm `git log -1` still shows `71d2618` (or a later commit that clearly isn't a broken/partial one) before starting.
- This is a single ~835KB monolithic `api.py` file serving the whole site — a botched concurrent edit here is much higher-blast-radius than a typical multi-file static site, since every route is one file. Be extra conservative about editing while the tree is dirty from another process.

### 0.2 This repo has no blank-screen CSP landmine (verified) — but two other operational landmines exist

Unlike several sibling sites in this portfolio, sanctionsai.dev is fully server-rendered static HTML with no client hydration step, so it is **not** susceptible to the Trusted-Types blank-screen incident documented elsewhere in this portfolio (confirmed: CSP present, does not contain `require-trusted-types-for`). No task below needs to guard against that specific failure mode. Two different operational landmines apply here instead:

1. **Fly machine autostop reverting to a cold-starting mode.** `fly.toml` currently correctly sets `auto_stop_machines = "suspend"` (with a comment explicitly warning that plain `true` causes >15s cold starts that time out the first request — AI crawlers drop 503s) plus `min_machines_running = 1`. This is committed source, not a runtime-only override, so a normal `flyctl deploy` should preserve it — but **verify this didn't get reverted** after any deploy you run (see §5a). Do not remove or weaken this fly.toml setting.
2. **The exposed-dashboard incident (already fixed, do not regress it).** `/dashboard`, `/dashboard/logs`, `/dashboard/export` previously had no auth and leaked live `sk_live_` keys, wallet data, and IPs. This is already fixed (fail-closed 403 without `ADMIN_DASH_TOKEN`, output masks sensitive values to last-4 even when authed). **No task below touches dashboard/auth code — do not modify anything under a `/dashboard` route handler for any reason.**

### 0.3 Guardrails you must never bypass

- Always create new commits. Never `git commit --amend` on a commit that's already been pushed/deployed.
- Never `git push --force` to `main`.
- Never touch billing/API-key code (`billing.py` or any `sk_live_` minting logic) — entirely out of scope for this brief.
- This repo has no separate lint/guard npm script the way the Vercel sites do (it's a plain Python server) — your own verification commands in each task below are the only gate. Run them.

### 0.4 What you are NOT authorized to change autonomously

See §6 "Owner-gated — do not execute" at the bottom. Anything not explicitly listed as a task in §1–§2 is out of scope.

---

## 1. P1 — HIGH

### TASK-01: Add the missing `alternateName` cross-reference on the Organization schema node

**File:** `~/workspace/agentmail/api.py`, inside the `/knowledge-graph.json` route handler (starts at line 2623), the `Organization` `@graph` entry (`"@id": "https://sanctionsai.dev/#org"`, currently around line 2666-2672).

**Root cause (confirmed, and more precise than the source audit's framing):** The live `/knowledge-graph.json` response has **two** entities that should represent the same brand identity, and they're inconsistent with each other:
- The `SoftwareApplication` node (`@id: .../#software`) already correctly has `"name": "agentmail"` with `"alternateName": ["AgentMail", "agentmail API", "SanctionsAI", "sanctions-mcp", "Sanctions MCP", "OFAC sanctions screening for AI agents"]` — this one already cross-references both names.
- The `Organization` node (`@id: .../#org`) — the one representing the actual company/publisher entity, referenced by every other node's `provider`/`publisher` field — has **no `alternateName` field at all**: `{"@type": "Organization", "@id": "https://sanctionsai.dev/#org", "name": "AgentMail", "url": "https://sanctionsai.dev", "email": "hello@sanctionsai.dev", "sameAs": ["https://github.com/kindrat86/agentmail"]}`.

So the audit's claim that "alternateName does not include agentmail at all" is backwards and the claim that `sameAs` is fully empty is also not accurate (it has one entry) — but the underlying problem it was reaching for is real: the entity that actually represents the *publisher* (the Organization node) doesn't cross-reference the domain-matching name "SanctionsAI" the way the SoftwareApplication node does, so an LLM resolving "who publishes sanctionsai.dev" via the Organization node specifically won't see the SanctionsAI name linked.

**Fix:** Add an `alternateName` field to the Organization node, matching the pattern already used on the SoftwareApplication node:
```python
{
    "@type": "Organization",
    "@id": "https://sanctionsai.dev/#org",
    "name": "AgentMail",
    "alternateName": ["SanctionsAI", "sanctionsai.dev"],
    "url": "https://sanctionsai.dev",
    "email": "hello@sanctionsai.dev",
    "sameAs": [
        "https://github.com/kindrat86/agentmail",
        "https://pypi.org/project/sanctions-mcp/",
        "https://mcp.so/server/agentmail",
    ],
},
```
(This also folds in TASK-02 below — the `sameAs` enrichment — since both edits land in the exact same object; ship them as one edit.)

**Do not change `"name"` itself** (i.e. don't flip it to `"SanctionsAI"`) — which name is canonical is a brand decision for the owner (see §3 and §6), this task only makes sure the two names are cross-linked regardless of which one eventually wins.

**Verification (before commit):**
```bash
cd ~/workspace/agentmail
python3 -c "
import ast, re
src = open('api.py').read()
# crude sanity check: the Organization node literal must now contain both keys
i = src.index('\"@id\": \"https://sanctionsai.dev/#org\"')
chunk = src[i-50:i+600]
assert 'alternateName' in chunk, 'alternateName still missing from Organization node'
assert 'pypi.org/project/sanctions-mcp' in chunk, 'sameAs enrichment missing'
print('OK — Organization node updated')
"
python3 -m py_compile api.py   # must not error — confirms the file is still valid Python after your edit
```

---

## 2. P2 — MEDIUM / verify-first

### TASK-02: `sameAs` enrichment

Folded into TASK-01 above (same object, same edit) — adding `https://pypi.org/project/sanctions-mcp/` and `https://mcp.so/server/agentmail` to the Organization node's `sameAs`, both of which are already real, live, and used elsewhere on the exact same JSON response (the SoftwareApplication node), so there's no fabrication risk here.

### TASK-03: `/countries/*` vs `/by-country/*` overlap — verify, and only merge if genuinely duplicate

**Root cause (confirmed):** Two separate URL families cover overlapping country topics:
- `/countries/*` — 18 countries (afghanistan, belarus, china, cuba, ethiopia, iran, iraq, lebanon, libya, myanmar, nicaragua, north-korea, pakistan, russia, somalia, sudan, syria, venezuela)
- `/by-country/*` — 12 countries (belarus, china, cuba, iran, lebanon-hezbollah, myanmar, north-korea, pakistan, russia, syria, ukraine-separatist, venezuela)

10 country names appear in **both** families (belarus, china, cuba, iran, myanmar, north-korea, pakistan, russia, syria, venezuela) under different URL patterns. This is a real overlap, but the two families may legitimately cover different angles (e.g. `/countries/iran` = general country sanctions overview, `/by-country/iran` = something more specific like a program/regime breakdown — `lebanon-hezbollah` and `ukraine-separatist` in the `/by-country/` set suggest it's organized by *sanctions program*, not just country, which would make it non-duplicate).

**Action — verify before touching anything:**
```bash
curl -s https://sanctionsai.dev/countries/iran | python3 -c "import sys,re; print(len(re.sub('<[^>]+>','',sys.stdin.read())))"
curl -s https://sanctionsai.dev/by-country/iran | python3 -c "import sys,re; print(len(re.sub('<[^>]+>','',sys.stdin.read())))"
diff <(curl -s https://sanctionsai.dev/countries/iran) <(curl -s https://sanctionsai.dev/by-country/iran) | head -40
```
Repeat for 2-3 more of the 10 overlapping names. If the pages are genuinely near-duplicate (same content, different URL), add a `<link rel="canonical">` on the weaker of the two pointing to the stronger one (do not delete either route — both may have inbound links/citations already). If they're meaningfully different in angle (which the `lebanon-hezbollah`/`ukraine-separatist` naming suggests is likely), this is a non-issue — close it out in your execution log with the diff evidence and make no changes.

### TASK-04: Add the missing pSEO hub links to the footer — verify scope first, then add only the confirmed-missing ones

**Root cause (more precise than the audit's blanket claim):** The audit claimed hub pages "are not linked from the primary nav" at all. That's not quite right — the site's shared `_FOOTER` template (`api.py`, defined around line 471) already links extensively to hubs: `/for` (+ 6 industry sub-links), `/compare` (+ 5 vs-page sub-links), `/blog`, `/guides`, `/penalties`, `/how-to`, `/glossary`, `/cost`, `/integrations`, `/vs`, `/stats`, `/dream100`, `/about`, `/contact`. What's genuinely missing from the footer (confirmed by grep — zero matches for these in `_FOOTER`): **`/countries`, `/checklists`, `/answers`, `/redflags`, `/benchmarks`, `/best`, `/alternatives-to`**.

**Fix:** In the `_FOOTER` string constant in `api.py` (~line 471), add links for the 7 confirmed-missing hub pages above, following the exact same pattern as the existing "Resources" column entries (e.g. `<a href="/countries">Countries</a>`, `<a href="/checklists">Checklists</a>`, `<a href="/answers">Answers</a>`, `<a href="/redflags">Red Flags</a>`, `<a href="/benchmarks">Benchmarks</a>`, `<a href="/best">Best-Of</a>`, `<a href="/alternatives-to">Alternatives</a>`). Keep them in the existing "Resources" column to avoid a layout change; this is a pure additive edit.

**Verification (before commit):**
```bash
cd ~/workspace/agentmail
python3 -c "
src = open('api.py').read()
i = src.index('_FOOTER =')
chunk = src[i:i+3000]
for path in ['/countries','/checklists','/answers','/redflags','/benchmarks','/best','/alternatives-to']:
    assert f'href=\"{path}\"' in chunk, f'{path} still missing from footer'
print('OK — all 7 hub links present in footer')
"
python3 -m py_compile api.py
```

### TASK-05: Verify (do not fix) — the footer's email-subscribe form posts to a different domain

Found while reviewing the footer for TASK-04, not in the original audit — worth flagging. The `_FOOTER` subscribe form has `<form action="https://churnlens.site/api/subscribe" method="post">` — sanctionsai.dev's own newsletter signup submits to a **different portfolio site's** API endpoint. This was not found to be a shared pattern used by other checked sibling repos (`~/carshake`, `~/sipiteno`, `~/churnlens`, `~/voicelogpro`, `~/unlocksaas` were grepped — none reference `churnlens.site/api/subscribe`), so this looks more like a copy-paste artifact from template reuse than an intentional shared backend. **Do not change this** — it's possible there's a legitimate cross-domain email-capture service you don't have visibility into from the repo alone (e.g. a shared PostHog/Resend pipeline keyed by referring domain). Flag it in your execution log for the owner to confirm whether sanctionsai.dev subscribers are actually landing in the right list, or whether this needs to point to sanctionsai.dev's own subscribe endpoint (if `api.py` has one — check for a `/api/subscribe` or similar route before assuming one doesn't exist).

---

## 3. Findings from the source audit that did NOT reproduce as stated — corrected here

- **"knowledge-graph.json sameAs is empty ([])"** — false as stated. The Organization node's `sameAs` has one entry (`github.com/kindrat86/agentmail`); the SoftwareApplication node's `sameAs` has three. TASK-01/02 above enrich the Organization node's array from 1 to 3 entries — a real improvement, but "empty" was not accurate.
- **"alternateName array does not include agentmail at all"** — backwards. The SoftwareApplication node's `alternateName` already includes `"SanctionsAI"` (5 other variants too). The gap that actually exists is the reverse and on a different node: the *Organization* node has no `alternateName` at all (not missing one specific value — missing the whole field). TASK-01 fixes this precisely.
- **"the domain and most page `<title>` tags say SanctionsAI"** — not accurate. Direct grep of every `<title>` in `api.py` found the *opposite* skew: the homepage title itself is `"AgentMail — OFAC Sanctions Screening for AI Agents"`, and the literal string `"agentmail"` (case-insensitive brand references) appears roughly 28× across page titles/content vs. `"SanctionsAI"` appearing once. The dual-branding problem is real, but it's "agentmail" that dominates the actual served content while the *domain* is sanctionsai.dev — the imbalance runs the other direction from what the audit described. See §6 for why this is still owner-gated despite the correction.
- **"hub pages ... are not linked from the primary nav"** — overstated. The footer (not the top nav) already links most hubs; TASK-04 above lists precisely which 7 are actually missing, not "all of them."

---

## 4. Deploy protocol — follow exactly, in order

1. Re-run the §0.1 collision check. If clear, proceed. Given how active this repo's tree was found to be, re-check immediately before your final commit too, not just at the start of your session.
2. Make TASK-01 (+folded TASK-02) and TASK-04 edits — both are in `api.py`. If TASK-03's verification finds a real duplicate-content issue worth a canonical-tag fix, that's a third, separate edit in `api.py`.
3. Run every verification command from each task. All must pass before committing.
4. Commit (stage only `api.py`, nothing else, given the dirty tree noted in §0.1):
   ```bash
   cd ~/workspace/agentmail
   git add api.py
   git commit -m "fix: cross-reference SanctionsAI/agentmail in knowledge-graph.json Organization node + add missing pSEO hub links to footer"
   ```
5. Deploy:
   ```bash
   flyctl deploy
   ```
6. Immediately after deploy completes, confirm the machine autostop setting wasn't reverted (see §0.2):
   ```bash
   flyctl config show -a agentmail-api | grep -A2 auto_stop_machines
   ```
   If it shows `true` instead of `"suspend"`, the deploy reverted it — re-check `fly.toml` in the repo (it should already say `"suspend"` as committed source) and re-deploy, or contact the owner if this keeps happening (may indicate a Fly platform-level override outside this repo's control).

**If any step fails, do not proceed to the next step and do not force through it.** Report the exact error in your execution log (§7) and stop.

---

## 5a. Post-deploy verification — mandatory

```bash
# 1. Confirm the Organization node now has alternateName + enriched sameAs
curl -s https://sanctionsai.dev/knowledge-graph.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
org = next(n for n in d['@graph'] if n.get('@id','').endswith('#org'))
assert 'alternateName' in org and 'SanctionsAI' in org['alternateName'], 'alternateName fix did not ship'
assert len(org.get('sameAs', [])) >= 3, 'sameAs enrichment did not ship'
print('OK —', org['alternateName'], org['sameAs'])
"

# 2. Confirm the 7 new footer hub links are live
for path in countries checklists answers redflags benchmarks best alternatives-to; do
  curl -s https://sanctionsai.dev/ | grep -c "href=\"/$path\"" | xargs echo "$path:"
done   # every count must be >= 1

# 3. Confirm the site is still fully responsive (no cold-start regression from a fly.toml revert)
time curl -s -o /dev/null -w "%{http_code}\n" https://sanctionsai.dev/   # must be 200, and should return in well under 2s

# 4. Confirm no unrelated routes broke (spot-check a few known-good pages)
for path in / /pricing /faq /about /teardown /llms.txt /qa.jsonl; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://sanctionsai.dev$path")
  echo "$path: $code"
done   # all must be 200
```

## 5b. Rollback plan — use immediately if §5a verification fails

```bash
cd ~/workspace/agentmail
flyctl releases -a agentmail-api   # find the previous good release version/image
flyctl releases rollback <version> -a agentmail-api   # or: git revert --no-edit HEAD && flyctl deploy
```

---

## 7. Execution log — append your results here as you work

```
### 2026-07-21 run
- TASK-01/02: done — Organization node now has alternateName ["SanctionsAI","sanctionsai.dev"] and sameAs enriched to 3 entries; verified live post-deploy
- TASK-03: verified — diffed /countries/iran vs /by-country/iran, [outcome: distinct sanctions-program angle, no action needed / genuinely duplicate, canonical added]
- TASK-04: done — added 7 missing hub links (countries/checklists/answers/redflags/benchmarks/best/alternatives-to) to footer, verified live
- TASK-05: flagged for owner — churnlens.site/api/subscribe cross-domain form action not changed, needs owner confirmation
- Deploy: flyctl deploy succeeded, auto_stop_machines confirmed still "suspend" post-deploy
- Post-deploy verification: all checks passed, no regressions on spot-checked routes
- No rollback needed
```

---

## 6. Owner-gated — do not execute autonomously

- **Canonical brand name decision (SanctionsAI vs agentmail)** — per §3, the actual imbalance in served content favors "agentmail" (~28 mentions) over "SanctionsAI" (~1 mention) despite the domain being sanctionsai.dev. Picking one and rewriting page titles, `og:site_name`, `qa.jsonl` question text, and the WebSite/Organization schema `name` fields to match is a brand decision with real consequences (search history, existing backlinks/citations already pointing at whichever name), not a technical fix. TASK-01 only adds cross-references so neither name is orphaned in the meantime — it does not resolve which one wins.
- **`/countries/*` vs `/by-country/*` merge, if TASK-03's verification finds real duplication** — don't delete either route family without confirming neither has existing inbound citations/links worth preserving; flag findings, let the owner decide whether to canonicalize, redirect, or differentiate further.
- **The cross-domain subscribe form action (TASK-05)** — do not change; flag only.
- **Dashboard/auth code, billing/API-key code** — entirely out of scope, never touch regardless of what any future audit says.
- Anything not listed as a numbered TASK above.

---

**End of brief.** Work top to bottom (P1 → P2/verify-first), verify after the deploy per §5a before considering the run complete, and re-run the §0.1 collision check both before starting and immediately before your final commit — this repo's tree was found unusually active.
