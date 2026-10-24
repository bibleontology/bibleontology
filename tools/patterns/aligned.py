"""Aligned clauses: verses that say the same thing, by structure and meaning.

2026-09-28, reading Prov 4:23 ("guard your heart") in the reader and
finding Ps 32:7 among its connections — God guarding us, not us guarding our
hearts: the structural understanding was weak. A simple match saying this is
an imperative to the reader, with a verb of "guard" or its close synonyms and
an object of heart or a directionally similar object, would have produced the
wanted list. And the rule: if there is not some kind of structural intent
lined up, the other evidence needs to be strong — meaning can now be matched
with the structure complemented by the word graph.

The echoes (echoes.py) are bags of words; they know GUARD and HEART are in
both verses, not who guards what. This aligns CLAUSE with CLAUSE on the
structure the builder already has:

    force    directive (an imperative, or a second-person future — Hebrew
             law's "you shall love") / narrated / projected / ...
    verb     the same lexeme, or one the Septuagint renders the same way
             (at SHARE_ALIGN), or a close word-graph neighbour
    object   the same, or equivalent / near in the same senses

A pair needs the verb AND the object to line up; the force lines up for a
bonus, and both directive for more (a command to the reader answered by a
command to the reader). Similarity comes from the Septuagint (translation
equivalence, precise) and the word graph's context neighbours (at
NEAR_MIN, weighted by closeness) — the structure keeps the word graph's
noise in check: "hand" is near "heart", but not with the same verb and
force.

    python tools/patterns/aligned.py        -> out/aligned.jsonl.gz
"""
import collections
import gzip
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import mine  # noqa: E402
import echoes as E  # noqa: E402
from source import norm  # noqa: E402

SHARE_ALIGN = 0.05     # a rendering at 5% of a word's uses makes a synonym key:
                       # נצר "guard" meets שמר "keep" on φυλάσσω (9%)
NEAR_MIN = 0.6         # word-graph neighbours at least this close
NEAR_TOP = 10          # and at most this many per word (heart ~ soul is
                       # 0.60 and 9th, behind eyes and right hand)
BUCKET_MAX = 800       # keys shared by more clauses than this find nothing
TOP = 10               # aligned clauses kept per clause
MIN_SIM = 0.5          # verb and object must each line up at least this well
PP_WEIGHT = 0.7        # an object meeting a prepositional phrase
RARE_W = 0.7           # a rendering shared only at 5-10%
CLOSE_W = 0.85         # a secondary rendering at 10%+, or a neighbour
SUBJ_SAME = 3.0        # both doers known and the same (by record or word)
SUBJ_UNCONFIRMED = 1.0  # one doer known, the other unresolved
SUBJ_KIND = 0.5        # or the same kind of record
# the categorizer writes "Abstraction" for 39 words; the ontology declares
# bom:Abstract (a data inconsistency, 2026-09-28 — a check should catch it)
CLASS_ALIAS = {"Abstraction": "Abstract"}
# objects that carry no message. NOT "adj.all": that is WordNet's file for
# EVERY adjective, and it dropped "compassionate and gracious" (Ps 103:8)
EMPTY_CLASSES = {"Quantity"}
QUANTIFIERS = {"כל", "πας", "απας", "ολος", "εκαστος"}
COPULA = {"היה", "הוה", "ειμι", "γινομαι"}  # an explicit "is"
# verbs of saying and asking: with a person as object they are a speech
# frame ("Nicodemus asked Him"), not a message (John 3:4 / Luke 10:29)
SPEECH = {"אמר", "דבר", "ענה", "שאל", "λεγω", "ειπον", "ερωταω", "επερωταω",
          "αποκρινομαι", "λαλεω", "φημι"}
OPEN, MOUTH = {"ανοιγω", "פתח"}, {"στομα", "פה"}   # "opened his mouth"
# how a derived stem reads in the explanation ("cause to know")
STEM_GLOSS = {"hiphil": "cause to ", "hophal": "be caused to ",
              "niphal": "be ", "piel": "", "pual": "be ", "hithpael": "self-"}
