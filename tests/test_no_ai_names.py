"""No tool is named, and no AI is pointed at, outside About (2026-10-16).

The UI downplays AI, since there is skepticism and even some hostility in the
Bible community towards it: AI, Sonnet, Haiku, Opus, DeepSeek and CoPilot are
named nowhere in the UI except in the About. The data keeps every reading's reader; what a reader is shown
says only how a line was found (index.html `prov`).

Samples what the app is sent, through the same `answer()` every route uses:
300 cards, 300 verses' connections and patterns, every major theme and its
table, 150 word cards, every tag sampled, and a handful of searches. Any of
the names, or "a model", in a reply is a failure. /api/about is exempt: it is
where the tools are credited.

Proof: run it with CREDIT_SCRUB emptied (the planted fault) and it fails.

In process, after the graph loads (~1 minute). Run: python tests/test_no_ai_names.py"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

if "--plant" in sys.argv:
    S.CREDIT_SCRUB[:] = []                       # the planted fault

NAMES = re.compile(r"\b(?:AI|Claude|Sonnet|Haiku|Opus|DeepSeek|Copilot|ChatGPT|GPT-\d|LLM)\b|\ba model(?:'s)?\b")
d = S.load()
fails, n = [], 0


def check(route, **q):
    global n
    try:
        body = S.answer(route, urlencode(q)).decode("utf-8")
    except Exception:                              # noqa: BLE001 -- a route that errors is another test's
        return
    n += 1
    for m in NAMES.finditer(body):
        fails.append(f"{route}?{urlencode(q)}: …{body[max(0, m.start() - 50):m.end() + 30]}…")
        return


ids = sorted(d["ents"])
for eid in ids[::max(1, len(ids) // 300)][:300]:
    check("/api/entity", id=eid)
verses = sorted(d["verses"])
for b, c, v in verses[::max(1, len(verses) // 300)][:300]:
    ref = f"{b}.{c}.{v}"
    check("/api/echoes", ref=ref)
    check("/api/patterns", ref=ref)
for t in json.loads(S.answer("/api/majorthemes", "").decode("utf-8")).get("themes", [])[:40]:
    tid = t.get("id") or t.get("theme")
    if tid:
        check("/api/majortheme", id=tid)
        check("/api/imagery", id=tid)
keys = sorted(d["profiles"])
for k in keys[::max(1, len(keys) // 150)][:150]:
    check("/api/sense", key=k)
for q in ("love", "Moses", "John 3:16", "covenant", "the cross", "Rahab"):
    check("/api/search", q=q)
print(f"{n} replies checked")
for f in fails[:15]:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} replies name a tool or point at AI")
sys.exit(1 if fails else 0)
