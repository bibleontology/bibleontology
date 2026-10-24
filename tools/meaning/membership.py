"""WHICH WORDS AND VERSES BELONG TO A CARD: the one definition (plan 4.8 step
0(a); the committee's practitioner, 2026-10-19).

Three tools had three answers. The server showed a card's anchored words at a
share of 0.15 or more, added words of the same root and the lexicon's
derived words, and kept a word of another sense only where it is rendered as
the card's word. The concept audit and the resolution layer took every anchor,
and no family words: 3,114 anchors on 1,107 cards hidden from readers were
counted by both, and 621 of the repair sheet's 833 "drops" were words the site
already hid. Now the server, the audit and the resolver all ask this module.

It holds no data of its own and builds no index: each caller passes what it
already has (the server its in-memory lemmas, occurrences and verse sets), so
the live server's memory does not grow.

    anchors(rows)                 card id -> [(word key, share or None)]
    words(base, lemmas, families) the anchored words, their same-root words and
                                  the lexicon's derived words
    verses(card, words, ...)      the verses those words give the card, a word of
                                  another sense giving only its card-sense uses

RULED REPAIRS (2026-10-20, the concept-repair sheets): one small curated
file, ontology/card-repairs.jsonl (tools/meaning/write_repairs.py), read here
and nowhere else, so every caller sees the same card. A dropped word leaves the
card (and does not come back as another word's family); a word with NAMED
VERSES gives the card only those verses, each a reading (two judges said the
verse speaks of the card), never every verse the word is in.
"""
import json
import re
import unicodedata
from pathlib import Path

# THE CUT A READER SEES: an anchored word whose share of the card's name is
# under this is not shown (a word that renders the name only now and then).
# Declared in the filter policy, ontology/schema/salience.json (plan 8.1f),
# read through tools/meaning/salience.py: no tool keeps its own copy
import salience as _salience  # noqa: E402
SHOWN_SHARE = _salience.cut("card_word_share")

GREEK_PREFIXES = sorted("αμφι ανα αντι απο δια εισ εκ εξ εν εμ επι κατα μετα παρα περι προ "
                        "προσ συν συμ συγ υπερ υπο".split(), key=len, reverse=True)
_STEM_STOP = set("the a an of and in to for his her their my your our on at by with from as is "
                 "be that this it s god lord".split())

REPAIRS_FILE = Path(__file__).resolve().parents[2] / "ontology" / "card-repairs.jsonl"
# what a verse given only by a named-verse word says about itself on the card
READING = "a reading: two judges said this verse speaks of it"
_REPAIRS = None


def repairs():
    """card id -> {"drop": {key}, "named": {key: {verse}}}, from the ruled
    repairs (empty when there are none)."""
    global _REPAIRS
    if _REPAIRS is None:
        out = {}
        if REPAIRS_FILE.exists():
            for line in REPAIRS_FILE.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                c = out.setdefault(r["card"], {"drop": set(), "named": {}})
                if r["action"] == "drop":
                    c["drop"].add(r["key"])
                elif r["action"] == "named":
                    c["named"].setdefault(r["key"], set()).update(r["verses"])
        _REPAIRS = out
    return _REPAIRS


def _off(card):
    """The words a ruling takes off the card's ordinary words: dropped, or
    limited to named verses (they come back through words(), named)."""
    r = repairs().get(card)
    return (r["drop"] | set(r["named"])) if r else set()


def anchors(rows):
    """card id -> its anchored words [(key, share)], as a reader is shown them:
    a word card's anchors at SHOWN_SHARE or more, and the word its own cited
    verse uses whatever its share (plan 4.7a: "the Bear", Job 38:32's עַיִשׁ)
    -- the verse is the evidence, not a count. `rows` are the records of
    out/concept-anchors.jsonl.gz (tools/meaning/concept_anchors.py)."""
    out = {}
    for r in rows:
        if "id" not in r:
            continue
        ks = [(a[0], a[2]) for p in r.get("parts", []) for a in p.get("anchors", [])
              if a[2] >= SHOWN_SHARE] if r.get("kind") == "word" else []
        have = {k for k, _s in ks}
        ks += [(v["key"], None) for v in r.get("from_verses", []) if v["key"] not in have]
        off = _off(r["id"])
        ks = [(k, s) for k, s in ks if k not in off]
        if ks:
            out[r["id"]] = ks
    return out


def all_words(rows):
    """card id -> EVERY anchored word, shown or not, with its share and basis:
    [(key, share or None, basis)], basis "anchored" or "cited verse". Keep
    much, show little (plan 8.1f): the export publishes all, each with its
    tier, and the shown view is a declared subset of them."""
    out = {}
    for r in rows:
        if "id" not in r:
            continue
        # a card named by a phrase shows none of its single-word anchors (no
        # single word carries a phrase), so they are on request whatever their
        # share: basis "anchored (phrase card)"
        word_card = r.get("kind") == "word"
        ks = [(a[0], a[2], "anchored" if word_card else "anchored (phrase card)")
              for p in r.get("parts", []) for a in p.get("anchors", [])]
        ks = list({k: (k, s, b) for k, s, b in ks}.values())
        have = {k for k, _s, _b in ks}
        ks += [(v["key"], None, "cited verse") for v in r.get("from_verses", []) if v["key"] not in have]
        # a ruled drop is not "on request": it was judged to mean something else
        drop = (repairs().get(r["id"]) or {}).get("drop", set())
        ks = [x for x in ks if x[0] not in drop]
        if ks:
            out[r["id"]] = ks
    return out


