"""The graph exported as claims (plan 8.1a; 2026-10-14, approving
P-2026-10-14-1: the site's own pages as addresses, one per speaker).

Every relation in ontology/relations/*.jsonl becomes a claim:Claim with its
subject, relation, object, verses, certainty and, where it has them, its
claimant and its reader -- always published, in the default graph. Its plain
triple is stated only inside ONE named graph, its voice:

    claim:narrator                        no claimed_by, no reading; explicit or
                                          implied, and not a grouping (plan 8.3f)
    https://bibleontology.org/voice/<id>  claimed_by <id> (Eliphaz, the serpent)
    https://bibleontology.org/voice/reader/<slug>   a credited reading
    https://bibleontology.org/voice/reader/editors  the graph's own groupings and
                                          conjectures, credited to no one else

A claim lying inside a speech turn the structure sweep resolved, and not
already voiced, goes to that turn's speaker too, with its finder as claim:readBy
"automated analysis: ..." (plan 8.1c; out/sweep/speaker-credits.jsonl, made by
tools/sweep/speaker_credit.py, which must run first).

So a tool that loads only the narrator's graph gets only what the text itself
states, and Eliphaz's "your own lips testify against you" (Job 15:6) is never
the book's verdict on Job. Two files:

    out/export/claims.trig        RDF 1.1 TriG: claim nodes + voice graphs
    out/export/claims-rdf12.trig  RDF 1.2 TriG (a Candidate Recommendation,
                                  2026): each claim also `rdf:reifies` its
                                  triple as an UNASSERTED triple term; only the
                                  narrator's triples are asserted

Left out on purpose: the relations' notes (AI-drafted wording, and a KJV
variant), the extraction batch (`source`: how the graph was built, not what
it says), story-echo word pairs.

    python tools/export_claims.py
"""
import collections
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import export_rights, gz_text  # noqa: E402
SITE = "https://bibleontology.org"
OUT = ROOT / "out" / "export"
CLAIM = SITE + "/ns/claim#"
BOR = SITE + "/ns/relation#"
NARRATOR = CLAIM + "narrator"
SWEEP_READING = "automated analysis: the speaker of the speech turn, from the structure sweep (Claude Haiku 5.5 and Sonnet 5.5)"
# the judging runs (ontology/provenance/runs.json): a claim read by one is
# prov:wasGeneratedBy it, and the run is a prov:Activity with its models
RUNS = json.loads((Path(__file__).resolve().parents[1] / "ontology" / "provenance" / "runs.json")
                  .read_text(encoding="utf-8"))
RUN_OF = {r["reading"]: rid for rid, r in RUNS["runs"].items()}
# WHAT THE NARRATOR ASSERTS (plan 8.3f, 2026-10-22). The simulated Reddit
# critics counted the export and found the narrator asserting about 3,500
# claims the text never states: anything not credited to someone else fell to
# the narrator. Only what the text states in so many words, or entails, is
# stated; and these relations are the graph's own groupings -- themes,
# patterns, story links, the text's divisions and what a passage speaks of --
# so they are credited to the editors' voice and described, never the
# narrator's (docs/review/reddit-sim-2026-10-22/assertion-tiers.md, counts;
# "groupings is fine", 2026-10-22)
STATED_CERTAINTY = ("explicit", "implied")
GROUPING = frozenset({"speaks_of", "aspect_of", "in_theme", "re_enacts", "takes_up", "same_steps_as",
                      "instance_of", "specializes", "spoken_in", "draws_on", "drawn_from", "possibly_same_as",
                      "occasion_of", "recounts", "part_of", "composed_of"})
EDITORS_READING = ("the editors of this graph: its groupings (themes, patterns, story links, the text's divisions) "
                   "and its conjectures, which the text does not state")
EDITORS = SITE + "/voice/reader/editors"


def iri(u):
    return f"<{u}>"


