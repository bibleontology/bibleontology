"""S2 — force and negation from form; S3 — links carried by a connective.

Both read tables/<lang>/lexicon.json; neither adds anything the text's form
does not mark (docs/BUILDER-DESIGN.md). Hebrew and Greek land on the SAME
kinds; what Greek marks beyond Hebrew is kept as an attribute (2026-09-27:
so that the core structures align).
"""
import json
import unicodedata
from pathlib import Path

from source import norm

TABLES = Path(__file__).resolve().parent / "tables"


def bare(s):
    """Kept for callers: the lexicon key of a word (Hebrew or Greek)."""
    return norm(s)


class Lexicon:
    def __init__(self, lang="hebrew"):
        d = json.load(open(TABLES / lang / "lexicon.json", encoding="utf-8"))
        self.lang = lang
        self.force = d["force_by_verb_type"]
        self.subjunctive_main = d.get("subjunctive_main")
        self.q_types = set(d["question_types"])
        self.q_lemmas = {norm(x) for x in d["question_lemmas"]}
        self.q_punct = d.get("question_punctuation")
        self.neg_types = set(d["negative_types"])
        self.neg_lemmas = {norm(x) for x in d.get("negative_lemmas", [])}
        self.subordinators = {norm(x) for x in d.get("subordinators", [])}
        self.conn = {norm(k) if " " not in k else " ".join(
            norm(p) for p in k.split()): v for k, v in d["connectives"].items()}
        self.within = {" ".join(norm(p) for p in k.split()): v
                       for k, v in d["within_by_prep"].items()}
        self.reverse = set(d.get("reverse", []))
        self.speech = {norm(x) for x in d["speech_verbs"]}
        self.perceive = {norm(x) for x in d["perceive_verbs"]}
        self.addressee_preps = {norm(x) for x in d["addressee_preps"]}
        self.addressee_role = d.get("addressee_role")
        self.narrative_moods = set(d.get("narrative_moods", ["wayyiqtol"]))
        self.heading_words = {norm(x) for x in d["heading_words"]}
        self.letters = set(d.get("letters", []))
        self.sequence_adverbs = {norm(x) for x in d.get("sequence_adverbs", [])}
        self.that_after = {norm(x) for x in d.get("that_after_perceive", [])}
        self.reflexive_marked = bool(d.get("reflexive_marked"))
        self.narrative_then = {norm(x) for x in d.get("narrative_then", [])}

    def negative(self, w):
        lemma = (w or {}).get("lemma") or ""
        # A ROUGH BREATHING IS ANOTHER WORD. norm() strips breathings, so
        # οὗ, "where", read as οὐ, "not": Col 3:1's "where Christ is seated"
        # was a negated clause and "says the opposite" of Mark 12:36 (27
        # clauses; the 2026-10-02 evaluation, M-D5). Every Greek negator has
        # a smooth breathing or none.
        if "̔" in unicodedata.normalize("NFD", lemma):
            return False
        return (w or {}).get("type") in self.neg_types or \
            norm(lemma) in self.neg_lemmas


# MACULA's `type` names a verb's form (qatal, imperative, indicative ...) and a
# noun's or adjective's kind; these are the kinds, never a verb form (plan 1.42)
NOT_A_FORM = {"common", "proper", "adjective", "relative", "demonstrative",
              "interjection", "gentilic", "personal", "cardinal", "ordinal"}


