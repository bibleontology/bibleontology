#!/bin/bash
# Sends out/second-pass/batch-*.txt to DeepSeek, off-peak only; stops at peak or at the first empty answer.
cd "$(dirname "$0")/../.."
export PYTHONPATH=src PYTHONIOENCODING=utf-8
offpeak() { python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)"; }
until offpeak; do sleep 120; done
for f in out/second-pass/batch-[0-9][0-9][0-9].txt; do
  a="${f%.txt}.answer.txt"
  [ -s "$a" ] && grep -q '^\[' "$a" && continue
  offpeak || { echo "peak began: stopping, resume off-peak"; exit 2; }
  timeout 900 python -X utf8 -m bibleont.delegate run --level 2 --effort high --blind --label "second pass $(basename "$f")" --task "$(cat "$f")" > "$a" 2>&1
  grep -q '^\[' "$a" || { echo "STOP: no answer for $f"; tail -3 "$a"; exit 1; }
  echo "$(basename "$f") $(grep -o '"cost": [0-9.]*' "$a" | tail -1)"
done
echo done
