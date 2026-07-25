# sanctionsai.dev — Expert Secrets audit

**Auditor's frame:** Russell Brunson, *Expert Secrets* (2nd ed.), all 15 Secrets across the three sections.
**Date:** 2026-07-25 · **Surface audited:** live production, sanctionsai.dev
**Composite: 47 / 100**

| Section | Secrets | Mean |
|---|---|---|
| One — Creating Your Movement | #1–#6 | **59** |
| Two — Creating Belief | #7–#10 | **58** |
| Three — 10X Secrets (one-to-many selling) | #11–#15 | **24** |
| **Composite (unweighted mean of 15)** | | **47** |

The previous portfolio audit (2026-07-25) scored this site **56** on Expert Secrets. I am scoring it
lower, and the reason is not that the site got worse. It is that I checked the claims. Three of the
site's load-bearing assertions do not survive being checked, and in Brunson's model a claim that
collapses under inspection does not score as a weak claim — it scores as a negative, because it takes
the rest of the page down with it.

---

## Scores

| # | Secret | Score |
|---|---|---|
| 1 | Finding Your Voice (the Attractive Character) | 48 |
| 2 | Teaching Your Framework | 71 |
| 3 | The Three Core Markets / Desires | 66 |
| 4 | The New Opportunity | 74 |
| 5 | More Money, Same Framework (the Value Ladder) | 34 |
| 6 | The Future-Based Cause | 63 |
| 7 | The Big Domino | 44 |
| 8 | The Epiphany Bridge | 79 |
| 9 | The Hero's Two Journeys | 51 |
| 10 | The Four Core Stories | 58 |
| 11 | The Perfect Webinar / one-to-many | 8 |
| 12 | The Three Secrets | 22 |
| 13 | The Stack Slide | 46 |
| 14 | Trial Closes | 19 |
| 15 | Closes and Risk Reversal | 26 |

---

## The three things that were breaking everything else

### 1. The number the whole offer rests on was wrong — in four different ways, on the same domain

The Big Domino here is: *if I can make you believe one unscreened agent payment is a
strict-liability fine you personally eat, nothing else matters.* Correct instinct. It was built on a
number that changed depending on which page you landed on:

| Figure | Where | Occurrences |
|---|---|---|
| $356,000 | hero H1, risk pill, the founder's own quote, Day-1 email | 26 |
| $330,944 | FAQ, /about, /penalties, research paper — labelled *"2024 adjustment"* | 17 |
| $330,000 | /teardown — described as the **"average OFAC penalty"** | 6 |
| `330944` | bare constant in the SEI exposure calculator | 1 |

None of them is right. The IEEPA maximum civil monetary penalty is **$377,700 per violation**
(Treasury inflation adjustment published 2025-01-15, Federal Register 2025-00786, amending
31 CFR 501.701; $368,136 in 2024, $356,579 in 2023 — which is where the rounded "$356,000" came
from, three years stale). No 2026 adjustment has been published.

And the framing inverted the statute. Every instance read *"OFAC penalties **start at** $X"*. It is a
**ceiling**, not a floor — the greater of $377,700 or twice the transaction value. Describing a
maximum as a minimum is the kind of error that, on a compliance product, tells a careful reader
everything they need to know.

This audience verifies. That is the whole reason the free curl works as well as it does. The same
instinct that makes a developer run the curl makes them check the citation — and it took about ninety
seconds to find the number wrong.

### 2. The headline guarantee was voided by the site's own Terms of Service

The risk reversal appeared four times, most forcefully as:

> **Zero-liability guarantee** — if a check you pass results in an OFAC fine, we cover the first
> **$10,000** of legal fees.

`/terms`, on the same domain:

> agentmail shall not be liable for any indirect, incidental, or consequential damages, **including
> but not limited to regulatory penalties, legal fees**, or business losses…

Brunson's rule on guarantees is that they should be specific enough to be frightening to offer, and
then honoured without argument. A guarantee your own lawyer has already voided is worse than no
guarantee at all, because the one prospect who reads both pages stops believing everything else.

### 3. Two product claims were contradicted by the code

- **"Synced hourly … never stale"** — on the trust bar, in the stack slide, and twice in the FAQ.
  `compliance/osint.py` sets `_TTL = 24 * 3600`, and `/health` has been publicly serving
  `cache_ttl_hours: 24` the entire time. The same site said "refreshed daily" in six other places, so
  it contradicted itself as well as the code — and the pessimistic version was the true one.
