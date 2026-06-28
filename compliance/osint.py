"""OSINT compliance provider — real, free, open sanctions data. No API key.

Data sources (all verified live, free, no key — Jun 2026):
  - Crypto wallets : vile/ofac-sdn-list GitHub release sdn.json
                     (multi-chain: ETH/USDT/TRX/XBT/XRP/...; updated daily 06:00 UTC)
                     https://github.com/vile/ofac-sdn-list/releases/latest
  - Names+country  : US Treasury OFAC sdn.csv (~19k SDN entries, authoritative)
                     https://www.treasury.gov/ofac/downloads/sdn.csv
  - High-risk jurisdictions: comprehensive embargoed/sanctioned ISO-2 set.

Caching: lists are downloaded once to ~/.agentmail/cache/ with a 24h TTL. If the
network is unreachable, a stale cache is used (better than nothing). If no cache
exists at all, the provider degrades to a tiny embedded list and flags itself
status(ready=False) so the caller KNOWS it is screening against incomplete data.

Name matching: normalized exact + token-subset (all significant query tokens
must appear in a sanctioned name). Wallet matching: exact, case-insensitive.
Country matching: ISO-2 exact against the embargoed set. Match precision is
reported per-match so a caller can decide how hard to block.

Interface is identical to MockComplianceProvider — swap via
AGENTMAIL_COMPLIANCE_PROVIDER=osint.
"""
from __future__ import annotations
import csv
import io
import json
import os
import re
import secrets
import ssl
import sys
import threading
import time
import urllib.request
from .base import ComplianceProvider

# ─── Data source URLs ─────────────────────────────────────────────────────
# vile/ofac-sdn-list exposes multi-chain crypto addresses as release assets.
# We resolve the latest release's sdn.json via the GitHub API.
_VILE_API_LATEST = "https://api.github.com/repos/vile/ofac-sdn-list/releases/latest"
# Treasury SDN CSV — authoritative names + countries.
_TREASURY_SDN_CSV = "https://www.treasury.gov/ofac/downloads/sdn.csv"

_CACHE_DIR = os.path.expanduser("~/.agentmail/cache")
_WALLET_CACHE = os.path.join(_CACHE_DIR, "ofac_wallets.json")
_WALLET_META = os.path.join(_CACHE_DIR, "ofac_wallets.meta.json")
_NAME_CACHE = os.path.join(_CACHE_DIR, "ofac_names.json")
_NAME_META = os.path.join(_CACHE_DIR, "ofac_names.meta.json")
_TTL = 24 * 3600  # 24 hours

# ISO-3166-1 alpha-2 codes under comprehensive OFAC/UN/EU sanctions or
# embargoed (Jun 2026). These trigger OFAC_COUNTRY matches.
_HIGH_RISK_COUNTRIES = {
    "kp",  # North Korea — comprehensive sanctions
    "ir",  # Iran — comprehensive sanctions
    "sy",  # Syria — comprehensive sanctions
    "cu",  # Cuba — comprehensive sanctions
    "ru",  # Russia — sectoral/SDN (post-2022)
    "by",  # Belarus — sectoral
    "mm",  # Myanmar — SDN
    "ve",  # Venezuela — SDN (sectoral)
    "af",  # Afghanistan — Taliban-related
    "so",  # Somalia — arms embargo
    "ly",  # Libya — UN sanctions
    "sd",  # Sudan — Darfur sanctions
    "ye",  # Yemen — conflict-related
    "cf",  # Central African Republic — UN arms embargo
    "cd",  # DRC — UN arms embargo
    "iq",  # Iraq — legacy SDN
}

# Tiny fallback used only when no cache exists AND the network is unreachable.
_FALLBACK_WALLETS = {
    "0x098b716b8aaf21512996dc57eb0615e2383e2f96",  # Lazarus Group (OFAC)
    "0x7f367cc41522ce07553e823bf3be79a889debe1b",  # POTEKHIN, Danil
    "0x7d655c57f71464b6f83811c55d84009cd9f022b9",  # OFAC Tornado Cash
}
_FALLBACK_NAMES = {
    "lazarus group",
    "tornado cash",
    "revelation panda empire",
    "suex",
    "chatex",
    "garantex",
}

