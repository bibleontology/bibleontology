"""S4 — groups the text MARKS; S5 — references decided by agreement.

S4 builds only groups a word or a form marks (docs/BUILDER-DESIGN.md):
  - a SPEECH TURN: a clause whose verb is a verb of saying (the frame), and
    the clauses after it in the same MACULA sentence (what is said). A
    quotation longer than one sentence is extended later from the BSB's
    quotation marks, in its own layer (PRINCIPLES 44: structure may be
    borrowed).
  - a CONDITIONAL: an אִם clause and the clause it conditions (S3's `if`).
  - a COMMAND: an imperative (or jussive, cohortative) clause and the
    clauses a connective attaches to it.
  - a WRITING: a psalm whose heading names a writer (לְ + a name).
Nothing is grouped by similarity: parallel lines, acts of one agent and the
like are deferred to the pattern work (plan 1.27).

S5 decides only what agreement decides:
  - an implicit subject for every finite verb with no subject, from the
    verb's person, gender and number;
  - a first-person pronoun inside a speech turn is its speaker, a second
    person its addressee; in a psalm's own voice, first person is the
    psalmist;
  - a third-person pronoun refers to a person or place only when exactly
    ONE earlier candidate in the verse or the verse before agrees with it
    in gender and number.
Everything else stays unresolved, and is counted.
"""
import collections

from s2_s3 import bare

FINITE = {"qatal", "yiqtol", "wayyiqtol", "weqatal", "imperative",
          "jussive", "cohortative",
          # Greek: every mood with a person (the participle and infinitive
          # have none)
          "indicative", "subjunctive", "optative"}


def _edge(v, typ, src, dst, **kw):
    e = {"ref": v.ref, "lang": v.lang, "type": typ, "src": src, "dst": dst}
    e.update(kw)
    v.edges.append(e)
    return e


def _node(verses, nid):
    v = verses.get(nid.split("#")[0])
    return (v.nodes.get(nid) if v else None) or {}


def _roles(v, cid):
    ct = cid.replace("#cl", "#ct")
    r = {}
    for e in v.edges:
        if e["src"] == ct and e.get("clause_role"):
            r.setdefault(e["type"], []).append(e)
    return r


