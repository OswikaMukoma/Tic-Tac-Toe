#!/bin/sh
# Re-render every diagram source in this folder to PNG.
#   *.mmd  Mermaid (needs mermaid-cli: mmdc). If Chromium needs --no-sandbox or a
#          custom path, point PUPPETEER_CFG at a JSON puppeteer config.
#   *.dot  Graphviz (needs `dot`).
cd "$(dirname "$0")" || exit 1
for f in *.mmd; do
  [ -e "$f" ] || continue
  if [ -n "$PUPPETEER_CFG" ]; then
    mmdc -p "$PUPPETEER_CFG" -i "$f" -o "${f%.mmd}.png" -s 2 -b white
  else
    mmdc -i "$f" -o "${f%.mmd}.png" -s 2 -b white
  fi
done
for f in *.dot; do
  [ -e "$f" ] || continue
  dot -Tpng -Gdpi=150 "$f" -o "${f%.dot}.png"
done
