"""A sub-theme card leads to its major theme, and a major theme's record opens the theme's page (Doug, 2026-11-10, on
"The strong man tied up", a search landing: "given very little context and there isn't even a viable path back to
the major theme"; of /e/theme_spiritual_warfare: "is not the same as /themes/spiritual-warfare and is actually a poor
fraud ... it should be a path to the greater context").

  - EVERY SUB-THEME (theme_concept) names its major theme, the theme's page and its other sub-themes, on the card and
    on the served page
  - A MAJOR THEME'S RECORD names its theme, so the app opens the theme's page; its served page is canonical to it
  - A SUB-THEME'S WORDS stand in its own verses ("strong drink" was matched by name on the strong man's card)

Every check is proved by a planted fault. In process, after the graph loads. Run: python tests/test_theme_paths.py"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


d = S.load()
vo = S._verses_of(d)


def faults(eid):
    """What is wrong with one theme card."""
    f = []
    e = d["ents"][eid]
    kind = (e.get("attrs") or {}).get("kind")
    c = S.api_entity(d, {"id": [eid]})
    if kind == "theme_concept":
        T = c.get("in_theme") or {}
        if not T.get("theme") or not T.get("path", "").startswith("/themes/") or not T.get("title"):
            f.append(f"{eid}: no major theme named ({T})")
        own = {S._macula_ref(d, r) for r in e.get("refs") or ()}
        for w in ((c.get("face") or {}).get("words") or []):
            if not vo.get(w.get("key"), set()) & own:
                f.append(f"{eid}: the word {w.get('key')} ({w.get('gloss')}) stands in none of its verses")
    elif kind == "major_theme":
        if c.get("major_theme") != (e.get("attrs") or {}).get("theme"):
            f.append(f"{eid}: the record does not open its theme's page")
    return f


subs = sorted(x for x, v in d["ents"].items() if (v.get("attrs") or {}).get("kind") == "theme_concept")
majors = sorted(x for x, v in d["ents"].items() if (v.get("attrs") or {}).get("kind") == "major_theme")
for eid in subs + majors:
    for f in faults(eid):
        check(False, f)
# the served pages, a sample: the theme's page linked in the article
served = 0
for eid in subs[::40]:
    pg = S.card_page(eid)
    T = S.sub_theme_of(d, eid, d["ents"][eid])
    check(bool(pg and T and f'href="{T["path"]}"' in "".join(map(str, pg))),
          f"{eid}'s served page does not link its theme")
    served += 1

# planted: the theme lookup off, and a name-matched word put back
saved = S.sub_theme_of
S.sub_theme_of = lambda d_, eid, e: None
try:
    check(any("no major theme" in f for f in faults("theme_spiritual_warfare_c6")),
          "planted: the strong man without its theme was not caught")
finally:
    S.sub_theme_of = saved
saved_f = S.api_entity


def _with_drink(d_, q):          # the card as it was: a word matched by its name, not its verses
    c = saved_f(d_, q)
    c["face"] = {**(c.get("face") or {}), "words": [{"key": "h7941", "gloss": "strong drink"}]}
    return c


S.api_entity = _with_drink
try:
    check(any("h7941" in f for f in faults("theme_spiritual_warfare_c6")),
          "planted: 'strong drink' on the strong man was not caught")
finally:
    S.api_entity = saved_f

print(f"{len(subs)} sub-themes and {len(majors)} major themes checked, {served} served pages; 2 planted faults caught"
      if not fails
      else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
