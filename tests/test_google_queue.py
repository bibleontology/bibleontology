"""Every page waiting in the Google submission queue can be indexed (2026-11-03).

Doug submitted /e/apostles from docs/review/google-submissions.md and Search Console answered "Excluded by 'noindex'
tag": the card was under the site's own thin-page bar (3 own verses and 100 words), and the queue had been written by
hand from what was improved, never checked against that rule. Doug: "why are we suggesting cards that fail such a
criteria?" Now each queued page that is not marked done or struck must render without noindex, here, before he sees it.

    python -X utf8 tests/test_google_queue.py

Planted: a card known to be under the bar, queued, must be caught.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

QUEUE_FILE = ROOT / "docs" / "review" / "google-submissions.md"
if not QUEUE_FILE.exists():
    print("google queue: skipped (the queue is a private document; the public copy does not carry it)")
    sys.exit(0)
S.load()
QUEUE = QUEUE_FILE.read_text(encoding="utf-8")
URL = re.compile(r"^\s*\d+\.\s+(https://bibleontology\.org(/\S*))", re.M)


def waiting(text):
    """The queued pages still to submit: a numbered line with a URL, not done, not struck."""
    out = []
    for m in URL.finditer(text):
        line = text[m.start():text.find("\n", m.start())]
        if "done" in line or "~~" in line:
            continue
        out.append(m.group(2))
    return out


def noindex(path):
    """True when the page the server renders for this path asks not to be indexed; None for a path not checked here."""
    if path.startswith("/e/"):
        out = S.card_page(path[3:].split("#")[0])
    elif path.startswith("/p/"):
        out = S.passage_page(path[3:])
    else:
        return None                       # the blog, /mcp and the like are served whole, with no thin-page rule
    if out is None:
        return True                       # no page at all is worse than noindex
    html = "".join(x for x in out if isinstance(x, str)) if isinstance(out, tuple) else str(out)
    return 'name="robots" content="noindex' in html


fails = []
paths = waiting(QUEUE)
for p in paths:
    if noindex(p):
        fails.append(p)
planted = noindex("/e/apostles") is True

for f in fails:
    print("FAIL queued but not indexable:", f)
print("google queue: %d waiting pages checked; planted fault caught: %s; %d failures"
      % (len(paths), planted, len(fails)))
sys.exit(1 if fails or not planted else 0)