- **"Screen a counterparty against OFAC/EU/UN/UK sanctions lists"** — in the MCP tool description,
  the CLI help, `core.py`, the docs, and twice on `/pricing` as *"All plans include OFAC/EU/UN/UK
  data"*. `osint.py` fetches exactly two sources, both OFAC: `vile/ofac-sdn-list` releases and
  Treasury `sdn.csv`. **EU, UN and UK consolidated lists are not screened at all.** On a compliance
  product this is the most dangerous sentence on the site: a customer who relies on it is exposed to
  precisely the fine we sell against.

---

## Section One — Creating Your Movement (59)

**#1 Finding Your Voice — 48.** The homepage has a real Attractive Character: Maryan, first person,
test #47, *"I sat there staring at the screen."* Then he disappears. `/about` is written by "a small
team" saying "we"; seven page types bylined "agentmail team"; the Cause was signed "— The agentmail
team". Two identities on one domain, and the committee is the one doing most of the talking. No
photo, no bio, no evidence the person exists outside the homepage.

**#2 Teaching Your Framework — 71.** The best thing on the site. *The 4-Gate Agent Payment
Protocol™* — SCREEN → SCORE → STOP → STAMP — is genuinely ownable, named, trademarked, and given a
philosophy ("a protocol, the same way TLS is a protocol"). Deduction: it is taught once, on the
homepage, with no dedicated page or diagram, and its four gates map 1:1 onto the four API endpoints —
which makes it read as a product menu in a framework's clothing rather than a method someone could
follow without buying.

**#3 Three Core Markets — 66.** Wealth → developers shipping autonomous payment agents → the
x402/AgentKit/MCP builders. A proper niche of a niche. Deduction: seven `/for/<industry>` pages drag
it back toward the generic compliance market, which is the one market where Chainalysis wins.

**#4 The New Opportunity — 74.** Strong. *"Chainalysis and Elliptic exist. They are not for you…
The SDK wanted a key. The key wanted a procurement cycle. The cycle wanted a budget that didn't
exist yet."* That is a textbook opportunity switch, not an improvement offer. Deduction: `/pricing`
then reverts to exactly the improvement frame — a five-way feature comparison against the incumbents.

**#5 The Value Ladder — 34.** The weakest of Section One. The $7 tripwire **cannot be bought** —
*"Checkout is not automated yet — email and we send payment details and the kit by hand"* — while $19
and $99 both have live Stripe sessions. The cheapest, highest-volume rung is the only one without
checkout. Nothing exists above $99, on a site whose entire pitch is a $377,700 liability; there is no
offer priced anywhere near the pain it describes. And two different front-end lead magnets (the
homepage 5-day series, the `/start` playbook PDF) compete for the same email.

**#6 The Future-Based Cause — 63.** Real and well-written: *"We are building the compliance layer
before the first massive fine makes agent payments illegal."* There is an enemy and a deadline.
Deductions: no manifesto page, no name for the tribe (a movement needs a noun for its members), no
way to join beyond an email box, no status or milestone — and it was signed by a team rather than a
person. A cause needs a face.

## Section Two — Creating Belief (58)

**#7 The Big Domino — 44.** See finding 1. The domino is correctly *chosen* and was resting on a
falsifiable number. Now cited to primary source.

**#8 The Epiphany Bridge — 79.** The strongest single asset. Backstory → wall (test #47) → epiphany
(checked it against the SDN list; it was there) → new opportunity. Specific, first person, a number
attached to the moment, no technobabble. Deductions: it appears once, on one page, in one medium; and
the wrong dollar figure sat inside the quote itself.

**#9 The Hero's Two Journeys — 51.** The founder's journey of achievement is told well. The reader's
journey of transformation is barely told at all. "What happens if you do nothing" is a good attempt
but is framed entirely as loss-avoidance — never as *who you become* (the developer whose agent is
auditable, who shipped compliance before it was mandatory). Right now the founder is the hero of
every story on the page, and the reader is the bystander.

**#10 The Four Core Stories — 58.** The vehicle belief is handled properly and twice: *"Doesn't my
payment provider handle this?" No. x402, AP2, ACP and AgentKit move money. They do not screen
recipients.* Named false belief, story attached. The internal belief ("I can't do this myself") is
asserted via "one curl, 30 seconds" but never told as a story. The external belief (procurement,
budget, legal) is touched in the Chainalysis passage but never resolved into a story with a
character. And there is not one customer story on the domain — deliberately, per the honest note
*"When real customers tell us what agentmail did for them, their words go right here. Not before."*
That restraint is correct and it is expensive. The answer is not to fabricate one; it is to go earn
one.

