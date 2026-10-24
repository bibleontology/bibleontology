"""Every link a card page gives a crawler is the address that page answers at,
not one that redirects (2026-10-05). Card pages linked their verses with the
dataset's book code ("/p/1Ch.10.14"), each answered 301 to "/p/1Chr.10.14",
and AhrefsBot spent 926 requests in a few hours on the bounces.

Checks the plain-HTML card pages (card_page) of 300 cards spread over the
graph: every /p/ link is a verse or chapter the site has, under the site's
own book code. Proven 2026-10-05 by restoring the old line in card_page: it
failed at once, naming "/p/Luk.16.23", "/p/Jos.15.3" ... (A first proof that
emptied MACULA_BACK instead passed -- it also broke the verse-text lookup,
so the links vanished rather than going wrong. Plant the real fault.)

In process, after the graph loads (~1 minute). Run: python tests/test_card_links.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()
chapters = {(b, c) for (b, c, _v) in d["verses"]}
ids = sorted(d["ents"])
sample = ids[::max(1, len(ids) // 300)][:300]
fails, n = [], 0
for eid in sample:
    try:
        out = S.card_page(eid)
    except Exception:            # noqa: BLE001 -- a card that is not a page is not this test's
        continue
    if not out:
        continue
    body = out[1] if isinstance(out, tuple) else ""
    for link in re.findall(r'href="/p/([^"#?]+)"', body):
        n += 1
        parts = link.split(".")
        ok = (len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit()
              and (parts[0], int(parts[1]), int(parts[2])) in d["verses"]) or \
             (len(parts) == 2 and parts[1].isdigit() and (parts[0], int(parts[1])) in chapters)
        if not ok:
            fails.append(f"{eid}: /p/{link} is not an address the site answers without a redirect")
# EVERY THEME PAGE AND TABLE PAGE RENDERS, with the same link rule (2026-10-06:
# a change to the front page's chapter list -- strings to {"label", "b", "c"}
# -- left theme_page calling the old form; /theme/apocalyptic answered 200 to
# crawlers with no article at all, and nothing in preflight looked)
themes = [t["id"] for t in S._theme_map().get("themes", [])]
pages = [(S.theme_path(t), lambda t=t: S.theme_page(t)) for t in themes] + \
        [(S._side_path(t), lambda t=t: S.imagery_page(t)) for t in S._theme_hubs() if S._imagery(t)]
for path, make in pages:
    try:
        out = make()
    except Exception as e:       # noqa: BLE001
        fails.append(f"{path}: the page failed to render: {e!r}"[:200])
        continue
    if not out or "<article" not in out[1]:
        fails.append(f"{path}: no page for crawlers")
        continue
    for link in re.findall(r'href="/p/([^"#?]+)"', out[1]):
        n += 1
        parts = link.split(".")
        ok = (len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit()
              and (parts[0], int(parts[1]), int(parts[2])) in d["verses"]) or \
             (len(parts) == 2 and parts[1].isdigit() and (parts[0], int(parts[1])) in chapters)
        if not ok:
            fails.append(f"{path}: /p/{link} is not an address the site answers without a redirect")
# A RENAMED THEME'S OLD NAME ON NO PAGE (2026-10-06: the home page, built from
# the records, kept "Prophetic Word & Fulfillment" after the rename), as the
# server sends it (with_card), and the home page links every theme's address
olds = [(pat, n["was"]) for pat, _name, _f in S._theme_renames()
        for n in (S._theme_homes().get("names") or {}).values() if n["name"] == _name]
home = S.with_card(b"<html><head><title>x</title></head><body></body></html>", *S.home_page()).decode("utf-8")
for path, make in [("/", None)] + pages + [(f"/e/{e}", lambda e=e: S.card_page(e)) for e in sample[:60]]:
    try:
        html = home if make is None else S.with_card(b"<title>x</title><body></body>", *make()[:2]).decode("utf-8")
    except Exception:            # noqa: BLE001 -- rendering failures are reported above
        continue
    for pat, was in olds:
        # the literal name too: the server's own pattern missed "Messiah / Christology" (no "/")
        if pat.search(html) or was in html or was.replace("&", "&amp;") in html:
            fails.append(f"{path}: still shows the old theme name {was!r}")
for t in themes:
    if f'href="{S.theme_path(t)}"' not in home:
        fails.append(f"/: the home page does not link {S.theme_path(t)}")
# THEME ADDRESSES IN THE USUAL FORM (7.6d, 2026-10-08): no page links the old
# /theme/<id> form (it answers 301, but a page that links a redirect makes
# every crawler take it), every theme has a /themes/ address, and every old
# address -- the theme and each table ending it ever had -- moves to the new one
for path, make in [("/", None)] + pages:
    try:
        html = home if make is None else make()[1]
    except Exception:            # noqa: BLE001 -- rendering failures are reported above
        continue
    for old in re.findall(r'href="(/theme/[^"]*)"', html):
        fails.append(f"{path}: links the old address {old}")
addr = S._theme_addr()[0]
for t in themes:
    if t not in addr:
        fails.append(f"{t}: no entry in ontology/themes/theme-addresses.json")
    if S._old_theme_path(f"/theme/{t}") != S.theme_path(t):
        fails.append(f"/theme/{t} does not move to {S.theme_path(t)}")
    for old_end in ("imagery", "side-by-side", "taken-up", "told-again", "titles", "sayings", "blessed-and-sent"):
        if S._old_theme_path(f"/theme/{t}/{old_end}") != S._side_path(t):
            fails.append(f"/theme/{t}/{old_end} does not move to {S._side_path(t)}")
if S._old_theme_path("/theme/no_such_theme") is not None:
    fails.append("an unknown old theme address is redirected instead of answering 404")
# NO KJV SPELLING IN A CARD'S ADDRESS (2026-10-07): "honour" looks like
# archaic language. A.22 renamed the old forms (thou, hath, -eth); twenty-six
# ids kept the KJV's -our ("honour", "the_whole_armour_of_god", "well_favoured")
# or its "kine" until this check, which found eleven of them.
# Each old id still opens its card (id_kjv / merged_from).
OUR = re.compile(r"(armour|honour|favour|labour|vapour|colour|saviour|savour|odour|neighbour|"
                 r"behaviour|harbour|rumour|valour|splendour|endeavour|clamour|fervour|vigour|"
                 r"(?:^|_)kine(?:_|$))")
for eid in ids:
    if OUR.search(eid):
        fails.append(f"/e/{eid}: the address keeps a KJV spelling")
# The KJV-spelled ones redirect through id_kjv, which the public repository
# strips with every *_kjv field (plan 8.3b): a copy without them checks only
# the redirect that rests on merged_from.
_kjv_ids = '"id_kjv"' in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(encoding="utf-8")
for old in (("honour", "the_whole_armour_of_god") if _kjv_ids else ()) + \
        ("you_shall_love_your_neighbour_as_yourself",):
    if d["renamed"].get(old) not in d["ents"]:
        fails.append(f"/e/{old}: the old address no longer opens its card")
print(f"{len(sample)} cards and {len(pages)} theme pages, {n} verse links, {len(fails)} failures")
for f in fails[:10]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
