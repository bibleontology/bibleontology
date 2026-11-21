#!/bin/bash
# Round 2 of the card layouts (layout_faces.py), then their mockups and the gallery. Resumable; off-peak only.
cd "$(dirname "$0")/../.."
export PYTHONPATH=src PYTHONIOENCODING=utf-8
D=out/layouts
offpeak() { python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)"; }
for ty in person place concept group object image saying message; do
  a="$D/$ty.layout2.txt"; [ -s "$a" ] && continue
  offpeak || { echo "peak: stopping"; exit 2; }
  for i in 1 2 3; do
    timeout 1800 python -X utf8 -m bibleont.delegate run --level 3 --think --effort high --blind --label "layout2 $ty" --task "@$D/$ty.round2.txt" > "$a.raw" 2>&1
    grep -q '"stopped": "timeout or connection' "$a.raw" || break; echo "retry $ty $i"
  done
  grep -q '"stopped": "timeout or connection' "$a.raw" && { echo "STOP $ty"; exit 1; }
  cp "$a.raw" "$a"; echo "$ty $(grep -o '"cost": [0-9.]*' "$a" | tail -1)"
done
echo layouts done
