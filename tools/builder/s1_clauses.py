"""S1 — clauses and roles, read off MACULA's trees.

A <wg class="cl"> is a Clause, with a Content it asserts. Each child of a
clause that carries a `role` fills that role of the content. A phrase is
read by tables/<lang>/heads.json: its head fills the role, and its other
children hang off the head under the relation the table names. A
coordination is a Composite whose members are its conjuncts. One word node
per OCCURRENCE; every node and edge carries the MACULA ids it stands for
(`src`, plan P-31).

A CLAUSE COMPLEX is a group that holds only connectives and clauses and
fills no role. The Hebrew marks it class="cl" (cjpCLx, ClCl2 ...); the Greek
leaves it unlabelled (Conj-CL, sub-CL, CLaCL, ClCl ...). It is recognised
by what it holds, not by its label, so both languages read alike. At the
top of a sentence its clauses stand side by side and their connectives are
recorded for S3; inside a clause, each of its clauses is linked to that
clause, carrying its connective, for S3 to type.

S1 decides nothing about force, links or references.
"""
import json
import re
from pathlib import Path

TABLES = Path(__file__).resolve().parent / "tables"
FUNCTION = ("cj", "rel", "prep", "ptcl", "art")
OPENERS = ("cj", "rel", "prep", "ptcl")


class Tables:
    def __init__(self, lang="hebrew"):
        h = json.load(open(TABLES / lang / "heads.json", encoding="utf-8"))
        self.coord = set(h["coord"])
        self.first = h["head_first"]
        self.last = h["head_last"]
        self.prep = set(h["prep"])
        self.wrap = set(h["wrap"])


class Verse:
    """What S1 builds for one verse: nodes, edges, connective candidates."""

    def __init__(self, ref, lang):
        self.ref, self.lang = ref, lang
        self.nodes, self.edges, self.connectives = {}, [], []
        self.n_clause = 0