def s4(verses, lx, sentences):
    speech = set(lx.speech)
    for v in verses.values():
        clauses = sorted((n for n in v.nodes.values() if n.get("clause")),
                         key=lambda n: n["order"])
        k = 0
        for c in clauses:
            # ---- speech turn
            if bare(c.get("verb_lemma")) in speech and not c.get("nested_in"):
                # what is said: the clauses AFTER the frame in its sentence,
                # up to the next verb of saying or the narrative resuming
                sent = sentences.get(c["id"], [])
                # GREEK MAKES THE QUOTATION THE VERB'S OBJECT: "εἶπεν αὐτῷ,
                # ..." holds what is said as a clause filling λέγω's `o`,
                # nested in the frame, where the Hebrew sets it after the
                # frame in the sentence. Either way it is what is said.
                # MACULA's role label varies (Jhn 3:3 gives "Truly, truly
                # ..." the role `adv`), so: any clause nested straight in
                # the frame that no connective has typed as something else
                # (a purpose, a reason, a condition).
                rest = [e["dst"] for e in v.edges if e.get("clause_link")
                        and e["src"] == c["id"] and e.get("role")
                        and e["type"] in ("within", "that")
                        and "#cl" in (e.get("dst") or "")]
                for x in sent[sent.index(c["id"]) + 1:] if c["id"] in sent \
                        else []:
                    xn = _node(verses, x)
                    # a new verb of saying ends the turn only when it is the
                    # narrator's: "Truly, truly, I SAY to you" (Jhn 3:3) is
                    # the speaker still speaking
                    if (bare(xn.get("verb_lemma")) in speech and
                            xn.get("verb_person") not in ("first", "second")
                            ) or (
                            xn.get("verb_mood") in lx.narrative_moods and
                            xn.get("verb_person") == "third"):
                        break
                    rest.append(x)
                if rest:
                    gid = f"{v.ref}#turn{k}"
                    k += 1
                    v.nodes[gid] = {"id": gid, "ref": v.ref,
                                    "local": gid.split("#")[1],
                                    "lang": v.lang, "pair": True,
                                    "kind": "turn", "head": c["id"],
                                    "text": c["text"],
                                    "evidence": "a verb of saying and the "
                                                "rest of its sentence"}
                    _edge(v, "frame", gid, c["id"], order=1,
                          clause_link=True)
                    for i, x in enumerate(rest):
                        _edge(v, "part", gid, x, order=i + 2,
                              clause_link=True)
                    r = _roles(v, c["id"])
                    for s in r.get("s", [])[:1]:
                        _edge(v, "sender", gid, s["dst"], clause_link=True)
                    # the one spoken to: Greek puts it in the dative (the
                    # indirect object), Hebrew after אֶל or לְ
                    to = (r.get(lx.addressee_role) or [])[:1] if \
                        lx.addressee_role else []
                    to = to or [p for p in r.get("pp", [])
                                if bare(p.get("prep")) in lx.addressee_preps][:1]
                    for p in to:
                        _edge(v, "addressee", gid, p["dst"], clause_link=True)
            # ---- command: a clause of directive force (a Hebrew
            # imperative, jussive or cohortative; a Greek imperative or
            # hortatory subjunctive)
            if c.get("upper_force") == "directive" and not c.get("nested_in"):
                att = [e["dst"] for e in v.edges if e.get("clause_link")
                       and e["src"] == c["id"] and e.get("connective")]
                if att:
                    gid = f"{v.ref}#imp{c['order']}"
                    v.nodes[gid] = {"id": gid, "ref": v.ref,
                                    "local": gid.split("#")[1],
                                    "lang": v.lang, "pair": True,
                                    "kind": "imperative", "head": c["id"],
                                    "text": c["text"],
                                    "evidence": "a command, and what a "
                                                "connective attaches to it"}
                    _edge(v, "command", gid, c["id"], clause_link=True)
                    # ATTACHED, not "part": a clause a connective attaches to
                    # a command, its kind (basis, aim, effect) not decided by
                    # form. "part" is a speech turn's, and 3,459 of these
                    # stood outside it (plan 1.42, 2026-10-18)
                    for x in att:
                        _edge(v, "attached", gid, x, clause_link=True)
        # ---- conditional, from S3's forward `if`
        for e in [e for e in v.edges if e["type"] == "if"]:
            gid = f"{v.ref}#cond{e['src'].split('#cl')[1]}"
            v.nodes[gid] = {"id": gid, "ref": v.ref, "local": gid.split("#")[1],
                            "lang": v.lang, "pair": True,
                            "kind": "conditional", "head": e["dst"],
                            "text": (v.nodes.get(e["src"]) or {}).get("text"),
                            "evidence": "an אִם clause and the clause it "
                                        "conditions"}
            _edge(v, "condition", gid, e["src"], clause_link=True)
            _edge(v, "consequence", gid, e["dst"], clause_link=True)


def s4_writings(verses, lx):
    """A psalm whose heading names its writer is a Writing by that writer:
    the heading is its frame, every clause of the psalm a part."""
    heads = set(lx.heading_words)
    by_psalm = {}
    for ref, v in verses.items():
        if ref.startswith("Psa."):
            by_psalm.setdefault(ref.rsplit(".", 1)[0], []).append(v)
    for ch, vs in by_psalm.items():
        v1 = next((v for v in vs if v.ref.endswith(".1")), None)
        if not v1:
            continue
        cl0 = v1.nodes.get(f"{v1.ref}#cl0") or {}
        words = [n for n in v1.nodes.values() if n.get("word")
                 and set(n.get("w") or []) & set(cl0.get("w") or [])]
        names = [n for n in words if n.get("proper")]
        if not names or not any(bare(n.get("lemma")) in heads
                                for n in words) and len(cl0.get("w") or []) > 3:
            continue
        gid = f"{v1.ref}#writing"
        v1.nodes[gid] = {"id": gid, "ref": v1.ref, "local": "writing",
                         "lang": v1.lang, "pair": True, "kind": "writing",
                         "spans_verses": True, "text": cl0.get("text"),
                         "evidence": "a psalm whose heading names a writer"}
        _edge(v1, "frame", gid, cl0["id"], order=1, clause_link=True)
        _edge(v1, "sender", gid, names[0]["id"], clause_link=True,
              stated_by="the psalm's heading")
        voice = f"{v1.ref}#psalmist"
        v1.nodes[voice] = {"id": voice, "ref": v1.ref, "local": "psalmist",
                           "lang": v1.lang, "voice": True,
                           "text": "the psalmist"}
        n = 2
        for v in sorted(vs, key=lambda v: int(v.ref.rsplit(".", 1)[1])):
            for c in sorted((c for c in v.nodes.values() if c.get("clause")
                             and not c.get("nested_in")),
                            key=lambda c: c["order"]):
                if c["id"] != cl0["id"]:
                    _edge(v, "part", gid, c["id"], order=n, clause_link=True)
                    n += 1
            v.voice = voice