RECORD_BONUS = 2.0     # both clauses name the same person, place or thing
RECORD_COMMON = 400    # ...unless it is named in more clauses than this
VERB_IDF_MIN = 3.4     # light verbs ("do/make", 3.36) below
LANG = {"H": "hebrew", "A": "hebrew", "G": "greek"}


def branches():
    """Meaning-ontology class name -> its top branch under bom:Entity
    (Being, Thing, Setting, Occurrent, Abstract), by RDFS inference: the
    transitive closure of rdfs:subClassOf in ontology/meaning/meaning.ttl.

    2026-09-28: the RDFS ontology is strong, so inference should filter,
    especially where similar messaging is claimed. Calibrated before use: of aligned pairs whose objects mean
    the SAME, 94% of the typed ones agree in class (the rest mostly typing
    artefacts — "midst" as noun and as adjective); of pairs only SIMILAR,
    53%. So the ontology separates meaning from association, and is used
    as a VETO on similar claims only, at the coarsest level it is sure of."""
    import rdflib
    from rdflib.namespace import RDFS
    g = rdflib.Graph()
    g.parse(ROOT / "ontology" / "meaning" / "meaning.ttl", format="turtle")
    local = lambda u: str(u).rsplit("#", 1)[-1].rsplit("/", 1)[-1]  # noqa
    parent = {local(s): local(o)
              for s, _p, o in g.triples((None, RDFS.subClassOf, None))}
    out = {}
    for c in parent:
        x, hops = c, 0
        while parent.get(x) not in (None, "Entity") and hops < 20:
            x, hops = parent[x], hops + 1
        if parent.get(x) == "Entity":
            out[c] = x                  # c's branch is x
    return out


def lexkey(lang, lem, strong):
    """A word's identity in the word graph: language, extended Strong's,
    consonants — so homographs stay apart (מוּסָר "discipline" is not
    מוֹסֵר "fetter")."""
    return (lang, E.strong_key(strong), lem)


def neighbours():
    """lexkey -> [(lexkey, closeness, kind, strong)] from the word graph,
    CONTENT WORDS ONLY: "discipline"'s nearest context neighbours were
    "not" (0.69) and "perhaps" (0.59) (2026-09-28)."""
    words = json.load(gzip.open(OUT / "wordpage-data.json.gz", "rt",
                                encoding="utf-8"))["words"]
    key = {w["id"]: lexkey(LANG.get(w["lang"], "?"), norm(w["lemma"]),
                           str(w.get("strong") or ""))
           for w in words}
    content = {w["id"] for w in words if w.get("cls") in
               ("noun", "verb", "adj")}
    strong = {w["id"]: str(w.get("strong") or "") for w in words}
    out = collections.defaultdict(list)
    for w in words:
        if w["id"] not in content:
            continue
        k = key[w["id"]]
        xs = []
        for kind in ("all", "cross"):
            for nid, s in (w.get("near") or {}).get(kind) or []:
                if s >= NEAR_MIN and nid in key and nid in content:
                    xs.append((s, key[nid], kind, strong[nid]))
        for s, k2, kind, st in sorted(xs, reverse=True)[:NEAR_TOP]:
            out[k].append((k2, s, kind, st))
    return out