class S1:
    def __init__(self, words, lang="hebrew", tables=None):
        self.words, self.lang = words, lang
        self.t = tables or Tables(lang)
        self.verses = {}
        self.stack = []              # the clauses being read, outermost first
        self.sentence = []           # top-level clauses of this sentence
        self.sentences = {}          # clause id -> its sentence's clauses
        self._last = None            # the last clause a complex read
        self._opened = set()         # clauses whose opening connective is known
        self._cjp_ids = set()        # words read as part of a connective phrase

    # ------------------------------------------------------------ helpers
    def verse(self, ref):
        if ref not in self.verses:
            self.verses[ref] = Verse(ref, self.lang)
        return self.verses[ref]

    def rec(self, w):
        return self.words.get(w.get(XID_)) if w.tag == "w" else None

    def first_ref(self, e):
        for w in e.iter("w"):
            r = self.rec(w)
            if r:
                return r["ref"]
        return None

    def word_node(self, w):
        r = self.rec(w)
        if not r:
            return None
        v = self.verse(r["ref"])
        nid = f"{r['ref']}#w{r['pos']}"
        if nid not in v.nodes:
            n = {"id": nid, "ref": r["ref"], "local": f"w{r['pos']}",
                 "lang": self.lang, "word": True, "src": [r["id"]],
                 "w": [r["pos"]], "hebrew": r["text"], "original": r["text"],
                 "text": r.get("english") or r.get("gloss") or r["text"]}
            for k in ("class", "lemma", "type", "stem", "person", "gender",
                      "number", "state", "tense", "voice", "case", "degree"):
                if r.get(k):
                    n[k] = r[k]
            if r.get("strongnumberx"):
                n["strong"] = r["strongnumberx"]
            if r.get("class") == "verb":
                n["verb"] = True
                n["mood"] = r.get("type")
            if r.get("type") == "proper":
                n["proper"] = True
            v.nodes[nid] = n
        return nid

    def edge(self, v, typ, src, dst, srcids, **kw):
        e = {"ref": v.ref, "lang": self.lang, "type": typ, "src": src,
             "dst": dst, "src_ids": srcids}
        e.update(kw)
        v.edges.append(e)
        return e

    def _ids(self, e):
        return [w.get(XID_) for w in e.iter("w")]

    def _cjp(self, ch, siblings=None):
        """A CONNECTIVE PHRASE: MACULA groups a many-word connective as
        class="cjp" (לָכֵן, עַל־כֵּן, וְעַתָּה, כִּי אִם; Aramaic בֵּאדַיִן,
        כָּל־קֳבֵל דְּנָה). It opens the clause after it, as a one-word
        connective does. Its words, or None. With `siblings`, only if a
        clause follows it: the "and now" (וּכְעֶנֶת) that ends a letter's
        salutation (Ezr 4:11) opens nothing, and keeps its own node."""
        if ch.tag != "wg" or ch.get("class") != "cjp" or ch.get("role"):
            return None
        if siblings is not None:
            after = siblings[siblings.index(ch) + 1:]
            if not any(k.get("class") == "cl" or self.is_complex(k)
                       for k in after):
                return None
        recs = [self.rec(w) for w in ch.iter("w") if self.rec(w)]
        self._cjp_ids.update(r["id"] for r in recs)
        return recs

    def _lemmas(self, pending):
        """The connective's lemmas: a lone preposition only marks a nested
        clause, but inside a connective phrase it is part of the connective
        (the עַל of עַל־כֵּן)."""
        return [p["lemma"] for p in pending
                if p.get("class") != "prep" or p["id"] in self._cjp_ids]

    def _fn(self, ch, classes=FUNCTION):
        r = self.rec(ch)
        return bool(r) and (r.get("class") in classes or
                            r.get("type") == "interrogative")

    # ------------------------------------------------------------ phrases
    def phrase(self, e):
        """The node that stands for a phrase (a word, a composite, or a
        clause), building its internal structure on the way."""
        if e.tag == "w":
            return self.word_node(e)
        if e.get("class") == "cl" or self.is_complex(e):
            return self.clause(e)
        kids = list(e)
        rule = e.get("rule")
        if rule in self.t.wrap and len(kids) == 1:
            return self.phrase(kids[0])
        if len(kids) == 1:
            return self.phrase(kids[0])          # any one-child group
        if rule in self.t.coord:
            return self.coordination(e, kids)
        if rule in self.t.prep:
            # a preposition and its object: the object stands for the phrase
            obj = next((k for k in kids if k.get("head") == "true"),
                       kids[-1])
            return self.phrase(obj)
        head_i = self.head_index(e, kids, rule)
        # AN ARTICLE NEVER HEADS A PHRASE: Greek ὁ + a clause ("the one
        # believing", DetCL) is headed by the clause, not by "-" (Jhn 3:16:
        # a wrong head is worse than no inference at all)
        if kids[head_i].tag == "w" and \
                (self.rec(kids[head_i]) or {}).get("class") == "art":
            head_i = next((i for i, k in enumerate(kids) if i > head_i and
                           not (k.tag == "w" and self._fn(k))), head_i)
        head = self.phrase(kids[head_i])
        rel = self.t.first.get(rule) if rule in self.t.first else \
            self.t.last.get(rule) if rule in self.t.last else "qualifier"
        # A CLAUSE HEADS ONLY WHEN NO WORD CAN: "everyone (πᾶς) the one
        # believing in him" is "everyone WHO believes", headed by the word
        # and qualified by the clause, as the Hebrew כָּל־אֲשֶׁר reads
        done = {head_i}
        if head and "#cl" in head:
            # a question word may head it too ("WHO is the one that ...";
            # without this 53 of them were left with no node)
            word_i = next((i for i, k in enumerate(kids) if i != head_i and
                           k.tag == "w" and (not self._fn(k) or (
                               self.rec(k) or {}).get("type") ==
                               "interrogative")), None)
            if word_i is not None:
                word = self.phrase(kids[word_i])
                if word:
                    v = self.verse(self.first_ref(e))
                    self.edge(v, "qualifier", word, head,
                              self._ids(kids[head_i]), rel="relative",
                              clause_role=True)
                    head, head_i = word, word_i
                    done.add(word_i)
        for i, k in enumerate(kids):
            if i in done or rel is None:
                continue
            if k.tag == "w" and self._fn(k, ("art", "om", "cj", "prep")):
                continue
            # A RELATIVE WORD OPENS ITS CLAUSE; IT DOES NOT QUALIFY IT. Where a
            # clause heads the phrase, "who" / "whom" (אֲשֶׁר) was made the
            # clause's qualifier: 5,101 edges, "they came forth from there"
            # qualified by "whom" (1Ch 1:12; plan 1.42, 2026-10-18). Its node
            # stays (the sweep resolves it to its antecedent) and it joins the
            # clause's span, as a clause keeps its opening "and".
            # NOT the Aramaic דִּי, which is as often "that" as "who": kept
            # apart, it is the connective S3 reads to type a link "that" (Dan
            # 6:6, 6:14; Ezr 4:13, 4:16, 7:24 became "within" without it)
            if k.tag == "w" and head and "#cl" in head and self._fn(k, ("rel",)) \
                    and re.sub(r"[֑-ׇ]", "", (self.rec(k) or {}).get("lemma") or "") != "די":
                self.word_node(k)
                self.absorb(head, [self.rec(k)])
                continue
            dep = self.phrase(k)
            if head and dep and dep != head:
                v = self.verse(self.first_ref(e))
                self.edge(v, "qualifier", head, dep, self._ids(k), rel=rel,
                          clause_role=True)
        return head

    def head_index(self, e, kids, rule):
        marked = [i for i, k in enumerate(kids) if k.get("head") == "true"]
        if marked:
            return marked[0]
        if rule in self.t.last:
            return len(kids) - 1
        return 0

    def _conjunct(self, k):
        """A LATER CONJUNCT WRAPPED WITH ITS CONJUNCTION. Greek MACULA groups
        it so: <wg type="group">καί Ἰωάννην</wg> (2,845 of them, always one
        conjunction and one conjunct). Read as a phrase, its head fell to the
        first child, the conjunction, so "Peter and John" had the members
        Peter and καί (2,188 of 2,433 Greek coordinations, plan 2.15, found as
        "Peter and and" on the divine-flag sheet, Luke 22:8). The conjunct
        is what is left once the conjunction is set aside. A group with a rule
        is a phrase of its own (ὡς + a phrase, "as ...") and is left alone."""
        if k.tag != "wg" or k.get("type") != "group" or k.get("rule"):
            return k, []
        # by the word as well as its tag: 7 such καί are tagged adverbs and
        # one ἤ a particle ("God and Father", 1Co 15:24; Mat 15:6)
        rest = [x for x in k if not (x.tag == "w" and (
            self._fn(x, ("cj",)) or (self.rec(x) or {}).get("lemma") in ("καί", "ἤ")))]
        if len(rest) == 1 and len(rest) < len(k):
            return rest[0], [self.rec(x) for x in k
                             if x is not rest[0] and self.rec(x)]
        return k, []

    def coordination(self, e, kids):
        v = self.verse(self.first_ref(e))
        unwrapped = [self._conjunct(k) for k in kids]
        members = []
        for k, conj in unwrapped:
            if k.tag == "w" and self._fn(k, ("cj",)):
                continue
            m = self.phrase(k)
            # a clause conjunct keeps its "and" in its span, as a Hebrew
            # clause keeps its ו (50 Greek clauses; without this they lost
            # it). Only a conjunct that IS a clause: one reached through an
            # article ("and the one watering", 1Co 3:8) would take the "and"
            # across the article it leaves out, and never had it
            if k.tag == "wg" and (k.get("class") == "cl" or self.is_complex(k)):
                self.absorb(m, conj)
            members.append(m)
        members = [m for m in members if m]
        first = min(self.rec(w)["pos"] for w in e.iter("w") if self.rec(w))
        cid = f"{v.ref}#c{first}"
        texts = [self._text(m) for m in members]
        v.nodes[cid] = {"id": cid, "ref": v.ref, "local": f"c{first}",
                        "lang": self.lang, "composite": True,
                        "text": " and ".join(texts), "src": self._ids(e),
                        "rule": e.get("rule")}
        for m in members:
            self.edge(v, "member", cid, m, [])
        return cid

    def _text(self, nid):
        ref = nid.split("#")[0]
        return (self.verses[ref].nodes.get(nid) or {}).get("text", "")

    # ------------------------------------------------------------ complexes
    def is_complex(self, e):
        """Only connectives and clauses (or complexes), and no role: not a
        clause itself. Hebrew marks it class="cl", Greek leaves it bare."""
        if e.tag != "wg" or e.get("class") not in (None, "cl"):
            return False
        kids = list(e)
        if any(ch.get("role") for ch in kids):
            return False
        has_clause = False
        for ch in kids:
            if ch.tag == "w":
                if not self._fn(ch, OPENERS + ("adv",)):
                    return False
            elif ch.get("class") == "cl" or self.is_complex(ch):
                has_clause = True
            elif ch.get("class") != "cjp":
                return False
        return has_clause

    def complex(self, e, parent=None, role=None, lead=None, before=None):
        """Read a complex's clauses at its own level, each with the words
        that open it. At the top of a sentence the connectives are recorded
        for S3; inside a clause (`parent`) each clause is linked to it,
        carrying its opening words, for S3 to type. Returns the first."""
        # INHERITED OPENERS: "in order that (ἵνα) everyone ... not perish BUT
        # have eternal life" (Jhn 3:16). The ἵνα opens the whole complex, so
        # EVERY clause in it is under ἵνα; the ἀλλά belongs to the second
        # alone, and relates it to the first.
        inherited = list(lead or [])
        first, prev, pending = None, before, list(inherited)
        for ch in e:
            r = self.rec(ch)
            if r and self._fn(ch, OPENERS + ("adv",)):
                pending.append(r)
                continue
            cjp = self._cjp(ch, list(e))
            if cjp:
                pending.extend(cjp)
                continue
            if ch.tag == "wg" and self.is_complex(ch):
                sub = self.complex(ch, parent, role, pending, prev)
                first = first or sub
                prev = self._last or prev
                pending = list(inherited)
                continue
            if ch.get("class") == "cl":
                cid = self.clause(ch)
                own = [p for p in pending if p not in inherited]
                self.absorb(cid, pending)
                if cid:
                    if parent:
                        v = self.verse(parent.split("#")[0])
                        self.edge(v, "within", parent, cid, self._ids(ch),
                                  clause_link=True, role=role,
                                  prep=[p["lemma"] for p in pending],
                                  connective=[p["id"] for p in pending])
                        if prev and own:
                            # its own connective relates it to the clause
                            # before it in the complex
                            self.verse(cid.split("#")[0]).connectives.append({
                                "clause": cid, "host": prev,
                                "words": [p["id"] for p in own],
                                "lemmas": self._lemmas(own)})
                    elif pending:
                        self.verse(cid.split("#")[0]).connectives.append({
                            "clause": cid, "words": [p["id"] for p in pending],
                            "lemmas": self._lemmas(pending)})
                first = first or cid
                prev = cid
                self._last = cid
                pending = list(inherited)
            elif ch.tag == "wg":
                sub = self.phrase(ch)
                first = first or sub
            elif r:
                self.word_node(ch)
        return first

    def absorb(self, cid, pending):
        """The words that OPEN a clause (a connective, a question particle)
        belong to its span: they are accounted for by it."""
        if not cid or "#cl" not in cid or not pending:
            return
        c = self.verses[cid.split("#")[0]].nodes[cid]
        for p in pending:
            if p["id"] not in c["src"]:
                c["src"].insert(0, p["id"])
                if p["ref"] == c["ref"]:
                    c["w"] = sorted(set(c["w"]) | {p["pos"]})

    # ------------------------------------------------------------ clauses
    def clause(self, e):
        if self.is_complex(e):
            if self.stack:
                return self.complex(e, parent=self.stack[-1])
            return self.complex(e)
        ref = self.first_ref(e)
        if not ref:
            return None
        v = self.verse(ref)
        k = v.n_clause
        v.n_clause += 1
        cid, ctid = f"{ref}#cl{k}", f"{ref}#ct{k}"
        ws = [self.rec(w) for w in e.iter("w") if self.rec(w)]
        v.nodes[cid] = {"id": cid, "ref": ref, "local": f"cl{k}",
                        "lang": self.lang, "clause": True, "order": k,
                        "rule": e.get("rule"),
                        "text": " ".join(w.get("gloss") or w["text"]
                                         for w in ws),
                        "w": [w["pos"] for w in ws if w["ref"] == ref],
                        "src": [w["id"] for w in ws]}
        if self.stack:
            v.nodes[cid]["nested_in"] = self.stack[-1]
        else:
            self.sentence.append(cid)
        v.nodes[ctid] = {"id": ctid, "ref": ref, "local": f"ct{k}",
                         "lang": self.lang, "content": True, "order": k,
                         "text": v.nodes[cid]["text"]}
        self.edge(v, "asserts", cid, ctid, [], clause_role=True)
        pending = []                 # function words since the last child
        opened = False               # has a role been read yet?
        self.stack.append(cid)
        for ch in e:
            role = ch.get("role")
            if ch.tag == "w" and not role and self._fn(ch, OPENERS):
                pending.append(self.rec(ch))
                continue
            cjp = self._cjp(ch)
            if cjp:
                pending.extend(cjp)
                continue
            if not role and (ch.get("class") == "cl" or self.is_complex(ch)):
                if self.is_complex(ch):
                    self.complex(ch, parent=cid, lead=pending)
                else:
                    sub = self.clause(ch)
                    if sub:
                        self.edge(v, "within", cid, sub, self._ids(ch),
                                  clause_link=True,
                                  prep=[p["lemma"] for p in pending],
                                  connective=[p["id"] for p in pending])
                pending = []
                continue
            if role:
                if opened and pending and cid not in self._opened and any(
                        p.get("class") == "cj" for p in pending):
                    # A POSTPOSITIVE CONNECTIVE: Greek δέ, γάρ, οὖν, τέ, μέν
                    # stand second in their clause ("ἀνευρόντες δέ ..."), so
                    # MACULA places them after its first word. It still opens
                    # the clause; word order does not change what it joins.
                    cjs = [p for p in pending if p.get("class") == "cj"]
                    v.connectives.append({
                        "clause": cid, "words": [p["id"] for p in cjs],
                        "lemmas": [p["lemma"] for p in cjs]})
                    self._opened.add(cid)
                if not opened and pending:
                    self._opened.add(cid)
                    # connectives that OPEN the clause, inside it (MACULA
                    # puts אִם, כִּי, waw there): S3 links them
                    v.connectives.append({
                        "clause": cid, "words": [p["id"] for p in pending],
                        "lemmas": self._lemmas(pending)})
                opened = True
                self.role(v, ctid, cid, role, ch, pending)
                pending = []
            elif ch.tag == "wg":
                # a group with no role (a vocative, an interjection): read
                # it so its words are accounted for
                self.phrase(ch)
            elif ch.tag == "w":
                self.word_node(ch)
        self.stack.pop()
        return cid

    def role(self, v, ctid, cid, role, ch, pending):
        # a clause, or clauses, filling a role (ἵνα ..., a PrepCL, a CL2NP)
        # are clause links for S3 to type; the role's opening words go with
        if self.is_complex(ch):
            self.complex(ch, parent=cid, role=role)
            return
        inner = self._inner_clause(ch)
        if inner is not None:
            inside = set(self._ids(inner))
            outside = [self.rec(w) for w in ch.iter("w")
                       if self.rec(w) and w.get(XID_) not in inside]
            sub = self.clause(inner)
            if sub:
                self.absorb(sub, [o for o in outside
                                  if o.get("class") in OPENERS])
                self.edge(v, "within", cid, sub, self._ids(ch),
                          clause_link=True, role=role,
                          prep=[o["lemma"] for o in outside],
                          connective=[p["id"] for p in pending])
            return
        filler = self.phrase(ch)
        if not filler:
            return
        if "#cl" in filler:
            inside = set(self.verses[filler.split("#")[0]].nodes[filler]
                         .get("src") or [])
            # ANOTHER CLAUSE IN THE SAME ROLE: "to ask mercy ... THAT they
            # not perish" (Dan 2:18) — MACULA sets the second beside the
            # first inside one PrepCL. It is read, and linked to the clause
            # that fills the role, which it extends.
            extra = [k for k in ch if k.tag == "wg" and
                     (k.get("class") == "cl" or self.is_complex(k)) and
                     not set(self._ids(k)) & inside]
            extra_ids = {i for k in extra for i in self._ids(k)}
            outside = [self.rec(w) for w in ch.iter("w")
                       if self.rec(w) and w.get(XID_) not in inside
                       and w.get(XID_) not in extra_ids]
            self.edge(v, "within", cid, filler, self._ids(ch),
                      clause_link=True, role=role,
                      prep=[o["lemma"] for o in outside],
                      connective=[p["id"] for p in pending])
            for k in extra:
                self.stack.append(filler)
                sub = self.clause(k)
                self.stack.pop()
                if sub and "#cl" in sub:
                    self.edge(self.verse(filler.split("#")[0]), "within",
                              filler, sub, self._ids(k), clause_link=True,
                              prep=[], connective=[])
            return
        kw = {"clause_role": True}
        preps = [self.rec(w) for w in ch.iter("w")
                 if self.rec(w) and self.rec(w).get("class") == "prep"]
        if role == "pp" and preps:
            kw["prep"] = preps[0]["lemma"]
        elif role == "adv" and preps:
            # Greek gives a prepositional phrase the role `adv`; it is the
            # same thing the Hebrew calls `pp`, so it is written as one
            role = "pp"
            kw["prep"] = preps[0]["lemma"]
        self.edge(v, role, ctid, filler, self._ids(ch), **kw)

    def _inner_clause(self, ch):
        """The clause a role phrase wraps, if the phrase is only function
        words (a preposition, an article, a conjunction) around one clause."""
        if ch.tag != "wg":
            return None
        if ch.get("class") == "cl":
            return ch
        kids = [k for k in ch if not (k.tag == "w" and self._fn(k))]
        if len(kids) == 1 and kids[0].tag == "wg":
            return kids[0] if kids[0].get("class") == "cl" else \
                self._inner_clause(kids[0])
        return None

    # ------------------------------------------------------------ run
    def run(self, root):
        for s in root.iter("sentence"):
            self.sentence = []
            for top in s:
                if top.tag == "wg":
                    self.top(top)
            for cid in self.sentence:
                self.sentences[cid] = list(self.sentence)
        return self.verses

    def top(self, e):
        """A sentence's top group: its clauses, and the words between."""
        if e.get("class") == "cl" and not self.is_complex(e):
            self.clause(e)
            return
        pending = []
        for ch in e:
            r = self.rec(ch)
            if r and self._fn(ch, OPENERS + ("adv",)):
                pending.append(r)
                continue
            cjp = self._cjp(ch, list(e))
            if cjp:
                pending.extend(cjp)
                continue
            if ch.get("class") == "cl" and not self.is_complex(ch):
                cid = self.clause(ch)
                self.absorb(cid, pending)
                if cid and pending:
                    v = self.verse(cid.split("#")[0])
                    v.connectives.append({"clause": cid,
                                          "words": [p["id"] for p in pending],
                                          "lemmas": self._lemmas(pending)})
                pending = []
            elif ch.tag == "wg" and (self.is_complex(ch) or
                                     ch.get("class") in (None, "cl")):
                self.complex(ch, lead=pending) if self.is_complex(ch) \
                    else self.top(ch)
                pending = []
            elif ch.tag == "wg":
                self.phrase(ch)           # a vocative, a heading
                pending = []
            elif r:
                # a word outside any clause: its own node, so it is
                # accounted for
                self.word_node(ch)


XID_ = "{http://www.w3.org/XML/1998/namespace}id"
