"""S6 — translation readings: the names the BSB supplies for a pronoun.

2026-09-27: kept as the last step, with the BSB also as a separate layer, and
then one more attempt at completing unresolved pronouns. It runs
after S5, and only on what S5 left open. Its output is NOT the structure:
it goes to its own file (out/structure-readings.jsonl.gz), every edge
marked `reading: "BSB"`, so the structure stands on the original language
alone and these can be shown, hidden or dropped without touching it.

THE SIGNAL. The Berean editors tag each stretch of their English with the
Hebrew or Greek word it renders (out/bsb-align.jsonl.gz). A name in their
verse that is in NO tagged stretch, and is not in the verse's original at
all, is one they supplied — 2Ch 36:20 "carried by NEBUCHADNEZZAR into
exile", where the Hebrew has only "he". That is their reading of who the
pronoun is, which is meaning, and it is recorded as theirs.

THE RULE (from tools/fixrules/examples/bsb_pronoun.py, measured 12-13 of
16): an unresolved third-person SUBJECT takes a supplied name when
  - the name belongs to a person or place named earlier in the chapter
    (the last 40 named), and agrees in number (and gender, where both have
    one);
  - it stands within 40 characters BEFORE the English its verb is tagged
    to, as an English subject does, and not after a preposition ("to
    Jesus", "about Jesus"; "by Nebuchadnezzar" is allowed, the English
    passive of a Hebrew active); the nearest such verb takes it, a tie
    decides nothing;
  - one name to one subject, and one subject to one name.
First widened to every third-person pronoun, placed by nearest word; a
sample of 20 was 11 right. The errors: the BSB's section headings, printed
after the verse, read as supplied names ("Jesus Expels an Unclean SPIRIT",
Mrk 1:20); and a name given to the only open pronoun wherever it sat
("Going directly to JESUS, he said", Mrk 14:45, gave Judas's "he" to
Jesus). Hence the heading cut, subjects only, and the placement.
A "name" is a proper noun, or a word MACULA's glossers capitalise ("God",
"LORD"): they write "God" for the one God and "a god", "gods" otherwise.
"""
import collections
import gzip
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent.parent / "out"
STOP = {"Of", "The", "In", "To", "From", "For", "With", "And", "A", "An",
        "By", "On", "At", "Unto", "Upon", "Into", "Between", "Toward"}
WINDOW = 40


def _num(s):
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def _key(ref):
    b, c, v = ref.split(".")
    return (b, int(c), int(v))


def name_of(n):
    """The name a node carries in English, or None: the capitalised words
    of its gloss, without the function words a gloss may carry ("of
    Jesus")."""
    if not n.get("word") or n.get("class") != "noun":
        return None
    toks = [t[:-2] if t.endswith(("’s", "'s")) else t
            for t in re.findall(r"[A-Z][\w’']*", n.get("text") or "")]
    toks = [t for t in toks if t not in STOP]
    name = " ".join(toks)
    return name if len(name) >= 3 else None


def _bsb():
    moved = {}
    try:
        moved = json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        pass
    align = {}
    for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line)
        if r.get("ref"):
            align[r["ref"]] = (r.get("text") or "", r.get("spans") or [])
    return moved, align


def _agrees(p, n):
    if p.get("number") and p["number"] != (n.get("number") or "singular"):
        return False
    g, h = p.get("gender"), n.get("gender")
    return not g or not h or "common" in (g, h) or g == h


def s6(verses):
    """Edges for the readings layer; the verses are not changed."""
    moved, align = _bsb()
    resolved = {e["src"] for v in verses.values() for e in v.edges
                if e["type"] == "refers_to"}
    out = []
    stats = collections.Counter()
    by_chapter = collections.defaultdict(list)
    for ref in verses:
        by_chapter[ref.rsplit(".", 1)[0]].append(ref)
    for chap in sorted(by_chapter, key=lambda c: _key(c + ".0")):
        window = []                  # (node id, node, name), oldest first
        for ref in sorted(by_chapter[chap], key=_key):
            v = verses[ref]
            text, spans = align.get(moved.get(ref, ref), ("", []))
            if text:
                out += _verse(v, text, spans, window, resolved, stats)
            for n in sorted((n for n in v.nodes.values() if n.get("word")),
                            key=lambda n: (n.get("w") or [0])[0]):
                nm = name_of(n)
                if nm:
                    window.append((n["id"], n, nm))
            del window[:-WINDOW]
    return out, stats


