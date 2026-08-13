# Consolidation Scope — sanctionsai.dev thin FAQ / glossary / learn pages

Scoped 2026-08-14. This is a plan, not yet executed.

## The problem (measured, not assumed)

sanctionsai.dev has **~1,132 thin pages** (53–122 words each), sampled live:

| Category | Pages | Word count | Verdict |
|---|--:|--:|---|
| `/faq` | 608 | 53–122w | thin |
| `/glossary` | 359 | 70–108w | thin |
| `/learn` | 165 | 53–87w | thin |
| `/by-country` | 28 | 438–484w | **fine** (keep) |
| `/penalties` case studies | ~5 | 271w | fine (keep) |

### Root cause: pagination fragmentation, not a real corpus

The `faq/` directory holds **190 "Part N" fragments** — `ofac-screening-{topic}-faq-{1..10}`
across **19 topics** (aml, crypto, wallet, stablecoin, nft, web3, licensing, kyc,
penalties, payment, ai, agent, enforcement, defi, dao, exchange, compliance,
blockchain, screening). Each fragment is a standalone ~100-word page titled
"OFAC {Topic} FAQs Part N" (e.g. "OFAC Aml FAQs Part 1", confirmed in
`faq/ofac-screening-aml-faq-1/index.html`).

Alongside them sit **429 individual question pages** (`are-russian-banks-sanctioned`,
`can-crypto-be-frozen`, …), many also ~60–120 words.

The glossary repeats the same "Part N" pattern ("OFAC Civil Penalty Glossary Part 3").

So the honest corpus is roughly **19 FAQ topics + ~429 real questions + a finite
glossary**, which was mechanically exploded into ~1,132 near-duplicate pages.

## The fix — consolidate, don't generate

Three merges, ordered by leverage:

1. **19 topic-fragments → 19 substantive FAQ pages.** Each `ofac-screening-{topic}`
   topic's 10 parts become sections of one ~600–1,000-word page. This is the
   cleanest win: 190 pages → 19.

2. **429 individual questions → ~60–100 grouped FAQ pages.** Group by intent
   (screening mechanics, crypto wallets, penalties, legal scope, agents). Do NOT
   over-merge: keep any question that maps to a distinct high-intent query as its
   own page; merge only the near-duplicate long tail.

3. **Glossary "Part N" → consolidated entries.** Same treatment as (1).

### Expected outcome

- Page count: **~1,132 → ~120–160** (the site is genuinely *under* its 2,000 ceiling
  once sitemap duplication is also fixed — the consolidation is about quality, not
  hitting a floor).
- Per-page word count: ~100 → ~600–1,000.
- Effect: concentrates crawl budget + authority onto substantive pages, removes the
  thin-content dilution that suppresses the whole domain.

## Technical approach

1. **Extract** each fragment's body from `faq/*/index.html` (and the glossary
   source) with a script; concatenate per topic.
2. **Write** 19 merged pages (topic hub format: intro + per-question `<h2>` +
   answer), reusing the existing page shell + Article schema.
3. **Rewrite the sitemap** `pages` list in `api.py`: drop the 190 fragment paths,
   add the 19 merged paths. (The 2026-08-14 dedup already runs at emission, so
   merged pages are added once and stay unique.)
4. **301-redirect** every old fragment URL to its merged parent (preserves any
   link equity and prevents 404s). The `api.py` request handler already has a
   redirect table pattern to extend.
5. **Verify + deploy** (Fly), then IndexNow + GSC sitemap re-submit.

## Risks / decisions to confirm before executing

- **Redirect volume**: 190 + (N merged individual questions) redirects. Confirm
  the handler's redirect table can take that many without a code path change.
- **Individual-question granularity**: the 429 questions need a pass to classify
  keep-vs-merge. This is the only judgment-heavy step; the fragment merge (1) is
  fully deterministic.
- **No content is invented**: merging reuses existing text verbatim. Word counts
  rise because ten 100-word pages become one 1,000-word page, not because anything
  new is written.

## Suggested execution order

1. Ship the fragment merge (1) first — deterministic, high leverage, low risk.
2. Measure (GSC indexation + the pseo-machine digest) before touching the
   individual questions.
3. Then do the selective individual-question merge (2) with the keep/merge pass.
