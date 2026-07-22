#!/bin/bash
# IndexNow ping for sanctionsai.dev
# Key file: https://sanctionsai.dev/89ce69c8d5e147dda9a4e6e9e5372f22.txt
set -euo pipefail

KEY="89ce69c8d5e147dda9a4e6e9e5372f22"
HOST="sanctionsai.dev"
KEY_LOCATION="https://${HOST}/${KEY}.txt"

# Submit sitemap URLs
SITEMAP_URLS=(
  "https://${HOST}/"
  "https://${HOST}/pricing"
  "https://${HOST}/leaderboard"
  "https://${HOST}/tools/wallet-checker"
  "https://${HOST}/faq"
  "https://${HOST}/docs"
  "https://${HOST}/about"
  "https://${HOST}/learn/sanctions-glossary"
)

for url in "${SITEMAP_URLS[@]}"; do
  payload=$(python3 -c "
import json
print(json.dumps({
    'host': '${HOST}',
    'key': '${KEY}',
    'keyLocation': '${KEY_LOCATION}',
    'urlList': ['${url}']
}))
")
  resp=$(curl -s -w "%{http_code}" -o /dev/null \
    -X POST https://api.indexnow.org/indexnow \
    -H "Content-Type: application/json" \
    -d "$payload")
  echo "IndexNow ${url}: HTTP ${resp}"
done

echo "Done."
