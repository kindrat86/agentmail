# Owner Actions — DotCom Secrets audit, 2026-07-26

The code changes from the 2026-07-26 DotCom Secrets audit are **deployed as
code** — every route, page, email body, and PDF is wired and verified locally.
**Three things require a human with access to the production accounts.** None
of them block the deploy; they turn the new infrastructure from "wired" to
"transacting."

---

## 1. Turn on email (the single biggest lever) — `RESEND_API_KEY`

Every email sequence (welcome, 5-day Soap Opera, 30-day Seinfeld, winback,
post-purchase) is written and wired, but none send because the Resend key is
not set on Fly.io. The `/subscribe` endpoint now **honestly reports**
`email_sent:false` until this is done, so you can verify the fix the moment the
key lands.

```bash
flyctl secrets set RESEND_API_KEY=re_xxxxxxxxxxxx --app agentmail-api
```

Then verify:
```bash
# should return email_sent:true once the key is live
curl -X POST https://sanctionsai.dev/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email":"your+test@sanctionsai.dev","source":"key-check"}'
```

**Impact:** turns the entire 35-email follow-up engine from dead code into a
live lead-nurturing machine. This alone lifts Dotcom Secrets Ch 6 (Follow-Up
Funnels) from 48 → ~75.

**Also recommended:** set a real `EMAIL_FROM` if you want a different from-name
(defaults to `agentmail <noreply@mail.sanctionsai.dev>` — your Resend domain
must already be verified for `mail.sanctionsai.dev`).

---

## 2. Create the $7 tripwire Stripe Payment Link — `STRIPE_PAYMENT_LINK_TRIPWIRE`

The `/tripwire` page is re-opened. Until this env is set, the buy-button falls
back to a **working** capture path (sends the subscriber the playbook + the
owner an email to invoice manually). The moment you set this, it becomes a
true one-click impulse buy.

In Stripe: **Payment Links → Create** → product "OFAC Compliance Quick-Start
Kit" → one-time $7 → copy the `https://buy.stripe.com/...` link.

```bash
flyctl secrets set STRIPE_PAYMENT_LINK_TRIPWIRE=https://buy.stripe.com/your_link --app agentmail-api
```

Verify: visit `https://sanctionsai.dev/tripwire` — the button should read
"Get the Quick-Start Kit - $7" and point to your Stripe link.

---

## 3. (Optional, for the order bump) `STRIPE_PRICE_BUMP_AUDIT`

The order-bump interstitial (`/checkout/dev/bump`) is live and the checkbox
works. The bump only actually *adds* the line item if this env is set; if it
isn't, the bump is silently skipped and the user still checks out fine with
just Dev (graceful degradation — `billing.py:227`).

In Stripe: create a product "Extended Audit Log" → recurring $9/mo → copy the
`price_...` ID.

```bash
flyctl secrets set STRIPE_PRICE_BUMP_AUDIT=price_xxxxxxxxxxxx --app agentmail-api
```

Verify: `https://sanctionsai.dev/checkout/dev/bump` → toggle the checkbox →
the checkout URL should change between `/checkout/dev` and
`/checkout/dev?bump=audit_plus`.

---

## Deploy command (no other config needed)

```bash
cd ~/workspace/agentmail
flyctl deploy
```

After deploy, smoke-test the four new routes:
```bash
for r in /playbook.pdf /checkout/dev/bump /upgrade /tripwire; do
  printf "%-26s " "$r"; curl -sI "https://sanctionsai.dev$r" | head -1
done
```
All four should return `HTTP/2 200`.

---

## What shipped (code-only, no owner action needed)

| Fix | Dotcom Secrets chapter | What changed |
|---|---|---|
| Honest subscribe | Ch 6 (Follow-Up) | `/subscribe` no longer claims `email_sent:true` when no email sent; returns `email_configured` + `send_error` |
| Playbook delivery | Ch 1 + Ch 3 (bait) | New `/playbook.pdf` (4-page PDF, built by `scripts/build_playbook.py`); welcome email now links it |
| Tripwire re-opened | Ch 1 + Ch 5 | Dead Stripe placeholder replaced with env-driven link + working fallback |
| Ascend path | Ch 14 + Ch 15 (order bump + upsell) | New `/checkout/dev/bump` interstitial + `/upgrade` page; post-purchase email + homepage CTA wired to them |
| VSL section | Ch 6 + Ch 7 (Hook/Story/Offer + Epiphany Bridge) | New homepage section: the one big idea, 3 false beliefs rebutted, stack + risk reversal |
| Pricing guarantee | Ch 6 (Offer) | Real guarantee block on `/pricing` (was buried in FAQ) |
| Real Seinfeld bodies | Ch 8 (Seinfeld) | All 30 emails now unique (was 1 template × 29) |

Files changed: `api.py`, `scripts/build_playbook.py` (new),
`public/agent-compliance-playbook.pdf` (new, generated).
Docs: `BRUNSON_DOTCOM_SECRETS_AUDIT_2026-07-26.md` (the full chapter-by-chapter
scorecard), this file.
