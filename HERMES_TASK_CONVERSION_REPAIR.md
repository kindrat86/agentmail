# HERMES TASK — sanctionsai.dev Conversion Repair

**Target site:** sanctionsai.dev (OFAC sanctions-screening API for AI agents)
**Repo:** `~/workspace/agentmail` — Python stdlib HTTP server, branch **`compliance-glossary`**
**Host:** Fly.io app `agentmail-api` — deploy with `flyctl deploy`
**Authored:** 2026-07-22
**Executor:** Hermes Agent (DeepSeek v4 Pro), autonomous
**Real data (90 days):** 70 pageviews · **44 visitors** · 68 sessions · 98.6% bounce — the lowest traffic in the portfolio

**Objective — read this before planning anything:** This site's page craft is **already better than its traffic justifies**. With 44 visitors in 90 days, **no conversion-rate change is measurable**. This task is therefore deliberately narrow: **fix the things that are untrue or contradictory, and change nothing else.** Do not redesign, do not restructure, do not "optimise". Two defects here would actively harm the business if a real prospect arrived tomorrow — fix those, ship, stop.

---

## 0. READ THIS FIRST — SIX HARD RULES

### RULE 1 — "12,000" MEANS TWO DIFFERENT THINGS. A BLIND REPLACE CORRUPTS REAL COMPLIANCE DATA.

- `api.py:6003` — `<h2>Why 12,000+ agents screen with us</h2>` → **FABRICATED.** 44 real visitors have ever seen this site.
- `data/global-sanctions-statistics/index.html:163`, `stats/index.html:94`, and related pages — *"~12,000+ active OFAC SDN designations"*, *"the SDN List contains over 12,000 entities"* → **TRUE, sourced, regulated fact about the OFAC list.**

Same digits, opposite meaning. **Never run a global find/replace on "12,000".** Read the surrounding sentence for every hit and decide individually. Destroying a real OFAC figure on a compliance site is far worse than the fabrication you came to fix.

### RULE 2 — NEVER ALTER SANCTIONS DATA, LEGAL TEXT, OR COMPLIANCE CLAIMS
This is a regulated domain. You may **not** edit OFAC counts, SDN data, jurisdiction lists, statutory citations, penalty figures, the `$10K legal-fee guarantee` terms, or any disclaimer. If one looks wrong, **record it for the owner** — do not touch it. The only compliance-adjacent number you may change is one that describes **our own product's limits** (Step 3.2), sourced from `billing.py`.

### RULE 3 — `api.py` IS 836 KB AND SERVES THE WHOLE SITE INLINE. SURGICAL EDITS ONLY.
`api.py` (836,637 bytes) serves the HTML pages *and* the AI-discoverability manifests (`/llms.txt`, `/agents.md`, `/.well-known/*`) as inline routes. You are permitted **single-line, targeted string edits** to specific verified line numbers. You are **forbidden** from: restructuring the file, reformatting it, regenerating any route, running a formatter over it, or making bulk substitutions. Every edit must be individually justified in the report.

### RULE 4 — THE TREE HAS 148 UNCOMMITTED FILES FROM ANOTHER TASK. NEVER `git add -A`.
Branch `compliance-glossary` carries ~148 modified files (the in-flight glossary/AEO work: `alternatives-to/*`, etc.). Stage **only** the files you personally edit, by explicit path. Committing that other task's half-finished work would ship it unreviewed.

### RULE 5 — PROTECT THE FLY MACHINE CONFIG
`fly.toml` currently sets:
```toml
auto_stop_machines = "suspend"   # RAM snapshot, ~1s wake
auto_start_machines = true
min_machines_running = 1         # a compliance API must not cold-start-503 the first request
```
These exist because cold starts were 503-ing first requests, and **AI crawlers drop 503s**. Do **not** modify `fly.toml`, and **verify after deploy** that these three values are still in effect (Section 6). If a deploy reverts them, that is a P0 regression.

### RULE 6 — NO NEW CLAIMS, NO NEW NUMBERS
You may delete an unverifiable claim. You may replace a wrong product limit with the value `billing.py` actually enforces. You may **never** invent a customer count, testimonial, logo, or usage statistic. The site currently has an honest *"no fabricated testimonials yet"* section — **keep it; it is an asset, not a gap.**

---

## 1. PRE-FLIGHT (abort conditions)

```bash
cd ~/workspace/agentmail
```

**1.1 — Branch, tree, rollback point.**
```bash
git branch --show-current            # expect: compliance-glossary
git status --short | wc -l           # expect ~148 (the in-flight glossary task)
git status --short -- api.py billing.py   # MUST be empty — if not, ABORT
git rev-parse HEAD                   # RECORD — rollback target
```
**ABORT** if `api.py` or `billing.py` already have uncommitted edits.

