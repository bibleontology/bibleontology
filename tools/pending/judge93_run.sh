#!/bin/bash
# Sends the layout briefs to DeepSeek in think mode (Doug's say-so, 2026-11-20), off-peak only, resumable: a brief
# with an answer is skipped. Stops at peak or at the first empty answer; run it again to resume (after a sleep too).
cd "$(dirname "$0")/../.."
export PYTHONPATH=src PYTHONIOENCODING=utf-8
D=out/judge93
offpeak() { python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)"; }
send() {  # label, brief file, answer file
  offpeak || { echo "peak began: stopping, resume off-peak"; exit 2; }
  timeout 1500 python -X utf8 -m bibleont.delegate run --level 3 --blind --think --effort high --label "$1" --task "@$2" > "$3.raw" 2>&1
  python -X utf8 - "$3.raw" "$3" <<'EOF' || { echo "STOP: no answer for $1"; tail -3 "$3.raw"; exit 1; }
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
if len(t.strip()) < 400 or '"stopped"' in t[-400:]:
    sys.exit(1)
open(sys.argv[2], "w", encoding="utf-8").write(t)
EOF
  echo "$1 $(grep -o '"cost": [0-9.]*' "$3.raw" | tail -1)"
}
until offpeak; do sleep 120; done
for f in out/judge93/*-[0-9][0-9][0-9].txt; do a="${f%.txt}.answer.txt"; [ -s "$a" ] && continue; send "judge93 $(basename $f)" "$f" "$a"; done; echo done; exit 0
for ty in x; do
  for pk in visitor teacher scholar designer; do
    a="$D/$ty.$pk.answer.txt"; [ -s "$a" ] && continue
    send "layout $ty $pk" "$D/$ty.$pk.txt" "$a"
  done
  a="$D/$ty.layout.txt"; [ -s "$a" ] && continue
  python -X utf8 tools/pending/layout_pass.py reconcile "$ty" > "$D/$ty.reconcile.txt"
  send "layout $ty reconcile" "$D/$ty.reconcile.txt" "$a"
done
echo done
