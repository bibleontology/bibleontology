"""The UBS dictionaries' senses on the word and verse pages (2026-11-04; docs/review/permissions/sdbh-2026-11-02.md).

    python -X utf8 tests/test_ubs_pages.py

Part 1 runs anywhere, on an invented fixture (no dictionary text: this file is public, and the exporter refuses UBS
text by content):
  1. the markup is cleaned: link codes to their words, notation marks out, Louw-Nida numbers as "LN"
  2. one entry under several numbers is split by where the site has each number; a number left with none of its
     verses shows no senses (H1122's case: the shared entry's verses were H1121's)
  3. a verse shows a sense only where the dictionary lists that verse under it (planted: a wrong verse, caught)
  4. a domain's other words come by how many of their uses it files there, never the word itself
  5. no files, no senses, and nothing raised
Part 2 needs data/raw/ubs/ and loads the server (about a minute); skipped without it:
  6. each credit is exactly the README's sentence
  7. ἀγάπη (G26): "fellowship meal" cites Jude 12 alone; Jude 12's card shows it on ἀγάπαις, Jude 11's on nothing
  8. every sense's verses resolve to a verse page; every domain word listed has a word card
  9. every sense shown on a sample of verse cards lists that verse (the same check catches a planted wrong verse)
 10. the served word and verse pages carry the senses and the credit; the MCP answer marks the licence and credits UBS
 11. a sense is shown under the number its verses carry: G2411 shows UBS's "temple" (filed under ἱερός, G2413, and
     saying so), G2413 no longer shows the temple's verses, and no sense sits where another number of the same word
     holds its verses (planted: the old rule)
"""
import json
import random
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "src"))
import ubs  # noqa: E402

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


# ---------------------------------------------------------------- part 1, the fixture
def sense(short, refs, code, label="Zone", glosses=("g",)):
    return {"domains": [{"code": code, "label": label}], "short": short, "long": "", "glosses": list(glosses),
            "refs": refs}


SHARED = [sense("= a made-up sense", ["Gen.1.1", "Gen.1.2", "Gen.1.3"], "001")]
HEB = [
    {"key": "h1", "lemma": "אא", "source": "ubs-hebrew", "version": "v0", "senses": [
        sense("= alpha ◄ of {L:Beta<SDBH:בב>} ► and so; ≈ fond{N:001}", ["Gen.1.1", "Gen.1.1", "Exod.2.3"], "001"),
        sense("= second", ["Gen.2.1"], "002")]},
    {"key": "h2", "lemma": "גג", "source": "ubs-hebrew", "version": "v0", "senses": SHARED},
    {"key": "h3", "lemma": "גג", "source": "ubs-hebrew", "version": "v0", "senses": SHARED},
    {"key": "h4", "lemma": "גג", "source": "ubs-hebrew", "version": "v0", "senses": SHARED},
    {"key": "h5", "lemma": "דד", "source": "ubs-hebrew", "version": "v0", "senses": [
        sense("= rare", ["Gen.5.5"], "001")]},
]
GRK = [{"key": "g7", "lemma": "αα", "source": "ubs-greek", "version": "v0", "senses": [
    sense("(from {L:β<SDBG:β:000000>}[a] ‘x,’ {D:15.215}) a thing", ["Jude.1.12"], "023")]}]
TO_M = {"Gen": "Gen", "Exod": "Exo", "Jude": "Jud"}
SITE = {"h2": {"Gen.1.1"}, "h3": {"Gen.1.2", "Gen.1.3"}, "h4": {"Gen.9.9"}}