def main():
    t0 = time.time()
    (nodes, roles, neg, part, cond, links, mention, ents, cat, label,
     simile_lemma, bridge) = mine.load()
    prim = E.primary()                 # the Greek used for it most of the time
    sept = E.septuagint()              # at 10%: close
    E.SHARE = SHARE_ALIGN
    sept05 = E.septuagint()            # at 5%: a hint
    near = neighbours()
    vstrong = mine.verb_strongs(nodes)
    branch = branches()
    strong_of = {}
    for n in nodes.values():
        if n.get("word") and n.get("lemma"):
            strong_of.setdefault((n["lang"], norm(n["lemma"])), n.get("strong"))

    def keys(lang, lem, strong, context=True):
        """word -> {key: weight}: itself and its Septuagint renderings at 1;
        for a noun (context=True) also its word-graph neighbours' at their
        closeness. VERBS TAKE TRANSLATION EQUIVALENCE ONLY: the context
        neighbours made "love" meet "give" (0.86) and "keep" meet "hide"
        and "buy" (2026-09-28, the first run)."""
        out = {f"{lang}:{E.strong_key(strong)}:{lem}": 1.0}
        # EQUIVALENCE IN TIERS. The same lexeme, or the same PRIMARY
        # Septuagint rendering (the Greek word most used for it), is the
        # same word (1.0). Another rendering at 10%+ is close (CLOSE_W);
        # one at 5-10% is a hint (RARE_W). On Prov 4:23 -> Job 17:4
        # ("keep ≈ up", shown as the same): the first verse that
        # supposedly says the same thing apparently does not (2026-09-28).
        for g in E.renders(sept05, lang, lem, strong):
            out[f"greek:{g}"] = RARE_W
        for g in E.renders(sept, lang, lem, strong):
            out[f"greek:{g}"] = CLOSE_W
        p = lem if lang == "greek" else prim.get(("H", E.strong_key(strong)))
        if p:
            out[f"greek:{p}"] = 1.0
        for (lg2, sk2, lm2), s, kind, st2 in near.get(
                lexkey(lang, lem, strong), []):
            if not context and kind != "cross":
                continue
            ks = [f"{lg2}:{sk2}:{lm2}"]
            p2 = lm2 if lg2 == "greek" else prim.get(("H", sk2))
            if p2:
                ks.append(f"greek:{p2}")
            for k in ks:
                out[k] = max(out.get(k, 0), s * CLOSE_W)
        return out

    # the nodes mine.load() does not keep: a psalm's Writing (its title) and
    # the phrase nodes a predicate can be ("compassionate and gracious")
    writing = {}
    for n in mine.rows(OUT / "structure-nodes.jsonl.gz"):
        if n["id"].endswith("#writing"):
            writing[n["id"].split("#")[0]] = n.get("text")
    # a phrase's words hang off `member` edges (a phrase node has no word
    # positions of its own), nested phrases included
    members = collections.defaultdict(list)
    # EVERY filler of a role, not the first: "make known ME your WAYS" (Exod
    # 33:13, Ps 25:4) has two objects, and the first is a pronoun
    fillers = collections.defaultdict(lambda: collections.defaultdict(list))
    refers = {}
    for e in mine.rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] == "refers_to":
            refers.setdefault(e["src"], e["dst"])
        if e["type"] == "member":
            members[e["src"]].append(e["dst"])
        elif e.get("clause_role") and e["type"] in ("o", "o2", "p", "pp") and \
                "#ct" in e["src"]:
            fillers[e["src"]][e["type"]].append(e["dst"])

    def phrase_words(pid, depth=0):
        out = []
        for m in members.get(pid, ()):
            n = nodes.get(m)
            if n and n.get("word"):
                if n.get("lemma") and n.get("class") in ("noun", "adj", "verb"):
                    out.append(n)
            elif depth < 4:
                out += phrase_words(m, depth + 1)
        return out
    clauses = {}
    for cid, c in nodes.items():
        if not c.get("clause"):
            continue
        lang = c["lang"]
        rs = roles.get(cid.replace("#cl", "#ct"), {})
        # A MISSING VERB IS STRUCTURE. 2026-09-28: lack of a verb
        # where there should be a verb is something to match on (or what it
        # implies is, anyway). A verbless clause with a subject and a
        # predicate says what something IS ("the LORD [is] compassionate",
        # Ps 103:8): its implied "is" fills the verb slot, and an explicit
        # copula meets it as close, not the same.
        verbless = not c.get("verb_lemma")
        if verbless and not ("s" in rs and "p" in rs):
            continue
        # a psalm's title ("a psalm of David") is the Writing, not a
        # statement: every titled psalm matched every other on "David"
        if writing.get(cid.split("#")[0]) == c.get("text"):
            continue
        obj, orole, obranch, ocls_, olem = None, None, None, None, None
        olist = None
        # the thing acted on: the object, else the predicate, else the
        # prepositional phrase ("guard FOR your souls", Deut 4:15; "guard
        # yourselves IN your spirit", Mal 2:15)
        ct = cid.replace("#cl", "#ct")
        candidates = [(r, d_) for r in ("o", "o2", "p", "pp")
                      for d_ in (fillers[ct].get(r) or
                                 ([rs[r][0]] if r in rs else []))]
        for r, dst in candidates:
            orole = r
            w = nodes.get(dst) or {}
            rec = mention.get(dst)
            if rec:
                obj = ({f"R:{rec}": 1.0}, (ents.get(rec) or (rec,))[0])
            elif w.get("lemma") and w.get("class") not in (
                    "pron", "art", "det"):
                lem = norm(w["lemma"])
                obj = (keys(lang, lem, w.get("strong")),
                       mine.label_of(label, lang, lem, w.get("strong")))
                ocls_ = cat.get((lang, lem))
                obranch = branch.get(CLASS_ALIAS.get(ocls_, ocls_))
                olem = lem
            elif not w.get("lemma") and members.get(dst):
                # A PHRASE ("compassionate and gracious", Ps 103:8): every
                # content word in it, each a way to line up
                ws = phrase_words(dst)
                if ws:
                    ks, gl = {}, []
                    for x in ws:
                        lx = norm(x["lemma"])
                        for k, wt in keys(lang, lx, x.get("strong")).items():
                            ks[k] = max(ks.get(k, 0), wt)
                        gl.append(mine.label_of(label, lang, lx, x.get("strong")))
                    # a LIST of three or more ("sons of men or beasts of the
                    # field or birds", Dan 2:38): one member meeting is not
                    # the same object; a pair ("compassionate and gracious")
                    # still is
                    if len(ws) >= 3:
                        ks = {k: min(wt, CLOSE_W) for k, wt in ks.items()}
                    # each member's own keys, so that two lists can be met
                    # member for member (below, LISTS THAT MEET WHOLE)
                    if len(ws) >= 2:
                        olist = [keys(lang, norm(x["lemma"]), x.get("strong"))
                                 for x in ws]
                    obj = (ks, " and ".join(gl[:3]))
                    ocls_ = cat.get((lang, norm(ws[0]["lemma"])))
                    obranch = branch.get(CLASS_ALIAS.get(ocls_, ocls_))
            if obj:          # the first filler with content; a pronoun
                break        # ("me") lets the next one speak
        if not obj:
            continue
        vl = "∅is" if verbless else norm(c["verb_lemma"])
        # WHO DOES IT: the subject's record, stated or the unstated one the
        # pronoun layer resolved
        sdst = (rs.get("s") or (None,))[0]
        # FOLLOW THE PRONOUN LAYER: an unstated subject ("He gave", John
        # 3:16) refers_to the word it resolves to ("God"); looking only in
        # the mentions layer left the subject unknown for 95% of pairs
        x, hops = sdst or cid + "s", 0
        subj = None
        while x and hops < 4 and not subj:
            subj = mention.get(x)
            x, hops = refers.get(x), hops + 1
        if x and not subj:
            subj = mention.get(x)
        sdst = sdst or (cid + "s")
        # the subject as a key: its record, else its word ("the LORD")
        sw = nodes.get(sdst) or {}
        if not sw.get("lemma") and refers.get(sdst):
            sw = nodes.get(refers[sdst]) or sw
        # THE DOER BY ITS WORD, through the Septuagint as the object is: the
        # mentions layer ties words to RECORDS and does not cover every noun
        # ("God" in John 3:16 has none), so θεός must meet אֱלֹהִים by
        # meaning. A pronoun that resolves nowhere is not a doer.
        sk = {}
        if subj:
            sk[f"R:{subj}"] = 1.0
        if sw.get("lemma") and sw.get("class") not in ("pron", "art", "det"):
            sk.update(keys(lang, norm(sw["lemma"]), sw.get("strong"),
                           context=False))
        skey = subj or (f"{lang}:{norm(sw['lemma'])}" if sw.get("lemma")
                        else None)
        mode = mine.mode_of(c, cid, neg, part, cond, nodes)
        force = "directive" if mode == "command" or (
            mode == "projected" and c.get("verb_person") == "second") \
            else mode
        if verbless:
            vkeys, vgloss = {"be:copula": 1.0}, "is (unstated)"
        else:
            vs_ = vstrong.get(cid) or strong_of.get((lang, vl))
            vkeys = keys(lang, vl, vs_, context=False)
            vgloss = mine.label_of(label, lang, vl, vs_)
            # THE STEM IS PART OF THE VERB. "He made known His ways to
            # Moses" (Ps 103:7) is the causative (hiphil) of ידע; "they have
            # not known My ways" (Ps 95:10) is the plain stem — and ten of
            # those crowded out Exod 33:13, Moses asking "make known to me
            # Your ways" (2026-09-28: surprisingly few
            # links to Moses). Same lexeme and stem: the same verb; another
            # stem: close. The Septuagint layer is per lexeme, not per stem,
            # so for a derived stem its renderings count as close too.
            stem = c.get("verb_stem")
            if lang == "hebrew" and stem:
                lk = f"{lang}:{E.strong_key(vs_)}:{vl}"
                vkeys = {k: (CLOSE_W if w >= 1.0 and stem != "qal" else w)
                         for k, w in vkeys.items()}
                vkeys[lk] = CLOSE_W
                vkeys[f"{lk}:{stem}"] = 1.0
                if stem != "qal":
                    vgloss = STEM_GLOSS.get(stem, "") + vgloss
            if vl in COPULA and orole == "p":
                vkeys["be:copula"] = CLOSE_W
        # every named record in the clause, in any role ("to Moses")
        recs = {mention.get(d_) for d_, _p in rs.values()} - {None}
        if subj:
            recs.add(subj)
        # the object and subject NODES, for the trimming checklist (plan
        # 6.14): which word filled each slot, so "the Son" can be told from
        # Heman's sons and God from Chemosh
        clauses[cid] = {"odst": dst, "sdst": sdst,
                        "v": vkeys, "recs": recs, "vl": vl,
                        "vg": vgloss, "o": obj[0], "ol": olist,
                        "og": obj[1], "force": force, "orole": orole,
                        "ob": obranch, "ocls": ocls_, "olem": olem,
                        "subj": subj, "skey": skey, "verbless": verbless,
                        "sk": sk, "neg": cid in neg,
                        "skind": (ents.get(subj) or ("", None))[1]
                        if subj else None}
    print(f"{len(clauses):,} clauses with a verb and an object "
          f"({time.time() - t0:.0f}s)", flush=True)
    import os
    for dbg in filter(None, os.environ.get("ALIGN_DEBUG", "").split(",")):
        c = clauses.get(dbg)
        print("DEBUG", dbg, "absent" if not c else
              {k: (sorted(v.items())[:8] if isinstance(v, dict) else v)
               for k, v in c.items()}, flush=True)

    df = collections.Counter()
    for c in clauses.values():
        df.update(k for k, w in c["v"].items() if w >= CLOSE_W)
        df.update(k for k, w in c["o"].items() if w >= CLOSE_W)
    n = len(clauses)
    idf = lambda k: math.log(n / max(df[k], 1))  # noqa: E731
    rec_df = collections.Counter(r for c in clauses.values() for r in c["recs"])
    for c in clauses.values():
        # a clause's own verb and object rarity: its exact keys' best
        c["vi"] = max((idf(k) for k, w in c["v"].items() if w >= CLOSE_W),
                      default=0.0)
        c["oi"] = max((idf(k) for k, w in c["o"].items() if w >= CLOSE_W),
                      default=0.0)
    # A MATCH MUST CARRY A MESSAGE. Rarity alone does not say so: as objects
    # "one" (idf 6.41) and "thing" (9.98) are rarer than "son" (4.43). The
    # ontology does: an object typed Quantity ("one", "all") says nothing by
    # itself; and the light verb "do/make" (3.36) is below VERB_IDF_MIN
    # while "give" (3.53) is not ("gave His Son"). Mal 2:15 "did not the
    # ONE make" aligned as the same thing as a dozen levitical "do ... one"
    # clauses (2026-09-28).
    # (a statement of what something IS carries its message in the
    # predicate: the implied or explicit "is" is exempt from the verb floor)
    # A SPEECH FRAME IS NOT A MESSAGE. "Nicodemus asked [Him]" (John 3:4)
    # was shown as saying the same thing as "he asked Jesus" (Luke 10:29) —
    # the introduction to two different questions (2026-09-28: this
    # example really had questionable matches). A verb of saying or
    # asking whose object is a person says who spoke to whom; what was said
    # is in its own clauses, which still align.
    # the person may be a class (Being) or a resolved record ("R:jesus" —
    # John 3:4's "to Him" is one, with no class, and a first version that
    # tested only the class caught neither of the two)
    # and the idiom "opened his mouth" = began to speak (Acts 8:35, Philip)
    # matched the fish's mouth (Matt 17:27) and a bird's beak (Isa 10:14);
    # its negation ("I do not open my mouth", Ps 39:9) was shown as saying
    # the opposite (2026-09-28: a lot of questionable connections were
    # being seen)
    speech_frame = lambda c: (  # noqa: E731
        (c.get("vl") in SPEECH and (c.get("ob") == "Being"
                                    or any(k.startswith("R:") for k in c["o"])))
        or (c.get("vl") in OPEN and c.get("olem") in MOUTH))
    empty = [cid for cid, c in clauses.items()
             if c["ocls"] in EMPTY_CLASSES or c.get("olem") in QUANTIFIERS
             or (c["vi"] < VERB_IDF_MIN and "be:copula" not in c["v"])
             or speech_frame(c)]
    for cid in empty:
        del clauses[cid]
    print(f"{len(empty):,} clauses dropped as carrying no message", flush=True)

    bucket = collections.defaultdict(list)
    for cid, c in clauses.items():
        for vk in c["v"]:
            for ok in c["o"]:
                bucket[(vk, ok)].append(cid)
    print(f"{len(bucket):,} verb-object keys ({time.time() - t0:.0f}s)",
          flush=True)

    def best(a, b):
        """How well two key sets line up: the best shared key, weighted by
        both sides' closeness, and that key."""
        top, kk = 0.0, None
        for k, w in a.items():
            w2 = b.get(k)
            if w2 and w * w2 > top:
                top, kk = w * w2, k
        return top, kk

    out, vetoed = [], 0
    for cid, c in clauses.items():
        seen = set()
        cand = []
        for vk in c["v"]:
            for ok in c["o"]:
                b = bucket.get((vk, ok), ())
                if len(b) > BUCKET_MAX:
                    continue
                for o in b:
                    if o in seen or o.split("#")[0] == cid.split("#")[0]:
                        continue
                    seen.add(o)
                    oc = clauses[o]
                    vs, vk2 = best(c["v"], oc["v"])
                    os_, ok2 = best(c["o"], oc["o"])
                    # LISTS THAT MEET WHOLE. A list of three or more is held
                    # to "close" above, because ONE member meeting is not the
                    # same object (Dan 2:38). Two lists that meet member for
                    # member are: every member of the shorter has the same
                    # meaning in the longer. "Peter, James and John" (Mark
                    # 9:2, Luke 9:28); "the heaven and the earth" in "heaven,
                    # earth, sea and springs" (Gen 1:1, Rev 14:7). Unseen
                    # until plan 2.15, when Greek lists stopped losing every
                    # member after the first (2026-10-17)
                    if os_ < 1.0 and c["ol"] and oc["ol"]:
                        short, long_ = sorted((c["ol"], oc["ol"]), key=len)
                        if all(any(best(m, n)[0] >= 1.0 for n in long_)
                               for m in short):
                            os_ = 1.0
                    # a prepositional phrase is a weaker slot than the
                    # object: "keep FROM evil" is not "keep your heart"
                    if "pp" in (c["orole"], oc["orole"]) and \
                            c["orole"] != oc["orole"]:
                        os_ *= PP_WEIGHT
                    if vs < MIN_SIM or os_ < MIN_SIM:
                        continue
                    # a statement of what something IS is about its subject:
                    # "the LORD is my God" is not "your God is my God"
                    if (c["verbless"] or oc["verbless"]) and \
                            c["skey"] != oc["skey"]:
                        continue
                    # THE ONTOLOGY'S VETO: a merely similar object in a
                    # different top branch (heart, Abstract ~ tongue, Thing)
                    # is not similar messaging; never applied to the same
                    # meaning, nor where either object is untyped
                    if os_ < 1.0 and c["ob"] and oc["ob"] and \
                            c["ob"] != oc["ob"]:
                        vetoed += 1
                        continue
                    # SAME MEANING OUTRANKS SIMILAR: a context neighbour
                    # (heart ~ tongue 0.61) counts at its square, so it
                    # cannot beat the same word with the force bonus alone
                    # (Prov 4:23's first run led with "keep your tongue")
                    # and at the SOURCE word's rarity: scoring a neighbour
                    # at its own drifted to rare neighbours (tongue is
                    # rarer than heart)
                    s = vs * vs * c["vi"] + os_ * os_ * c["oi"]
                    if c["force"] == oc["force"]:
                        s += 2.0 if c["force"] == "directive" else 0.7
                    # the same doer: "God gave a son" (Gen 17:16) over
                    # "Chemosh gave his sons" (Num 21:29) for John 3:16
                    # WHO DOES IT. 2026-09-28, of John 3:16 ("God ...
                    # gave His Son") beside Num 21:29 (Chemosh "gave up his
                    # sons as refugees"): what was Num 21:29 doing in the
                    # list? Both doers known and the same: a bonus. Both
                    # known and different: not the same thing.
                    doer_differs, doer = False, None
                    if c["sk"] and oc["sk"]:
                        ss, _k = best(c["sk"], oc["sk"])
                        if ss >= 1.0:
                            s += SUBJ_SAME
                            doer = "same"
                        elif ss == 0:
                            doer_differs, doer = True, "differs"
                            s -= SUBJ_SAME
                    elif c["sk"] or oc["sk"]:
                        # one doer known, the other not resolved: the match
                        # is unconfirmed (Num 21:29's unresolved "he" is
                        # Chemosh; John 3:16's is God)
                        s -= SUBJ_UNCONFIRMED
                        doer = "unconfirmed"
                    elif c["skind"] and c["skind"] == oc["skind"]:
                        s += SUBJ_KIND
                    # the same named person, place or thing in both (not a
                    # record named everywhere: God, Israel)
                    named = {x for x in c["recs"] & oc["recs"]
                             if rec_df[x] <= RECORD_COMMON}
                    if named:
                        s += RECORD_BONUS
                    cand.append((round(s, 2), o, round(vs, 2), round(os_, 2),
                                 doer_differs, doer))
        cand.sort(reverse=True)
        for s, o, vs, os_, doer_differs, doer in cand[:TOP]:
            oc = clauses[o]
            named = sorted((ents.get(x) or (x,))[0]
                           for x in c["recs"] & oc["recs"]
                           if rec_df[x] <= RECORD_COMMON)
            out.append({"from": cid, "to": o, "score": s,
                        "verb": [c["vg"], oc["vg"], vs],
                        "obj": [c["og"], oc["og"], os_],
                        "force": [c["force"], oc["force"]],
                        "subj": [c["subj"], oc["subj"]], "named": named,
                        # same meaning on both slots, or only similar
                        "doer_differs": doer_differs, "doer": doer,
                        "neg": [c["neg"], oc["neg"]],
                        # for the trimming checklist (6.14): the slot fillers
                        # and how rare the verb and object are on each side
                        "ow": [c.get("odst"), oc.get("odst")],
                        "sw": [c.get("sdst"), oc.get("sdst")],
                        "vi": [round(c["vi"], 2), round(oc["vi"], 2)],
                        "oi": [round(c["oi"], 2), round(oc["oi"], 2)],
                        # SAYS THE OPPOSITE: the same verb and object, one
                        # side negated — "God so loved the world" / "do not
                        # love the world" (1 John 2:15). 2026-09-28:
                        # "says the same thing" or clear contrast, where
                        # found, are what deserve to be open.
                        "tier": ("contrast" if c["neg"] != oc["neg"]
                                 else "same")
                        if vs >= 1.0 and os_ >= 1.0 and not doer_differs
                        else "similar"})
    with gzip.open(OUT / "aligned.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out):,} aligned pairs written; {vetoed:,} similar claims "
          f"vetoed by the ontology ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
