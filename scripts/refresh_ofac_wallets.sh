#!/usr/bin/env bash
# Weekly refresh for /data/ofac-crypto-wallets (SanctionsAI).
#
# Idempotent and safe to run on any schedule: downloads the OFAC SDN Advanced
# XML, compares its DateOfIssue to the published snapshot, and ONLY regenerates
# + commits + deploys when Treasury actually republished the list.
#
# Output contract (for the no-agent cron wrapper):
#   - progress lines go to stderr (always visible in a manual run)
#   - stdout is empty when nothing changed (cron stays silent)
#   - stdout carries a one-line summary only when a refresh shipped
#
# Uses system python3 (stdlib-only parsing) + flyctl for the deploy.
set -euo pipefail

REPO="${REPO:-$HOME/workspace/agentmail}"
SRC_URL="https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml"
DATADIR="$REPO/data/ofac-crypto-wallets"
PY="${PYTHON:-python3}"
FLYCTL="$(command -v flyctl || echo "$HOME/.fly/bin/flyctl")"

log() { echo "[ofac-refresh] $*" >&2; }

# ---- download ---------------------------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
XML="$WORK/sdn_advanced.xml"

log "downloading $SRC_URL"
curl -sL --max-time 300 -A "SanctionsAI/1.0 (dataset refresh)" "$SRC_URL" -o "$XML"
[ -s "$XML" ] || { log "ERROR: empty download"; exit 1; }

# ---- extract DateOfIssue (appears near the top; iterparse breaks early) -----
NEW_DATE="$("$PY" - "$XML" <<'PY'
import sys, xml.etree.ElementTree as ET
for _ev, e in ET.iterparse(sys.argv[1], events=("end",)):
    if e.tag.split("}", 1)[-1] == "DateOfIssue":
        y = e.findtext("{*}Year"); m = e.findtext("{*}Month"); d = e.findtext("{*}Day")
        if y and m and d:
            print(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")
        break
PY
)"
[ -n "$NEW_DATE" ] || { log "ERROR: no DateOfIssue in download"; exit 1; }

# ---- compare to the published snapshot -------------------------------------
PUBLISHED="$("$PY" -c "import json;print(json.load(open('$DATADIR/data.json'))['sdn_list_date'])")"
log "source DateOfIssue=$NEW_DATE  published=$PUBLISHED"

if [ "$NEW_DATE" = "$PUBLISHED" ]; then
    log "no change — nothing to do."
    exit 0
fi

log "OFAC republished the list ($PUBLISHED -> $NEW_DATE). Regenerating..."

# ---- regenerate -------------------------------------------------------------
"$PY" "$REPO/scripts/build_ofac_wallets.py" --src "$XML" --out "$WORK/ofac_wallets.json"
"$PY" "$REPO/scripts/gen_wallet_page.py" --json "$WORK/ofac_wallets.json" \
    --as-of "$NEW_DATE" --generated "$(date +%F)"
"$PY" "$REPO/scripts/gen_sanctioned_addresses.py"

# ---- guardrail 5.2: refuse a degenerate distribution ------------------------
"$PY" - "$DATADIR/data.json" <<'PY'
import json, sys, collections
d = json.load(open(sys.argv[1]))
recs = d["records"]
n = len(recs)
assert n > 0, "empty dataset"
for field in ("chain", "entity", "ofac_programs", "entity_designation_date"):
    top, cnt = collections.Counter(r[field] for r in recs).most_common(1)[0]
    pct = cnt / n
    assert pct < 0.95, f"degenerate {field}: {top!r} = {pct:.1%}"
print(f"guardrail 5.2 ok: {n} records", file=sys.stderr)
PY

# ---- bump the JSON Feed item's date_modified --------------------------------
"$PY" - "$DATADIR" "$NEW_DATE" <<'PY'
import json, sys, datetime
datadir, new_date = sys.argv[1], sys.argv[2]
feed_path = datadir.rsplit("/", 1)[0] + "/feed.json"
feed = json.load(open(feed_path))
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for item in feed.get("items", []):
    if item.get("id", "").endswith("/data/ofac-crypto-wallets/"):
        item["date_modified"] = now
json.dump(feed, open(feed_path, "w"), indent=2)
print(f"feed.json date_modified -> {now}", file=sys.stderr)
PY

# ---- repo rule: syntax-check api.py before any deploy -----------------------
"$PY" -c "import py_compile; py_compile.compile('$REPO/api.py', doraise=True)" \
    || { log "api.py failed py_compile — aborting before commit/deploy"; exit 1; }

# ---- commit only the regenerated files --------------------------------------
cd "$REPO"
git add "$DATADIR" "$REPO/data/feed.json" "$REPO/sanctioned-addresses"
if git diff --cached --quiet; then
    log "no diff after regeneration — aborting"
    exit 1
fi
git commit -q -m "data(ofac-crypto-wallets): refresh to SDN publication $NEW_DATE"
SHA="$(git rev-parse --short HEAD)"
log "committed $SHA"

# ---- deploy from the commit, never the working tree -------------------------
"$HOME/growth-loop/lib/deploy_from_commit.sh" \
    --worktree "$REPO" \
    --deploy-cmd "\"$FLYCTL\" deploy" \
    --repo-path "$REPO"

# ---- IndexNow ping (best effort; 403 here is a known, owner-tracked issue) ---
if [ -f "$REPO/scripts/indexnow-ping.sh" ]; then
    bash "$REPO/scripts/indexnow-ping.sh" >&2 || log "IndexNow ping failed (see backlog)"
fi

echo "ofac-crypto-wallets refreshed: SDN $PUBLISHED -> $NEW_DATE (commit $SHA, deployed to agentmail-api)"
log "done."