**1.2 — Another agent active?**
```bash
ps aux | grep -i hermes | grep -v grep
```
**ABORT** if anything references `agentmail`, `sanctionsai`, or a `flyctl` deploy in flight.

**1.3 — Author + Fly reachability.**
```bash
git config user.email        # MUST be sales@sipiteno.com
flyctl status -a agentmail-api | head -12
```

**1.4 — Reproduce the before-state.**
```bash
curl -s https://sanctionsai.dev/tools/wallet-checker | grep -c "12,000+ agents"    # expect 1
curl -s https://sanctionsai.dev/tools/wallet-checker | grep -o "screens today"     # expect a hit
for u in / /pricing /docs /faq /tools/wallet-checker; do
  printf "%-24s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' https://sanctionsai.dev$u)"
done   # ALL should be 200 — this is your regression baseline
```

---

## 2. THE DIAGNOSIS

### 2.1 — P0: A fabricated social-proof claim

`api.py:6003`:
```html
<h2 style="text-align:center;color:var(--teal)">Why 12,000+ agents screen with us</h2>
```
Against **44 total visitors in 90 days**, this is not an exaggeration — it is an invention, sitting on the free tool page that is the site's main entry point. For a compliance product sold to technical buyers who verify things, this is the highest-severity item here.

### 2.2 — P0: The site promises up to 3× more API quota than the code enforces

`billing.py` is the **enforced source of truth** — `_authorize()` checks these on every call:

| Tier | Price | **Enforced limit** | Rate limit |
|---|---|---|---|
| Free | $0 | **50 checks / day** (by IP, no key) | — |
| Dev | $19/mo | **10,000 checks / MONTH** | 1,000 / hour |
| Team | $99/mo | **100,000 checks / MONTH** | 5,000 / hour |

The marketing copy contradicts this, in the dangerous direction:
- `api.py:713` — *"10,000+ **daily** checks"* → the limit is 10,000 **per month**.
- `api.py:2196-2197` — the `/pricing` table's *"1,000 checks" / "10,000 checks"* framed per-day.
- `api.py:199`, `:512`, `:796` — further variants (`10,000+`, `100,000`, `100,000+`).

A buyer reading *"1,000/day"* on `/pricing` reasonably expects ~30,000 checks/month for $19. `billing.py` cuts them off at **10,000**. They will hit the wall, mid-integration, having paid. That is a material misrepresentation the code will enforce against the customer.

### 2.3 — P1: A visibly broken counter on the primary free tool

`api.py:5952`:
```html
<strong id="live-count">—</strong> screens today
```
If nothing populates `#live-count`, the page renders literally **"— screens today"** — a dash where a number should be, on the page that is supposed to demonstrate live data.

### 2.4 — Things that are RIGHT — do not "fix" them

- **The honest "no fabricated testimonials yet" section** — a genuine trust asset on a site whose sister properties invented proof. Keep it.
- **Real, working Stripe checkout** — `/checkout/dev` and `/checkout/team` resolve to live `cs_live_` sessions. **Do not touch the checkout flow.**
- **The free wallet checker genuinely works** with no signup.
- The `782 OFAC wallets tracked` / `19,086 names` / `16 jurisdictions` stat tiles reflect real data — leave them alone (RULE 2).

### 2.5 — EXPLICIT NON-GOALS (do not do these)

Do **not** redesign the hero, restructure the value stack, add exit-intent, add a cookie banner, add heatmaps, or rewrite the founder story. At 44 visitors/90 days none of it is measurable, and every one of those edits risks the 836 KB `api.py` (RULE 3). **The bottleneck on this site is distribution, not conversion.** That is an owner decision, recorded in Section 7 — not something you fix by editing pages.

---

## 3. EXECUTION

Three targeted edits. Nothing more.

### STEP 3.1 — Delete the fabricated claim

**File:** `api.py`, **line ~6003** (verify the line before editing — the file is large and line numbers drift):
```bash
grep -n "12,000+ agents screen with us" api.py
```

Remove the fabricated framing. Replace the heading with something true that needs no count — e.g. **"Why screen with us"** or **"What this checks"** — or delete the heading and keep the section body if the body itself is factual.

**Read the section body underneath it.** If the body also asserts adoption numbers or invented usage, remove those sentences too. If the body is a factual description of the screening method, keep it.

**Gate 3.1 — all must pass:**
```bash
grep -c "12,000+ agents" api.py                    # MUST be 0
# The REAL OFAC figures MUST survive (RULE 1):
grep -c "12,000" data/global-sanctions-statistics/index.html   # MUST be UNCHANGED (>0)
grep -c "12,000" stats/index.html                              # MUST be UNCHANGED (>0)
git diff --stat data/ stats/ public/                           # MUST be empty
python3 -c "import ast;ast.parse(open('api.py').read());print('api.py parses OK')"
```
**If `git diff --stat data/ stats/ public/` is non-empty you touched real OFAC data — revert immediately.**