def s4_letters(verses, lx):
    """A LETTER is a Writing, as a psalm is. 2026-09-27: match the
    Hebrew as well as possible. Its opening names its writer in
    the nominative ("Paul, a servant of Christ Jesus"), as a psalm's heading
    does; the writer is the letter's voice, so its "I" is the writer as a
    psalm's is the psalmist. Its addressee is the first dative in the
    opening verses that stands in no prepositional phrase ("to all who are
    in Rome", Rom 1:7); left unset where there is none."""
    by_book = {}
    for ref, v in verses.items():
        b = ref.split(".")[0]
        if b in lx.letters:
            by_book.setdefault(b, []).append(v)
    for b, vs in by_book.items():
        vs.sort(key=lambda v: (int(v.ref.split(".")[1]),
                               int(v.ref.split(".")[2])))
        v1 = vs[0]
        cl0 = next((c for c in sorted(v1.nodes.values(),
                                      key=lambda c: c.get("order", 0))
                    if c.get("clause")), None)
        sender = next((n for n in sorted(v1.nodes.values(),
                                         key=lambda n: (n.get("w") or [0])[0])
                       if n.get("proper") and n.get("case") == "nominative"),
                      None)
        if not cl0 or not sender:
            continue
        in_pp = {e["dst"] for v in vs[:7] for e in v.edges
                 if e["type"] == "pp"}
        in_pp |= {e["dst"] for v in vs[:7] for e in v.edges
                  if e["type"] == "qualifier" and e["src"] in in_pp}
        addressee = next((n for v in vs[:7] for n in sorted(
            v.nodes.values(), key=lambda n: (n.get("w") or [0])[0])
            if n.get("case") == "dative" and n.get("class") in ("noun", "adj",
                                                                 "verb")
            and n["id"] not in in_pp), None)
        gid = f"{v1.ref}#writing"
        v1.nodes[gid] = {"id": gid, "ref": v1.ref, "local": "writing",
                         "lang": v1.lang, "pair": True, "kind": "writing",
                         "medium": "letter", "spans_verses": True,
                         "text": cl0.get("text"),
                         "evidence": "a letter whose opening names its writer"}
        _edge(v1, "frame", gid, cl0["id"], order=1, clause_link=True)
        _edge(v1, "sender", gid, sender["id"], clause_link=True,
              stated_by="the letter's opening")
        if addressee:
            _edge(v1, "addressee", gid, addressee["id"], clause_link=True,
                  stated_by="the letter's opening")
        n = 2
        for v in vs:
            for c in sorted((c for c in v.nodes.values() if c.get("clause")
                             and not c.get("nested_in")),
                            key=lambda c: c["order"]):
                if c["id"] != cl0["id"]:
                    _edge(v, "part", gid, c["id"], order=n, clause_link=True)
                    n += 1
            v.voice = sender["id"]
            v.addressee = addressee["id"] if addressee else None


