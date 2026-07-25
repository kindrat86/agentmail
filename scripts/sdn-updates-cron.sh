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

# Commit ONLY this feature's paths, by pathspec rather than `git add` + `commit`.
# Several autonomous sessions share this working tree and stage things in it; a
# bare `git commit` commits whatever is in the index, so the staged form would
# sweep up another session's half-finished work and ship it. A pathspec commit
# ignores the index entirely and takes the working-tree state of these paths only.
PATHS="updates data/sdn-deltas"
if [ -z "$(git status --porcelain -- $PATHS)" ]; then
  echo "builder reported a new publication but produced no file changes — not deploying"
  exit 0
fi
git -c user.email=sales@sipiteno.com -c user.name="SanctionsAI Bot" \
    commit -q -m "data(updates): OFAC SDN publication $DATE" -- $PATHS || {
      echo "commit failed — not deploying"; exit 1; }

# fly.toml carries auto_stop_machines="suspend" + min_machines_running=1; a
# deploy from a tree where that regressed would reintroduce 15s cold starts.
if ! grep -q 'auto_stop_machines *= *"suspend"' fly.toml; then
  echo "FATAL: fly.toml lost auto_stop_machines=suspend — refusing to deploy"
  exit 1
fi

if [ -n "${SDN_UPDATES_NO_DEPLOY:-}" ]; then
  echo "SDN_UPDATES_NO_DEPLOY set — captured and committed $DATE, skipping deploy"
  exit 0
fi

# Deploy in two steps. A single `flyctl deploy` holds one long connection through
# the whole remote build and is regularly killed part-way ("terminated signal
# received"), leaving the release interrupted; splitting it means the only
# long-running call is the build, and the release itself is seconds long.
#
# The build output goes to its own file rather than straight down the pipe: the
# image reference has to be read back out of it, and grepping the shared append
# log instead would happily match a stale reference from an earlier run.
BUILD_LOG=$(mktemp -t sdn-build)
echo "building image..."
flyctl deploy -a agentmail-api --build-only --push >"$BUILD_LOG" 2>&1
rc_build=$?
tail -15 "$BUILD_LOG"
IMAGE_REF=$(grep -oE 'registry\.fly\.io/agentmail-api:deployment-[A-Za-z0-9]+' "$BUILD_LOG" | tail -1)
rm -f "$BUILD_LOG"
if [ "$rc_build" != "0" ] || [ -z "$IMAGE_REF" ]; then
  echo "build FAILED (exit $rc_build, image='$IMAGE_REF') — commit $DATE is in git but not live"
  exit 1
fi

echo "releasing $IMAGE_REF ..."
flyctl deploy -a agentmail-api --image "$IMAGE_REF" 2>&1 | tail -15
rc_rel=$?
if [ "$rc_rel" != "0" ]; then
  # A release can report failure and still be live, and concurrent sessions
  # deploy this app constantly — the URL check below is the real verdict, so
  # warn rather than bail here.
  echo "WARNING: release reported exit $rc_rel; verifying by URL before deciding"
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