def lit(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def verses(ref):
    """'Gen 4:19-20' -> Gen.4.19, Gen.4.20; 'Gen 4:19' -> Gen.4.19; a range
    across chapters gives its first and last verse."""
    m = re.match(r"^(\S+) (\d+):(\d+)(?:[-–](?:(\d+):)?(\d+))?$", ref.strip())
    if not m:
        return []
    b, c, v, c2, v2 = m.groups()
    if not v2:
        return [f"{b}.{c}.{v}"]
    if c2 and c2 != c:
        return [f"{b}.{c}.{v}", f"{b}.{c2}.{v2}"]
    return [f"{b}.{c}.{n}" for n in range(int(v), int(v2) + 1)][:40]


def structure_iri(cl):
    """A part of the structure, addressed with the verse pages' book codes
    (G5, approved on the 1.2.0 inventory, 2026-10-20): MACULA's Jhn.3.16#cl0
    is published as /structure/John.3.16#cl0, beside /p/John.3.16, so a
    consumer joins a clause to its verse without a table."""
    from derive import BOOK
    site = {m: s for s, m in BOOK.items()}
    ref, _, part = cl.partition("#")
    b, rest = ref.split(".", 1)
    if b not in site:
        raise SystemExit(f"structure_iri: no site book code for {b!r} ({cl})")
    return f"{SITE}/structure/{site[b]}.{rest}#{part}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def reader_iri(rd):
    """A reader as an agent (PROV alignment, plan 8.1e, P-2026-10-18-18): the
    automated pass and every credited reader get one IRI each. A reading made
    by a recorded judging run is that run's judges, a software agent named by
    the run, not the reading's sentence turned into an address (the
    committee's ontology expert, second sitting: "/reader/lifted-from-the-
    clause-two-judges-every-end-checked" was a method published as an agent)."""
    if rd in RUN_OF:
        return f"{SITE}/reader/judges-{RUN_OF[rd]}"
    if rd == EDITORS_READING:
        return f"{SITE}/reader/editors"
    return f"{SITE}/reader/{'automated-analysis' if rd.startswith('automated analysis') else slug(rd)}"


def asserted(c):
    """WHETHER A CLAIM'S TRIPLE IS STATED in its voice's graph (1.2.0 step 5,
    2026-10-20). A statement not made outright -- a command, promise, wish or
    question, a negated clause, a verb whose form does not say it happened --
    is described by its claim and never stated, whatever the store holds. The
    store held none on 2026-10-19 and the test checked only that; lift 4
    (commands, credited to their speaker) brings them, so the rule belongs
    here, not in what happens to be in the store.

    A conjecture or a disputed claim is described and never stated, in any
    voice (plan 8.3f, 2026-10-22): the text neither says nor entails it."""
    if (c.get("c") or "explicit") not in STATED_CERTAINTY:
        return False
    st = c.get("st")
    if not st:
        return True
    # past or present by the verb's form, or by two judges' reading (plan
    # 2.19a: "past or present (by reading)")
    return ((st.get("modality") or "stated") in ("stated", "nonfinite") and not st.get("negated")
            and (st.get("time") or "past or present (by form)").startswith("past or present"))


def stated(c):
    """WHETHER A CLAIM'S PLAIN TRIPLE IS WRITTEN in its voice's graph:
    asserted(), and never for bor:states (plan 8.3f; Doug, 2026-10-22,
    "states: A"). The relation has no verb -- the verb is on the claim -- so
    different sentences fall onto one triple: God's words and the narrator's
    shared `god states david`, 98 speaker claims on triples the narrator
    asserted. A verb statement is described by its claim, verb and all, and
    stated nowhere. asserted() still decides its label's tense: whether the
    text says it outright is a different question from whether a verbless
    triple can carry it."""
    return asserted(c) and c.get("p") != BOR + "states"


def main():
    ents = set()
    for p in (ROOT / "ontology" / "entities").glob("*.jsonl"):
        for ln in open(p, encoding="utf-8"):
            if ln.strip():
                ents.add(json.loads(ln)["id"])
    rows = []
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for ln in open(p, encoding="utf-8"):
            if ln.strip():
                r_ = json.loads(ln)
                # a statement inside speech whose speaker cannot be said (plan
                # 2.19) is held: exported in no voice, so never the narrator's
                if not r_.get("held"):
                    rows.append(r_)
    # THE SWEEP'S SPEAKERS (plan 8.1c): a claim lying inside a speech turn the
    # structure sweep resolved is credited to that turn's speaker, and says
    # so: claimed by the speaker, read by the automated pass that found him
    # (tools/sweep/speaker_credit.py has the rules and what each one held out)
    credits = {}
    cpath = ROOT / "out" / "sweep" / "speaker-credits.jsonl"
    if not cpath.exists():
        # an error, not a fallback: without it every one of these claims
        # would quietly go back to being the narrator's, asserted
        raise SystemExit(f"{cpath.relative_to(ROOT)} missing -- python tools/sweep/speaker_credit.py first")
    for ln in open(cpath, encoding="utf-8"):
        c = json.loads(ln)
        credits[(c["src"], c["type"], c["dst"], tuple(c["refs"]))] = (c["speaker"], c.get("reported_by"))
    # HAND-BUILT RELATIONS A CLAUSE STATEMENT EVIDENCES (plan 2.17 step 3): the
    # hand row stays the curated form, and the clause is its evidence; a hand
    # type is never put under a verb family
    evidence = collections.defaultdict(list)
    evp = ROOT / "ontology" / "relations" / "statement-evidence.json"
    if evp.exists():
        for x in json.loads(evp.read_text(encoding="utf-8"))["evidence"]:
            evidence[(x["src"], x["type"], x["dst"])].append((set(verses(x["ref"])), x["clause"]))
    # A RETIRED RECORD IS ITS REPLACEMENT HERE (the code review, 2026-10-22,
    # B1; Doug approved): ontology/aliases.jsonl records each "one thing
    # recorded twice" decision, and the entities export says so
    # (dcterms:isReplacedBy), but 57 claims still named the old id -- Bashemath
    # had two fathers, Elon and Elon the Hittite. Resolved here, chains and
    # all; a claim that then says exactly what another says is the same claim
    alias = {}
    ap = ROOT / "ontology" / "aliases.jsonl"
    if ap.exists():
        alias = {a["id"]: a["alias_of"] for a in map(json.loads, open(ap, encoding="utf-8")) if a.get("alias_of")}

    def canon(x):
        hops = 0
        while x in alias and hops < 10:
            x, hops = alias[x], hops + 1
        return x

    claims, voices, seen, verbs = [], {}, set(), {}
    for r in rows:
        if alias:
            r = {**r, "src": canon(r["src"]), "dst": canon(r["dst"]),
                 **({"claimed_by": canon(r["claimed_by"])} if r.get("claimed_by") else {})}
        if r["src"] not in ents or r["dst"] not in ents:
            continue
        refs = sorted({v for x in r.get("refs") or [] for v in verses(x)})
        if not refs:
            continue
        cb, rd = r.get("claimed_by"), r.get("reading")
        # a grouping is the editors', whoever is speaking where it sits
        found = (None if cb or rd or r["type"] in GROUPING
                 else credits.get((r["src"], r["type"], r["dst"], tuple(refs))))
        reporter = None
        if found:
            (cb, reporter), rd = found, SWEEP_READING
            reporter = reporter if reporter in ents else None
        # the claim's identity is what it says and where (a claim is never
        # deduplicated across citations): content, not file position, so a
        # rebuild keeps the same address
        key = "|".join([r["src"], r["type"], r["dst"], cb or "", rd or "", ",".join(refs)]
                       + ([f"reported by {reporter}"] if reporter else []))
        cid = hashlib.sha1(key.encode()).hexdigest()[:16]
        if cid in seen and r["type"] == "states" and r.get("verb_key") and verbs.get(cid) != r.get("verb_key"):
            # TWO VERBS, ONE KEY (the correctness review, 2026-10-22): the key
            # has no verb, so Isa 54:7's "gathered" fell as a duplicate of its
            # "abandoned". Only the colliding one takes its verb into the key,
            # so no other claim's address moves
            key += f"|verb {r['verb_key']}"
            cid = hashlib.sha1(key.encode()).hexdigest()[:16]
        if cid in seen:
            continue
        seen.add(cid)
        verbs[cid] = r.get("verb_key")
        # A VERB STATEMENT is the TEXT's statement, found by a reader (plan
        # 2.17): it sits in the voice of whoever says it in the text, the
        # speaker or the narrator, and its reader is recorded as readBy, as the
        # sweep-credited claims are. Only a reader's own interpretation sits in
        # the reader's voice. (First export of the statements, 2026-10-19: God
        # "set" the world in Hannah's words, 1 Sam 2:8, came out in the
        # lifting pass's voice.)
        if rd and not found and r["type"] != "states":
            voice = f"{SITE}/voice/reader/{slug(rd)}"
            voices.setdefault(voice, ("reader", rd))
        elif reporter and cb in ents:
            # SPEECH WITHIN SPEECH (plan 8.1d): the inner speaker's words as
            # the outer one reports them. Their triple is stated in a voice of
            # its own, neither speaker's: God's words in Jeremiah's report are
            # not simply God's voice, nor Jeremiah's
            voice = f"{SITE}/voice/{reporter}/reports/{cb}"
            voices.setdefault(voice, ("reported", (cb, reporter)))
        elif cb and cb in ents:
            voice = f"{SITE}/voice/{cb}"
            voices.setdefault(voice, ("record", cb))
        elif r["type"] in GROUPING or (r.get("certainty") or "explicit") not in STATED_CERTAINTY:
            # NOT THE NARRATOR'S (plan 8.3f): a grouping or a conjecture is the
            # editors', credited as a reading. The claim's address was made
            # above from the row as written, so it does not move
            voice, rd = EDITORS, EDITORS_READING
            voices.setdefault(voice, ("reader", rd))
        else:
            voice = NARRATOR
        claims.append({"id": f"{SITE}/claim/{cid}", "s": f"{SITE}/e/{r['src']}", "p": BOR + r["type"],
                       "o": f"{SITE}/e/{r['dst']}", "refs": refs, "c": r.get("certainty") or "explicit",
                       "cb": cb if cb in ents else None, "rd": rd, "voice": voice, "swept": bool(found),
                       # A VERB STATEMENT (plan 2.17 step 3): its verb, grammar,
                       # modality and family travel with the claim
                       **({"ev": sorted({cl for vs, cl in evidence[(r["src"], r["type"], r["dst"])] if vs & set(refs)})}
                          if (r["src"], r["type"], r["dst"]) in evidence else {}),
                       **({"st": {k: r.get(k) for k in ("label", "label_plain", "verb_key", "verb_strong", "stem", "mood", "person",
                                                         "grammatical_voice", "negated", "modality",
                                                         "modality_from", "family", "family_from", "clauses",
                                                         "time")}}
                          if r["type"] == "states" else {})})
        if reporter and cb in ents:
            # ...and the reporter's own claim: that the inner speaker says it.
            # In RDF 1.2 it reifies a NESTED triple term, <<( god says <<( s p
            # o )>> )>>: one speaker's claim about another's, described and
            # never stated, the case triple terms nest for
            inner = claims[-1]
            oid = hashlib.sha1(("says|" + cid).encode()).hexdigest()[:16]
            seen.add(oid)
            voices.setdefault(f"{SITE}/voice/{reporter}", ("record", reporter))
            claims.append({"id": f"{SITE}/claim/{oid}", "s": f"{SITE}/e/{cb}", "p": CLAIM + "says",
                           "o": inner["id"], "refs": refs, "c": inner["c"], "cb": reporter, "rd": rd,
                           "voice": f"{SITE}/voice/{reporter}", "swept": True, "inner": inner})
    OUT.mkdir(parents=True, exist_ok=True)
    prefixes = ("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
                "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                "@prefix prov: <http://www.w3.org/ns/prov#> .\n"
                "@prefix claim: <https://bibleontology.org/ns/claim#> .\n"
                "@prefix bor: <https://bibleontology.org/ns/relation#> .\n"
                "@prefix e: <https://bibleontology.org/e/> .\n"
                "@prefix p: <https://bibleontology.org/p/> .\n"
                "@prefix voice: <https://bibleontology.org/voice/> .\n"
                "@prefix c: <https://bibleontology.org/claim/> .\n\n")

    def short(u):
        for pre, ns in (("e:", f"{SITE}/e/"), ("p:", f"{SITE}/p/"), ("c:", f"{SITE}/claim/"),
                        ("voice:", f"{SITE}/voice/"), ("bor:", BOR), ("claim:", CLAIM)):
            if u.startswith(ns) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*[A-Za-z0-9_]|[A-Za-z0-9_]", u[len(ns):]):
                return pre + u[len(ns):]
        return iri(u)

    def claim_block(c, rdf12):
        lines = [f"{short(c['id'])} a claim:Claim ;"]
        # ONE RANGE FOR claim:says IN BOTH FILES (plan 8.1e item 4; the
        # committee, 2026-10-19): the reporter's claim reifies "the reporter
        # says the inner CLAIM", the inner claim being itself the reifier of
        # its own triple. Before, the 1.2 file nested the inner triple term
        # instead, so one term had two ranges; the nested form stays a blog
        # demonstration, not the data
        if rdf12:
            lines.append(f"    rdf:reifies <<( {short(c['s'])} {short(c['p'])} {short(c['o'])} )>> ;")
        lines += [f"    claim:subject {short(c['s'])} ; claim:relation {short(c['p'])} ; claim:object {short(c['o'])} ;",
                  "    claim:verse " + ", ".join(short(f"{SITE}/p/{v}") for v in c["refs"]) + " ;",
                  f"    claim:certainty claim:{c['c']} ;"]
        # PROV, STATED AS WELL AS IMPLIED: claimedBy and reader sit under
        # prov:wasAttributedTo, but a PROV query without a reasoner sees only
        # what is written, so the attribution is written out too (the 13
        # October evaluation: materialise, do not leave it to the consumer)
        attributed = []
        if c["cb"]:
            lines.append(f"    claim:claimedBy {short(SITE + '/e/' + c['cb'])} ;")
            attributed.append(short(SITE + "/e/" + c["cb"]))
        if c["rd"]:
            lines.append(f"    claim:readBy {lit(c['rd'])} ;")
            lines.append(f"    claim:reader {short(reader_iri(c['rd']))} ;")
            attributed.append(short(reader_iri(c["rd"])))
        if attributed:
            lines.append(f"    prov:wasAttributedTo {', '.join(attributed)} ;")
        # THE RUN THAT PRODUCED IT (plan 8.1e item 4, one provenance idiom):
        # the reader stays claim:reader; the judging run is prov:wasGeneratedBy
        if c["rd"] in RUN_OF:
            lines.append(f"    prov:wasGeneratedBy <{SITE}/run/{RUN_OF[c['rd']]}> ;")
        for cl in c.get("ev") or []:
            lines.append(f"    claim:evidencedBy <{structure_iri(cl)}> ;")
        st = c.get("st")
        if st:
            # the verb's own words and grammar, its modality and its family
            # the past tense only for what is stated; a described statement
            # takes the verb's plain form (G6)
            label = st.get("label") if asserted(c) else (st.get("label_plain") or st.get("label"))
            if label:
                lines.append(f"    claim:verbLabel {lit(label)} ;")
            if st.get("verb_key"):
                lines.append(f"    claim:verb <{SITE}/word/{st['verb_key']}> ;")
            for k, prop in (("stem", "stem"), ("mood", "mood"), ("person", "person"),
                            ("grammatical_voice", "grammaticalVoice")):
                if st.get(k):
                    lines.append(f"    claim:{prop} {lit(st[k])} ;")
            lines.append(f"    claim:negated {'true' if st.get('negated') else 'false'} ;")
            mod = re.sub(r"[^a-z]+", "_", (st.get("modality") or "stated")).strip("_")
            lines.append(f"    claim:modality claim:modality_{mod} ; claim:modalityFrom {lit(st.get('modality_from') or 'form')} ;")
            # its time read by a judging run (plan 2.19a): that run influenced
            # it (the committee's practitioner, second sitting)
            if st.get("modality_from") == "reading" and "statement-time-2026-10-20" in RUNS["runs"]:
                lines.append(f"    prov:wasInfluencedBy <{SITE}/run/statement-time-2026-10-20> ;")
            if st.get("family"):
                lines.append(f"    claim:family claim:family_{st['family'].replace('.', '_')} ; "
                             f"claim:familyFrom {lit(st.get('family_from') or '')} ;")
            for cl in (st.get("clauses") or [])[:8]:
                lines.append(f"    claim:clause <{structure_iri(cl)}> ;")
        lines.append(f"    claim:voice {short(c['voice'])} .")
        return "\n".join(lines)

    for name, rdf12 in (("claims.trig", False), ("claims-rdf12.trig", True)):
        head = ("# Bible Ontology -- the graph as claims" + (" (RDF 1.2)" if rdf12 else " (RDF 1.1)") + ".\n"
                # the named-graph sentence is true of the 1.1 file only (found
                # 2026-10-20 while drawing the standards view): the RDF 1.2 file
                # has had no named graphs since the RDF4J measurement of 10-14
                + ("# Every relation is a claim with its verses, certainty and voice; its plain triple is stated\n"
                   "# only in the named graph of that voice (claim:narrator = what the text itself states).\n"
                   if not rdf12 else
                   "# Every relation is a claim with its verses, certainty and voice (claim:narrator = what the\n"
                   "# text itself states).\n")
                + "# The narrator's claims are what the text states or entails; conjectures, disputed claims\n"
                  "# and the graph's own groupings (themes, patterns, story links, the text's divisions) are\n"
                  "# the editors' (voice:reader/editors), described and never asserted.\n"
                + ("# RDF 1.2 (its Concepts a W3C Candidate Recommendation since April 2026; the TriG 1.2 syntax\n"
                   "# used here still a Working Draft): rdf:reifies names each claim's triple\n"
                   "# as an unasserted triple term. Only the narrator's triples are asserted (default graph);\n"
                   "# a speaker's or reader's claim is described, never stated, whatever the store.\n"
                   if rdf12 else "") +
                "# Vocabulary: https://bibleontology.org/ns/claim  Relations: https://bibleontology.org/ns/relation\n"
                # the terms and sources, one switch for every export
                # (tools/ns_common.py, export_rights; plan 8.3a)
                + "\n".join(export_rights(wordnet=True)) + "\n\n")
        parts = [head, prefixes]
        for rid, run in sorted(RUNS["runs"].items()):
            parts.append(f"<{SITE}/run/{rid}> a prov:Activity ; rdfs:label {lit(run['label'])} ;\n"
                         f"    prov:endedAtTime \"{run['ended']}\"^^<http://www.w3.org/2001/XMLSchema#date> ;\n"
                         f"    prov:wasAssociatedWith " + ", ".join(f"<{SITE}/agent/{m}>" for m in run["models"]) + " .\n")
        for aid, ag in sorted(RUNS["agents"].items()):
            parts.append(f"<{SITE}/agent/{aid}> a prov:SoftwareAgent ; rdfs:label {lit(ag['label'])} .\n")
        for v, (kind, who) in sorted(voices.items()):
            if kind == "reported":
                parts.append(f"{short(v)} a claim:Voice ; claim:voiceOf {short(SITE + '/e/' + who[0])} ; "
                             f"claim:reportedBy {short(SITE + '/e/' + who[1])} .\n")
                continue
            # a reader's voice is attributed to the reader as an agent, not to
            # a name: claim:voiceOf is an object property (a literal here
            # until 2026-10-18)
            parts.append(f"{short(v)} a claim:Voice ; claim:voiceOf "
                         + (short(reader_iri(who)) if kind == "reader" else short(SITE + "/e/" + who)) + " .\n")
        parts.append("claim:narrator a claim:Voice .\n")
        # every reader an agent, with its name (PROV alignment)
        for rd in sorted({c["rd"] for c in claims if c["rd"]}):
            # a judging run's reader is software; the run names its models
            soft = rd.startswith("automated analysis") or rd in RUN_OF
            agent = "prov:SoftwareAgent" if soft else "prov:Agent"
            parts.append(f"{short(reader_iri(rd))} a {agent} ; rdfs:label {lit(rd)} .\n")
        parts.append("\n")
        parts += [claim_block(c, rdf12) + "\n" for c in claims]
        by_voice = {}
        for c in claims:
            if stated(c):
                by_voice.setdefault(c["voice"], []).append(c)
        if rdf12:
            # ONLY THE NARRATOR IS ASSERTED (measured 2026-10-14): with the
            # speakers' triples in named graphs, RDF4J 6.1 -- whose default
            # graph is the union of all graphs -- answered a plain "what is Job
            # described as?" with 39 rows, Eliphaz's verdict among them; Jena
            # 6.2 answered 0. Named graphs protect a claim only as far as the
            # store's idea of the default graph does. So here a speaker's or a
            # reader's claim exists ONLY as the unasserted triple term its claim
            # rdf:reifies -- described, never stated, in any store -- and the
            # narrator's statements are the asserted triples, in the default graph
            # each triple once (the committee's practitioner, W8: 198 of 19,151
            # were written twice or more, one per claim asserting them --
            # harmless to a store, RDF being a set, but careless to a reader)
            parts.append("\n# What the text itself states (the narrator), asserted:\n")
            parts += list(dict.fromkeys(f"{short(c['s'])} {short(c['p'])} {short(c['o'])} .\n"
                                        for c in by_voice.get(NARRATOR, [])))
        else:
            for v in sorted(by_voice, key=lambda x: (x != NARRATOR, x)):
                parts.append(f"\n{short(v)} {{\n")
                parts += list(dict.fromkeys(f"    {short(c['s'])} {short(c['p'])} {short(c['o'])} .\n"
                                            for c in by_voice[v]))
                parts.append("}\n")
        body = "".join(parts)
        (OUT / name).write_text(body, encoding="utf-8", newline="\n")
        with gz_text(OUT / (name + ".gz")) as f:
            f.write(body)
    n_nar = sum(c["voice"] == NARRATOR for c in claims)
    print(f"{len(claims):,} claims ({len(rows):,} relation rows); narrator {n_nar:,}, "
          f"speakers' {sum(c['cb'] is not None for c in claims):,} in "
          f"{sum(k == 'record' for k, _ in voices.values()):,} voices (of them, found by the sweep "
          f"{sum(c['swept'] for c in claims)}), readings {sum(bool(c['rd']) and not c['swept'] for c in claims)}; "
          f"speech within speech {sum(bool(c.get('inner')) for c in claims)}")


if __name__ == "__main__":
    main()
