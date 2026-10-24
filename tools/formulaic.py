"""Formulas: the same shape said again with different fillers.

2026-09-12: proceed to pattern_, after the rebuilt audit showed the
legacy graph's `pattern_*` namespace at **0% covered** — 225 relations over 87
pattern nodes, every one carrying a note, and nothing in the computed floor
reading any of it. It is also the namespace the whole project is
driving toward.

## Why the existing tools do not cover it

`tools/formulae.py` extends a pattern **already named** to units it already
had; it detects nothing. `tools/eventpatterns.py` finds recurring verb runs but
writes no layer the audit can probe. Neither produces a formula from the text.

## What a formula looks like in the legacy graph

    pattern_lived_begat_died          Gen 5, ten repetitions of a 3-verse shape
    pattern_naming_a_son              birth, speech, "she called his name X"
    pattern_peradventure_x_found_there  Gen 18, the negotiation
    pattern_and_it_came_to_pass       the narrative hinge

Two properties decide the method. **Instances are verse RANGES**, not single
verses — so the window is a passage, not a verse. And the formula is
**non-contiguous**: "lived ... begat ... died" has ages and names between its
verbs, so a word n-gram finds nothing. What recurs is the **sequence of verbs**,
with the fillers thrown away.

## The method

A verb-lemma sequence per verse from the frame layer, n-grams of 3 and 4 over a
three-verse window, kept when they recur in **three or more distinct
chapters** — a repetition inside one passage is that passage, not a form.

Ranked by the **rarity of the verbs it is built from**, because that is what
separates a formula from a coincidence:

    he spoke -> he said -> it was          45x and means nothing
    lay down -> be buried -> reigned       62x and is the regnal formula

Both recur. Only one is made of verbs whose co-occurrence is surprising.

## What a row claims

That these passages share a verb sequence. **Not that they are about the same
thing** — the regnal formula spans Judah and Israel, good kings and bad. A
formula is a form, and what it carries is the next question, not this one.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import re
import unicodedata as ud

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "out" / "formulaic.jsonl.gz"

WINDOW = 3          # legacy instances are 2-3 verse ranges
MIN_OCC = 3         # a form REPEATS; where it repeats is a label, not a gate
NGRAM = (3, 4)


def nfc(s):
    return ud.normalize("NFC", s or "")


STOP = {"he", "she", "it", "they", "you", "i", "we", "the", "a", "of", "will",
        "was", "were", "be", "is", "are", "did", "do", "them", "him", "her",
        "his", "to", "and", "up", "out", "in", "on"}


def node_id(glosses):
    """`pattern_lay_down_buried_reigned` -- the legacy graph's own convention.

    2026-09-12: make them node based if possible. The legacy
    graph names a form as a NODE and points `instance_of` edges at it, so a
    computed form built the same way can be compared with it directly and can
    sit in the same graph without translation.
    """
    parts = []
    for g in glosses:
        w = [x for x in re.sub(r"[^a-z ]", " ", (g or "").lower()).split()
             if x not in STOP]
        parts.append("_".join(w[:2]) if w else "x")
    return "pattern_" + "_".join(parts)


def vkey(r):
    b, c, v = r.split(".")
    return (b, int(c), int(v))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()

    # A PATTERN ELEMENT IS A TUPLE, NOT A WORD.
    #
    # 2026-09-12: these should be complete tuples at a minimum in form,
    # and not just random three words that go together often. That is
    # the unit defined on 2026-09-09 -- "Jesus fed the 5000" can
    # be described with a tuple.
    #
    # So each element carries its predicate AND its argument shape:
    #
    #     lay_down(agent)  ->  bury(agent,patient)  ->  reign(agent)
    #
    # Two passages match when the predicates AND the shapes agree. The
    # FILLERS are what varies, and their variation is what makes it a form
    # rather than a retelling -- checked below, not assumed.
    seq = collections.defaultdict(list)
    gloss = {}
    df = collections.Counter()
    with gzip.open(ROOT / "out/frames.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            lem = nfc(d.get("lemma") or "")
            if not lem:
                continue
            # A COMPLETE TUPLE IN FORM: an agent at minimum. A verb with no
            # argument recorded is a word, and a sequence of those is the
            # "three words that go together often" this is meant to exclude.
            named = d.get("named") or {}
            ag = (d.get("agent") or []) + (named.get("agent") or [])
            pa = (d.get("patient") or []) + (named.get("patient") or [])
            if not ag:
                continue
            shape = "a" + ("p" if pa else "")
            seq[d["ref"]].append({
                "k": (lem, shape),
                "agent": nfc(ag[0]), "patient": nfc(pa[0]) if pa else None,
            })
            gloss.setdefault(lem, (d.get("gloss") or lem).strip())
    for tups in seq.values():
        df.update({t["k"][0] for t in tups})
    n_verses = max(len(seq), 1)
    idf = {w: math.log(n_verses / c) for w, c in df.items()}
    print(f"verses with a verb sequence: {len(seq):,}   "
          f"distinct verbs: {len(df):,}")

    refs = sorted(seq, key=vkey)
    grams = collections.defaultdict(list)
    for i, r in enumerate(refs):
        b, c, v = vkey(r)
        win = [r]
        for j in range(i + 1, min(i + WINDOW, len(refs))):
            b2, c2, v2 = vkey(refs[j])
            if (b2, c2) != (b, c) or v2 != v + (j - i):
                break
            win.append(refs[j])
        vs = [x for w in win for x in seq[w]]
        for n in NGRAM:
            for k in range(len(vs) - n + 1):
                run = vs[k:k + n]
                g = tuple(t["k"] for t in run)
                # A verb repeated inside its own window is emphasis, not a
                # sequence; requiring distinct members keeps "said, said,
                # said" out.
                if len({x[0] for x in g}) == n:
                    grams[g].append((r, win[-1],
                                     tuple(t["agent"] for t in run)))

    # SAME EVENT vs SAME FORM -- two claims, both wanted, never merged.
    #
    # 2026-09-12: there is real value in matching the same events
    # across the synoptics. An earlier draft of this module treated synoptic
    # agreement as skew to be discounted, which was backwards -- and that had
    # already been said on 2026-09-10: the parallel passages should be caught
    # for sure.
    #
    # A formula whose occurrences are Matthew, Mark and Luke on ONE incident
    # is an ALIGNMENT: the same event told three times. A formula spread over
    # nineteen chapters of Kings is a PATTERN: one form carrying many events.
    # Filtering either away loses a real capability; conflating them makes a
    # form out of a retelling. So they are labelled, using the editorial
    # parallel-passage links, which are an outside judgment and not ours.
    par = collections.defaultdict(set)
    xp = ROOT / "out/xrefs.jsonl.gz"
    if xp.exists():
        with gzip.open(xp, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                if d.get("kind") != "parallel":
                    continue
                a_, b_ = d.get("from"), d.get("to")
                if a_ and b_:
                    ca = a_.rsplit(".", 1)[0]
                    cb = b_.rsplit(".", 1)[0]
                    par[ca].add(cb)
                    par[cb].add(ca)
    print(f"editorial parallel chapter-links: {len(par):,} chapters")

    def alignment(chapters):
        """True when the chapters are editorially linked as the same passage."""
        cs = list(chapters)
        if len(cs) < 2:
            return False
        linked = sum(1 for i in range(len(cs)) for j in range(i + 1, len(cs))
                     if cs[j] in par.get(cs[i], ()))
        pairs = len(cs) * (len(cs) - 1) / 2
        return pairs and linked / pairs >= 0.5

    # THE EXCLUSION LIST, with reasons.
    #
    # 2026-09-12: along with the overlay layer, track an excluded list with
    # reasons -- patterns that have been ruled out -- which should take a quick
    # glance to approve.
    #
    # Every rule that throws a candidate away records WHY and keeps examples,
    # so a rejection is reviewable instead of invisible. A filter nobody can
    # see is a filter nobody can overturn -- and three of today's four worst
    # bugs were things that failed silently.
    excluded = collections.defaultdict(list)

    def drop(reason, g, places):
        if len(excluded[reason]) < 40:
            excluded[reason].append({
                "formula": [f"{gloss.get(x[0], x[0])}({x[1]})" for x in g],
                "occurrences": len(places),
                "chapters": len({p[0].rsplit(".", 1)[0] for p in places}),
                "mass": round(sum(idf.get(x[0], 0) for x in g), 1),
                "at": [p[0] for p in places[:4]],
            })
        excluded[reason + "__count"] = excluded.get(reason + "__count", 0) + 1

    def collapse(places):
        """Merge overlapping window hits into maximal runs.

        The window slides one verse at a time, so a formula spanning Gen
        5:10-12 is caught again at 5:11-13 and 5:12-14. Counting raw hits
        reported Genesis 5's genealogy as 14 instances when it is ten
        repetitions caught at successive offsets -- a number inflated by the
        detector's own stride, which would then drive the ranking.
        """
        byc = collections.defaultdict(list)
        for s, e, fill in places:
            b, c, v = vkey(s)
            byc[(b, c)].append((v, int(e.rsplit(".", 1)[1]), s, e, fill))
        runs = []
        for (b, c), items in byc.items():
            items.sort()
            cs, ce, cf = None, None, set()
            for v, ev, s, e, fill in items:
                if cs is None or v > ce:
                    if cs is not None:
                        runs.append((f"{b}.{c}.{cs}", f"{b}.{c}.{ce}", cf))
                    cs, ce, cf = v, ev, {fill}
                else:
                    ce = max(ce, ev)
                    cf.add(fill)
            if cs is not None:
                runs.append((f"{b}.{c}.{cs}", f"{b}.{c}.{ce}", cf))
        return runs

    # BOTH COUNTS, because neither alone is honest.
    #
    # Raw window hits are inflated by the detector's one-verse stride: a
    # formula at Gen 5:10-12 is caught again at 5:11-13. Collapsing to
    # maximal runs over-corrects: Gen 39:13-20 becomes ONE run, losing that
    # Potiphar's wife tells the story twice inside it. Nothing structural
    # separates "stride artifact" from "genuinely adjacent repetition", so
    # both numbers are recorded and a consumer picks.
    rows = []
    for g, raw in grams.items():
        places = raw
        runs = collapse(raw)
        chapters = {p[0].rsplit(".", 1)[0] for p in places}
        # REPETITION IS THE GATE; SCOPE IS A LABEL.
        #
        # The first version required three distinct CHAPTERS, counting spread
        # as a proxy for repetition. They come apart exactly where the best
        # evidence lives, because **the most formulaic writing in the corpus
        # is deliberately concentrated**. Two cases proved it:
        #
        #   Gen 5     ten repetitions of "lived X years ... begat ... died",
        #             the clearest formula in the legacy set. All one chapter.
        #             Discarded.
        #   Gen 39    Potiphar's wife tells the same event twice (v14-15,
        #             v17-18) after the narrative relates it (v12). The frames
        #             are near-identical -- he left / he fled / he went out,
        #             three times -- and this is the Psalm 32 problem at
        #             chapter scale, with ground truth. Discarded.
        #
        # 2026-09-12: if the beatitudes were the only verses in the
        # Bible in that form, the pattern would still be captured, as it
        # is important for the collection. Concentration is what makes a
        # form structural, not what disqualifies it.
        if len(places) < MIN_OCC:
            drop(f"occurs fewer than {MIN_OCC} times -- not a repetition",
                 g, places)
            continue
        # RARITY IS THE WHOLE DISCRIMINATOR. A sequence of the commonest verbs
        # in the language recurs because those verbs are common, which is not
        # a form. Score is the summed IDF of the members, so a sequence is
        # interesting in proportion to how surprising its co-occurrence is.
        # FILLERS MUST VARY. If every occurrence has the same agents it is
        # one event retold, not a form -- which is the alignment case, kept
        # and labelled rather than dropped.
        fillers = {p[2] for p in places}
        mass = sum(idf.get(x[0], 0) for x in g)
        books = {c.split(".")[0] for c in chapters}
        rows.append({
            "id": node_id(gloss.get(x[0], x[0]) for x in g),
            "formula": [f"{gloss.get(x[0], x[0])}({x[1]})" for x in g],
            "tuples": [{"predicate": gloss.get(x[0], x[0]), "lemma": x[0],
                        "slots": x[1]} for x in g],
            "distinct_fillings": len(fillers),
            "occurrences": len(places), "runs": len(runs),
            "chapters": len(chapters),
            "books": sorted(books),
            "scope": ("within-passage" if len(chapters) == 1
                      else "across-books" if len(books) > 1
                      else "across-chapters"),
            "claim": ("alignment" if (alignment(chapters)
                                      or len(fillers) < 2) else "form"),
            "mass": round(mass, 2),
            "at": [f"{s}-{e.rsplit('.', 1)[1]}" if s != e else s
                   for s, e, _f in places[:40]],
        })
    # GRAMMATICAL FURNITURE. "he said -> he spoke -> it was" recurs because
    # those are the commonest verbs in the language, not because it is a form.
    # This is the rule named in the legacy set: pattern_and_it_came_to_pass
    # is a real repetition and carries nothing.
    MIN_MASS = 9.0
    keep = []
    for r in rows:
        if r["mass"] < MIN_MASS:
            excluded["built from the commonest verbs -- a repetition, not a "
                     "form"].append({k: r[k] for k in
                                     ("formula", "occurrences", "chapters",
                                      "mass")} | {"at": r["at"][:4]})
            excluded["built from the commonest verbs -- a repetition, not a "
                     "form__count"] = excluded.get(
                "built from the commonest verbs -- a repetition, not a "
                "form__count", 0) + 1
            continue
        keep.append(r)
    rows = keep
    rows.sort(key=lambda r: -r["mass"] * math.log(1 + r["chapters"]))
    print(f"tuple sequences repeating {MIN_OCC}+ times: {len(rows):,}")
    print(f"  scope {dict(collections.Counter(r['scope'] for r in rows))}")

    cl = collections.Counter(r["claim"] for r in rows)
    print(f"  FORM (one shape, many events) {cl['form']:,}   "
          f"ALIGNMENT (one event retold) {cl['alignment']:,}")

    for want, title in (
            ("form", "FORMS -- one shape carrying different events"),
            ("alignment", "ALIGNMENTS -- the same event told more than once")):
        # Spread matters more for a form and less for an alignment: the regnal
        # formula over 19 chapters is a stronger form than a rare run over 3.
        sub = sorted((r for r in rows if r["claim"] == want),
                     key=lambda r: -(r["mass"] * math.log(1 + r["chapters"])
                                     if want == "form" else r["mass"]))[:a.top]
        print(f"\n{title}")
        print(f"  {'chs':>4}{'occ':>5}{'mass':>7}  {'books':<16}formula")
        for r in sub:
            print(f"  {r['chapters']:>4}{r['occurrences']:>5}{r['mass']:>7.1f}"
                  f"  {','.join(r['books'][:3])[:15]:<16}"
                  f"{' -> '.join(x[:14] for x in r['formula'])}")

    # ---- the exclusion list, for review -----------------------------------
    print("\nRULED OUT, with reasons -- approve or overturn:")
    for reason in sorted(k for k in excluded if not k.endswith("__count")):
        n = excluded.get(reason + "__count", len(excluded[reason]))
        print(f"\n  [{n:,}]  {reason}")
        for e in excluded[reason][:3]:
            print(f"      {e['chapters']:>3}ch {e['occurrences']:>3}x "
                  f"mass {e['mass']:>5}  "
                  f"{' -> '.join(x[:13] for x in e['formula'])}")
            print(f"           {', '.join(e['at'][:3])}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            **provenance.stamp(__file__, inputs=["out/frames.jsonl.gz"]),
            "_source": "Derived from out/frames.jsonl.gz, itself MACULA "
                       "Hebrew/Greek Linguistic Datasets, Clear Bible, "
                       "CC BY 4.0.",
            "_note": "Recurring VERB SEQUENCES over a three-verse window, "
                     "kept when they span three or more chapters and ranked "
                     "by the rarity of their verbs. A row claims these "
                     "passages share a FORM. It does not claim they are "
                     "about the same thing: the regnal formula covers Judah "
                     "and Israel, good kings and bad.",
        }, ensure_ascii=False) + "\n")
        # NODES then EDGES -- the legacy graph's own shape: a form is a node
        # and each occurrence is an `instance_of` pointing at it. Ids can
        # collide when two formulas reduce to the same words; they are
        # suffixed rather than merged, because a merge would claim two
        # different forms are one.
        seen = collections.Counter()
        for r in rows:
            seen[r["id"]] += 1
            if seen[r["id"]] > 1:
                r["id"] = f"{r['id']}_{seen[r['id']]}"
            f.write(json.dumps({
                "kind": "pattern", "id": r["id"], "formula": r["formula"],
                "tuples": r["tuples"], "chapters": r["chapters"],
                "distinct_fillings": r["distinct_fillings"],
                "occurrences": r["occurrences"], "runs": r["runs"],
                "mass": r["mass"],
                # Scope and claim are LABELS on the form, never gates that
                # decided whether it exists. A consumer filters on them; the
                # detector does not.
                "scope": r["scope"], "claim": r["claim"],
                "books": r["books"],
            }, ensure_ascii=False) + "\n")
        for r in rows:
            for at in r["at"]:
                f.write(json.dumps({
                    "kind": "instance_of", "src": at, "dst": r["id"],
                }, ensure_ascii=False) + "\n")
        # The ruled-out candidates travel WITH the kept ones, in the same
        # file. A reviewer should not have to go looking for what was thrown
        # away, and a filter nobody can see is a filter nobody can overturn.
        for reason in sorted(k for k in excluded if not k.endswith("__count")):
            f.write(json.dumps({
                "kind": "excluded", "reason": reason,
                "n": excluded.get(reason + "__count", len(excluded[reason])),
                "examples": excluded[reason][:12],
            }, ensure_ascii=False) + "\n")
    edges = sum(len(r["at"]) for r in rows)
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} pattern nodes, "
          f"{edges:,} instance_of edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