def s5(verses, reflexive_marked=()):
    """Implicit subjects, and pronouns resolved only by agreement.
    `reflexive_marked`: the languages with a reflexive pronoun of their own
    (tables/<lang>/lexicon.json "reflexive_marked")."""
    refs = sorted(verses, key=lambda r: (r.split(".")[0],
                                         int(r.split(".")[1]),
                                         int(r.split(".")[2])))
    prev = None
    subj_all = {}                    # content -> its subject, every verse
    _name_agreement(verses)
    for ref in refs:
        v = verses[ref]
        turn_of = {}
        for e in v.edges:
            if e["type"] in ("frame", "part") and "#turn" in e["src"]:
                turn_of[e["dst"]] = e["src"]
        spk = {e["src"]: e["dst"] for e in v.edges if e["type"] == "sender"}
        adr = {e["src"]: e["dst"] for e in v.edges
               if e["type"] == "addressee"}
        voice = getattr(v, "voice", None)
        reader = getattr(v, "addressee", None)
        # a clause whose SUBJECT IS A CLAUSE ("the one who boasts, let him
        # boast", 1Co 1:31) has a subject: 808 were given an invented "he"
        clause_subject = {e["src"] for e in v.edges if e.get("clause_link")
                          and e.get("role") == "s"}
        for c in sorted((c for c in v.nodes.values() if c.get("clause")),
                        key=lambda c: c["order"]):
            r = _roles(v, c["id"])
            if c.get("verb_mood") in FINITE and "s" not in r and \
                    c["id"] not in clause_subject:
                pid = f"{c['id']}s"
                v.nodes[pid] = {"id": pid, "ref": ref,
                                "local": pid.split("#")[1], "lang": v.lang,
                                "implicit": True, "class": "pron",
                                "person": c.get("verb_person"),
                                "gender": c.get("verb_gender"),
                                "number": c.get("verb_number"),
                                "text": _pro(c)}
                _edge(v, "s", c["id"].replace("#cl", "#ct"), pid,
                      clause_role=True,
                      implicit="stated by the verb's person, gender and "
                               "number")
        cands = _candidates(prev) + _candidates(v)
        # implicit subjects first, so a pronoun can know who its clause's
        # subject is
        resolved = {}
        subj_of = {e["src"]: e["dst"] for e in v.edges if e["type"] == "s"}
        # A TURN WHOSE VERB STATES NO SUBJECT ("εἶπεν αὐτῷ", וַיֹּאמֶר):
        # its speaker is the verb's implicit subject, minted just above
        for e in [e for e in v.edges if e["type"] == "frame"
                  and "#turn" in e["src"]]:
            s = subj_of.get(e["dst"].replace("#cl", "#ct"))
            if e["src"] not in spk and s:
                spk[e["src"]] = s
                _edge(v, "sender", e["src"], s, clause_link=True,
                      stated_by="the verb's person, gender and number")
        role_ct = {e["dst"]: e["src"] for e in v.edges
                   if e.get("clause_role") and e["type"] != "s"}
        subj_all.update(subj_of)
        into = collections.defaultdict(list)     # clause -> links into it
        for e in v.edges:
            if e.get("clause_link") and e["type"] in SHARED | CARRIED and \
                    "#cl" in (e.get("src") or "") and \
                    "#cl" in (e.get("dst") or ""):
                into[e["dst"]].append(e)
        for n in sorted(v.nodes.values(), key=lambda n: not n.get("implicit")):
            if n.get("class") != "pron" or not n.get("person"):
                continue
            tgt, why, kw = None, None, {}
            turn = _turn_holding(v, n, turn_of)
            if n["person"] == "first" and turn and spk.get(turn):
                tgt, why = spk[turn], "the speaker of the turn it is in"
            elif n["person"] == "second" and turn and adr.get(turn):
                tgt, why = adr[turn], "the addressee of the turn it is in"
            elif n["person"] == "first" and not turn and voice:
                tgt, why = voice, ("the writer, the letter's own voice"
                                   if v.lang == "greek" else
                                   "the psalmist, the psalm's own voice")
            elif n["person"] == "second" and not turn and reader:
                tgt, why = reader, "the letter's addressee"
            elif n.get("implicit") and _carried(verses, n, into, subj_all):
                tgt, why, kw = _carried(verses, n, into, subj_all)
            elif n["person"] == "third":
                agree = [x for x in cands if _agrees(n, x)
                         and x["id"] != n["id"]]
                ids = {x["id"] for x in agree}
                # NOT ITS OWN CLAUSE'S SUBJECT, where the language has a
                # reflexive of its own: Greek says "to himself" with ἑαυτῷ,
                # so "εἶπεν αὐτῷ" (Jhn 3:3) is someone else. Hebrew uses the
                # plain pronoun reflexively (וַיַּעַשׂ לוֹ), so not there.
                if v.lang in reflexive_marked and n["id"] in role_ct:
                    s = subj_of.get(role_ct[n["id"]])
                    ids -= {s, resolved.get(s)}
                # "he" inside someone's speech is neither the speaker nor
                # the one spoken to: they would be "I" and "you" (Jhn 3:3,
                # "unless one is born again, HE cannot see")
                if turn:
                    for p in (spk.get(turn), adr.get(turn)):
                        ids -= {p, resolved.get(p)}
                # THE NAME'S GENDER FROM ITS VERBS VETOES, IT NEVER SELECTS.
                # Used to narrow the candidates it added 1,125 resolutions at
                # about 1 in 2 right (Job 1:18 "their" -> the Chaldeans);
                # used as a veto it removes 844 at 12 of 12 right ("she" ->
                # the LORD). A fix moves its own measure and no other
                # (PRINCIPLES 51).
                if len(ids) == 1:
                    only = next(iter(ids))
                    t = next((x for x in agree if x["id"] == only), {})
                    if t.get("gender_from") and n.get("gender") not in (
                            None, "common") and t.get("gender") and \
                            t["gender"] != n["gender"]:
                        only = None
                    if only:
                        tgt, why = only, "the only agreeing referent " \
                                         "in the leading text"
            if tgt:
                resolved[n["id"]] = tgt
                _edge(v, "refers_to", n["id"], tgt, inferred=why, **kw)
        prev = v


