#!/usr/bin/env python3
"""
Build the /faq/* consolidation map for sanctionsai.dev (work order #3).

Reads the on-disk faq/*/index.html corpus and emits
scripts/faq_consolidation_map.json with:
  keep      -> slugs that survive as hub pages (the ~60 destinations)
  redirect  -> { stub_slug: target_slug } for every stub being 301'd
  targets_needing_build -> hubs that must be expanded to >=1800 chars
               before their inbound redirects go live (guardrail 5.7).

ANALYSIS/PLAN artifact only. The 301 rollout is gated by guardrail 5.6
(owner approval + rollback commit + 50-URL canary, <=500/week) and is NOT
executed here. Nothing mutates routes or deploys anything.
"""
import os, re, html, json, collections

FAQ = "faq"

def slugs():
    return sorted(d for d in os.listdir(FAQ)
                  if os.path.isfile(os.path.join(FAQ, d, "index.html")))

def title_of(slug):
    p = os.path.join(FAQ, slug, "index.html")
    s = open(p).read()
    m = re.search(r"<h1>(.*?)</h1>", s, re.S) or re.search(r"<title>(.*?)</title>", s, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

def body_len(slug):
    s = open(os.path.join(FAQ, slug, "index.html")).read()
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return len(html.unescape(s).strip())

# --- 1. Existing topic hubs ("OFAC X FAQs" pages) -------------------------
EXISTING_HUBS = [
    "ofac-screening-agent", "ofac-screening-ai", "ofac-screening-aml",
    "ofac-screening-blockchain", "ofac-screening-compliance",
    "ofac-screening-crypto", "ofac-screening-dao", "ofac-screening-defi",
    "ofac-screening-enforcement", "ofac-screening-exchange",
    "ofac-screening-kyc", "ofac-screening-licensing", "ofac-screening-nft",
    "ofac-screening-payment", "ofac-screening-penalties",
    "ofac-screening-screening", "ofac-screening-stablecoin",
    "ofac-screening-wallet", "ofac-screening-web3",
]

# --- 2. Guide series "ofac-screening-{topic}-guide-{N}" -> part 1 hub ------
GUIDE_SERIES = [
    "api", "mcp", "risk", "x402", "crewai", "fincen", "openai", "solana",
    "autogen", "bitcoin", "fintech", "polygon", "startup", "agentkit",
    "ethereum", "treasury", "developer", "langchain", "enterprise",
    "regulation",
]

# --- 3. Standalone Q&A that survive as their own hub (distinct query intent,
#       substantive today or clearly worth deepening). ~25 pages. ------------
STANDALONE_KEEP = [
    # core questions a person with money + a problem actually types
    "what-is-ofac-screening", "does-ofac-apply-to-crypto",
    "how-to-comply-with-ofac", "what-is-an-ofac-compliance-program",
    "is-ofac-screening-required",            # absorbs the "required for crypto/agents" dups
    "how-often-does-ofac-update-sanctions",  # absorbs list-sync/frequency dups
    "what-happens-if-you-violate-ofac", "what-are-ofac-penalties",
    "how-are-sanctions-enforced", "what-is-the-ofac-blocking-process",
    "how-to-report-a-sanctions-violation",
    "what-is-an-sdn-list-entry", "what-is-a-sanctioned-wallet",
    "how-to-screen-crypto-wallets-ofac", "how-much-does-sanctions-screening-cost",
    "what-are-secondary-sanctions", "what-is-a-general-license-ofac",
    "what-is-the-magnitsky-act", "is-bitcoin-sanctioned", "is-usdt-sanctioned",
    "what-is-the-travel-rule", "can-i-trust-an-ai-agent-with-payments",
    "how-accurate-is-sanctions-screening", "what-chains-are-covered",
    "are-russian-banks-sanctioned", "what-is-wagner-group",
    "how-many-wallets-are-sanctioned", "what-is-a-mixer",
]

# --- 4. Explicit near-duplicate merges: thin page -> canonical kept page ----
NEAR_DUP_MERGE = {
    # "is screening required" family -> is-ofac-screening-required
    "is-crypto-ofac-screening-required": "is-ofac-screening-required",
    "is-ofac-screening-required-for-crypto": "is-ofac-screening-required",
    "is-sanctions-screening-required-for-ai-agents": "is-ofac-screening-required",
    "do-crypto-exchanges-need-ofac-screening": "is-ofac-screening-required",
    "do-i-need-sanctions-screening-for-defi": "is-ofac-screening-required",
    "do-i-need-sanctions-screening-for-stablecoins": "is-ofac-screening-required",
    "does-ofac-require-kyc-for-crypto": "is-ofac-screening-required",
    # list freshness / sync family -> how-often-does-ofac-update-sanctions
    "how-often-ofac-list-updated": "how-often-does-ofac-update-sanctions",
    "how-often-update-sdn-list": "how-often-does-ofac-update-sanctions",
    "what-is-the-ofac-list-update-process": "how-often-does-ofac-update-sanctions",
    "how-is-the-list-synced": "how-often-does-ofac-update-sanctions",
    "how-often-should-i-re-screen-counterparties": "how-often-does-ofac-update-sanctions",
    # "does OFAC apply to X" family -> closest topic hub
    "does-ofac-apply-to-defi": "ofac-screening-defi",
    "does-ofac-apply-to-daos": "ofac-screening-dao",
    "does-ofac-apply-to-stablecoins": "ofac-screening-stablecoin",
    "does-ofac-apply-to-crypto-lending": "ofac-screening-crypto",
    "does-ofac-apply-to-defi-yield-farming": "ofac-screening-defi",
    "does-ofac-apply-to-gaming-crypto": "ofac-screening-nft",
    "does-ofac-apply-to-layer-2-networks": "ofac-screening-blockchain",
    "does-ofac-apply-to-lightning-network": "ofac-screening-blockchain",
    "does-ofac-apply-to-mining": "ofac-screening-blockchain",
    "does-ofac-apply-to-non-us-companies": "ofac-screening-compliance",
    "does-ofac-apply-to-stablecoin-lending": "ofac-screening-stablecoin",
    "does-ofac-apply-to-stablecoin-yield": "ofac-screening-stablecoin",
    "does-ofac-require-screening-for-stablecoin-issuance": "ofac-screening-stablecoin",
    "does-sanctions-screening-apply-to-nfts": "ofac-screening-nft",
    "does-sanctions-screening-apply-to-testnet": "ofac-screening-crypto",
    # blocked / seized / blocking process family
    "what-is-a-blocked-transaction": "what-is-the-ofac-blocking-process",
    "what-is-the-difference-between-blocked-and-seized": "what-is-the-ofac-blocking-process",
    "can-crypto-be-frozen": "what-is-the-ofac-blocking-process",
    # false-positive / match handling family
    "how-to-handle-a-sanctions-false-positive": "ofac-screening-screening",
    "how-to-handle-an-ofac-match": "ofac-screening-screening",
    "what-is-a-sanctions-screening-false-positive-rate": "ofac-screening-screening",
    "what-is-a-sanctions-match": "ofac-screening-screening",
    # compliance program / stay compliant family
    "how-to-stay-compliant-with-ofac": "how-to-comply-with-ofac",
    "how-to-build-a-sanctions-list": "what-is-an-ofac-compliance-program",
    "how-to-build-ofac-compliance-program": "what-is-an-ofac-compliance-program",
    "how-to-audit-ofac-compliance-program": "what-is-an-ofac-compliance-program",
    "how-to-verify-ofac-compliance": "what-is-an-ofac-compliance-program",
    "how-to-monitor-sanctions-compliance": "what-is-an-ofac-compliance-program",
    "do-i-need-a-compliance-officer": "what-is-an-ofac-compliance-program",
    "how-to-respond-to-ofac-inquiry": "what-happens-if-you-violate-ofac",
    # jurisdiction / country / programs family
    "how-many-countries-are-sanctioned": "ofac-screening-compliance",
    "what-are-ofac-sanctions-programs-explained": "ofac-screening-compliance",
    "what-is-an-sdgt": "ofac-screening-compliance",
    # enforcement / penalties family
    "what-is-ofac-enforcement-guidelines": "ofac-screening-enforcement",
    "what-is-the-cost-of-a-sanctions-violation": "ofac-screening-enforcement",
    "what-is-ofac-enforcement-for-crypto": "ofac-screening-enforcement",
    "what-is-the-ofac-licensing-process": "ofac-screening-licensing",
    "what-is-ofac-compliance-risk": "ofac-screening-screening",
    "what-is-an-ofac-risk-score": "ofac-screening-screening",
    "what-is-ofac-risk-assessment": "ofac-screening-screening",
    "can-ofac-enforcement-apply-retroactively": "ofac-screening-enforcement",
    "ofac-enforcement-trends-2026": "ofac-screening-enforcement",
    "can-sanctions-be-removed": "ofac-screening-compliance",
    "can-sanctions-be-lifted": "ofac-screening-compliance",
    "what-is-ofac-facilitation": "ofac-screening-compliance",
    "what-is-fail-closed": "ofac-screening-screening",
    "screening-vs-monitoring": "ofac-screening-screening",
    "what-is-a-vasp": "ofac-screening-aml",
    "what-is-the-travel-rule-and-ofac": "what-is-the-travel-rule",
    "what-is-the-difference-between-ofac-and-fincen": "ofac-screening-aml",
    "does-ofac-screening-replace-aml": "ofac-screening-aml",
    "can-ofac-sanction-open-source-code": "ofac-screening-blockchain",
    "can-i-screen-crypto-by-ip-address": "ofac-screening-crypto",
    "can-ofac-track-crypto-transactions": "ofac-screening-crypto",
    "how-to-audit-crypto-transactions": "ofac-screening-crypto",
    "can-an-agent-violate-ofac": "ofac-screening-agent",
    "can-i-screen-business-names": "ofac-screening-screening",
    "can-i-screen-by-name-only": "ofac-screening-screening",
    "can-i-screen-in-bulk": "ofac-screening-screening",
    "can-i-use-sanctionsai-for-hiring": "ofac-screening-screening",
    "can-i-self-host-sanctions-screening": "ofac-screening-screening",
    "can-sanctionsai-screen-multiple-wallets": "ofac-screening-wallet",
    "does-sanctionsai-support-multi-language": "ofac-screening-screening",
    "does-sanctionsai-work-with-stripe": "ofac-screening-payment",
    "how-much-does-agentmail-cost": "ofac-screening-screening",
    "what-is-a-sanctions-screening-api-key": "ofac-screening-screening",
    "what-is-an-ofac-screening-api": "ofac-screening-screening",
    "how-do-i-monitor-agent-payments": "ofac-screening-agent",
    "what-is-a-sanctions-screening-audit": "ofac-screening-screening",
    "what-is-a-sanctions-screening-tool": "ofac-screening-screening",
    "how-to-choose-a-sanctions-screening-tool": "ofac-screening-screening",
    "how-to-implement-ofac-screening": "ofac-screening-screening",
    "how-to-test-ofac-screening": "ofac-screening-screening",
    "how-to-add-ofac-screening-to-existing-app": "ofac-screening-screening",
    "how-to-integrate-ofac-screening-into-agent": "ofac-screening-agent",
    "how-to-screen-crypto-exchanges-for-ofac": "ofac-screening-exchange",
    "how-to-screen-stablecoin-payments": "ofac-screening-stablecoin",
    "how-to-screen-x402-payments": "ofac-screening-payment",
    "how-to-screen-defi-transactions": "ofac-screening-defi",
    "how-to-build-a-sanctions-list": "ofac-screening-screening",
    "what-is-the-cost-of-sanctions-compliance": "how-much-does-sanctions-screening-cost",
    "how-many-countries-are-sanctioned": "ofac-screening-compliance",
    "does-agentmail-screen-names": "ofac-screening-screening",
    "does-agentmail-store-screen-data": "ofac-screening-screening",
    "how-does-sanctionsai-compare-to-chainalysis": "ofac-screening-exchange",
    "is-sanctions-screening-required-for-ai-agents": "is-ofac-screening-required",
    "what-is-ofac-screening-for-crypto-wallets": "ofac-screening-wallet",
    "what-is-ofac-screening-for-stablecoin-transfers": "ofac-screening-stablecoin",
    "what-is-sanctions-screening-for-daos": "ofac-screening-dao",
}

# --- 5. Keyword -> hub for the remaining "explained"/"what-is-for-X" cluster
KEYWORD_HUBS = [
    ("agent", "ofac-screening-agent"), ("ai", "ofac-screening-agent"),
    ("agentic", "ofac-screening-agent"), ("kyc", "ofac-screening-kyc"),
    ("aml", "ofac-screening-aml"), ("stablecoin", "ofac-screening-stablecoin"),
    ("defi", "ofac-screening-defi"), ("dao", "ofac-screening-dao"),
    ("nft", "ofac-screening-nft"), ("gaming", "ofac-screening-nft"),
    ("metaverse", "ofac-screening-nft"), ("wallet", "ofac-screening-wallet"),
    ("custod", "ofac-screening-wallet"), ("exchange", "ofac-screening-exchange"),
    ("otc", "ofac-screening-exchange"), ("payment", "ofac-screening-payment"),
    ("remittance", "ofac-screening-payment"), ("gateway", "ofac-screening-payment"),
    ("processor", "ofac-screening-payment"), ("web3", "ofac-screening-web3"),
    ("bridge", "ofac-screening-blockchain"), ("layer-2", "ofac-screening-blockchain"),
    ("oracle", "ofac-screening-blockchain"), ("validator", "ofac-screening-blockchain"),
    ("mining", "ofac-screening-blockchain"), ("smart-contract", "ofac-screening-blockchain"),
    ("smart contract", "ofac-screening-blockchain"), ("blockchain", "ofac-screening-blockchain"),
    ("lightning", "ofac-screening-blockchain"), ("cross-chain", "ofac-screening-blockchain"),
    ("compliance", "ofac-screening-compliance"), ("program", "ofac-screening-compliance"),
    ("audit", "ofac-screening-compliance"), ("officer", "ofac-screening-compliance"),
    ("penalt", "ofac-screening-penalties"), ("enforcement", "ofac-screening-enforcement"),
    ("violation", "ofac-screening-enforcement"), ("fine", "ofac-screening-enforcement"),
    ("subpoena", "ofac-screening-enforcement"), ("inquiry", "ofac-screening-enforcement"),
    ("licens", "ofac-screening-licensing"), ("crypto", "ofac-screening-crypto"),
    ("screening", "ofac-screening-screening"), ("treasury", "ofac-screening-compliance"),
    ("token", "ofac-screening-crypto"), ("charit", "ofac-screening-compliance"),
    ("jurisdiction", "ofac-screening-compliance"), ("country", "ofac-screening-compliance"),
    ("marketplace", "ofac-screening-payment"), ("risk", "ofac-screening-screening"),
    ("false positive", "ofac-screening-screening"), ("api", "ofac-screening-screening"),
    ("market", "ofac-screening-screening"), ("cbdc", "ofac-screening-crypto"),
    ("debit card", "ofac-screening-payment"), ("terminal", "ofac-screening-payment"),
    ("real-world", "ofac-screening-crypto"), ("rwa", "ofac-screening-crypto"),
    ("vesting", "ofac-screening-crypto"), ("staking", "ofac-screening-crypto"),
    ("airdrop", "ofac-screening-crypto"), ("ico", "ofac-screening-crypto"),
    ("launch", "ofac-screening-crypto"), ("yield", "ofac-screening-crypto"),
    ("lending", "ofac-screening-crypto"), ("governance", "ofac-screening-dao"),
    ("treasur", "ofac-screening-dao"), ("high-risk", "ofac-screening-compliance"),
    ("cross-border", "ofac-screening-payment"), ("b2b", "ofac-screening-payment"),
    ("subscription", "ofac-screening-payment"), ("facilitator", "ofac-screening-payment"),
    ("aggregator", "ofac-screening-payment"), ("orchestration", "ofac-screening-payment"),
    ("network", "ofac-screening-payment"), ("routing", "ofac-screening-payment"),
    ("commerce", "ofac-screening-payment"), ("infrastructure", "ofac-screening-payment"),
    ("enterprise", "ofac-screening-compliance"), ("small-business", "ofac-screening-compliance"),
    ("startup", "ofac-screening-compliance"), ("fintech", "ofac-screening-compliance"),
    ("p2p", "ofac-screening-payment"), ("peer-to-peer", "ofac-screening-payment"),
    ("developer", "ofac-screening-agent"), ("agent-payments", "ofac-screening-agent"),
    ("openai", "ofac-screening-agent"), ("marketplaces", "ofac-screening-payment"),
]

def main():
    all_slugs = slugs()
    keep = set()
    redirect = {}

    # guide series -> part 1 hub
    for topic in GUIDE_SERIES:
        hub = f"ofac-screening-{topic}-guide-1"
        keep.add(hub)
        for n in range(2, 11):
            redirect[f"ofac-screening-{topic}-guide-{n}"] = hub

    keep.update(EXISTING_HUBS)
    keep.update(s for s in STANDALONE_KEEP if s in all_slugs)

    for s, t in NEAR_DUP_MERGE.items():
        if s in all_slugs and t in keep:
            redirect[s] = t

    # remaining -> keyword hub
    for s in all_slugs:
        if s in keep or s in redirect:
            continue
        low = (s + " " + title_of(s)).lower()
        target = next((hub for kw, hub in KEYWORD_HUBS if kw in low), None)
        if target and target in keep and target != s:
            redirect[s] = target
        else:
            keep.add(s)  # safety: never orphan a page without a destination

    # resolve redirect chains (stub -> stub -> hub)
    changed = True
    while changed:
        changed = False
        for s, t in list(redirect.items()):
            if t in redirect:
                redirect[s] = redirect[t]
                changed = True

    # validate
    assert not (keep & set(redirect)), "overlap"
    for s, t in redirect.items():
        assert t in keep, f"redirect target {t} not a hub (from {s})"
    assert len(keep) + len(redirect) == len(all_slugs), "partition mismatch"

    needs_build = sorted([s for s in keep if body_len(s) < 1800])
    n_keep, n_red = len(keep), len(redirect)
    out = {
        "generated_for": "sanctionsai.dev /faq consolidation (order #3, PRUNE ->~60 hubs)",
        "total_faq_slugs": len(all_slugs),
        "keep_hubs": n_keep,
        "redirect_stubs": n_red,
        "keep": sorted(keep),
        "redirect": {k: redirect[k] for k in sorted(redirect)},
        "guide_series_collapsed": len(GUIDE_SERIES),
        "targets_needing_build_ge1800": needs_build,
    }
    with open("scripts/faq_consolidation_map.json", "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")

    print(f"total: {len(all_slugs)}  keep: {n_keep}  redirect: {n_red}  needs_build: {len(needs_build)}")
    print("\nredirect target distribution:")
    for t, c in collections.Counter(redirect.values()).most_common():
        print(f"  {c:3d} -> {t}")
    print("\nkept but thin (<1800) AND not an existing hub / guide seed:")
    for s in needs_build:
        if s not in EXISTING_HUBS and not re.match(r"ofac-screening-.+-guide-1$", s):
            print(f"  {s} ({body_len(s)} chars)  {title_of(s)[:55]}")

if __name__ == "__main__":
    main()