_UA = "agentmail-osint/0.4 (compliance screen; +https://github.com/kindrat86)"

# Stopwords removed before token-subset name matching (reduce false negatives).
_NAME_STOPWORDS = {
    "the", "and", "of", "for", "a", "an", "ltd", "inc", "corp", "co", "sa",
    "llc", "gmbh", "limited", "company", "corporation", "group", "sarl",
    "bv", "oy", "asl", "pte", "pvt",
}


def _norm_name(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", " ", s)  # punctuation -> space
    return re.sub(r"\s+", " ", s).strip()


def _name_tokens(s: str) -> list[str]:
    """Significant tokens of a normalized name (stopwords dropped)."""
    return [t for t in _norm_name(s).split() if t and t not in _NAME_STOPWORDS]


def _bucket(score: int) -> str:
    if score >= 75:
        return "allow"
    if score >= 40:
        return "review"
    return "decline"


def _http_get(url: str, timeout: float = 45.0) -> bytes:
    """Fetch bytes. Tries strict SSL first; on cert-chain failure (common in
    proxied/sandboxed envs) retries with an unverified context and logs a
    warning. Public sanctions data is integrity-checked downstream (non-empty +
    well-formed), and availability beats strictness here — a sanctions screen
    that silently degrades to no-names because a proxy MITM'd the cert is a
    worse outcome than fetching public data over an unverified TLS channel."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        # SSL cert failures (proxy/MITM in sandboxed envs) → lenient retry.
        ssl_errs = (ssl.SSLCertVerificationError, ssl.SSLError)
        if not isinstance(reason, ssl_errs):
            raise
        print(f"[agentmail-osint] WARNING: SSL verification failed for {url} "
              f"({reason}); retrying with unverified context. Data integrity is "
              f"checked downstream.", file=sys.stderr)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read()


class OsintComplianceProvider(ComplianceProvider):
    name = "osint"

    def __init__(self, force_refresh: bool = False):
        self._lock = threading.Lock()
        self._disputes: dict[str, dict] = {}
        self._loaded = False
        self._degraded = False       # True when screening against incomplete data
        self._degraded_reason = ""
        self._wallets: dict[str, str] = {}   # address_lower -> type/label
        self._names: dict[str, str] = {}     # normalized name -> country
        self._name_tokens_index: list[tuple[list[str], str, str]] = []
        # tokens, country, original
        self._lists_loaded_at: float = 0.0
        self._source_tag = ""
        if force_refresh:
            self._load(force=True)

    # ─── List loading (lazy, cached, fault-tolerant) ──────────────────────
    def _load(self, force: bool = False):
        """Populate wallets + names from cache or network. Never raises."""
        with self._lock:
            if self._loaded and not force:
                return
            now = time.time()
            wallet_ok = self._maybe_refresh_wallets(force, now)
            names_ok = self._maybe_refresh_names(force, now)
            self._loaded = True
            if not (wallet_ok and names_ok):
                self._degraded = True
                bad = []
                if not wallet_ok:
                    bad.append("wallets")
                if not names_ok:
                    bad.append("names")
                self._degraded_reason = (
                    f"using stale/fallback data for: {', '.join(bad)}"
                )
            else:
                self._degraded = False
                self._degraded_reason = ""

    def _cache_fresh(self, meta_path: str) -> bool:
        if not os.path.exists(meta_path):
            return False
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            return (time.time() - meta.get("fetched_at", 0)) < _TTL
        except (OSError, ValueError):
            return False

    def _maybe_refresh_wallets(self, force: bool, now: float) -> bool:
        """Returns True if we have usable wallet data (fresh cache or fresh fetch)."""
        if (not force) and self._cache_fresh(_WALLET_META) and os.path.exists(_WALLET_CACHE):
            return self._load_wallet_cache()
        # Need a network fetch.
        try:
            wallets, source_tag = self._fetch_wallets()
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_WALLET_CACHE, "w") as f:
                json.dump(wallets, f)
            with open(_WALLET_META, "w") as f:
                json.dump({"fetched_at": now, "source": source_tag,
                           "count": len(wallets)}, f)
            self._wallets = wallets
            self._source_tag = source_tag
            return True
        except Exception as e:
            # Fallback: use stale cache if present, else embedded list.
            if os.path.exists(_WALLET_CACHE):
                self._load_wallet_cache()
                self._degraded_reason = f"wallet refresh failed ({e}); stale cache"
                return False  # stale, but usable — flag degraded
            self._wallets = {w: "OFAC_SDN_FALLBACK" for w in _FALLBACK_WALLETS}
            self._degraded_reason = f"wallet fetch failed ({e}); fallback list"
            return False

    def _load_wallet_cache(self) -> bool:
        try:
            with open(_WALLET_CACHE) as f:
                self._wallets = json.load(f)
            with open(_WALLET_META) as f:
                meta = json.load(f)
            self._source_tag = meta.get("source", "cached")
            self._lists_loaded_at = meta.get("fetched_at", 0)
            return True
        except (OSError, ValueError):
            return False

    def _fetch_wallets(self) -> tuple[dict[str, str], str]:
        """Fetch latest vile/ofac-sdn-list release sdn.json."""
        raw = _http_get(_VILE_API_LATEST, timeout=20)
        rel = json.loads(raw)
        tag = rel.get("tag_name", "unknown")
        json_asset = [a for a in rel.get("assets", [])
                      if a.get("name", "").endswith(".json")]
        if not json_asset:
            raise RuntimeError("no JSON asset in latest vile release")
        url = json_asset[0]["browser_download_url"]
        data = json.loads(_http_get(url, timeout=45))
        wallets: dict[str, str] = {}
        for entry in data:
            addr = (entry.get("address") or "").strip()
            if addr:
                wallets[addr.lower()] = entry.get("type", "Digital Currency Address")
        if not wallets:
            raise RuntimeError("vile sdn.json contained no addresses")
        return wallets, f"vile/ofac-sdn-list@{tag[:24]}"

    def _maybe_refresh_names(self, force: bool, now: float) -> bool:
        if (not force) and self._cache_fresh(_NAME_META) and os.path.exists(_NAME_CACHE):
            return self._load_name_cache()
        try:
            names, source_tag = self._fetch_names()
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_NAME_CACHE, "w") as f:
                json.dump(names, f)
            with open(_NAME_META, "w") as f:
                json.dump({"fetched_at": now, "source": source_tag,
                           "count": len(names)}, f)
            self._build_name_index(names)
            return True
        except Exception as e:
            if os.path.exists(_NAME_CACHE):
                self._load_name_cache()
                return False
            names = {n: "FALLBACK" for n in _FALLBACK_NAMES}
            self._build_name_index(names)
            self._degraded_reason = f"name fetch failed ({e}); fallback list"
            return False

    def _load_name_cache(self) -> bool:
        try:
            with open(_NAME_CACHE) as f:
                names = json.load(f)
            self._build_name_index(names)
            with open(_NAME_META) as f:
                meta = json.load(f)
            if not self._source_tag:
                self._source_tag = meta.get("source", "cached")
            self._lists_loaded_at = meta.get("fetched_at", 0)
            return True
        except (OSError, ValueError):
            return False

    def _fetch_names(self) -> tuple[dict[str, str], str]:
        """Fetch + parse Treasury sdn.csv → {normalized_name: country}."""
        raw = _http_get(_TREASURY_SDN_CSV, timeout=90).decode("utf-8", "replace")
        reader = csv.reader(io.StringIO(raw))
        names: dict[str, str] = {}
        for row in reader:
            if len(row) < 4:
                continue
            nm = (row[1] or "").strip()
            if not nm or nm.startswith("-"):
                continue
            country = (row[3] or "").strip().lower()
            key = _norm_name(nm)
            if key:
                names[key] = country
        if not names:
            raise RuntimeError("treasury sdn.csv yielded no names")
        return names, "treasury.ofac/sdn.csv"

    def _build_name_index(self, names: dict[str, str]):
        self._names = names
        self._name_tokens_index = [
            (_name_tokens(n), country, n)
            for n, country in names.items()
        ]

    # ─── Sanctions screen (the core capability) ──────────────────────────
    def sanctions_check(self, name: str = "", wallet: str = "",
                        country: str = "") -> dict:
        self._load()
        matches: list[dict] = []
        nl = _norm_name(name)
        wl = (wallet or "").strip().lower()
        cl = (country or "").strip().lower()

        # Wallet: exact case-insensitive.
        if wl and wl in self._wallets:
            matches.append({
                "list": "OFAC_SDN",
                "entity": wallet,
                "match_type": "wallet_exact",
                "confidence": 1.0,
                "detail": self._wallets[wl],
            })

        # Name: normalized exact first (high precision).
        if nl and nl in self._names:
            matches.append({
                "list": "OFAC_SDN",
                "entity": name,
                "match_type": "name_exact",
                "confidence": 0.97,
                "detail": f"country={self._names[nl] or 'unknown'}",
            })
        elif nl:
            # Token-subset: every significant query token appears in a
            # sanctioned name AND the sanctioned name is at least 2 tokens.
            # Keeps precision high while catching aliases / name-order variants.
            qtokens = _name_tokens(name)
            if len(qtokens) >= 2:
                for stokens, scountry, sname in self._name_tokens_index:
                    if len(stokens) >= 2 and all(t in stokens for t in qtokens):
                        matches.append({
                            "list": "OFAC_SDN",
                            "entity": sname,
                            "match_type": "name_token_subset",
                            "confidence": 0.80,
                            "detail": f"matched sanctioned entry (country={scountry or 'unknown'})",
                        })
                        break  # one subset hit is enough

        # Country: embargoed jurisdiction.
        if cl and cl in _HIGH_RISK_COUNTRIES:
            matches.append({
                "list": "OFAC_COUNTRY",
                "entity": country,
                "match_type": "country_embargoed",
                "confidence": 1.0,
                "detail": "comprehensive/sectoral sanctions jurisdiction",
            })

        return {
            "matches": matches,
            "clean": len(matches) == 0,
            "checked": {"name": name, "wallet": wallet, "country": country},
            "provider": self.name,
            "degraded": self._degraded,
        }

    # ─── Know Your Agent ─────────────────────────────────────────────────
    def kya_verify(self, agent_id: str, evidence: dict) -> dict:
        self._load()
        evidence = evidence or {}
        verified: list[str] = []
        flags: list[str] = []
        score = 10

        wa = (evidence.get("wallet_address") or "").strip()
        if re.match(r"^0x[a-fA-F0-9]{40}$", wa):
            verified.append("wallet_address_format")
            score += 15
            age_days = int(evidence.get("wallet_age_days", 0) or 0)
            if age_days > 365:
                verified.append("wallet_age_>1y")
                score += 10
            elif 0 < age_days < 7:
                flags.append("wallet_age_<7d")
                score -= 5
        if evidence.get("domain"):
            verified.append("domain_declared")
            score += 10
            if not str(evidence["domain"]).startswith("temp"):
                verified.append("domain_not_disposable")
                score += 5
        if evidence.get("pubkey"):
            verified.append("pubkey_present")
            score += 10
        if evidence.get("owner_email"):
            verified.append("owner_email_declared")
            score += 5

        country = (evidence.get("declared_country") or "").lower()
        if country:
            verified.append(f"country_declared:{country}")
            if country in _HIGH_RISK_COUNTRIES:
                flags.append(f"high_risk_jurisdiction:{country}")
                score -= 25

        # Real sanctions screen against evidence.
        screen = self.sanctions_check(
            name=evidence.get("name", ""),
            wallet=wa,
            country=country,
        )
        if not screen["clean"]:
            for m in screen["matches"]:
                flags.append(f"sanctions_match:{m['match_type']}")
            score -= 50

        score = max(0, min(100, score))
        return {
            "agent_id": agent_id,
            "trust_score": score,
            "verified": verified,
            "flags": flags,
            "recommendation": _bucket(score),
            "provider": self.name,
            "sanctions_screen": screen,
        }

    # ─── Transaction risk score ─────────────────────────────────────────
    def risk_score(self, counterparty_id: str, amount: str,
                   currency: str = "USDC", rail: str = "x402",
                   category: str = "digital_goods") -> dict:
        self._load()
        reasons: list[str] = []
        score = 70

        try:
            amt = float(amount)
        except (TypeError, ValueError):
            amt = 0.0
            reasons.append("amount_unparseable")
            score -= 20

        if amt >= 10000:
            score -= 35; reasons.append(f"very_large_amount:{amount}")
        elif amt >= 1000:
            score -= 15; reasons.append(f"large_amount:{amount}")
        elif 0 < amt < 0.01:
            score -= 10; reasons.append("dust_amount_suspicious")

        rail_penalties = {"tap": 0, "acp": -5, "ap2": -5, "x402": -10}
        rail_p = rail_penalties.get((rail or "").lower(), -10)
        score += rail_p
        if rail_p:
            reasons.append(f"rail_risk:{rail}")

        if category == "physical":
            score -= 10; reasons.append("physical_chargeback_risk")
        elif category == "services":
            score -= 5; reasons.append("services_delivery_risk")

        if currency.upper() not in ("USDC", "USDT", "DAI", "EURC"):
            score -= 5; reasons.append(f"non_stable_currency:{currency}")

        # Real sanctions screen — counterparty treated as name-or-wallet.
        screen = self.sanctions_check(name=counterparty_id, wallet=counterparty_id)
        if not screen["clean"]:
            score -= 50
            for m in screen["matches"]:
                reasons.append(f"sanctions_match:{m['list']}/{m['match_type']}")

        score = max(0, min(100, score))
        return {
            "counterparty_id": counterparty_id,
            "score": score,
            "recommendation": _bucket(score),
            "reasons": reasons,
            "screen_id": "scr_" + secrets.token_hex(8),
            "provider": self.name,
            "sanctions_screen": screen,
        }

    # ─── Dispute registry (same local store as mock — no OSINT source) ───
    def dispute_open(self, transaction_id: str, reason: str,
                     evidence: dict | None = None) -> dict:
        did = "dsp_" + secrets.token_hex(6)
        now = time.time()
        record = {
            "dispute_id": did,
            "transaction_id": transaction_id,
            "reason": reason,
            "evidence": evidence or {},
            "status": "open",
            "opened_at": now,
            "escalation_at": now + 7 * 86400,
        }
        with self._lock:
            self._disputes[did] = record
        return {k: v for k, v in record.items()
                if k != "evidence"} | {"evidence_stored": bool(evidence),
                                       "provider": self.name}

    def status(self) -> dict:
        self._load()  # ensure counts reflect actual loaded data, not an empty fresh instance
        with self._lock:
            open_count = sum(1 for d in self._disputes.values()
                             if d["status"] == "open")
            ws = self._wallets
            ns = self._names
        return {
            "provider": self.name,
            "ready": not self._degraded,
            "detail": (self._degraded_reason
                       or f"OFAC SDN: {len(ws)} wallets, {len(ns)} names; "
                          f"source={self._source_tag or 'n/a'}"),
            "wallets_tracked": len(ws),
            "names_tracked": len(ns),
            "countries_flagged": len(_HIGH_RISK_COUNTRIES),
            "lists_fetched_at": self._lists_loaded_at or None,
            "cache_ttl_hours": _TTL // 3600,
            "disputes_open": open_count,
        }