def s2(verses, words, lx):
    """Force of every clause, and a `neg` role for every negative in it."""
    # "NOT ONLY ... BUT ALSO" negates "only", not the verb, whichever route
    # the negative arrives by (Eph 1:20-21; John 12:9, "not because of Jesus
    # only", read as "the opposite" of Peter coming to Jesus on the water)
    only_at = {(w.get("ref"), w.get("pos")) for w in words.values()
               if norm(w.get("lemma")) in ("μονον", "μονος")}

    def not_only(ref, pos):
        return any((ref, (pos or 0) + k) in only_at for k in range(1, 5))

    for v in verses.values():
        opening = {}                 # clause -> the lemmas that open it
        for c in v.connectives:
            opening.setdefault(c["clause"], []).extend(
                norm((words.get(i) or {}).get("lemma")) for i in c["words"])
        for e in v.edges:
            if e.get("clause_link") and e.get("prep"):
                opening.setdefault(e["dst"], []).extend(
                    norm(p) for p in e["prep"])
        # a question particle standing before its clause makes it a question
        asks = {c["clause"] for c in v.connectives
                if any((words.get(i) or {}).get("type") in lx.q_types
                       for i in c["words"])}
        # a negative MACULA gives a clause as its adverb IS the clause's
        # negation: the role is retyped, read straight off the source
        for e in v.edges:
            n_ = v.nodes.get(e["dst"]) or {}
            if e["type"] == "adv" and lx.negative(n_) and not not_only(
                    n_.get("ref"), (n_.get("w") or [None])[0]):
                e["type"] = "neg"
        for cid, c in list(v.nodes.items()):
            if not c.get("clause"):
                continue
            ctid = cid.replace("#cl", "#ct")
            verb = next((v.nodes.get(e["dst"]) for e in v.edges
                         if e["src"] == ctid and e["type"] == "v"), None)
            # A VERB FORM ONLY FROM A VERB. MACULA puts a verbal adjective
            # ("feared", יָרֵא), a noun or a "behold" (הִנֵּה) in the verb role
            # at times; its word class ("adjective", "common", "interjection")
            # was being recorded as the clause's verb form, 103 Hebrew clauses
            # with a "force" no form has (plan 1.42, 2026-10-18). Such a clause
            # has no verb form, as a verbless one has none. But a word whose
            # recorded form IS a verb form keeps it: "hush!" (הַס) is an
            # interjection MACULA gives the form imperative, and is a command
            # (Amo 6:10, Jdg 3:19); a first cut that asked only "is it a verb"
            # made those two assertions.
            # So the test is the value itself: a word-class name is not a verb
            # form, whatever the word's class. A second case needed it: words
            # MACULA classes as verbs whose recorded "form" is a noun's
            # ("common": מָוֶת, "when Ahab died", 2Ki 3:5), 31 of them; the
            # force table cannot be the test, since it lists only the forms
            # that change a clause's force (not qatal, not indicative).
            vt = (verb or {}).get("type")
            if vt in NOT_A_FORM:
                vt = None
            force = lx.force.get(vt, lx.force["_default"])
            # a Greek subjunctive in a main clause, opened by no
            # subordinator: hortatory or prohibitive, like the Hebrew
            # cohortative and jussive
            if vt == "subjunctive" and lx.subjunctive_main and \
                    not c.get("nested_in") and not (
                        set(opening.get(cid, [])) & lx.subordinators):
                force = lx.subjunctive_main
            direct = _direct_words(v, c, words)
            if force != "directive" and (cid in asks or any(
                    w.get("type") in lx.q_types or
                    norm(w.get("lemma")) in lx.q_lemmas for w in direct)):
                force = "question"
            c["upper_force"] = force
            # the predicate's lemma and agreement are kept whatever its word
            # class: only the false FORM is withheld. Withholding the lemma too
            # made "Job feared God" (יְרֵא, a verbal adjective) a verbless
            # clause, and the verse matcher lost Job 1:1 / Acts 10:2 ("feared
            # God"), 190 verse pairs in all (plan 1.42, 2026-10-18)
            if (verb or {}).get("type"):
                if vt:
                    c["verb_mood"] = vt
                for k in ("stem", "person", "gender", "number", "tense",
                          "voice"):
                    if verb.get(k):
                        c[f"verb_{k}"] = verb[k]
                c["verb_lemma"] = verb.get("lemma")
            for e in v.edges:
                if e["type"] == "asserts" and e["src"] == cid:
                    e["force"], e["upper"] = vt or "-", force
            for w in direct:
                # "NOT ONLY ... BUT ALSO" negates "only", not the verb: Eph
                # 1:20-21's "seated Him at His right hand ... not only in this
                # age" was a negated clause, "the opposite" of Heb 1:3. The
                # "only" may stand a few words on: οὐ διὰ τὸν Ἰησοῦν μόνον,
                # "not because of Jesus only" (John 12:9)
                if not_only(w.get("ref"), w.get("pos")):
                    continue
                if lx.negative(w):
                    nid = f"{w['ref']}#w{w['pos']}"
                    v.nodes.setdefault(nid, {
                        "id": nid, "ref": w["ref"], "local": f"w{w['pos']}",
                        "lang": v.lang, "word": True, "src": [w["id"]],
                        "w": [w["pos"]], "text": w.get("english") or "not",
                        # the word's own facts, as S1's word nodes carry them:
                        # a "nor" inside a coordination (οὐδέ, μηδέ) is first
                        # made here, and was shown with no word (plan 2.15)
                        "hebrew": w.get("text"), "original": w.get("text"),
                        "class": w.get("class"),
                        "lemma": w.get("lemma"), "type": w.get("type"),
                        "strong": w.get("strongnumberx")})
                    if not any(e["type"] == "neg" and e["src"] == ctid
                               for e in v.edges):
                        v.edges.append({"ref": v.ref, "lang": v.lang,
                                        "type": "neg", "src": ctid,
                                        "dst": nid, "src_ids": [w["id"]],
                                        "clause_role": True})
        # THE GREEK QUESTION MARK (Nestle 1904 prints ";"): the sentence it
        # ends is a question. The editor's punctuation, used as structure
        # (PRINCIPLES 44) and recorded as the source.
        if lx.q_punct:
            for cid, c in list(v.nodes.items()):
                if not c.get("clause") or c.get("upper_force") == "question":
                    continue
                last = (c.get("src") or [None])[-1]
                if lx.q_punct in ((words.get(last) or {}).get("after") or ""):
                    top = c
                    while top.get("nested_in") and \
                            top["nested_in"] in v.nodes:
                        top = v.nodes[top["nested_in"]]
                    if top.get("upper_force") != "directive":
                        top["upper_force"] = "question"
                        top["question_from"] = "the edition's question mark"


