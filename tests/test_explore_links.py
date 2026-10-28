"""Every kind of link on the Explore page opens something (2026-10-27).

Explore gives each `.link` its own onclick, a chain of `l.dataset.X ? openX(...)`
branches ending in openSense. The page-wide listener, which the question cards
rely on, skips any element that already has an onclick. So a link whose
attribute has no branch in Explore's chain falls through to
openSense(undefined) and opens nothing. The traditions' rows (`data-tradition`)
did exactly that from 2026-10-26 to 2026-10-27, while the same links worked
from every question card. Found by a reader clicking them, not by any check.

Reads the static file, no server: every `data-X=` written in buildExplore must
be a branch of its dispatcher, apart from the attributes a branch reads as its
second argument and the section marker. Planted: the dispatcher with the
tradition branch removed, and a new attribute with no branch; both must fail.

Run: python tests/test_explore_links.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")

# read by a branch beside its own attribute (data-lkey with data-layer, data-cb
# with data-ca, data-word with data-key), or not a link at all (data-sec)
SECONDARY = {"lkey", "cb", "word", "sec"}
FALLBACK = "key"           # openSense(l.dataset.key, ...), the chain's last branch


def unrouted(src):
    start = src.index("async function buildExplore(){")
    end = re.compile(r"\n(?:async )?function ").search(src, start + 1).start()
    body = src[start:end]
    d0 = body.index(".querySelectorAll('.link').forEach(l =>")
    d1 = body.index("openSense(", d0)
    routed = set(re.findall(r"dataset\.(\w+)", body[d0:d1])) | {FALLBACK}
    used = set(re.findall(r"data-([a-z]+)=", body))
    return sorted(used - routed - SECONDARY), sorted(used)


fails = []
missing, used = unrouted(HTML)
if missing:
    fails.append(f"Explore links with no branch in its dispatcher: {', '.join('data-' + m for m in missing)}")

# planted faults: each must be caught
branch = "                      : l.dataset.tradition ? openTradition(l.dataset.tradition)\n"
if branch not in HTML:
    fails.append("planted: the tradition branch is not where the test expects it")
else:
    if "tradition" not in unrouted(HTML.replace(branch, ""))[0]:
        fails.append("planted: removing the tradition branch was not caught")
rowdef = "  const row = (attrs, title, sub) =>"
planted = HTML.replace(rowdef, "  const zz = `<span class=\"link\" data-planted=\"1\">`;\n" + rowdef)
if "planted" not in unrouted(planted)[0]:
    fails.append("planted: a new attribute with no branch was not caught")

for f in fails:
    print("FAIL", f)
print(f"Explore links: {len(used)} attributes, every link routed; planted faults caught: 2 of 2; {len(fails)} failures"
      if not fails else f"Explore links: {len(fails)} failures")
sys.exit(1 if fails else 0)