PREPS = {"to", "from", "with", "for", "about", "of", "at", "in", "on",
         "against", "toward", "towards", "before", "after", "upon", "unto",
         "into", "over", "under", "among", "through", "like", "than"}
NEAR = 40                                   # characters before the verb


def _verse_only(text, spans):
    """The verse without the section heading the BSB prints after it
    ("... Jesus Expels an Unclean Spirit (Luke 4:31-37)"): up to the end of
    the sentence holding the last tagged word."""
    if not spans:
        return text
    last = max(b for _, b, _ in spans)
    m = re.match(r"[^.?!;]*[.?!;]*[”’\"')\]]*", text[last:])
    return text[:last + (m.end() if m else 0)]


def _verse(v, text, spans, window, resolved, stats):
    fam = "g" if v.lang == "greek" else "h"
    text = _verse_only(text, spans)
    here = {_num(n.get("strong")) for n in v.nodes.values()
            if n.get("strong") and not n.get("clause")}
    at = collections.defaultdict(list)          # tag key -> span starts
    for a, b, k in spans:
        at[k].append((a, b))

    def untagged(m):
        return not any(a < m.end() and b > m.start() for a, b, _ in spans)

    # the supplied names: nearest earlier holder of each name
    holder = {}
    for nid, n, nm in reversed(window):
        if nm not in holder and _num(n.get("strong")) not in here:
            holder[nm] = (nid, n)
    names = []                                  # (position, name, id, node)
    for nm, (nid, n) in holder.items():
        for m in re.finditer(r"\b" + re.escape(nm) + r"\b", text):
            before = [w.lower() for w in
                      re.findall(r"[A-Za-z]+", text[:m.start()])[-2:]]
            if before[-1:] == ["the"]:
                before = before[:-1]             # "to the LORD"
            # "to Jesus", "the news about Jesus": not a subject. "by
            # Nebuchadnezzar" is (the English passive of a Hebrew active)
            if untagged(m) and not set(before[-1:]) & PREPS:
                names.append((m.start(), nm, nid, n))
    if not names:
        return []
    # the SUBJECTS S5 left open (the rule as measured: a subject the verb
    # carries, or a subject pronoun), each placed by its verb's English
    pron = []
    ct_verb = {e["src"]: e["dst"] for e in v.edges if e["type"] == "v"}
    subj_ct = {e["dst"]: e["src"] for e in v.edges if e["type"] == "s"}
    for n in v.nodes.values():
        if n.get("class") != "pron" or n.get("person") != "third" or \
                n["id"] in resolved or n["id"] not in subj_ct:
            continue
        stats["open third-person subjects in verses the BSB names"] += 1
        verb = v.nodes.get(ct_verb.get(subj_ct[n["id"]])) or {}
        places = at.get(fam + _num(verb.get("strong")), [])
        pron.append((n, [a for a, _ in places]))
    claims = collections.defaultdict(list)
    for pos, nm, nid, node in names:
        # the name stands just BEFORE its verb, as an English subject does
        fits = sorted((min(a - pos for a in places if 0 < a - pos <= NEAR),
                       p["id"]) for p, places in pron if _agrees(p, node)
                      and any(0 < a - pos <= NEAR for a in places))
        if not fits or (len(fits) > 1 and fits[0][0] == fits[1][0]):
            stats["a supplied name with no single subject"] += 1
            continue
        claims[fits[0][1]].append((nm, nid))
    out = []
    for pid, got in claims.items():
        if len({nid for _, nid in got}) != 1:
            stats["a pronoun claimed by two names"] += 1
            continue
        nm, nid = got[0]
        stats["resolved"] += 1
        out.append({"ref": v.ref, "lang": v.lang, "type": "refers_to",
                    "src": pid, "dst": nid, "reading": "BSB",
                    "inferred": f"the BSB names '{nm}' here, a word the "
                                f"{'Greek' if v.lang == 'greek' else 'Hebrew'}"
                                f" does not have"})
    return out