# THE SUBJECT CARRIES. 2026-09-27, on Jhn 3:16-17's unresolved
# pronouns, both approved. A verb that states no subject, in a clause
# joined to another:
#  - by and / but / or: the two share their subject ("everyone believing
#    ... should not perish BUT [he] should have eternal life"). Safe.
#  - as its result or purpose: the subject usually carries ("God so loved
#    ... that [he] gave"), but not always — Jhn 3:17 "that [he] might judge
#    the world" is God or the Son, and readers differ — so the link is
#    marked a DEFAULT READING, not a settled one.
# Either way only when the verb's person, number and gender agree with the
# clause it continues.
#
# Measured on a sample of the first run: shared 8 of 10 right, and BOTH
# wrong ones crossed a verse ("He said to this one", Luk 19:19, took "the
# second" servant; Lev 11:28 took the verse before's "he"). So the link
# must stay inside its verse, and not be Greek δέ, which marks a new
# development and often a new subject. Carried: 3 of 5 (Jhn 15:2 "that
# [it] may bear more fruit" took the vinedresser), hence the flag.
SHARED = {"and", "contrast", "but_rather", "or"}
CARRIED = {"result", "purpose"}
SWITCH = {"δε"}


def _carried(verses, n, into, subj_all):
    cid = n["id"][:-1]
    links = sorted(into.get(cid, []), key=lambda e: e["type"] not in SHARED)
    for e in links:
        if e["src"].split("#")[0] != cid.split("#")[0] or \
                bare(str(e.get("connective") or "")) in SWITCH:
            continue
        host = _node(verses, e["src"])
        s = subj_all.get(e["src"].replace("#cl", "#ct"))
        if not s or s == n["id"] or not _same_subject(n, host,
                                                      _node(verses, s)):
            continue
        if e["type"] in SHARED:
            return s, (f"shares the subject of the clause it is joined to "
                       f"('{e['type']}')"), {}
        return s, (f"carries the subject of the clause it is the "
                   f"{e['type']} of"), {"default_reading": True}
    return None