## Section Three — 10X Secrets (24)

**#11 The Perfect Webinar — 8.** There isn't one. No webinar, no VSL, no recorded walkthrough, no
presentation funnel of any kind. For a $19–$99/mo self-serve product that is defensible; against the
$377,700 frame the site itself builds, it means the entire high-intent audience is being sold by a
pricing table. Biggest single scoring gap.

**#12 The Three Secrets — 22.** Three belief-breaking blocks exist on the homepage but are not
structured as the Three Secrets, are not each anchored by story → strategy → case study, and do not
stack toward a close.

**#13 The Stack Slide — 46.** A real stack slide exists — four items, individual values, a $1,096
total against a $19 price. Correct mechanics and rare in dev tools. Deductions: the individual values
were unanchored (nothing justifies $499/mo for `sanctions_check`, so a skeptical developer discounts
the entire stack — a concurrent session has since replaced them with "included"), and the stack is
never restated at the point of purchase; `/pricing` is a bare feature grid with no total-value anchor.

**#14 Trial Closes — 19.** Almost absent. No yes-ladder, no micro-commitments, no "if I could show
you X, would you Y?". The one genuine trial close on the site is excellent and nobody would recognise
it as one: *run this curl against a known-sanctioned wallet and watch it return `BLOCK`.* That
converts a skeptic into someone who has already used the product. It is buried mid-page instead of
being the spine of the funnel.

**#15 Closes and Risk Reversal — 26.** See finding 2. Compounded by a 15-minute countdown on
`/tripwire` that reset on every page load, an unverifiable *"First 50 devs locked in at $19/mo
forever"*, and an empty testimonial box still carrying the attribution *"— Agent Framework Author,
San Francisco"* with the quote removed. Four closing claims, none of which survived inspection.

---

## What was changed

Committed `cea7225` plus edits carried in `6f345cc`. All live.

1. **Penalty figure corrected sitewide** — 113 replacements across 13 files. $356,000 / $330,944 /
   $330,000 / `330944` → **$377,700**; "penalties start at" → "penalties reach"; "(2024 adjustment)"
   → "(2025 adjustment)"; "average OFAC penalty" → "maximum"; the SEI calculator constant and its
   derived $165.5M/day ceiling → $188.9M/day.
2. **Primary source cited** — the hero risk pill now links to 31 CFR 501.701, and a new FAQ entry
   ("Where does the $377,700 figure come from?") gives the Federal Register document, the date, and
   the fact that it is a ceiling and not a floor. This is the Big Domino fix: the claim now gets
   *stronger* when the reader checks it.
3. **"Synced hourly" → daily** everywhere, pointing at `/health` for the actual fetch time.
4. **"OFAC/EU/UN/UK" → "the US Treasury OFAC SDN list"** in the MCP tool description, CLI help,
   `core.py`, `mcp_server.py`, the docs and `/pricing`.
5. **$10K legal-fee guarantee removed**, replaced with a 30-day money-back guarantee and the
   audit-trail receipt — both deliverable, neither contradicted by Terms.
6. **"First 50 devs locked in at $19/mo forever"** removed.
7. **One voice** — seven "agentmail team" bylines → Maryan; the Cause signed by the founder;
   `/about` rewritten from "a small team … we" to first person, matching the homepage story.
8. Email templates (`landing_new.html`, `agent_page_new.html`) carried the same three false claims,
   including the fabricated precision *"If the Treasury adds a wallet at 2:47 PM, agentmail catches
   it at 3:00 PM."* Fixed.
9. Stray `</div>` on `/tripwire` removed.

## What is left, in priority order

**Owner decisions (I did not make these):**

- **Reinstate the legal-fee guarantee properly, or leave it out.** It is a genuinely strong Brunson
  close and the category has nobody offering one. It needs `/terms` amended and a real reserve behind
  it. That is a financial commitment, not a copy edit.
- **The brand collision.** The domain is `sanctionsai.dev`; the product calls itself **agentmail**
  in the nav, footer, `/about`, `/pricing` and every byline; the homepage logo says "Sanctions AI";
  and the hero curl points at `agentmail-api.fly.dev`. Secret #1 asks for one identity a reader can
  form a relationship with, and there are three. `sanctionsai.dev/sanctions` returns the identical
  response, so switching the demo curl to the branded domain is free — the rest is a naming decision
  only the owner can make.
