"""Which gospel events a passage speaks of: candidates, with their evidence.

2026-09-28, the day the gospel event map was drawn: Philippians 2:5-11 is to be
mapped to it. The event map exists so that a passage outside
the story can point INTO it (plan 7.4; P-2026-09-28-46): the hymn's
"became obedient to death-even death on a cross" (Phil 2:8) is the crucifixion,
told four times.

## What counts as evidence, and what it cannot decide

For each content word of the passage (MACULA Greek lemma, noun / verb /
adjective), every event whose tellings carry the same lemma or one of its
FAMILY — the compound or simplex built on it (ὑπερυψόω / ὑψόω, κάμπτω γόνυ
/ γονυπετέω) — is a candidate. Each hit says WHERE in the telling the word
sits:

    narration   the event itself: the thing happens (they crucified Him)
    speech      said inside the event: a prediction, a teaching, a taunt
                (John 3:14 "so must the Son of Man be lifted up")

These are different links and the page keeps them apart: a passage that
recounts an event, and a passage that enacts a saying (Luke 14:11 "he who
humbles himself will be exalted"), are both real and not the same claim.

A word's weight is its rarity ACROSS EVENTS (log of events / events
carrying it), so κύριος and ὄνομα count little and σταυρός much. Words do
not decide that an event is referred to; they surface the candidates, and
the decision is a reading, recorded with its reader (JUDGED-PAIRS).

    python tools/event_refs.py Php.2.5 Php.2.11   -> docs/review/event-refs-<from>.html
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
from gospel_events import read_bsb, GOSPELS, USFM  # noqa: E402

CONTENT = ("noun", "verb", "adj")
PREFIXES = ("ὑπερ", "συν", "συμ", "ἀπο", "ἐκ", "ἐξ", "κατα", "ἀνα", "δια",
            "ἐπι", "παρα", "προ", "προσ", "μετα", "περι", "ὑπο", "ἐν", "εἰσ")
STEM = 4          # a compound's first element: this many letters of a noun
TOP = 8           # events shown per word
COMMON = 40       # a word in more events than this pairs with nothing


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def plain(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def speech_share():
    """Per gospel verse, the share of its BSB text inside quotation marks."""
    share = {}
    for code, bk in GOSPELS.items():
        f = next(USFM.glob(f"*{code}*.usfm"))
        ch, depth, cur, inside, total = 0, 0, None, 0, 0
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
                continue
            if line.startswith(("\\s", "\\r", "\\m", "\\id", "\\h", "\\toc",
                                "\\mt")):
                continue
            text = re.sub(r"\\f .*?\\f\*", "", line)
            text = re.sub(r"\\w ([^|]*)\|[^\\]*\\w\*", r"\1", text)
            for piece in re.split(r"(\\v \d+)", text):
                m = re.match(r"\\v (\d+)", piece)
                if m:
                    if cur and total:
                        share[cur] = inside / total
                    cur, inside, total = f"{bk}.{ch}.{m.group(1)}", 0, 0
                    continue
                piece = re.sub(r"\\\S+\*?", "", piece)
                # on/off, never a count: a speech running into a new
                # paragraph reopens with “ and never closed the last one,
                # so counting leaked John 19:17's narration into speech
                for c in piece:
                    if c == "“":
                        depth = 1
                    elif c == "”":
                        depth = 0
                    elif c.isalpha():
                        total += 1
                        inside += depth > 0
        if cur and total:
            share[cur] = inside / total
    return share


def main(first, last):
    seq, _sections = read_bsb()
    evs = list(rows(OUT / "gospel-events.jsonl.gz"))
    pos = {v: i for i, v in enumerate(seq)}
    verse_ev = {}
    for e in evs:
        for t in e["tellings"]:
            for p in range(pos[t["start"]], pos[t["end"]] + 1):
                verse_ev[seq[p]] = e["id"]
    # the lemmas of every gospel verse and of the passage
    bk, c1, v1 = first.split(".")
    _, c2, v2 = last.split(".")
    lo, hi = (int(c1), int(v1)), (int(c2), int(v2))
    lem_v = collections.defaultdict(set)
    passage = []                                 # (verse, lemma, gloss)
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if not n.get("word") or not n.get("lemma"):
            continue
        v = n["id"].split("#")[0]
        cls = (n.get("class") or n.get("pos") or "").lower()
        if v in verse_ev:
            lem_v[plain(n["lemma"])].add(v)
        b, c, vv = v.split(".")
        if b == bk and lo <= (int(c), int(vv)) <= hi and \
                any(cls.startswith(k) for k in CONTENT):
            passage.append((v, plain(n["lemma"]), n.get("text") or ""))
    all_lemmas = set(lem_v)

    def family(lem):
        fam = {lem}
        for p in map(plain, PREFIXES):
            if lem.startswith(p) and lem[len(p):] in all_lemmas:
                fam.add(lem[len(p):])
            if p + lem in all_lemmas:
                fam.add(p + lem)
        if len(lem) > STEM + 1:
            stem = lem[:STEM + 1]
            fam |= {x for x in all_lemmas if x.startswith(stem) and
                    len(x) > len(lem) + 2}
        return fam
    speech = speech_share()
    n_ev = len(evs)
    title = {e["id"]: e["title"] for e in evs}
    seen, words = set(), []
    for v, lem, gloss in passage:
        if lem in seen:
            continue
        seen.add(lem)
        fam = family(lem)
        hits = collections.defaultdict(lambda: {"narration": [], "speech": []})
        for x in fam:
            for gv in lem_v.get(x, ()):
                kind = "speech" if speech.get(gv, 0) > 0.5 else "narration"
                hits[verse_ev[gv]][kind].append((gv, x))
        if not hits:
            continue
        w = math.log(n_ev / len(hits))
        words.append({"verse": v, "lemma": lem, "gloss": gloss,
                      "family": sorted(fam - {lem} & set(
                          x for h in hits.values() for k in h.values()
                          for _v, x in k)),
                      "weight": round(w, 2), "events": len(hits),
                      "hits": sorted(({"event": e, "title": title[e],
                                       "narration": sorted({a for a, _ in h["narration"]}),
                                       "speech": sorted({a for a, _ in h["speech"]})}
                                      for e, h in hits.items()),
                                     key=lambda r: -len(r["narration"]) -
                                     len(r["speech"]))})
    # COLLOCATION, not a sum. Summing every word's weight per event ranked
    # "Jesus Appears to Two Disciples" first on Jesus / God / every / be
    # (2026-09-28). Two of the passage's words in ONE gospel verse is the
    # evidence: humbles + exalted is Luke 14:11's saying, and neither word
    # alone shows it. A pair scores its rarer word's weight plus the other's.
    verse_words = collections.defaultdict(dict)      # gospel verse -> lemma
    for w in words:
        if w["events"] > COMMON:
            continue
        for h in w["hits"]:
            for gv in h["narration"] + h["speech"]:
                verse_words[gv][w["lemma"]] = w
    pairs = []
    for gv, ws in verse_words.items():
        if len(ws) < 2:
            continue
        ws = sorted(ws.values(), key=lambda w: -w["weight"])
        pairs.append({"verse": gv, "event": verse_ev[gv],
                      "title": title[verse_ev[gv]],
                      "where": "speech" if speech.get(gv, 0) > 0.5 else "narration",
                      "words": [w["gloss"] for w in ws],
                      "score": round(ws[0]["weight"] + ws[1]["weight"], 1)})
    pairs.sort(key=lambda p: -p["score"])
    tag = first.replace(".", "")
    res = {"passage": f"{first}-{last}", "words": words, "pairs": pairs}
    (OUT / f"event-refs-{tag}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in pairs[:30]:
        print(f'{p["score"]:5.1f} {p["verse"]:10s} {p["where"]:9s} '
              f'{p["title"]}: {", ".join(p["words"])}')
    print()
    for w in sorted(words, key=lambda w: -w["weight"]):
        print(f'{w["weight"]:4.1f} {w["verse"]} {w["gloss"]} [{w["lemma"]}'
              f'{" +" + ",".join(w["family"]) if w["family"] else ""}] '
              f'{w["events"]} events: ' + "; ".join(
                  f'{h["title"]} ({len(h["narration"])}n/{len(h["speech"])}s)'
                  for h in w["hits"][:5]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
