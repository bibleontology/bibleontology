"""Trim connections by a checklist (plan 6.14).

2026-09-29: a trimming tool on pattern connections that scored high but do
not hold up to rigor when examined: a checklist that, at a minimum, demotes
anything that does not completely pass to the other-possible-connections
section, and removes altogether those that scored low originally and/or fail
the trimming pass badly.

And how to judge rigor with what the graph knows: *"same doer could be the
Father or Jesus as we understand that they are both God. The object might be
the nation of Israel in the OT and the listener is the new - understanding
that objects are more interchangeable"* -- and, the same morning, *"even if
a thing is matched against a person it might be interchangeable - Saul being
told that obedience is better than sacrifice might have some kind of refrain
later ... The point is that the refrains may not be to Saul and may still be
good matches."*

So objects are NOT checked for being the same person or the same kind; only
the one case where the same word means two different beings is. Each "says
the same thing" / "says the opposite" clause pair (out/aligned.jsonl.gz) is
checked:

    doer        both doers known and different fails -- except within the
                DIVINE class (God, the LORD, the Father, Jesus, the Spirit:
                one by the old graph's overlay, never merged), which passes
                and is named
    member      the SAME WORD naming two different beings fails HARD: the
                Son of God against an ordinary son (John 3:16 / 1 Chr 25:5
                "God gave Heman sons"); the God of Israel against another god
    stock       the verb and object are a stock phrase (in STOCK_N or more
                clauses, e.g. "heard . voice", 193): fails, unless the two
                clauses are read as speaking of the same thing. 1 Sam 15:22
                matched seven "listened to the voice" clauses, Amnon's
                refusal of Tamar among them, and none of its refrains
                (Hos 6:6, Ps 51:17, Rom 12:1)
    generic     verb and object both common (below the rarity floors) fails
    meaning     both clauses read (clause tags) and sharing no tag fails;
                sharing one is noted and rescues a stock phrase

Verdict: every check passed -> keep; one failure -> demote to "other
potential matches" with the reason; a hard failure, two failures, or one
failure on a pair that scored low to begin with -> remove.

The meaning check depends on the clause tags, so this is RE-RUN whenever
out/clause-tags.jsonl.gz is rebuilt (it takes a minute).

    python tools/patterns/trim.py     -> out/trim.jsonl.gz
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DIVINE = {"god", "yahweh", "the_father", "jesus", "holy_ghost", "spirit_of_god", "the_lord",
          "jesus_christ", "the_son_of_god", "the_son_of_man"}
SON = {"υιος", "בן"}
GODWORD = {"θεος", "אלהים", "אל"}
VI_FLOOR, OI_FLOOR = 4.0, 4.5       # rarity (idf) below which a word is common
STOCK_N = 50                        # clauses sharing a verb+object: a stock phrase
CONTRAST_VI = 5.5                   # a contrast's verb must be rarer than this
LOW_SCORE = 11.0                    # "scored low originally"
# Both verses stamped and sharing no stamp fails. OFF, measured twice on the
# 63 judged pairs. With 2,576 of 3,009 sections read: 7 true pairs demoted,
# 2 removed, 0 of the false caught. With the whole corpus (3,007 sections):
# 10 demoted and 5 removed of 34 true and related pairs (Ps 103:9 / Jer 3:12
# "not angry forever"; Rom 10:9 / Rom 8:11, Eph 1:20, Col 2:12 "raised from
# the dead"), and STILL 0 of the 6 false. Each section chose its stamps from
# its own slate, so one idea wears two names in two sections; a stamp is a
# section's theme, not a clause's claim.
STAMP_GATE = False


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower()


def main():
    pairs = [r for r in rows(OUT / "aligned.jsonl.gz") if r.get("tier") in ("same", "contrast")]
    objs = {r["ow"][i] for r in pairs if r.get("ow") for i in (0, 1) if r["ow"][i]}
    members = collections.defaultdict(list)
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] == "member" and e["src"] in objs:
            members[e["src"]].append(e["dst"])
    wanted = objs | {m for ms in members.values() for m in ms}
    # and the word after each (the possessor of a construct noun)
    nxt = lambda w: re.sub(r"#w(\d+)$", lambda m: f"#w{int(m[1]) + 1}", w)
    wanted |= {nxt(w) for w in list(wanted) if "#w" in w}
    lemma, construct = {}, set()
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if n.get("word") and n["id"] in wanted:
            lemma[n["id"]] = plain(n.get("lemma"))
            if n.get("state") == "construct":
                construct.add(n["id"])
    mention = {m["occurrence"]: m["record"] for m in rows(OUT / "mentions.jsonl.gz")}
    son = {json.loads(l)["occurrence"] for l in (OUT / "son-titles.jsonl").read_text(
        encoding="utf-8").splitlines()[1:]}
    # VERSE -> STAMP -> strength, medium or better. Measured 2026-09-29 on the
    # judged pairs, with 2,576 sections read:
    #  - CONCEPT tags are pinned where their word stands ("stone", "stones",
    #    "the stone" on Rom 9:33 and on Hag 2:15's temple stones; "nose" on
    #    Ps 103:8's slow to anger). Sharing one repeats the word match that
    #    made the pair; counted, they KEPT all five "none" stone pairs.
    #  - At CLAUSE level the pin lands on a neighbour as often as not (two
    #    runs agreed on 45% of clauses): Ps 103:8's tags sit on cl1, its match
    #    on cl0. Required per clause, it demoted five true Grace Formula pairs.
    # So only stamps count, by verse, and only where both verses carry one.
    stamps = collections.defaultdict(dict)
    for line in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8").read().splitlines()[1:]:
        t = json.loads(line)
        if t["kind"] != "stamp" or t["weight"] < 0.67:
            continue
        v, k = t["clause"].split("#")[0], re.sub(r"_ev$", "", t["tag"])
        stamps[v][k] = max(stamps[v].get(k, 0), t["weight"])
    phrase = collections.defaultdict(set)
    for r in pairs:
        phrase[(r["verb"][0], r["obj"][0])].add(r["from"])
        phrase[(r["verb"][1], r["obj"][1])].add(r["to"])

    def being(nid):
        """which being the object word names, where the same word can name
        two: the Son of God or a son; God or another god. Else None."""
        for w in members.get(nid) or [nid]:
            lem = lemma.get(w)
            if lem in SON:
                return "the Son of God" if w in son else "an ordinary son"
            if lem in GODWORD:
                r = mention.get(w)
                return "God" if (r is None or r in DIVINE) else f"another god ({r})"
        return None

    def gods(nid):
        """the object is God's own -- "the house of the LORD" (Ps 23:6),
        not a house (Deut 21:13): the head is in construct and the LORD or
        God follows. Hebrew only; the Greek genitive is not read here."""
        for w in members.get(nid) or [nid]:
            if w in construct and lemma.get(nxt(w)) in GODWORD | {"יהוה"}:
                return True
        return False

    out, tally = [], collections.Counter()
    for r in pairs:
        fails, hard, notes = [], [], []
        # medium or better on both sides: a low stamp is "any chance at all"
        # (the stamping brief to Flash) and does not carry a match
        ta, tb = stamps.get(r["from"].split("#")[0], {}), stamps.get(r["to"].split("#")[0], {})
        shared = ta.keys() & tb.keys()
        read_both = bool(ta) and bool(tb)
        # doer
        sa, sb = r.get("subj") or [None, None]
        if sa and sb and sa != sb and sa in DIVINE and sb in DIVINE:
            notes.append(f"the same doer by the overlay ({sa} / {sb})")
        elif r.get("doer_differs"):
            fails.append(f"different doers ({sa} / {sb})" if sa and sb else "different doers")
        # member: one word, two beings
        ow = r.get("ow") or [None, None]
        ka, kb = being(ow[0]), being(ow[1])
        if ka and kb and ka != kb:
            hard.append(f"the object is {ka} in one and {kb} in the other")
        elif gods(ow[0]) != gods(ow[1]):
            fails.append(f"God's own in one, not in the other ({r['obj'][0]})")
        # a contrast on an everyday verb is not an opposite: Ps 1:1 "does not
        # sit in the seat of mockers" against Judg 16:9's ambush "sitting in
        # the room" (sit, 4.76); "love the world" (6.7) is the model
        if r.get("tier") == "contrast" and max(vi_ := (r.get("vi") or [9, 9])) < CONTRAST_VI:
            fails.append(f"a contrast on a common verb ({r['verb'][0]})")
        # stock phrase
        n = max(len(phrase[(r["verb"][0], r["obj"][0])]), len(phrase[(r["verb"][1], r["obj"][1])]))
        if n >= STOCK_N and not shared:
            fails.append(f"a stock phrase ({r['verb'][0]} · {r['obj'][0]}, {n} places)")
        # generic words only
        vi, oi = r.get("vi") or [9, 9], r.get("oi") or [9, 9]
        if max(vi) < VI_FLOOR and max(oi) < OI_FLOOR:
            fails.append("only common words match")
        # meaning (clause tags)
        if shared:
            notes.append("both read as speaking of " + ", ".join(sorted(shared)[:3]).replace("_", " "))
        elif read_both and STAMP_GATE:
            # 2026-09-29: less is more on the verse-to-verse connections,
            # with potentially even greater emphasis on tag matching. Where both verses have been read, words and
            # structure alone no longer carry a match to the shown list.
            fails.append("not read as speaking of the same thing")
        if hard or len(fails) >= 2 or (fails and r["score"] < LOW_SCORE):
            verdict = "remove"
        elif fails:
            verdict = "demote"
        else:
            verdict = "keep"
        tally[verdict] += 1
        out.append({"from": r["from"], "to": r["to"], "verdict": verdict,
                    "fails": hard + fails, "notes": notes})
    with gzip.open(OUT / "trim.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "Trimming checklist verdicts for 'same' and 'contrast' "
                            "clause pairs (tools/patterns/trim.py, plan 6.14). Re-run after "
                            "the clause tags are rebuilt."}) + "\n")
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"{len(out):,} pairs checked: " + ", ".join(f"{k} {v:,}" for k, v in tally.most_common()))
    reasons = collections.Counter(re.sub(r" \(.*\)$", "", f) for x in out for f in x["fails"])
    print("reasons:", reasons.most_common(8))


if __name__ == "__main__":
    main()