def _direct_words(v, c, words):
    """The words of a clause that are not inside a clause nested in it."""
    nested = set()
    for e in v.edges:
        if e.get("clause_link") and e["src"] == c["id"] and e.get("dst"):
            d = v.nodes.get(e["dst"]) or {}
            nested |= set(d.get("src") or [])
    # and every clause nested in it at any depth (Dan 2:18: a clause set
    # inside the clause that fills a role)
    for n in v.nodes.values():
        p = n.get("nested_in")
        while p and p != c["id"]:
            p = (v.nodes.get(p) or {}).get("nested_in")
        if n.get("clause") and p == c["id"]:
            nested |= set(n.get("src") or [])
    return [words[i] for i in (c.get("src") or [])
            if i in words and i not in nested]


def _within_type(lx, preps):
    """The relation a clause nested under these words carries: the whole
    phrase first ('εἰς τό'), then each word in turn."""
    keys = [norm(p) for p in preps]
    whole = " ".join(keys)
    if whole in lx.within:
        return lx.within[whole]
    for i in range(len(keys)):
        for j in range(len(keys), i, -1):
            k = " ".join(keys[i:j])
            if k in lx.within:
                return lx.within[k]
    return None


def _key(ref):
    b, c, v = ref.split(".")
    return (b, int(c), int(v))