with tempfile.TemporaryDirectory() as tmp:
    for name, rows in (("ubs-hebrew.jsonl", HEB), ("ubs-greek.jsonl", GRK)):
        (Path(tmp) / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    U = ubs.Ubs(TO_M, root=tmp, has=lambda k, r: r in SITE.get(k, ()))

    # 1. cleaning
    s0 = U.entry("h1")["senses"][0]["short"]
    check(s0 == "alpha of Beta and so; fond", f"1: cleaned Hebrew reads {s0!r}")
    g0 = U.entry("G0007")["senses"][0]["short"]
    check(g0 == "(from β ‘x,’ LN 15.215) a thing", f"1: cleaned Greek reads {g0!r}")
    check(ubs.base_key("H6213a") == "h6213" and ubs.base_key("g0026") == "g26" and ubs.base_key("x1") is None,
          "1: base_key")

    # 2. the shared entry, split by where the site has each number
    check([s["refs"] for s in U.entry("h2")["senses"]] == [["Gen.1.1"]], f"2: h2 {U.entry('h2')['senses']}")
    check([s["refs"] for s in U.entry("h3")["senses"]] == [["Gen.1.2", "Gen.1.3"]], "2: h3 kept its two verses")
    check(U.entry("h4")["senses"] == [], "2: h4, none of whose verses the entry names, shows a sense")
    check(sorted(U.entry("h2")["shared"]) == ["h3", "h4"], "2: the shared numbers are named")
    check([s["refs"] for s in U.entry("h1")["senses"]][0] == ["Gen.1.1", "Exo.2.3"]
          and U.entry("h1")["senses"][0]["uses"] == 3, "2: an unshared entry keeps every verse, once each, uses counted")

    # 3. a verse shows the sense only where it is listed; a planted wrong verse is caught by the same rule
    check([s["short"] for s in U.senses_at("Gen.1.1", "H1")] == ["alpha of Beta and so; fond"], "3: h1 at Gen 1:1")
    check(U.senses_at("Gen.2.2", "h1") == [], "3: h1 shown at a verse no sense lists")
    check(U.senses_at("Jud.1.12", "G7") and not U.senses_at("Jud.1.11", "g7"), "3: g7 at Jude 12 and not 11")

    def wrong(U_, pairs):
        """(mref, key) pairs whose shown sense does not list that verse."""
        return [(m, k) for m, k in pairs for s in U_.senses_at(m, k) if m not in s["refs"]]
    U.at[("Gen.2.2", "h1")] = [0]                                  # planted
    check(wrong(U, [("Gen.2.2", "h1"), ("Gen.1.1", "h1")]) == [("Gen.2.2", "h1")], "3: a planted wrong verse missed")
    del U.at[("Gen.2.2", "h1")]

    # 4. a domain's other words, by how many uses it files there
    check(U.domain_keys("h1", "001") == ["h3", "h2", "h5"], f"4: domain 001 order {U.domain_keys('h1', '001')}")
    check("h1" not in U.domain_keys("h1", "001"), "4: the word listed among its own domain's others")

# 5. nothing to read
E = ubs.Ubs(TO_M, root=Path(tempfile.gettempdir()) / "no-such-ubs-folder")
check(not E and E.entry("h1") is None and E.senses_at("Gen.1.1", "h1") == [], "5: an empty dictionary answered")
check(U.source("G7")["credit"] == ubs.CREDIT["g"] == U.source("g7")["credit"], "5: the credit by a card's key (G7)")
print(f"ubs pages, part 1: 5 groups on a fixture, 1 planted fault; {len(fails)} failures")

# ---------------------------------------------------------------- part 2, the real files and the server
if not all((ubs.RAW / f).exists() for f in ubs.FILES.values()):
    print("ubs pages, part 2: skipped, data/raw/ubs/ is not on this machine (python tools/fetch_ubs.py)")
else:
    # 6. each credit as its README gives it
    for letter, readme in (("h", "README-hebrew.md"), ("g", "README-greek.md")):
        # the Greek README breaks "Testa-ment" with a soft hyphen, which is not shown
        txt = " ".join((ubs.RAW / readme).read_text(encoding="utf-8").replace("­", "").split())
        check(ubs.CREDIT[letter] in txt, f"6: the {letter} credit is not the README's sentence")

    import server as S                                    # noqa: E402
    d = S.load()
    U = S.ubs_data(d)
    c = S.api_sense(d, {"key": ["g26"]})
    u = c.get("ubs") or {}
    meal = [s for s in u.get("senses") or [] if "fellowship meal" in s["glosses"]]
    check(len(meal) == 1 and meal[0]["refs"] == ["Jud.1.12"], f"7: G26's fellowship meal {meal}")
    vc = S.verse_card(d, "Jude", 1, 12)
    shown = {w["t"]: [g for s in w.get("ubs") or [] for g in s["glosses"]] for w in vc["words"]}
    check(any("ἀγάπ" in t and "fellowship meal" in gl for t, gl in shown.items()), f"7: Jude 12 {shown}")
    vc11 = S.verse_card(d, "Jude", 1, 11)
    check(not any("fellowship meal" in s["glosses"] for w in vc11["words"] for s in w.get("ubs") or []),
          "7: Jude 11 shows the fellowship meal")
    check(u.get("credit") == ubs.CREDIT["g"] and u.get("licence") == "CC BY-SA 4.0", "7: the card's credit")

    # 8. verses resolve, domain words have cards (a sample of words, seeded)
    random.seed(11)
    keys = random.sample(sorted(k for k in U.entries if k in d["profiles"]), 150) + ["g26", "h1", "h430"]
    bad_v, bad_w, nref = [], [], 0
    for k in keys:
        uk = S.ubs_senses(d, k)
        for s in (uk or {}).get("senses") or []:
            for r in s["refs"]:
                nref += 1
                if not S._word_verse(d, r):
                    bad_v.append((k, r))
            for dm in s["domains"]:
                bad_w += [(k, w["key"]) for w in dm["words"] if w["key"] not in d["profiles"]]
    check(not bad_v, f"8: {len(bad_v)} of {nref} sense verses open no verse page, e.g. {bad_v[:4]}")
    check(not bad_w, f"8: domain words with no card, e.g. {bad_w[:4]}")

    # 9. every sense on a sample of verse cards lists that verse
    S._VC_CACHE.clear()
    seen = wrong_at = 0
    for (b, ch, v) in sorted(d["verses"])[::997]:
        card = S.verse_card(d, b, ch, v)
        m = S._vc_mref(d, b, ch, v)
        for w in card["words"]:
            if w.get("ubs"):
                seen += 1
                full = U.entry(w["card"])["senses"]
                for s in w["ubs"]:
                    if not any(f["short"] == s["short"] and m in f["refs"] for f in full):
                        wrong_at += 1
    check(seen > 50 and not wrong_at, f"9: {wrong_at} of {seen} words show a sense that does not list the verse")

    # 10. the served pages and the MCP
    head, body, _addr = S.word_page("G26")
    check("Its senses, in the UBS dictionary" in body and '/p/Jude.1.12"' in body and "CC BY-SA 4.0" in body
          and S._esc(ubs.CREDIT["g"]) in body, "10: the word page's UBS section or credit")
    head, body, _p = S.passage_page("Jude.1.12")
    check("fellowship meal" in body and "senses here" in body and S._esc(ubs.CREDIT["g"]) in body,
          "10: the verse page's senses or credit")
    import mcp_backend                                   # noqa: E402
    it = mcp_backend.Backend(S, d)._word("G26")
    check("CC BY-SA 4.0" in it["text"] and "fellowship meal" in it["text"]
          and any(x["name"] == ubs.CREDIT["g"] for x in it["sources_extra"]), "10: the MCP word answer")
    print(f"ubs pages, part 2: {len(keys)} words' senses, {seen} verse-card words checked")

    # 11. A SENSE IS SHOWN UNDER THE NUMBER ITS VERSES CARRY (2026-11-07). UBS files ἱερός under G2413 only, and its
    # "temple" sense's 71 verses are ἱερόν's (G2411): G2413 "sacred" showed "temple" with 67 verses, G2411 nothing.
    # 973 senses were under a number holding under half their verses, where another number of the same word held them
    vo = S._verses_of(d)
    temple = [s for s in (U.entry("g2411") or {}).get("senses", []) if "temple" in s["short"]]
    check(temple and len(temple[0]["refs"]) > 50 and (U.entry("g2411").get("filed_under") or {}).get("key") == "g2413",
          "11: G2411 does not show UBS's 'temple' sense, filed under ἱερός (G2413)")
    check(all(len(s["refs"]) <= 3 for s in U.entry("g2413")["senses"]), "11: G2413 'sacred' still shows the temple's verses")
    _, body, _a = S.word_page("G2411")
    check("UBS files it under" in body or "UBS files them under" in body, "11: G2411's page does not say where UBS files it")
    at = {}
    for k_, vs_ in vo.items():
        for m_ in vs_:
            at.setdefault(m_, set()).add(k_)
    lem = d["lemmas"]
    import unicodedata
    def letters(x):
        return "".join(c for c in unicodedata.normalize("NFD", x or "") if not unicodedata.combining(c))
    def stray(U_):
        n = 0
        for k_, e_ in U_.entries.items():
            if e_.get("shared"):
                continue
            for s_ in e_["senses"]:
                away = [m_ for m_ in s_["refs"] if m_ not in vo.get(k_, ())
                        and any(o != k_ and o[0] == k_[0] and letters(lem.get(o)) == letters(e_["lemma"]) for o in at.get(m_, ()))]
                if s_["refs"] and len(away) * 2 > len(s_["refs"]):
                    n += 1
        return n
    check(stray(U) == 0, f"11: {stray(U)} senses shown under a number when another number of the same word holds their verses")
    planted = ubs.Ubs(S.TO_MACULA, has=lambda k_, m_: m_ in vo.get(k_, ()))          # the rule of 2026-11-04: no owners
    check(stray(planted) > 100 and not (planted.entry("g2411") or {}).get("senses"),
          "planted: the old rule (senses kept under UBS's number) was not caught")

for f in fails:
    print("FAIL", f)
print(f"ubs pages: 11 groups; {len(fails)} failures")
sys.exit(1 if fails else 0)