---

### STEP 3.2 — Make every stated limit match what `billing.py` enforces

Canonical values (from `billing.py` `TIERS`, Section 2.2). Correct **each** marketing occurrence to match:

```bash
grep -n "10,000\|100,000\|1,000 checks" api.py | head -20
```

Work them **one at a time**, reading context:
- `api.py:713` — *"10,000+ daily checks"* → **"10,000 checks/month"** (this is the clearest error: daily vs monthly).
- `api.py:2196-2197` — the `/pricing` table → state **10,000/month** (Dev) and **100,000/month** (Team), not per-day figures.
- `api.py:199`, `:512`, `:796` — normalise to the same monthly framing.
- Free tier — state **50 checks/day by IP, no key required** (that one genuinely *is* per-day).

Rules for this step:
- **`billing.py` wins.** Never edit `billing.py` to match the marketing — that would change what paying customers actually receive.
- Do **not** drop the `+` into a bigger number, and do not "round up" to look better.
- Preserve the hourly rate-limit mention if a page already states it; do not invent one where none exists.

**Gate 3.2:**
```bash
grep -c "daily checks" api.py            # MUST be 0 for the Dev/Team tiers
git diff --stat billing.py               # MUST be empty
python3 -c "import ast;ast.parse(open('api.py').read());print('OK')"
```

---

### STEP 3.3 — Fix or remove the blank counter

**File:** `api.py:~5952` — `<strong id="live-count">—</strong> screens today`

```bash
grep -n "live-count" api.py    # find the element AND any JS that populates it
```

- **If a real endpoint exists** that returns a screen count, wire `#live-count` to it and ensure a sensible fallback when the fetch fails (hide the whole pill rather than showing a dash).
- **If no such endpoint exists — remove the entire pill.** Do **not** invent a number, and do not hardcode one (RULE 6).

Keep the neighbouring `782 OFAC wallets tracked` pill — that is real data.

**Gate 3.3:**
```bash
grep -c 'id="live-count">—<' api.py    # MUST be 0
python3 -c "import ast;ast.parse(open('api.py').read());print('OK')"
```

---

## 4. VALIDATION (before deploy)

```bash
cd ~/workspace/agentmail

# 4.1 api.py still parses (it IS the whole server — a syntax error takes the site down)
python3 -c "import ast;ast.parse(open('api.py').read());print('api.py OK')"
python3 -c "import ast;ast.parse(open('billing.py').read());print('billing.py OK')"

# 4.2 Fabrication gone, real OFAC facts intact
grep -c "12,000+ agents" api.py                       # 0
git diff --stat data/ stats/ public/ alternatives-to/  # EMPTY

# 4.3 Enforced limits untouched
git diff --stat billing.py                             # EMPTY

# 4.4 Infra untouched (RULE 5)
git diff --name-only | grep -cE "fly.toml|Dockerfile"  # 0

# 4.5 ONLY api.py is modified by you
git diff --name-only -- . ':!alternatives-to' | grep -v "^HERMES_TASK" 
# should list api.py and nothing else you didn't intend

# 4.6 Smoke-test locally if feasible
python3 -c "import api" 2>&1 | head -5     # import errors surface here
```

**Do not deploy if `api.py` fails to parse.** It is the entire server; a syntax error is a total outage on a compliance API.

---

## 5. COMMIT & DEPLOY

**5.1 — Stage explicitly (never `git add -A` — RULE 4).**
```bash
git add api.py
git status --short | head -5   # REVIEW: alternatives-to/* must NOT be staged
```

**5.2 — Commit.**
```bash
git commit -m "fix(sanctionsai): remove fabricated adoption claim, align stated quotas with enforced limits

- Delete 'Why 12,000+ agents screen with us' — the site has had 44 visitors
  in 90 days. Real OFAC SDN figures (~12,000 designations) left untouched.
- Correct Dev/Team quota copy: billing.py enforces 10,000 and 100,000 checks
  per MONTH; pages advertised up to 'daily', promising ~3x what the API
  delivers and cutting off paying customers mid-integration.
- Remove the blank '— screens today' counter on the free wallet checker.

billing.py, fly.toml and all OFAC/sanctions data unmodified."
```

**5.3 — Deploy.**
```bash
flyctl deploy -a agentmail-api
```
No config changes, no secrets, `fly.toml` unchanged — a single deploy publishes everything (the pages are inline routes in `api.py`).

If the deploy fails, read the error. **Do not** retry with modified `fly.toml`, changed machine sizes, or new secrets. Report and stop.

---

## 6. POST-DEPLOY VERIFICATION

