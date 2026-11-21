#!/bin/bash
# Waits for DeepSeek's off-peak window, then runs every merge brief twice, blind (runs a and b); stops at the first empty answer.
cd "<local> Ontology/.claude/worktrees/ubs-lexicon-word-verse-c23765"
D="<local>"
until python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10) and not (n.hour==4 and n.minute<5)) else 1)"; do sleep 120; done
echo "off-peak at $(date -u +%H:%M) UTC"
for run in a b; do
for f in "$D"/batch-[0-9][0-9].txt; do
  a="${f%.txt}.$run.txt"
  [ -s "$a" ] && grep -q '^\[' "$a" && continue
  python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)" || { echo "peak began: stopping, resume off-peak"; exit 2; }
  timeout 900 python -X utf8 -m bibleont.delegate run --level 2 --effort high --blind --label "merge judge $run $(basename "$f" .txt)" --task "$(cat "$f")" > "$a" 2>&1
  if ! grep -q '^\[' "$a"; then echo "STOP: no answer for $(basename "$f") run $run"; tail -5 "$a"; exit 1; fi
  echo "$run $(basename "$f") $(grep -o '"cost": [0-9.]*' "$a")"
done
done
echo "done"