def _plain(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(ch)).lower()


def root_index(lemmas):
    """{(language letter, first five plain letters): [(key, plain, lemma)]}: a
    root match always shares the first five letters (n is never under 5), so a
    tool asking for every card can look these up instead of scanning ~14,000
    lemmas per anchored word. Same answers; the server may pass none."""
    ix = {}
    for k2, l2 in lemmas.items():
        if (l2 or "")[:1].isupper():
            continue
        p2 = _plain(l2)
        ix.setdefault((k2[0], p2[:5]), []).append((k2, p2, l2))
    return ix


def words(base, lemmas, families, index=None, card=None):
    """The card's words: its anchored words, and

    THE SAME ROOT in the same language (first five letters: βάπτισμα finds
    βαπτίζω, which Acts 8:36 and 8:38 use). A Greek prefix is not a root:
    παράκλητος shares "παρακ" with παρακύπτω "stoop" (2026-09-30, the
    Comforter card), so past a prepositional prefix, three more letters. A
    name is not a word's family: φίλημα "kiss" and Φιλήμων, Philemon.

    THE LEXICON'S WORD FAMILY, alongside the prefix (plan 5.10, P-79): only
    words MADE FROM the card's word ("gives", "akin to"), never the word it was
    made from, which is usually broader (glory would gain δοκέω "think").

    THE RULED REPAIRS, given `card`: a dropped word is not re-added as another
    word's family, and a named-verse word joins as itself, marked `only`.

    `base` [(key, share)], `lemmas` {key: lemma}, `families` {key: [(key2, how)]}
    -> {key: {"key", "lemma", "share", "family"}}"""
    out = {k: {"key": k, "lemma": lemmas.get(k), "share": s, "family": False} for k, s in base}
    ix = index if index is not None else root_index(lemmas)
    for k, _s in base:
        p = _plain(lemmas.get(k))
        if len(p) < 6:
            continue
        n = 5
        if k[0] == "g":
            for pre in GREEK_PREFIXES:
                if p.startswith(pre):
                    n = max(n, len(pre) + 3)
                    break
        for k2, p2, l2 in ix.get((k[0], p[:5]), ()):
            if k2 not in out and p2[:n] == p[:n]:
                out[k2] = {"key": k2, "lemma": l2, "share": None, "family": True}
    for k, _s in base:
        for k2, how in families.get(k, []):
            if how in ("gives", "akin to") and k2 not in out and not (lemmas.get(k2) or "")[:1].isupper():
                out[k2] = {"key": k2, "lemma": lemmas.get(k2), "share": None, "family": True}
    rep = repairs().get(card) if card else None
    if rep:
        for k in _off(card):
            out.pop(k, None)
        for k, vs in rep["named"].items():
            out[k] = {"key": k, "lemma": lemmas.get(k), "share": None, "family": False,
                      "only": f"named verses ({len(vs)}): a reading"}
    return out


def card_stems(e):
    """The card's own English, as stems a rendering can contain ("curse" in
    "cursed"), from its name and other names."""
    out = set()
    for n in [e.get("name") or ""] + list(e.get("aka") or []):
        for w in re.findall(r"[A-Za-z]+", n):
            w = w.lower()
            if w in _STEM_STOP or len(w) < 3:
                continue
            for suf in ("ings", "ing", "ies", "ied", "ed", "es", "s", "e"):
                if len(w) > len(suf) + 2 and w.endswith(suf):
                    w = w[:-len(suf)]
                    break
            out.add(w)
    return out


def verses(card, entity, ws, verses_of, occurrences, verse_senses, how=None):
    """The verses the card's words give it.

    A WORD WITH ANOTHER SENSE GIVES ONLY THIS CARD'S USES (C-D13, the
    2026-10-02 evaluation): the temple card had listed 1,830 verses of בַּיִת
    "house". Where a blind judgment said the word's other renderings are
    another sense (ontology/verse-senses.jsonl, "card_only"), only the uses
    rendered as the card's own word count, and the word is marked so.

    `ws` from words(); `verses_of` {key: {verse}}; `occurrences` {key: [(verse,
    rendering)]}; `verse_senses` {(card, key): verdict} -> a set of verses
    (MACULA references). Marks `only` on the words it narrows.

    A NAMED-VERSE WORD (a ruled repair) gives only its named verses; where
    `how` is a dict, each verse no other word gives is marked READING in it."""
    out = set()
    st = None
    named = (repairs().get(card) or {}).get("named", {})
    for k in ws:
        if k in named:
            continue
        if verse_senses.get((card, k)) == "card_only":
            st = st if st is not None else card_stems(entity or {})
            out |= {ref for ref, t in occurrences.get(k, ()) if any(s in (t or "").lower() for s in st)}
            ws[k]["only"] = "rendered as this card's word"
        else:
            out |= verses_of.get(k, set())
    for k, vs in named.items():
        if k not in ws:
            continue
        for v in vs:
            if v not in out and how is not None:
                how[v] = READING
        out |= vs
    return out