def _same_subject(n, host, sn):
    person = host.get("verb_person") or sn.get("person") or "third"
    number = host.get("verb_number") or sn.get("number")
    gender = host.get("verb_gender") or sn.get("gender")
    if n.get("person") and n["person"] != person:
        return False
    if n.get("number") and number and n["number"] != number:
        return False
    g = n.get("gender")
    return not g or not gender or "common" in (g, gender) or g == gender


def _pro(c):
    p, g, n = c.get("verb_person"), c.get("verb_gender"), c.get("verb_number")
    if p == "first":
        return "I" if n == "singular" else "we"
    if p == "second":
        return "you"
    if n == "plural":
        return "they"
    return "she" if g == "feminine" else "he"


def _candidates(v):
    if v is None:
        return []
    return [n for n in v.nodes.values() if n.get("proper")
            and n.get("type") == "proper"]


def _name_agreement(verses, least=3, share=0.8):
    """A HEBREW NAME'S GENDER AND NUMBER, FROM ITS OWN VERBS. MACULA gives
    no gender or number to a proper noun (2,043 of 2,043 checked), so S5's
    agreement test never ruled a name out: every "she" and "her" in Num 30:7
    resolved to the LORD (found 2026-09-28 through the mentions layer). The
    text itself says what a name is: a Hebrew verb marks its subject's
    gender and number ("David SAID", masculine singular). So across the
    corpus, where a name is the subject of at least `least` verbs that agree
    `share` of the time, the name takes that gender (and number), marked
    `gender_from: "its verbs"` so it is never mistaken for MACULA's."""
    obs = collections.defaultdict(lambda: (collections.Counter(),
                                           collections.Counter()))
    for v in verses.values():
        for e in v.edges:
            if e["type"] != "s" or not e.get("clause_role"):
                continue
            x = v.nodes.get(e["dst"]) or {}
            if not x.get("proper") or x.get("gender"):
                continue
            cl = v.nodes.get(e["src"].replace("#ct", "#cl")) or {}
            g, n = cl.get("verb_gender"), cl.get("verb_number")
            k = (v.lang, bare(x.get("lemma")))
            if g in ("masculine", "feminine"):
                obs[k][0][g] += 1
            if n in ("singular", "plural"):
                obs[k][1][n] += 1
    decided = {}
    for k, (gs, ns) in obs.items():
        d = {}
        for field, c in (("gender", gs), ("number", ns)):
            tot = sum(c.values())
            if tot >= least:
                top, cnt = c.most_common(1)[0]
                if cnt / tot >= share:
                    d[field] = top
        if d:
            decided[k] = d
    for v in verses.values():
        for x in v.nodes.values():
            if x.get("proper") and not x.get("gender"):
                d = decided.get((v.lang, bare(x.get("lemma"))))
                if d:
                    x.update(d)
                    x["gender_from"] = "its verbs"


def _agrees(p, x):
    """Agreement by what the SOURCE marks. A name's gender and number
    learned from its verbs (`gender_from`) are ignored here — they veto a
    resolution afterwards, but must not narrow the candidates."""
    inferred = bool(x.get("gender_from"))
    num = p.get("number")
    # exactly as before the inference: a name with no number of its own
    # counts as singular (skipping the check instead let plural "they"
    # match single names: 2,638 added on the first try)
    xn = None if inferred else x.get("number")
    if num and num != (xn or "singular"):
        return False
    g = p.get("gender")
    return not g or g == "common" or inferred or not x.get("gender") or \
        x.get("gender") == g


def _turn_holding(v, n, turn_of):
    """The speech turn a pronoun sits in: through the clause that holds its
    word (or, for an implicit subject, the clause it was minted for)."""
    if n.get("implicit"):
        # the clause it was minted for, or the nearest clause it is nested
        # in that is part of a turn (a ἵνα clause inside a quotation)
        cid = n["id"][:-1]
        while cid and cid not in turn_of:
            cid = (v.nodes.get(cid) or {}).get("nested_in")
        return turn_of.get(cid) if cid else None
    pos = set(n.get("w") or [])
    for c in v.nodes.values():
        if c.get("clause") and pos & set(c.get("w") or []):
            t = turn_of.get(c["id"])
            if t:
                return t
    return None