def s3(verses, lx):
    """Type the `within` links by the words that open them, and write a link
    for every connective S1 recorded before a clause.

    THE CHAIN ACROSS VERSES. A connective that opens a verse joins it to the
    verse before: Greek δέ ("Ἰδὼν δὲ τοὺς ὄχλους", Mat 5:1, which MACULA
    moves to the front) and the Hebrew waw and כִּי alike. With no clause
    before it in its own verse, its host is the last main clause of the
    previous verse in the same chapter."""
    last_main = {}
    for ref in sorted(verses, key=_key):
        mains = [n for n in verses[ref].nodes.values()
                 if n.get("clause") and not n.get("nested_in")]
        if mains:
            last_main[ref] = max(mains, key=lambda n: n["order"])["id"]
    refs = sorted(verses, key=_key)

    def node_of(nid):
        x = verses.get((nid or "").split("#")[0])
        return (x.nodes.get(nid) if x else None) or {}
    # THE HOST IS THE LAST MAIN CLAUSE BEFORE THE VERSE, not of the verse
    # before it. A verse that is all subordinate clause has none: John 3:15,
    # "that everyone who believes in Him may have eternal life", is nested in
    # 3:14's sentence, so 3:16's opening "For" (γάρ) found no host and was
    # linked to nothing, while 3:17's was (2026-10-18; 57 Greek γάρ verses
    # alone). Walk back within the chapter to the nearest verse with a main
    # clause: 3:14, the sentence 3:15 belongs to, which is what "For" explains.
    prev_of = {}
    carry = None
    for a, b in zip(refs, refs[1:]):
        if _key(a)[:2] != _key(b)[:2]:
            carry = None
            continue
        carry = last_main.get(a) or carry
        prev_of[b] = carry
    for v in verses.values():
        negated = {e["src"].replace("#ct", "#cl") for e in v.edges
                   if e["type"] == "neg"}
        for e in v.edges:
            if e["type"] == "within" and e.get("prep"):
                t = _within_type(lx, e["prep"])
                if norm(e["prep"][0]) in lx.that_after and norm(
                        (v.nodes.get(e["src"]) or {}).get("verb_lemma")) \
                        in lx.perceive:
                    t = "that"   # "he saw THAT ...", not "because"
                if t:
                    e["type"] = t
                    if t in lx.reverse:
                        # condition -> consequence, as the Hebrew writes it
                        e["src"], e["dst"] = e["dst"], e["src"]
        order = sorted((n for n in v.nodes.values() if n.get("clause")),
                       key=lambda n: n["order"])
        # THE NARRATIVE'S "THEN" AS A WORD: Aramaic אֱדַיִן / בֵּאדַיִן, Greek
        # τότε. Hebrew carries it inside the wayyiqtol; these say it, and
        # land on the same `then`, from the clause before.
        linked_in = {e["dst"] for e in v.edges if e.get("clause_link")}
        for e in list(v.edges):
            if e.get("clause_role") and e["type"] in ("adv", "pp") and \
                    norm((v.nodes.get(e["dst"]) or {}).get("lemma")) \
                    in lx.sequence_adverbs:
                cid = e["src"].replace("#ct", "#cl")
                cl = v.nodes.get(cid) or {}
                if cid in linked_in or cl.get("nested_in"):
                    continue
                host = _host(order, cl) or prev_of.get(v.ref)
                if host:
                    v.edges.append({
                        "ref": v.ref, "lang": v.lang, "type": "then",
                        "src": host, "dst": cid, "clause_link": True,
                        "connective": v.nodes[e["dst"]].get("lemma"),
                        "src_ids": v.nodes[e["dst"]].get("src") or []})
                    linked_in.add(cid)
        opened_by = {}
        for c in v.connectives:
            opened_by.setdefault(c["clause"], []).extend(
                norm(x) for x in c["lemmas"])
        for c in v.connectives:
            cid = c["clause"]
            cl = v.nodes.get(cid) or {}
            if not c["lemmas"]:
                continue             # only prepositions: not a connective
            lem = [norm(x) for x in c["lemmas"]]
            key = " ".join(lem)
            key = key if key in lx.conn else next(
                (x for x in reversed(lem) if x in lx.conn), lem[-1])
            rule = lx.conn.get(key)
            if not rule:
                continue
            # a clause inside a complex is related to the clause before it
            # there (S1 names it); otherwise the nearest one at its level
            host = c.get("host") or _host(order, cl) or prev_of.get(v.ref)
            verse_initial = not c.get("host") and cl.get("w") and \
                min(cl["w"]) <= len(c["words"])
            kw = {}
            if key == "ו" and cl.get("verb_mood") in ("wayyiqtol", "weqatal"):
                typ = rule["fused"]
            elif "verse_initial" in rule and verse_initial:
                cand = rule["verse_initial"]["undecided"]
                if host:
                    v.edges.append(_link(v, "undecided", host, cid, c,
                                         candidates=cand))
                continue
            else:
                typ = rule.get("mid") or rule.get("any")
                # after a verb of perceiving or saying, כִּי / ὅτι say WHAT
                # is known or said ("that"), not why
                if key in lx.that_after and host and norm(
                        (v.nodes.get(host) or {}).get("verb_lemma")) \
                        in lx.perceive:
                    typ = "that"
                # "not X BUT Y": ἀλλά after a negated clause is the Hebrew
                # כִּי אִם, `but_rather`
                if rule.get("after_negative") and host in negated:
                    typ = rule["after_negative"]
                # μέν ... δέ: a correlated contrast, which Greek marks and
                # Hebrew does not: the shared kind, with the mark kept
                if rule.get("after_men") and host and \
                        "μεν" in opened_by.get(host, []):
                    typ = rule["after_men"]
                    kw["correlative"] = "μέν … δέ"
                if rule.get("negative"):
                    kw["negated"] = True
                # GREEK NARRATIVE SEQUENCE. Hebrew fuses "and then" into the
                # wayyiqtol (20,177 `then` links); Greek narrates with καί /
                # δέ between past indicatives, and those were written as
                # plain `and` (121 Greek `then` in all) — so every sequence
                # pattern was Old Testament by construction (0 NT chains,
                # 2026-09-28). Between two past-tense indicatives it is the
                # same `then`, with the connective kept on the link.
                if typ == "and" and key in lx.narrative_then and host and \
                        _narrative(cl) and _narrative(node_of(host)):
                    typ = "then"
            if rule.get("forward"):
                nxt = _next(order, cl)
                if nxt:
                    # written from the clause the connective opens
                    v.edges.append(_link(v, typ, cid, nxt, c, forward=True,
                                         **kw))
            elif host:
                v.edges.append(_link(v, typ, host, cid, c, **kw))


def _narrative(n):
    """A Greek past-tense indicative: the narrative's own form."""
    return (n or {}).get("verb_mood") == "indicative" and \
        (n or {}).get("verb_tense") in ("aorist", "imperfect")


def _host(order, cl):
    """The nearest preceding clause at the same level: the latest earlier
    clause that is not nested inside another (a nested one has a
    `within`-family parent, recorded by S1 as `nested_in`)."""
    prev = [n for n in order if n["order"] < cl.get("order", 0)
            and not n.get("nested_in")]
    return prev[-1]["id"] if prev else None


def _next(order, cl):
    nxt = [n for n in order if n["order"] > cl.get("order", 0)
           and not n.get("nested_in")]
    return nxt[0]["id"] if nxt else None


def _link(v, typ, src, dst, c, **kw):
    e = {"ref": v.ref, "lang": v.lang, "type": typ, "src": src, "dst": dst,
         "clause_link": True, "connective": " ".join(c["lemmas"]),
         "src_ids": c["words"]}
    e.update(kw)
    return e
