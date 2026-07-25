#!/bin/bash
# Daily capture + publish of the OFAC SDN Change Log.
#
# OFAC's delta API only ever exposes the CURRENT publication (/changes/latest),
# and publication IDs are UUIDs, so a publication that is missed while it is
# `latest` cannot be fetched later. A gap in the archive is permanent. That is
# what this job exists to prevent — it is a capture job first and a deploy job
# second, which is why it archives even on days it does not deploy.
#
# Deploys only when the publication is new (builder exits 10), so an unchanged
# day costs one HTTP request and nothing else.
#
# Install:  launchctl load -w ~/Library/LaunchAgents/dev.sanctionsai.sdn-updates.plist
set -uo pipefail

REPO="$HOME/workspace/agentmail"
LOG="$HOME/.sanctionsai/sdn-updates.log"
PY="$HOME/growth-harness/.venv/bin/python"
[ -x "$PY" ] || PY=python3

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) sdn-updates run ==="

cd "$REPO" || { echo "FATAL: $REPO missing"; exit 1; }

"$PY" scripts/build_sdn_updates.py
rc=$?

if [ "$rc" = "0" ]; then
  echo "no new OFAC publication — archive already current, nothing to deploy"
  exit 0
fi
if [ "$rc" != "10" ]; then
  echo "FATAL: builder failed with exit $rc — not deploying"
  exit "$rc"
fi

DATE=$(ls -1 data/sdn-deltas/*.xml 2>/dev/null | sed 's|.*/||;s|\.xml$||' | sort | tail -1)
echo "new OFAC publication captured: $DATE"

# Commit only this feature's paths. The working tree is shared with other
# autonomous sessions and is itself what gets deployed, so `git add -A` here
# would ship whatever half-finished edit happened to be sitting in the tree.
git add updates data/sdn-deltas scripts/build_sdn_updates.py 2>/dev/null
if git diff --cached --quiet; then
  echo "builder reported new publication but produced no file changes — not deploying"
  exit 0
fi
git -c user.email=sales@sipiteno.com -c user.name="SanctionsAI Bot" \
    commit -q -m "data(updates): OFAC SDN publication $DATE" || {
      echo "commit failed — not deploying"; exit 1; }

# fly.toml carries auto_stop_machines="suspend" + min_machines_running=1; a
# deploy from a tree where that regressed would reintroduce 15s cold starts.
if ! grep -q 'auto_stop_machines *= *"suspend"' fly.toml; then
  echo "FATAL: fly.toml lost auto_stop_machines=suspend — refusing to deploy"
  exit 1
fi

echo "deploying..."
if ! flyctl deploy -a agentmail-api --now 2>&1 | tail -20; then
  echo "deploy FAILED — commit $DATE is in git but not live"
  exit 1
fi

# Tell IndexNow the new URLs exist. Best-effort by design: the ping is not what
# gets these pages found, and a failure must not fail the run.
#
# As of 2026-07-25 it returns HTTP 403 UserForbiddedToAccessSite. That is NOT the
# portfolio's usual broken-key problem — the key file is byte-perfect (32 hex
# chars, no trailing newline, text/plain, matches its filename). It is Bing
# refusing the host, i.e. sanctionsai.dev is not claimed in Bing Webmaster Tools.
# Claiming it is an owner task. Until then this line logs 403 and moves on.
#
# Discovery does not depend on it: /updates/sitemap.xml is registered in
# sitemap-index.xml and robots.txt, and the hub is linked from the primary nav
# and the sitewide footer.
URLS=$("$PY" - "$DATE" <<'PY'
import json, sys
KEY = "87aaa199acaf7d14c812e974ce115e32"
date = sys.argv[1]
urls = ["https://sanctionsai.dev/updates/",
        "https://sanctionsai.dev/updates/%s/" % date]
try:
    with open("data/sdn-deltas/%s.json" % date, encoding="utf-8") as fh:
        for e in json.load(fh)["entities"]:
            urls.append("https://sanctionsai.dev/updates/entity/%s" % e["slug"])
except (OSError, ValueError, KeyError):
    pass
print(json.dumps({"host": "sanctionsai.dev", "key": KEY,
                  "keyLocation": "https://sanctionsai.dev/%s.txt" % KEY,
                  "urlList": urls}))
PY
)
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "https://api.indexnow.org/indexnow" \
  -H "Content-Type: application/json; charset=utf-8" -d "$URLS" --max-time 30)
echo "IndexNow HTTP $code"

live=$(curl -s -o /dev/null -w '%{http_code}' "https://sanctionsai.dev/updates/$DATE/" --max-time 30)
echo "live check /updates/$DATE/ -> HTTP $live"
[ "$live" = "200" ] || { echo "WARNING: new publication page is not serving"; exit 1; }
echo "done: $DATE published"
