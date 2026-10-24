"""Invariants: deterministic checks of the graph against its SOURCE, every build.

Plan 1.25 (2026-09-27, invariants first): the gate for the clean
builder, and for any fix (PRINCIPLES 51-52). The source is the oracle, so no
check here needs judgement. Each writes a number and a sample to
out/invariants.json; the previous run is kept as out/invariants-prev.json,
and the drift between them is printed. A change is kept only if it moves its
own measure and no other.

    python tools/invariants.py            # run, compare with the last run
    python tools/invariants.py --verse Psa.103.1   # one verse, in detail

WHAT THE GRAPH KEEPS OF THE SOURCE (measured 2026-09-27). A clause carries
`w`, the 0-based positions of its morphemes in the verse; exact. A word
node carries `word_ref`, MACULA's whitespace-word number ("2SA 17:14!23"),
and today ONE node stands for every occurrence of the same word text in a
verse. So a node's position is known only for one occurrence. Checks at node
level therefore credit a morpheme if a node of the same lemma sits in the
same clause: lenient, and said so. The clean builder's per-occurrence ids
(1.26) make them exact.

Only these MACULA fields are read: ref, xml:id, class, lemma, strongnumberx,
text. Never SDBH, lexdomain, coredomain, domain or ln.
"""
import argparse
import collections
import gzip
import json
import random
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                               # noqa: E402
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import source as SRC                                       # noqa: E402

OUT = ROOT / "out"
XID = "{http://www.w3.org/XML/1998/namespace}id"
# Morpheme classes that carry no node of their own by design: the article,
# the object marker; conjunctions and prepositions are accounted by the edge
# that carries them (a link's connective, a pp's `prep`), checked separately.
STRUCTURAL = {"art", "om", "x"}   # x: paragogic / directional letters
FUNCTION = {"cj", "prep", "rel"}  # rel: אֲשֶׁר, carried by a relative link


def source(lang="hebrew"):
    """ref -> [morpheme dicts in order]: pos (0-based), id, cls, lemma,
    strong, text, type, after. Read by the builder's own source reader, so
    Hebrew and Greek are made alike exactly as the builder makes them (Greek
    `conj` is `cj`, `det` is `art`, `strong` is `strongnumberx`)."""
    verses = collections.defaultdict(list)
    for path in SRC.files(lang):
        _, ws = SRC.load(path, lang)
        for r in sorted(ws.values(), key=lambda r: (r["ref"], r["pos"])):
            verses[r["ref"]].append({
                "pos": r["pos"], "id": r["id"], "cls": r.get("class"),
                "lemma": r.get("lemma"),
                "strong": re.sub(r"\D", "", r.get("strongnumberx") or ""),
                "text": r.get("text") or "", "type": r.get("type"),
                "after": r.get("after") or ""})
    return verses


PREFIX = "placeholder"           # --graph structure: the clean builder's


def _file(kind):
    """--graph old: the OLD builder's graph, kept as *.old.jsonl.gz once
    the new one was installed where the app reads it."""
    if PREFIX == "old":
        return f"placeholder-{kind}.old.jsonl.gz"
    return f"{PREFIX}-{kind}.jsonl.gz"


def graph(lang="hebrew"):
    lang = {"H": "hebrew", "G": "greek"}.get(lang, lang)
    nodes, edges = {}, collections.defaultdict(list)
    for l in gzip.open(OUT / _file("nodes"), "rt",
                       encoding="utf-8"):
        r = json.loads(l)
        if r.get("lang") == lang and r.get("id"):
            nodes[r["id"]] = r
    for l in gzip.open(OUT / _file("edges"), "rt",
                       encoding="utf-8"):
        r = json.loads(l)
        if r.get("lang") == lang and r.get("ref"):
            edges[r["ref"]].append(r)
    by_ref = collections.defaultdict(list)
    for n in nodes.values():
        if n.get("ref"):
            by_ref[n["ref"]].append(n)
    return nodes, by_ref, edges


def _num(s):
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def _bare(s):
    """Consonants only: points, accents and maqqef removed."""
    return "".join(ch for ch in (s or "") if "א" <= ch <= "ת")