- **The $7 tripwire: automate it or retire it.** A rung nobody can climb is worse than no rung.

**Highest-leverage remaining work, in Brunson order:**

1. **A one-to-many asset (#11, scored 8).** Even a 12-minute recorded screen-share — *"I wired OFAC
   screening into an x402 agent in 12 minutes"* — built on the Perfect Webinar spine: one thing,
   three secrets, stack, close. This is the largest single point gain available.
2. **Make the curl the trial close (#14, scored 19).** Put the sanctioned-wallet curl at the top,
   have it return `BLOCK` in the reader's own terminal, and close from the fact that they have
   already run the product. Micro-commitment before any ask.
3. **Tell the reader's journey (#9, scored 51).** One section on who they become, not what they
   avoid.
4. **Restate the stack at the point of sale (#13).** `/pricing` is a feature grid; it should carry
   the stack and the total-value anchor the homepage already has.
5. **Earn one real customer story (#10).** The refusal to fabricate is right and should be kept. The
   fix is to go get one.

---

# Re-score after remediation — **72 / 100** (was 47)

Verified against production on 2026-07-26 (Fly v394, image
`deployment-01KYDHEW19ZMD15HWNS94YRENJ`, health check passing, `ready: true`,
947 wallets). Some of this gain is concurrent sessions' work, marked *(c)*.

| Section | Was | Now |
|---|---|---|
| One — Creating Your Movement | 59 | **70** |
| Two — Creating Belief | 58 | **78** |
| Three — 10X Secrets | 24 | **69** |
| **Composite** | **47** | **72** |

| # | Secret | Was | Now | What moved it |
|---|---|---|---|---|
| 1 | Finding Your Voice | 48 | 68 | Seven "agentmail team" bylines → Maryan; /about rewritten first person; the founder now has a stated reason to be listened to (building with AI since 2013, ~a decade before ChatGPT) — authority via mechanism, not adjectives. Still no photo, no bio, and the brand collision is now *four*-way. |
| 2 | Teaching Your Framework | 71 | 86 | `/protocol` teaches all four gates end to end — what each does, what failing it looks like in production, the exact call. |
| 3 | Three Core Markets | 66 | 66 | Unchanged. |
| 4 | The New Opportunity | 74 | 78 | `/protocol` restates the opportunity switch; `/pricing` is still comparison-framed. |
| 5 | The Value Ladder | 34 | 52 | `/playbook` is real *(c)*; post-purchase ascension rebuilt *(c)*; `/protocol` is a new free rung. Tripwire still manual, still nothing above $99. |
| 6 | The Future-Based Cause | 63 | 70 | Signed by the founder; giving the whole method away is itself a movement move. No manifesto, no name for the tribe. |
| 7 | The Big Domino | 44 | 82 | Correct figure, cited to 31 CFR 501.701 and FR 2025-00786. The claim now gets *stronger* when checked. |
| 8 | The Epiphany Bridge | 79 | 82 | Retold on `/protocol` in a second context, with the correct figure inside the quote. |
| 9 | The Hero's Two Journeys | 51 | 74 | The self-audit puts the reader in their own story, and "And if you do" now pairs the loss-aversion block with the transformation: the agent acquires a property (it *cannot* pay a sanctioned address) rather than the reader adopting a policy. |
| 10 | The Four Core Stories | 58 | 74 | All three belief stories now told with story → strategy → a proof the reader can run. Still no customer story. |
| 11 | The Perfect Webinar | **8** | **64** | `/protocol` is a real one-to-many asset. Not video, no replay, no urgency mechanism — that is the remaining 36. |
| 12 | The Three Secrets | 22 | 76 | Explicitly structured on `/protocol`. |
| 13 | The Stack Slide | 46 | 72 | Fabricated $499/$299/$199/$99 anchors replaced with our own published $0.05 × 10,000 = $500 *(c)*; stack now also appears at the point of sale *(c)*. |
| 14 | Trial Closes | 19 | 61 | Four-question yes-ladder on `/protocol`, ending with the reader running a real screen against a real sanctioned address. |
| 15 | Closes / Risk Reversal | 26 | 74 | The $10K guarantee is real: Terms 5a carves it out *(c)*, `/guarantee` documents scope and claim process *(c)*, and responses now carry `screened_at` / `screen_id` / `list_version` so a claim can be evaluated *(c)*. Fake countdown, false scarcity and the false "First month free" all gone. |

## What shipped in the second pass

- **`/protocol`** — the site's first one-to-many asset (19 KB body; live, in the
  sitemap, linked from the footer and the homepage framework CTA). One Thing →
  Three Secrets → the four gates → self-audit → stack → close. The self-audit was
  exercised in production under the trusted-types CSP: both branches render and
  route correctly (`/playbook` when gates are open, `/guarantee` when closed), no
  console errors. The proof curl on the page returns
  `clean:false, action:BLOCK` with `screened_at` / `screen_id` / `list_version`,
  so the STAMP gate's claim is literally true.
- **The demo curl was rebranded** — 17 displayed examples moved from
  `agentmail-api.fly.dev` to `sanctionsai.dev`, which returns the identical
  response. The brand now appears in the artefact developers copy. `_PUBLIC_URL`
  and the preconnect hints still name Fly, deliberately.
- **`"First month free"` was false.** `billing.py` builds `mode="subscription"`
  with no trial of any kind, and the live Stripe page reads *"Subscribe to
  agentmail Dev / $19.00 per month"*, button *"Pay and subscribe"*. Removed.
- **`"30-day money back"` removed** — I introduced it earlier in this session while
  the $10K guarantee was still void, then wrongly kept it once the guarantee became
  real. Terms 6 says only "You can cancel at any time". A fix for one honesty
  defect had introduced another.

## Still open

**Owner decisions:**
- **The brand collision is four-way, and the fourth costs money.** The Stripe
  account presents as **"MicroSaaS"** on the checkout page, so a buyer hands a card
  to a name that appears nowhere on the site. Unrecognised descriptors drive
  disputes. Stripe dashboard fix.
- **No trial and no refund policy in Terms.** Either is a legitimate offer and a
  strong close — but the copy must not promise one until Terms does.
- **The $7 tripwire** still only sells by emailing a human.
- **Nothing above $99.** For a product framed around a $377,700 liability, there is
  no offer priced anywhere near the pain.

**Highest-leverage remaining work:**
1. **Video (#11, 64).** `/protocol` is the script. A 12-minute screen recording of
   the same content, with a replay page, is the rest of that secret.
2. **The reader's journey (#9, 58).** One section on who they become, not what they
   avoid.
3. **One real customer story (#10, 74).** The refusal to fabricate is correct and
   should hold. Go earn one.
4. **A name for the tribe (#6, 70).** A movement needs a noun for its members.

## The constraint this audit does not touch

Expert Secrets is a **conversion** framework, and conversion is a multiplier on
traffic. Per `sanctionsai-traffic-ceiling`, this domain recorded **0 clicks in 90
days**, and the earlier portfolio audit scored its Traffic Secrets at **28/100** —
the lowest of the three books by a wide margin, on every site in the portfolio.

So read the 47 → 72 correctly: the funnel is now honest and structurally sound, and
it is converting almost nobody, because almost nobody arrives. Every remaining
Expert Secrets point is worth less than the first real traffic source. The
recommendations above are still worth doing — a broken funnel wastes traffic you
later buy — but they are not the binding constraint and this document should not be
read as if they were.

## Note on concurrency

Several other Claude sessions were editing `~/workspace/agentmail` throughout this audit. One was
running an overlapping honesty pass (it removed the `/tripwire` countdown and the orphaned
testimonial while I was reading them) and swept my `api.py` edits into its own commit `6f345cc`;
another was mid-flight on a Stripe order-bump gate in `billing.py`; a third published its own full
trilogy audit (`BRUNSON_AUDIT_2026-07-25.md`, composite 59.2) and a DotCom Secrets one. The deploys
therefore carry their in-flight work as well as mine. Everything was compile-checked and
render-checked before shipping, and every fix was verified live afterwards.

Two things this cost, worth knowing for next time:

- **Commit attribution here does not reflect who wrote what.** My `api.py` work was swept into
  other sessions' commits twice, including the whole of `/protocol`.
- **A commit of mine was silently dropped.** `dd37283`, carrying the first version of this
  document, stopped being an ancestor of `HEAD` when a concurrent session rewrote the branch.
  Nothing reported it: `git log` on the path returned nothing and the file was simply absent.
  Recovered from the dangling commit. When work "disappears" in this repo, check
  `git merge-base --is-ancestor <commit> HEAD` before assuming it was never made.