```bash
sleep 30

# 6.1 The site is UP (api.py is the whole server — verify first, always)
for u in / /pricing /docs /faq /tools/wallet-checker; do
  printf "%-24s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' https://sanctionsai.dev$u)"
done   # ALL MUST be 200

# 6.2 Fabrication gone
curl -s https://sanctionsai.dev/tools/wallet-checker | grep -c "12,000+ agents"   # MUST be 0

# 6.3 Blank counter gone
curl -s https://sanctionsai.dev/tools/wallet-checker | grep -c "id=\"live-count\">—"  # MUST be 0

# 6.4 Quotas now consistent
curl -s https://sanctionsai.dev/pricing | grep -oE "[0-9,]+ checks?/(month|day)" | sort -u

# 6.5 ⚠ MACHINE CONFIG SURVIVED THE DEPLOY (RULE 5 — this has regressed before)
flyctl config show -a agentmail-api | grep -E "auto_stop_machines|auto_start_machines|min_machines_running"
# MUST show: suspend / true / 1

# 6.6 The manifests still serve (api.py surgery regression check)
for u in /llms.txt /agents.md /.well-known/agent-card.json /.well-known/mcp.json /openapi.json; do
  printf "%-38s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' https://sanctionsai.dev$u)"
done   # ALL MUST be 200

# 6.7 The free tool still actually works
curl -s "https://sanctionsai.dev/tools/wallet-checker" | grep -c "782 OFAC wallets"   # real data intact
```

**6.8 — Rendered check:** open `/tools/wallet-checker` in a browser, run a real wallet check, confirm it returns a result and no dash-placeholder remains.

**Rollback:**
```bash
git revert --no-edit HEAD && flyctl deploy -a agentmail-api
# or, faster for an outage:
flyctl releases -a agentmail-api          # find the previous release
flyctl deploy -a agentmail-api --image <previous-image>
```

---

## 7. REPORT (write this file, always — even on abort)

Write `~/workspace/agentmail/HERMES_REPORT_CONVERSION_REPAIR.md` with:

1. **Every `api.py` edit, line by line** — old string → new string, with the justification. RULE 3 requires each to be individually accounted for.
2. **Quota reconciliation table** — the `billing.py` enforced value vs every page that stated something different, before and after.
3. **Proof the real OFAC data was untouched** — the `git diff --stat data/ stats/ public/` output (must be empty).
4. **Machine config check (6.5)** — the actual `flyctl config show` values. If `auto_stop_machines`, `auto_start_machines`, or `min_machines_running` regressed, say so loudly; that is a P0.
5. **Manifest check (6.6)** — all AI-discoverability routes still 200.
6. **Escalate to owner:**
   - **Distribution is the bottleneck, not conversion.** 44 visitors in 90 days. The page craft (real free tool, working Stripe checkout, strong copy, honest no-testimonials section) already exceeds what this traffic can validate. Further CRO work here has **no measurable return** until traffic exists. This is the single most useful finding on this site.
   - **The $499 "Compliance Pro" tier may not be sellable.** `billing.py` defines only `dev` and `team`, with a **commented-out** third tier around lines 52-53. If a $499 plan is advertised anywhere, confirm a Stripe price and a `TIERS` entry exist — otherwise it cannot be purchased or enforced. **Do not create one yourself.**
   - **API keys need rotation** (carried over from the portfolio security audit) — owner action, not yours.
   - Whether the previously advertised per-day quotas were ever sold to a real customer. If anyone purchased Dev expecting ~30,000 checks/month, the owner should decide how to honour it.

---

## 8. WHAT SUCCESS LOOKS LIKE

- `grep -c "12,000+ agents" api.py` → **0**, while `data/`, `stats/` and `public/` are **byte-identical** (real OFAC figures intact).
- Every advertised quota matches what `billing.py` enforces; `billing.py` itself is **unmodified**.
- No blank `—` placeholder remains on the free tool.
- `api.py` parses, the site returns **200** on all five key routes, and every AI manifest still serves.
- `fly.toml` untouched, and `auto_stop_machines=suspend` / `min_machines_running=1` **confirmed still in effect after deploy**.
- The 148 in-flight `alternatives-to/*` files were **never staged**.
- No new number, testimonial, or claim was invented anywhere.

**The deepest point:** this is the best-built page in the portfolio and the least-visited — a real working tool, a real Stripe checkout, a real guarantee, and an unusually honest "we have no testimonials yet" admission. It does not need conversion work; it needs people. The only two things worth changing are the two that would embarrass it in front of the first serious prospect: a claim that 12,000 agents use it when 44 humans have ever seen it, and a price page promising three times the quota the code will actually grant. Fix those, verify the machine config survived, and then go argue for distribution — not another redesign.