# Greek, by lemma (MACULA's Greek marks no `type` for them)
NEG_GREEK = {SRC.norm(x) for x in ("οὐ", "οὐκ", "οὐχ", "οὐχί", "μή", "μηδέ",
             "οὐδέ", "οὐκέτι", "μηκέτι", "οὐδέποτε", "μηδέποτε", "μήπω", "οὔπω")}
Q_GREEK = {SRC.norm(x) for x in ("πῶς", "ποῦ", "πότε", "πόθεν", "πόσος",
           "ποῖος", "μήτι")}
# לֹא, אַל, אַיִן/אֵין, בְּלִי, בִּלְתִּי
NEGATIVES = {"3808", "408", "369", "1097", "1115"}
# מִי, מָה, אֵיךְ, אֵיכָה, אַיֵּה, אָן, מַדּוּעַ, אֵי ; the prefixed הֲ by class
INTERROGATIVES = {"4310", "4100", "349", "351", "346", "575", "4069", "335"}
# a clause-opening waw is carried by any of these links into its clause
LINKS_FOR_WAW = {"and", "then", "but_rather", "contrast", "or", "because",
                 "when_if_though", "conceded", "holds_anyway", "part",
                 # plan 1.42 (2026-10-18): a command's attached clause, and
                 # גַּם כִּי as the clause link it is
                 "attached", "though"}


