"""A word card's own address is its Strong's number (2026-10-16): /word/H1254.

Over 200 words spread across the Hebrew and Greek keys:
  - a word that has a page names /word/<H|G><number> as its address, and
    that address gives the same page back (no 301 loop, no second spelling);
  - a loose spelling of it (lower case, leading zeros) names the same address,
    so the caller sends it on;
  - every verse the page links is a verse the site has, under its own book
    code (the card pages once linked 926 redirects; test_card_links.py);
  - what is not a Strong's number has no page.

In process, after the graph loads (~1 minute). Run: python tests/test_word_addresses.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()
keys = sorted(k for k in set(d["lex"]) | set(d["profiles"]) if re.match(r"^[hg]\d+$", k))
sample = keys[::max(1, len(keys) // 200)][:200]
fails, pages, links = [], 0, 0
for k in sample:
    spelt = k[:1].upper() + k[1:]
    got = S.word_page(spelt)
    if not got:
        continue
    pages += 1
    head, body, addr = got
    if addr != spelt:
        fails.append(f"{k}: address {addr!r}, not {spelt!r}")
    if f'href="{S.SITE}/word/{spelt}"' not in head:
        fails.append(f"{k}: canonical is not /word/{spelt}")
    loose = S.word_page(k[:1].lower() + "00" + k[1:])
    if not loose or loose[2] != spelt:
        fails.append(f"{k}: the loose spelling does not name /word/{spelt}")
    for link in re.findall(r'href="/p/([^"#?]+)"', body):
        links += 1
        b, c, v = (link.split(".") + ["", "", ""])[:3]
        if not (c.isdigit() and v.isdigit() and (b, int(c), int(v)) in d["verses"]):
            fails.append(f"{k}: links /p/{link}, not a verse the site has")
for bad in ("", "X12", "H", "H12x3", "G-26", "../e/david"):
    if S.word_page(bad) is not None:
        fails.append(f"{bad!r} has a page")
print(f"{pages} word pages of {len(sample)} sampled; {links} verse links")
if not pages:
    fails.append("no word page at all")
for f in fails[:20]:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failures")
sys.exit(1 if fails else 0)
