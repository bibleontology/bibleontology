#!/bin/bash
# Waits for DeepSeek's off-peak window, then sends each brief in turn. A brief whose answer is capped (all output spent
# reasoning, no answer: briefs 23, 47 and 50 on 2026-11-19) is re-sent one card at a time and the answers combined;
# any other empty answer (a connection reset, no balance) stops the run.
cd "<local> Ontology/.claude/worktrees/ubs-lexicon-word-verse-c23765"
S="<local>"
D="<local> Ontology/.claude/worktrees/ubs-lexicon-word-verse-c23765/out/pairs/briefs"
offpeak() { python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)"; }
send() { timeout 900 python -X utf8 -m bibleont.delegate run --level 2 --effort high --blind --label "$1" --task "$(cat "$2")" > "$3" 2>&1; }
until offpeak; do sleep 120; done
echo "off-peak at $(date -u +%H:%M) UTC"
for f in "$D"/batch-[0-9][0-9][0-9].txt; do
  a="${f%.txt}.answer.txt"; b=$(basename "$f" .txt)
  [ -s "$a" ] && grep -q '^\[' "$a" && continue
  offpeak || { echo "peak began: stopping, resume off-peak"; exit 2; }
  send "pairs $b" "$f" "$a"
  if grep -q '^\[' "$a"; then echo "$b $(grep -o '"cost": [0-9.]*' "$a")"; continue; fi
  if ! grep -q '"reasoning": 32000' "$a"; then echo "STOP: no answer for $b"; grep '"stopped"' "$a"; exit 1; fi
  echo "$b capped: one card at a time"
  sp="$D/split_$b"; mkdir -p "$sp"; i=0
  for id in $(grep -o '^CARD [a-z0-9_]*' "$f" | cut -d' ' -f2); do
    python -X utf8 "$S/zero_brief.py" "<local> Ontology/.claude/worktrees/ubs-lexicon-word-verse-c23765/out/pairs/pairs_cand.json" "$sp/out$i" "$id" > /dev/null
    send "pairs $b card $i" "$sp/out$i/batch-000.txt" "$sp/out$i/answer.txt"
    if grep -q '^\[' "$sp/out$i/answer.txt"; then echo "  card $i ($id) answered"; else echo "  card $i ($id) NO ANSWER"; fi
    i=$((i+1))
  done
  python -X utf8 - "$sp" "$a" <<'EOF'
import json, re, sys, glob
out = []
for p in sorted(glob.glob(sys.argv[1] + "/out*/answer.txt")):
    m = re.search(r"^\[.*?^\]", open(p, encoding="utf-8").read(), re.S | re.M)
    if m: out += json.loads(m.group(0))
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print("  combined", len(out), "items")
EOF
done
echo "done"