def check_verse(ref, morph, vnodes, vedges, nodes):
    """Both invariants for one verse. Returns (counts, findings)."""
    c, f = collections.Counter(), []
    clauses = sorted((n for n in vnodes if n.get("clause")),
                     key=lambda n: n.get("order", 0))
    span = {}                        # clause id -> set of morpheme positions
    for cl in clauses:
        span[cl["id"]] = set(cl.get("w") or [])
    in_clause = set().union(*span.values()) if span else set()
    lemmas_in = collections.defaultdict(set)     # clause id -> strongs there
    for cid, s in span.items():
        for p in s:
            if p < len(morph):
                lemmas_in[cid].add(_num(morph[p]["strong"]))
    node_strongs = {_num(n.get("strong")) for n in vnodes
                    if n.get("strong") and not n.get("clause")}
    node_lemmas = {n.get("lemma") for n in vnodes
                   if n.get("lemma") and not n.get("clause")}

    # A CONNECTIVE PHRASE's words (the כֵּן of לָכֵן, the עַתָּה of וְעַתָּה,
    # the Aramaic קֳבֵל): recorded as the source of the typed link they open,
    # not as nodes. Only a link that was written carries them; a phrase the
    # lexicon could not type stays unaccounted.
    link_ids = {i for e in vedges if e.get("clause_link") and
                e.get("connective") for i in (e.get("src_ids") or [])}

    def has_node(m):
        # by Strong's where MACULA gives one, else by lemma (name parts such
        # as the "zebub" of Baal-zebub carry no Strong's number)
        s = _num(m["strong"])
        return (s and s in node_strongs) or m["lemma"] in node_lemmas

    # ---- 1. WORD ACCOUNTABILITY -------------------------------------------
    # (a) exact: a morpheme in no clause's span is outside the structure.
    # (b) lenient: a content morpheme whose lemma has no node in the verse.
    for m in morph:
        c["morphemes"] += 1
        if m["cls"] in STRUCTURAL:
            c["structural"] += 1
            continue
        if m["cls"] in FUNCTION:
            # a conjunction or preposition between clauses is normal; the
            # connector invariant accounts for these
            c["function_words"] += 1
            continue
        c["content_morphemes"] += 1
        if m["id"] in link_ids and not has_node(m):
            c["carried_by_link"] += 1
            continue
        node = has_node(m)
        if m["pos"] not in in_clause:
            # outside every clause WITH a node is normal (a vocative, a
            # heading); outside every clause with NO node is lost outright
            c["outside_any_clause"] += 1
            f.append(("outside_any_clause", ref, m["pos"],
                      f"{m['text']} ({m['cls']}) is in no clause"))
            if not node:
                c["lost"] += 1
                f.append(("lost", ref, m["pos"],
                          f"{m['text']} ({m['cls']}) is in no clause and "
                          f"has no node"))
        if not node:
            c["content_without_node"] += 1
            f.append(("content_without_node", ref, m["pos"],
                      f"{m['text']} ({m['cls']}, H{m['strong']}) has no node"))

    # ---- 3. CONNECTORS, NEGATION, QUESTIONS --------------------------------
    first = {}                       # morpheme position -> clause it opens
    for cl in clauses:
        if cl.get("w"):
            first.setdefault(min(cl["w"]), cl)
    links_of = collections.defaultdict(list)
    for e in vedges:
        if e.get("clause_link"):
            links_of[e.get("src")].append(e)
            links_of[e.get("dst")].append(e)
    neg_ct = {e.get("src") for e in vedges if e.get("type") == "neg"}
    carried = collections.defaultdict(set)   # clause -> opening lemmas
    for e in vedges:
        if e.get("clause_link"):
            for x in (e.get("prep") or []):
                carried[e.get("dst")].add(SRC.norm(x))
                carried[e.get("src")].add(SRC.norm(x))
            for x in SRC.norm(e.get("connective") if isinstance(
                    e.get("connective"), str) else "").split():
                # a forward link (אִם / הֵן / εἰ "if ... then") is written
                # FROM the clause its connective opens
                carried[e.get("src") if e.get("forward")
                        else e.get("dst")].add(x)
    for m in morph:
        p, bare = m["pos"], SRC.norm(m["lemma"])
        # the INNERMOST clause holding the word: an outer clause's span
        # includes the words of the clauses nested in it
        owner = min((cl for cl in clauses if p in span[cl["id"]]),
                    key=lambda cl: len(span[cl["id"]]), default=None)
        if m["cls"] == "cj":
            c["connectors"] += 1
            opens = first.get(p) or first.get(p + 1)
            if owner and bare in carried[owner["id"]]:
                c["connector_linked"] += 1
                continue
            if owner and opens is not owner and min(owner["w"]) != p:
                c["connector_inside_phrase"] += 1        # "X and Y"
                continue
            if opens and opens.get("verb_mood") in ("wayyiqtol", "weqatal") \
                    and bare == "ו":
                c["connector_fused"] += 1                # waw of the verb
                continue
            if opens and (bare in carried[opens["id"]] or any(
                    bare == "ו" and e.get("type") in LINKS_FOR_WAW
                    for e in links_of[opens["id"]])):
                c["connector_linked"] += 1
                continue
            c["connector_unaccounted"] += 1
            f.append(("connector_unaccounted", ref, p,
                      f"{m['text']} opens "
                      f"{(opens or owner or {}).get('text', 'no clause')[:50]}"
                      f" and no link carries it"))
        s = _num(m["strong"])
        gk = SRC.norm(m["lemma"])
        greek = not any("\u05d0" <= ch <= "\u05ea" for ch in m["lemma"] or "")
        if ((s in NEGATIVES and not greek) or (greek and gk in NEG_GREEK)) \
                and owner:
            c["negatives"] += 1
            if owner["id"].replace("#cl", "#ct") not in neg_ct:
                c["negative_unrecorded"] += 1
                f.append(("negative_unrecorded", ref, p,
                          f"{m['text']} in {owner.get('text', '')[:50]} has "
                          f"no neg"))
        if (not greek and (s in INTERROGATIVES or (m["cls"] == "ptcl" and
                                                    bare == "ה"))) or \
                (greek and (m.get("type") == "interrogative" or
                            gk in Q_GREEK)):
            c["interrogatives"] += 1
            if (owner or {}).get("upper_force") != "question":
                c["question_unmarked"] += 1
                f.append(("question_unmarked", ref, p,
                          f"{m['text']} in "
                          f"{(owner or {}).get('text', 'no clause')[:50]} is "
                          f"not marked a question"))

    # ---- 2. SPAN CONTAINMENT ----------------------------------------------
    # A word filling a clause's role must lie in THAT clause's own words,
    # unless the edge is marked inferred / implicit (a rule supplied it) or
    # the filler is minted (an implied pronoun, a composite).
    for e in vedges:
        if not e.get("clause_role") or e.get("type") not in (
                "s", "o", "o2", "io", "p", "pp", "v"):
            continue
        if e.get("inferred") or e.get("implicit") or e.get("reading"):
            continue
        src, dst = e.get("src") or "", e.get("dst") or ""
        cid = re.sub(r"#ct(\d+)c?$", r"#cl\1", src)
        if cid not in span or not span[cid]:
            continue
        d = nodes.get(dst) or {}
        if d.get("composite") or d.get("implicit") or d.get("minted_for") \
                or d.get("verb") or not d.get("strong") \
                or d.get("class") == "pron" or d.get("pos") == "pronoun":
            # a pronoun node carries the independent pronoun's number, not
            # its suffix's, so it cannot be matched by Strong's here
            continue
        c["role_edges_checked"] += 1
        if _num(d["strong"]) not in lemmas_in[cid]:
            c["role_outside_its_clause"] += 1
            f.append(("role_outside_its_clause", ref, None,
                      f"{e['type']} of {cid.split('#')[1]} -> "
                      f"{d.get('text')} (H{_num(d['strong'])}), not among "
                      f"that clause's words"))
    return c, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verse")
    ap.add_argument("--graph", default="placeholder")
    ap.add_argument("--lang", default="hebrew", choices=("hebrew", "greek"))
    a = ap.parse_args()
    global PREFIX
    PREFIX = a.graph
    print("reading the source ...", flush=True)
    src = source(a.lang)
    print("reading the graph ...", flush=True)
    nodes, by_ref, edges = graph(a.lang)
    total, findings = collections.Counter(), collections.defaultdict(list)
    verses_hit = collections.defaultdict(set)
    refs = [a.verse] if a.verse else sorted(src)
    for ref in refs:
        c, f = check_verse(ref, src[ref], by_ref.get(ref, []),
                           edges.get(ref, []), nodes)
        total.update(c)
        for kind, r, pos, why in f:
            findings[kind].append((r, why))
            verses_hit[kind].add(r)
    if a.verse:
        print(json.dumps(total, indent=1))
        for k, v in findings.items():
            for r, why in v:
                print(f"  {k}: {why}")
        return
    nv = len(refs)
    res = {"verses": nv, "counts": dict(total),
           "rates": {
               "lost": total["lost"] / max(1, total["content_morphemes"]),
               "outside_any_clause": total["outside_any_clause"] /
               max(1, total["content_morphemes"]),
               "content_without_node": total["content_without_node"] /
               max(1, total["content_morphemes"]),
               "role_outside_its_clause": total["role_outside_its_clause"] /
               max(1, total["role_edges_checked"]),
               "connector_unaccounted": total["connector_unaccounted"] /
               max(1, total["connectors"]),
               "negative_unrecorded": total["negative_unrecorded"] /
               max(1, total["negatives"]),
               "question_unmarked": total["question_unmarked"] /
               max(1, total["interrogatives"])},
           "verses_with": {k: len(v) for k, v in verses_hit.items()},
           "samples": {k: random.Random(1).sample(v, min(12, len(v)))
                       for k, v in findings.items()}}
    if PREFIX in ("placeholder", "old"):
        tag = "" if a.lang == "hebrew" else "-greek"
        cur, prev = OUT / f"invariants{tag}.json", \
            OUT / f"invariants{tag}-prev.json"
        old = json.loads(cur.read_text(encoding="utf-8")) \
            if cur.exists() else None
        if old:
            prev.write_text(json.dumps(old, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    else:
        # another graph is compared with the OLD builder's baseline
        tag = "" if a.lang == "hebrew" else "-greek"
        cur = OUT / f"invariants-{PREFIX}{tag}.json"
        base = OUT / f"invariants{tag}.json"
        old = json.loads(base.read_text(encoding="utf-8")) \
            if base.exists() else None
    cur.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n{nv:,} verses, {total['morphemes']:,} morphemes")
    for k in ("lost", "outside_any_clause", "content_without_node",
              "role_outside_its_clause", "connector_unaccounted",
              "negative_unrecorded", "question_unmarked"):
        was = ""
        if old and k in old.get("counts", {}):
            d = total[k] - old["counts"][k]
            was = f"   (drift {d:+,})" if d else "   (no drift)"
        print(f"  {k:26} {total[k]:>8,}  {res['rates'][k]:6.2%}  in "
              f"{len(verses_hit[k]):,} verses{was}")
    print(f"  (accounted, not faults: {total['carried_by_link']:,} words of "
          f"connective phrases carried by their link)")


if __name__ == "__main__":
    main()
