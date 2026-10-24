"""A card's words, one definition (plan 4.8 step 0(a), 2026-10-19).

tools/meaning/membership.py decides which words and verses belong to a card for
the server, the concept audit and the resolution layer. These tests hold its
rules, each with a planted case that must be refused, and check that the three
callers really use it -- three copies of the rule are what the module ended
(3,114 anchors hidden from readers were counted by the audit and the resolver).

    python tests/test_membership.py          (preflight runs it so)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import membership as M  # noqa: E402


def row(cid, anchors, kind="word", from_verses=()):
    return {"id": cid, "kind": kind, "parts": [{"word": cid, "anchors": [[k, None, s] for k, s in anchors]}],
            "from_verses": [{"key": k} for k in from_verses]}


def test_shown_share_cut_and_planted_low_anchor():
    a = M.anchors([row("love", [("g26", 0.9), ("h2617", 0.10)])])
    assert ("g26", 0.9) in a["love"]
    assert all(k != "h2617" for k, _ in a["love"]), "an anchor under the shown share must not count"


def test_cited_verse_word_counts_whatever_its_share():
    a = M.anchors([row("the_bear", [], kind="phrase", from_verses=["h5906"])])
    assert a["the_bear"] == [("h5906", None)]


def test_root_and_planted_name():
    lemmas = {"g908": "βάπτισμα", "g907": "βαπτίζω", "g5371": "φίλημα", "g5371b": "Φιλήμων"}
    w = M.words([("g908", 0.9)], lemmas, {})
    assert "g907" in w and w["g907"]["family"], "the same root is the card's word"
    w2 = M.words([("g5371", 0.9)], lemmas, {})
    assert "g5371b" not in w2, "a name is not a word's family (Philemon)"


def test_greek_prefix_is_not_a_root():
    lemmas = {"g3875": "παράκλητος", "g3879": "παρακύπτω"}
    assert "g3879" not in M.words([("g3875", 0.9)], lemmas, {}), "a shared prefix is not a shared root"


def test_family_only_words_made_from_it():
    lemmas = {"g1391": "δόξα", "g1392": "δοξάζω", "g1380": "δοκέω"}
    fam = {"g1391": [("g1392", "gives"), ("g1380", "from")]}
    w = M.words([("g1391", 0.9)], lemmas, fam)
    assert "g1392" in w and "g1380" not in w, "the word it came from is broader, not the card's"


def test_index_gives_the_same_words():
    lemmas = {"g908": "βάπτισμα", "g907": "βαπτίζω", "g909": "βαπτισμός", "g1": "ἄλφα"}
    assert set(M.words([("g908", 0.9)], lemmas, {})) == set(M.words([("g908", 0.9)], lemmas, {}, M.root_index(lemmas)))


def test_another_sense_gives_only_card_uses():
    ws = M.words([("h1004", 0.9)], {"h1004": "בַּיִת"}, {})
    occ = {"h1004": [("1Ki.6.1", "the temple"), ("Gen.12.1", "house")]}
    v = M.verses("image_temple", {"name": "temple"}, ws, {"h1004": {"1Ki.6.1", "Gen.12.1"}}, occ,
                 {("image_temple", "h1004"): "card_only"})
    assert v == {"1Ki.6.1"}, "a word of another sense gives only the uses rendered as the card"


def _with_repairs(rep, fn):
    """Run fn with these ruled repairs in place of the file's."""
    saved = M._REPAIRS
    M._REPAIRS = rep
    try:
        return fn()
    finally:
        M._REPAIRS = saved


def test_dropped_word_leaves_and_does_not_return_as_family():
    lemmas = {"g908": "βάπτισμα", "g907": "βαπτίζω"}
    rep = {"x": {"drop": {"g907"}, "named": {}}}
    a = _with_repairs(rep, lambda: M.anchors([row("x", [("g908", 0.9), ("g907", 0.9)])]))
    assert ("g907", 0.9) not in a["x"], "a dropped word is still among the card's anchors"
    w = _with_repairs(rep, lambda: M.words([("g908", 0.9)], lemmas, {}, card="x"))
    assert "g907" not in w, "planted: a dropped word came back as the same root"
    w0 = _with_repairs(rep, lambda: M.words([("g908", 0.9)], lemmas, {}))
    assert "g907" in w0, "without the card, the rule does not apply (callers must pass it)"


def test_named_verses_only_and_marked_a_reading():
    """Decision 1's adds: two judges said these verses speak of the card; the
    word's other verses must not come with them (Israel's 73 were the people,
    gold's 53 were gifts and jewelry)."""
    rep = {"tithe": {"drop": set(), "named": {"h6237": {"Deu.14.22", "Gen.28.22"}}}}
    vof = {"h4643": {"Lev.27.30"}, "h6237": {"Deu.14.22", "Gen.28.22", "Num.31.30"}}
    how = {}

    def run():
        ws = M.words([("h4643", 0.9)], {"h4643": "מַעֲשֵׂר", "h6237": "עָשַׂר"}, {}, card="tithe")
        return ws, M.verses("tithe", {"name": "the tithe"}, ws, vof, {}, {}, how)
    ws, v = _with_repairs(rep, run)
    assert v == {"Lev.27.30", "Deu.14.22", "Gen.28.22"}, f"planted: a named word gave other verses: {v}"
    assert ws["h6237"].get("only", "").startswith("named"), "a named word is not marked as limited"
    assert how.get("Deu.14.22") == M.READING and "Lev.27.30" not in how, "the reading mark is wrong"


def test_repairs_file_rows_are_well_formed():
    if not M.REPAIRS_FILE.exists():
        return
    import json
    for line in M.REPAIRS_FILE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        assert r["action"] in ("named", "drop"), f"unknown repair action {r['action']}"
        assert r.get("ruling") and r.get("reader"), f"a repair without its ruling or reader: {r['card']} {r['key']}"
        if r["action"] == "named":
            assert r["verses"] and all(re.fullmatch(r"[1-3]?[A-Z][a-z]+\.\d+\.\d+", v) for v in r["verses"]), \
                f"named verses not as MACULA references: {r['card']} {r['verses'][:3]}"


def test_callers_use_the_module():
    """No caller keeps its own copy of the rule: the 0.15 cut and the anchor
    walk live in membership.py only."""
    for p in ("app2/server.py", "tools/meaning/resolve_records.py", "tools/meaning/concept_audit.py",
              "tools/meaning/repair_sheet.py"):
        src = (ROOT / p).read_text(encoding="utf-8")
        assert "membership" in src, f"{p} does not use the shared module"
        assert not re.search(r"a\[2\]\s*>=\s*0\.15", src), f"{p} keeps its own copy of the shown cut"
    # every caller that asks for a card's words passes the card, or the ruled
    # repairs silently do not apply to it
    for p in ("app2/server.py", "tools/meaning/resolve_records.py", "tools/meaning/concept_audit.py",
              "tools/export_card_words.py"):
        src = (ROOT / p).read_text(encoding="utf-8")
        for m in re.finditer(r"M\.words\(([^\n]*)", src):
            assert "card=" in m.group(1), f"{p} asks for a card's words without the card: {m.group(0)[:80]}"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for n, f in tests:
        try:
            f()
        except AssertionError as ex:
            failed.append(f"FAIL {n}: {ex}")
    print(f"card membership: {len(tests)} checks, {len(tests) - len(failed)} passed, planted faults among them")
    for x in failed:
        print(x)
    sys.exit(1 if failed else 0)
