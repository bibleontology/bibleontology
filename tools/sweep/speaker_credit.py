"""WHO SAYS IT: the sweep's speech turns matched to the earlier graph's claims
(plan 8.1c; approved 2026-10-18, P-2026-10-18-1).

The claim export (tools/export_claims.py) puts a claim in a speaker's voice
only where the earlier graph recorded `claimed_by`. The sweep has since named
a sender for thousands of speech turns. This finds, for each relation, the turn
its verses lie inside, and the earlier graph's record for that turn's speaker.

A verse is credited to a turn only by what the claim is about, never by the
verse alone, because a verse often holds the narrator's frame and the speech
together ("Then Satan answered the LORD, 'Does Job fear God for nothing?'"):

  - the claim's subject and object, where the verse names them (out/mentions),
    must all lie inside the turn's spoken clauses, and at least one must; or
  - where the verse names neither, every clause of the verse must be spoken
    in the turn (a verse wholly inside the speech).

A claim is credited when every one of its verses gives the same speaker.
The speaker is the turn's sender, followed through what it refers to until a
word the earlier graph has a record for. A sender that is a generic ("his
armor-bearer") has no record, and the claim is counted, not credited.

    python tools/sweep/speaker_credit.py   -> out/sweep/speaker-credits.jsonl
                                              out/sweep/speaker-credits-stats.json
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import verses  # noqa: E402

GROUP_EDGES = {"part", "command", "attached", "line", "condition", "consequence", "basis",
               "agent_act", "group_subject", "content"}
ABOUT_THE_TEXT = {"asserted_by", "speaks_of", "part_of", "instance_of", "specializes", "in_theme",
                  "draws_on", "spoken_in", "quoted", "recounts", "composed_of",
                  # the graph's analysis of a figure ("the covering is drawn from
                  # a covering", Job 22:14), not anything the speaker says
                  "drawn_from", "signifies", "token_of", "aspect_of"}
TEXT_KINDS = {"text", "passage", "pattern"}
# the act of speaking, which the frame itself reports ("he charged them,
# saying"): the narrator's, even where only the speaker and hearer are named
SPEECH_ACTS = {"told", "charged", "besought", "answered", "rebuked", "accused", "warned", "explained",
               "blessed", "cursed", "named", "titled", "wrote_to", "wrote_letter_to", "heard", "incited",
               "appeared_to", "deceived", "conspired_against", "self_designated_as", "spoken_of_as"}


def jl(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                yield json.loads(ln)


def main():
    nodes = {}
    for d in jl(ROOT / "out" / "placeholder-nodes.jsonl.gz"):
        if d.get("clause") or d.get("pair") or d.get("word"):
            nodes[d["id"]] = {k: d.get(k) for k in ("ref", "w", "clause", "pair", "head", "nested_in", "word", "kind")}
    layer = list(jl(ROOT / "out" / "sweep-layer.jsonl.gz"))
    gone_groups = {d["id"] for d in layer if d.get("action") == "remove" and "type" not in d and d.get("id")}
    gone = {(d["src"], d["type"], d["dst"]) for d in layer if d.get("action") == "remove" and "type" in d}
    edges = [e for e in jl(ROOT / "out" / "placeholder-edges.jsonl.gz")
             if (e.get("src"), e.get("type"), e.get("dst")) not in gone
             and e.get("src") not in gone_groups and e.get("dst") not in gone_groups]
    for d in layer:
        if d.get("action") == "remove":
            continue
        if d.get("node"):
            nodes[d["id"]] = {"ref": d.get("ref"), "pair": True, "kind": d.get("kind")}
        else:
            edges.append(d)
    for g in gone_groups:
        nodes.pop(g, None)

    out_of = collections.defaultdict(list)       # src -> [(type, dst)]
    refers = {}
    for e in edges:
        out_of[e["src"]].append((e["type"], e["dst"]))
        if e["type"] == "refers_to" and e.get("reading") == "sweep":
            refers[e["src"]] = e["dst"]
    for e in edges:                               # the builder's, where the sweep said nothing
        if e["type"] == "refers_to":
            refers.setdefault(e["src"], e["dst"])
    nested = collections.defaultdict(list)
    for nid, n in nodes.items():
        if n.get("nested_in"):
            nested[n["nested_in"]].append(nid)

    # ONLY WORDS THAT NAME: a mention got by following the builder's
    # refers_to predates the sweep, which corrected many of them (Job 1:17's
    # "he said" went to the Chaldeans, his own report's subject, not to the
    # messenger: measured 2026-10-18). Those are followed here afresh,
    # through the sweep's links
    mention = {}
    for d in jl(ROOT / "out" / "mentions.jsonl.gz"):
        if "occurrence" in d and not str(d.get("how", "")).startswith("refers_to"):
            mention[d["occurrence"]] = d["record"]

    def record_of(x, seen=()):
        """A sender to the earlier graph's record, through what it refers to."""
        if x in seen or len(seen) > 8:
            return None
        if x in mention:
            return mention[x]
        n = nodes.get(x) or {}
        if n.get("ref") and n.get("w") and n.get("word"):
            for i in n["w"]:
                r = mention.get(f"{n['ref']}#w{i}")
                if r:
                    return r
        if x in refers:
            return record_of(refers[x], seen + (x,))
        return None

    def clauses_under(x, seen):
        """Every clause a turn member covers: a clause and what is nested in it,
        a group's head and its members."""
        if x in seen:
            return
        seen.add(x)
        n = nodes.get(x) or {}
        if n.get("clause"):
            yield x
            for c in nested.get(x, []):
                yield from clauses_under(c, seen)
        if n.get("head"):
            yield from clauses_under(n["head"], seen)
        for t, d in out_of.get(x, []):
            if t in GROUP_EDGES:
                yield from clauses_under(d, seen)

    # spoken words per verse, per turn; and each verse's clauses
    turns = {nid for nid, n in nodes.items() if n.get("kind") == "turn"}
    spoken = collections.defaultdict(lambda: collections.defaultdict(set))   # ref -> turn -> {w}
    spoken_cl = collections.defaultdict(lambda: collections.defaultdict(set))
    speaker, generic_sender = {}, set()
    frame_cl = collections.defaultdict(lambda: collections.defaultdict(set))  # ref -> turn -> {clause}
    frame_w = collections.defaultdict(lambda: collections.defaultdict(set))
    party_w = collections.defaultdict(lambda: collections.defaultdict(set))
    for t in turns:
        fseen, frefs = set(), set()
        for ty, d in out_of.get(t, []):
            if ty == "frame":
                for c in clauses_under(d, fseen):
                    frame_cl[nodes[c]["ref"]][t].add(c)
                    frefs.add(nodes[c]["ref"])
        senders = [d for ty, d in out_of.get(t, []) if ty == "sender"]
        recs = {record_of(s) for s in senders} - {None}
        if len(recs) == 1:
            speaker[t] = recs.pop()
        elif senders and any("#generic:" in s for s in senders):
            generic_sender.add(t)
        seen = set()
        for ty, d in out_of.get(t, []):
            if ty != "part":
                continue
            for c in clauses_under(d, seen):
                cn = nodes[c]
                spoken[cn["ref"]][t] |= set(cn.get("w") or [])
                spoken_cl[cn["ref"]][t].add(c)
        # THE FRAME IS ONLY WHAT IS NOT SPOKEN: a quotation is often nested
        # in its verb of saying, so the frame clause "contains" the speech
        # (Job 2:3 put "Job" in God's frame and not in his words)
        for ref in frefs:
            frame_cl[ref][t] -= spoken_cl[ref][t]
            frame_w[ref][t] = set().union(set(), *[set(nodes[c].get("w") or []) for c in frame_cl[ref][t]]) - spoken[ref][t]
        # who the frame names: the speaker and the hearer, and nobody else
        # (Num 10:29's frame also says Hobab is Reuel's son; that is the narrator's)
        for ty, d in out_of.get(t, []):
            if ty in ("sender", "addressee") and nodes.get(d, {}).get("w"):
                party_w[nodes[d]["ref"]][t] |= set(nodes[d]["w"])
    # SPEECH WITHIN SPEECH: a turn whose frame is itself spoken in another
    # turn ("Yet you say, 'What does God know?'", Job 22:13) is words one
    # speaker puts in another's mouth. Neither voice alone is right; held out
    nested_turn = {t for ref in frame_cl for t, cs in frame_cl[ref].items()
                   if any(cs & spoken_cl[ref][u] for u in spoken_cl[ref] if u != t)}
    # and who reports it: the turn whose speech holds the inner turn's frame
    reporter = {}
    for ref in frame_cl:
        for t, cs in frame_cl[ref].items():
            outer = [u for u in spoken_cl[ref] if u != t and cs & spoken_cl[ref][u]]
            if t in nested_turn and len(outer) == 1:
                reporter[t] = outer[0]
    if "--nested" in sys.argv:
        print(f"{len(nested_turn)} turns spoken inside another's speech; "
              f"{sum(1 for t in nested_turn if speaker.get(t))} with a speaker on record, "
              f"{sum(1 for t in reporter if speaker.get(t) and speaker.get(reporter[t]))} with both on record")
        for t in sorted(nested_turn)[:12]:
            print("  ", t, speaker.get(t), "reported by", reporter.get(t), speaker.get(reporter.get(t)))
    clause_turn = collections.defaultdict(set)        # clause -> the turns that speak it
    for ref_ in spoken_cl:
        for t_, cs_ in spoken_cl[ref_].items():
            for c_ in cs_:
                clause_turn[c_].add(t_)
    verse_clauses = collections.defaultdict(set)
    for nid, n in nodes.items():
        if n.get("clause") and not n.get("nested_in"):
            verse_clauses[n["ref"]].add(nid)

    ents = {}
    for p in (ROOT / "ontology" / "entities").glob("*.jsonl"):
        for ln in open(p, encoding="utf-8"):
            if ln.strip():
                d = json.loads(ln)
                ents[d["id"]] = d.get("type")
    words_of = collections.defaultdict(lambda: collections.defaultdict(set))  # ref -> record -> {w}
    for occ, rec in mention.items():
        ref, _, loc = occ.partition("#")
        m = re.fullmatch(r"w(\d+)", loc)
        if m:
            words_of[ref][rec].add(int(m.group(1)))

    def verse_turn(ref, s, o, rtype):
        """The turn a claim lies inside in one verse, and how it was decided.

        The frame names the speaker and the hearer ("Then God said to Noah"),
        so a name found only there does not put the claim outside the speech:
        the first run kept every claim God makes about himself with the
        narrator. What the frame itself reports (SPEECH_ACTS) stays there."""
        ns, no = words_of[ref].get(s, set()), words_of[ref].get(o, set())
        named = ns | no
        hits = []
        for t, ws in spoken[ref].items():
            rest = named - frame_w[ref][t]
            spoken_top = {c for c in spoken_cl[ref][t] if not nodes[c].get("nested_in")}
            rest_of_verse = verse_clauses[ref] - frame_cl[ref][t]
            # a frame carrying its own narration ("his officials who were in
            # custody with him", Gen 40:7) is not a bare "he said"
            plain = len(frame_cl[ref][t]) <= 1
            whole = bool(rest_of_verse) and rest_of_verse <= spoken_top and plain
            if rest:
                # BOTH ENDS IN THE SPEECH, or the verse all speech: Hosea 1:6
                # names only the child in God's words ("Name her Lo-ruhamah");
                # "Gomer is her mother" is the narrator's "she conceived"
                inside = ws | party_w[ref][t]
                both = bool(ns) and bool(no) and ns <= inside and no <= inside
                if rest <= ws and (both or whole):
                    hits.append((t, "named inside"))
            elif whole:
                if not named:
                    hits.append((t, "whole verse"))
                elif rtype not in SPEECH_ACTS and named <= party_w[ref][t]:
                    hits.append((t, "named in the frame only, as speaker or hearer"))
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None, "two turns"
        return None, "named outside" if named else "not named"

    stats = collections.Counter()
    # statements inside speech whose speaker cannot be said, kept apart: the
    # claim export reads speaker-credits.jsonl and every row there has a speaker
    out, held_out, voices = [], [], []
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for ln in open(p, encoding="utf-8"):
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r["src"] not in ents or r["dst"] not in ents:
                continue
            refs = sorted({v for x in r.get("refs") or [] for v in verses(x)})
            if not refs:
                continue
            stats["claims"] += 1
            # A STATEMENT LIFTED FROM A CLAUSE (plan 2.19) knows its own clause,
            # better evidence than its verse: John 21:15 holds the narrator's
            # "he answered" and Peter's "You know I love You" together, and by
            # verse it could not be credited. Credited by the turn that speaks
            # that clause, under the same rules as the rest below
            # VOICE PER CLAUSE: one row may gather the same statement from
            # several verses, and the verses' voices can differ ("deny" in
            # Jesus' prediction, John 13:38, and in the narrator's Mark 14:72,
            # merged into one row on the first preview). So each clause's voice
            # is decided here, written to its own file, and the statement writer
            # merges only within one voice
            if r.get("type") == "states" and (r.get("clauses") or r.get("clause")):
                for cl in r.get("clauses") or [r["clause"]]:
                    ts = sorted(clause_turn.get(cl, ()))
                    v = {"clause": cl}
                    if len(ts) > 1:
                        v["held"] = "inside two speech turns"
                    elif ts:
                        t = ts[0]
                        reported = speaker.get(reporter.get(t)) if t in nested_turn else None
                        sp = speaker.get(t)
                        if t in nested_turn and not reported:
                            v["held"] = "speech within speech, reporter not on record"
                        elif not sp or sp not in ents or (reported and (reported == sp or reported not in ents)):
                            v["held"] = "in speech, speaker not on record"
                        else:
                            v.update({"speaker": sp, "turn": t, **({"reported_by": reported} if reported else {})})
                    stats["statement clause: " + ("held: " + v["held"] if "held" in v else
                                                  "credited" if "speaker" in v else "narrator")] += 1
                    voices.append(v)
                continue
            if r.get("claimed_by") or r.get("reading"):
                stats["already voiced"] += 1
                continue
            # ABOUT THE TEXT, NOT IN IT: "the speech of Job 1:21 speaks of God",
            # "this speech is part of Eliphaz's" describe the speech; they are
            # the graph's, never the speaker's (the first run credited 207
            # asserted_by and 476 speaks_of to the speakers)
            if r["type"] in ABOUT_THE_TEXT or {ents[r["src"]], ents[r["dst"]]} & TEXT_KINDS:
                stats["narrator: about the text"] += 1
                continue
            found = [verse_turn(v, r["src"], r["dst"], r["type"]) for v in refs]
            ts = [t for t, _ in found]
            if not any(ts):
                part = any(spoken[v] for v in refs)
                stats["narrator: " + found[0][1] + (" (a verse holds speech)" if part else "")] += 1
                continue
            if not all(ts):
                stats["narrator: some verses outside speech"] += 1
                continue
            # SPEECH WITHIN SPEECH (plan 8.1d; 2026-10-18: build speech
            # within speech): words one speaker gives another ("Yet you say,
            # 'What does God know?'", Job 22:13; "This is what the LORD says",
            # in a prophet's mouth) are the inner speaker's AS REPORTED by the
            # outer one, never either alone. Both must be on record, and one
            # reporter for the whole claim; otherwise it stays held
            reported = None
            if any(t in nested_turn for t in ts):
                reps = {speaker.get(reporter.get(t)) if t in nested_turn else None for t in ts}
                if len(reps) != 1 or None in reps or not all(t in nested_turn for t in ts):
                    stats["narrator: speech within speech, reporter not on record"] += 1
                    continue
                reported = reps.pop()
            who = {speaker.get(t) for t in ts}
            if None in who:
                stats["speech, speaker has no record" + (" (a generic)" if any(t in generic_sender for t in ts) else "")] += 1
                continue
            if len(who) > 1:
                stats["speech, two speakers"] += 1
                continue
            sp = who.pop()
            if sp not in ents:
                stats["speech, speaker not an entity"] += 1
                continue
            # THE SPEECH ACT ITSELF: "God warned Adam" (Gen 2:17), "Noah blessed
            # Shem" (9:26) describe the speaking, so they are the narrator's
            # even where every word of the verse is the speaker's
            if r["type"] in SPEECH_ACTS and r["src"] == sp:
                stats["narrator: the speech act itself"] += 1
                continue
            if reported and (reported == sp or reported not in ents):
                stats["narrator: speech within speech, reporter is the speaker or no entity"] += 1
                continue
            stats["credited" + (", as reported" if reported else "")] += 1
            out.append({"src": r["src"], "type": r["type"], "dst": r["dst"], "refs": refs, "speaker": sp,
                        **({"reported_by": reported} if reported else {}),
                        "turns": sorted(set(ts)), "how": sorted({h for _, h in found}),
                        "by": "sweep (automated analysis): the turn's sender"
                              + (", inside the reporting speaker's turn" if reported else "")})
    dest = ROOT / "out" / "sweep" / "speaker-credits.jsonl"
    dest.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    # each statement clause's voice (plan 2.19), read by
    # tools/meaning/write_statements.py; not by the claim export, which takes a
    # statement's voice from its row's `claimed_by`
    (ROOT / "out" / "sweep" / "statement-voices.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in voices), encoding="utf-8")
    st = dict(stats.most_common())
    st["turns with a speaker on record"] = len(speaker)
    st["turns"] = len(turns)
    (ROOT / "out" / "sweep" / "speaker-credits-stats.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
    print(json.dumps(st, indent=1))
    print("by speaker:", collections.Counter(x["speaker"] for x in out).most_common(15))


if __name__ == "__main__":
    main()
