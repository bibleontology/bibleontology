"""The images audit: the Copilot list against what the graph holds
(2026-09-30).

The next list is really long and is an audit to compare against: it mixed in
some people and concepts, but all of it can be checked for completeness. So nothing here writes to the graph. For every
image, concept and person the list names, and every reference it gives:

  in the graph   the graph already keys that passage to the image (its
                 node's own references, or any edge that touches it)
  word there     the image's word stands in the passage -- in the Hebrew or
                 Greek, by the node's anchored words -- but the graph does
                 not key it: a candidate gap, to be read
  not named      the word is not there: Copilot's association, a reading
  bad reference  the reference does not resolve in the Berean text

and a quotation Copilot gives is checked against the Berean's words (a
low match is a paraphrase, or a verse that says something else). The
other direction too: the passages the graph keys that the list never
cites. Principles 17 and 18 hold: an image signifying something is not a
link between images, and a contested literal/figurative case is not
resolved by this list.

    python tools/themes/images_audit.py
      -> docs/review/IMAGES-AUDIT.md, out/images-audit.json
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
sys.path.insert(0, str(ROOT / "tools" / "phrases"))
from messages import corpus  # noqa: E402
from theme_map import check, spans_in  # noqa: E402
from event_nodes import verses, vkey  # noqa: E402

SRC = ROOT / "ontology" / "themes" / "images.md"

# ---- what each key is, and the words to find it by
CONCEPT_THEMES = {"covenant": ["covenant"], "kingdom": ["kingdom"], "temple": ["temple_presence"],
                  "priesthood": ["priesthood"], "sacred_space": ["temple_presence"],
                  "torah": ["law_wisdom"], "prophet": ["prophetic_word"], "spirit": ["spirit"],
                  "word": ["prophetic_word"], "wisdom": ["law_wisdom", "wisdom_literature"],
                  "death": ["sin_exile_death"], "exile": ["sin_exile_death"],
                  "resurrection": ["new_creation"], "judgment": ["judgment"],
                  "mercy_grace": ["mercy_restoration"], "sacrifice": ["sacrifice"],
                  "spiritual_warfare": ["apocalyptic"]}
CONCEPTS = set(CONCEPT_THEMES) | {"holiness", "love", "faith", "hope"}
PEOPLE = {"adam", "eve", "cain", "abel", "cain_and_abel"}
# the words that name a key (for the node lookup and the phrase search)
WORDS = {
    "tree_of_life": ["tree of life"], "tree_of_knowledge": ["tree of the knowledge"],
    "stars": ["star", "stars"], "branches": ["branch", "branches"], "olive_tree": ["olive tree"],
    "fig_tree": ["fig tree"], "mustard_seed": ["mustard seed"], "tares": ["weeds", "tares"],
    "sheaves": ["sheaf", "sheaves"], "thorns": ["thorn", "thorns"], "cornerstone": ["cornerstone"],
    "capstone": ["capstone", "top stone"], "scales": ["scales", "balance", "balances"],
    "keys": ["key", "keys"], "chains": ["chain", "chains"], "path_way": ["path", "way"],
    "holy_of_holies": ["most holy place"], "ark_of_covenant": ["ark of the covenant", "ark"],
    "showbread": ["bread of the presence", "showbread"], "menorah": ["lampstand"],
    "sacrificial_blood": ["blood"], "baptismal_water": ["baptism", "baptized", "washing"],
    "priestly_garments": ["garments", "robes"], "trumpets_gathering": ["trumpet"],
    "shepherd_img": ["shepherd"], "beasts": ["beast", "beasts"], "locusts": ["locust", "locusts"],
    "blindness": ["blind"], "deafness": ["deaf"], "slavery": ["slave", "slaves"],
    "old_self": ["old self"], "new_self": ["new self"], "death_to_sin": ["died to sin", "dead to sin"],
    "new_creature": ["new creation"], "circumcision_of_heart": ["circumcision of the heart",
                                                                 "circumcise your hearts"],
    "firstborn_from_the_dead": ["firstborn from the dead"], "imperishable_seed": ["imperishable seed"],
    "renewal_of_the_mind": ["renewing of your mind"], "groaning_creation": ["groaning"],
    "harvest_of_firstfruits": ["firstfruits"], "wiped_away_tears": ["wipe away every tear"],
    "no_more_sea": ["no longer any sea", "sea was no more"],
    "leaves_for_healing": ["healing of the nations"], "flaming_sword": ["flaming sword"],
    "garments": ["garment", "garments", "clothes", "clothing"],
    "sacred_space": ["holy place"], "torah": ["law"], "prophet": ["prophet", "prophesy", "prophecy"],
    "spiritual_warfare": ["powers", "rulers", "authorities"], "mercy_grace": ["mercy", "grace"],
    # "rose again" (ἀνίστημι, 1Thess 4:14) and "darkened" (σκοτίζω, Rom
    # 1:21) are the same words in other forms
    "resurrection": ["resurrection", "raised", "rose again", "rise again", "risen"],
    "darkness": ["darkness", "dark", "darkened"], "judgment": ["judgment", "judge"],
    "holiness": ["holy", "holiness"], "faith": ["faith", "believe"], "death": ["death", "die"],
    "cain_and_abel": ["cain", "abel"], "exile": ["exile"], "priesthood": ["priest", "priesthood"],
    "firstfruits": ["firstfruits"], "wind": ["wind"], "dust": ["dust"],
}
# Strong's named outright where no English word carries the sense alone
KEYS = {"earthquake": {"h7493", "h7494", "g4578", "g4579"},   # רָעַשׁ, σεισμός
        "flaming_sword": {"h3858"},                           # לַהַט, "whirling sword of flame" (Gen 3:24)
        "capstone": {"h6438"},                                # פִּנָּה, "head of the corner" (Ps 118:22)
        # περιτομή, "circumcision is a matter of the heart" (Rom 2:29)
        "circumcision_of_heart": {"g4061", "g4059", "h4135"},
        "yoke": {"g2086"},                                    # ἑτεροζυγέω, "unequally yoked" (2Cor 6:14)
        # πρωτότοκος: "firstborn from among the dead" (Col 1:18)
        "firstborn_from_the_dead": {"g4416"},
        # ἄφθαρτος: "not of perishable seed, but of imperishable" (1Pet 1:23)
        "imperishable_seed": {"g862"},
        "hope": {"h6960"}}                                    # קָוָה, "wait for the LORD" (Ps 27:14), root of תִּקְוָה
# the list's items under the graph's older names (candlestick: Rev 1:20's
# λυχνία; corner stone: Ps 118:22's פִּנָּה, which Copilot calls both the
# cornerstone and the capstone)
HAND = {"lampstand": ["image_candlestick"], "menorah": ["image_candlestick"],
        "cornerstone": ["image_corner_stone"], "capstone": ["image_corner_stone"]}
SECTION = {  # a pass-2 heading -> its key
    "sacred space / holy place": "sacred_space", "law / torah": "torah", "prophet / prophecy": "prophet",
    "spiritual warfare / powers": "spiritual_warfare", "mercy / grace": "mercy_grace",
    "cain + abel": "cain_and_abel", "tree_of_knowledge": "tree_of_knowledge",
}
SUB = {"clothing": "garments", "exile": "exile", "cherubim": "cherubim", "flaming sword": "flaming_sword",
       "ground": "ground", "dust": "dust", "thorns": "thorns", "sweat": "sweat", "altar": "altar",
       "sacrifice": "sacrifice"}


def key_of_heading(h):
    h = re.sub(r"\(.*?\)", "", h.split(" — ")[0]).strip().lower()
    return SECTION.get(h, h.replace(" ", "_"))


def parse(text):
    """-> [{key, pass, group, ref, claim, spans, problems}]"""
    out, key, pas, group, combined = [], None, None, "", False
    labels = []
    body = text.split("-->", 1)[1]
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            pas = {"# The list": "list", "# Pass 1": "1", "# Pass 2a": "2a", "# Pass 2b": "2b",
                   "# Pass 3": "3", "# Doug": None}.get(next((p for p in ("# The list", "# Pass 1", "# Pass 2a",
                                                                         "# Pass 2b", "# Pass 3", "# Doug")
                                                          if line.startswith(p)), None), None)
            key = None
            continue
        if pas is None or not line:
            continue
        if line.startswith("## "):
            h = line[3:]
            # clothing + exile + ..., ground + dust + ..., altar + sacrifice
            # are split by their subsections; Cain and Abel are one pair
            combined = "+" in h.split(" — ")[0] and key_of_heading(h) != "cain_and_abel"
            key = None if pas in ("list", "3") or combined else key_of_heading(h)
            group = ""
            continue
        if line.startswith("**"):
            group = line.strip("*").strip()
            if combined:
                m = re.match(r"^\d+\.\s+([A-Z ]+?)(?:\s+\(|\s+—|$)", group)
                key = SUB.get(m.group(1).strip().lower()) if m else None
            continue
        if not line.startswith("- "):
            continue
        item = line[2:]
        if pas in ("list", "3"):
            if " — " not in item:
                continue
            lab, rest = item.split(" — ", 1)
            lab = lab.strip()
            labels.append(lab) if pas == "list" else None
            refpart = " ".join(re.findall(r"\(([^()]*\d[^()]*)\)", rest)) if pas == "list" else \
                re.sub(r"\([^()]*\)", "", rest)
            claim = rest
            k = lab
        else:
            if not key:
                continue
            if " — " in item:
                refpart, claim = item.split(" — ", 1)
            else:
                refpart, claim = item, ""
            k = key
        if not refpart.strip():
            continue
        probs = []
        sp = [s for s in spans_in(refpart, probs) if s[1] is not None and check(s, probs, refpart)]
        if sp or probs:
            out.append({"key": k, "pass": pas, "group": group, "ref": refpart.strip(), "claim": claim.strip(),
                        "spans": [[c, list(a), list(b)] for c, a, b in sp], "problems": probs})
    return out, labels


def kind_of(k, labels):
    if k in PEOPLE:
        return "person"
    if k in CONCEPTS:
        return "concept"
    return "image"


def main():
    src = SRC.read_text(encoding="utf-8")
    items, labels = parse(src)
    keys = list(dict.fromkeys(labels + [i["key"] for i in items]))
    C = corpus()

    # ---- the graph: nodes, their references, the edges that touch them
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            ents[r["id"]] = r
    by_name = collections.defaultdict(set)
    for eid, e in ents.items():
        for n in [e.get("name") or ""] + list(e.get("aka") or []):
            by_name[re.sub(r"\s*\(as an image\)", "", n.lower()).strip()].add(eid)
    edges = collections.defaultdict(list)
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            for end in ("src", "dst"):
                edges[r[end]].append(r)
    anchors, top_anchor = {}, {}
    for ln in gzip.open(OUT / "concept-anchors.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        parts = [p for p in r.get("parts", []) if p.get("word") not in ("image", "as", "of", "the", "a")]
        ks = {a[0] for p in parts for a in p.get("anchors", []) if a[2] >= 0.1}
        if ks:
            anchors[r["id"]] = ks
        # each part's leading word, for matching by the original
        if r["id"] in ents and ents[r["id"]]["type"] == "image" and parts \
                and all(p.get("anchors") for p in parts):
            top_anchor[r["id"]] = {max(p["anchors"], key=lambda a: a[2])[0] for p in parts}
    tm = json.loads((OUT / "theme-map.json").read_text(encoding="utf-8"))
    theme_verses = collections.defaultdict(set)
    for t in tm["themes"]:
        for c in t["concepts"]:
            for p in c["passages"]:
                for r in p["refs"]:
                    if r.get("start"):
                        vs = verses({"book": r["book"], "start": r["start"], "end": r["end"]})
                        if len(vs) <= 30:
                            theme_verses[t["id"]] |= set(vs)

    def ref_verses(refs):
        out = set()
        for ref in refs or []:
            probs = []
            for s in spans_in(ref, probs):
                if s[1] is not None and check(s, probs, ref):
                    vs = verses({"book": s[0], "start": list(s[1]), "end": list(s[2])})
                    if len(vs) <= 30:
                        out |= set(vs)
        return out

    def nodes_for(k, kind):
        words = WORDS.get(k, [k.replace("_", " ")])
        ids = set()
        cands = [f"image_{k}", k] + [f"image_{w.replace(' ', '_')}" for w in words] + \
                [w.replace(" ", "_") for w in words]
        ids |= {c for c in cands if c in ents}
        for w in words + [k.replace("_", " ")]:
            ids |= by_name.get(w, set())
        if kind == "image":
            imgs = {i for i in ids if ents[i]["type"] == "image"}
            if not imgs:
                # by the original's word, not the English name: the graph's
                # older names ("corner stone", "candlestick") are the list's
                # cornerstone and lampstand
                # the node's word must be the list word's DOMINANT rendering,
                # not any rendering: "ground" sometimes renders עָפָר, which
                # is not the ground image; "deaf" once a root of the plough
                dom = set()
                for w in WORDS.get(k, [k.replace("_", " ")]):
                    c = tags.get(w)
                    if c and " " not in w:
                        n = sum(c.values())
                        dom |= {s for s, x in c.items() if x / n >= 0.25}
                imgs = {i for i, tops in top_anchor.items() if tops <= dom and i not in bad_anchor} \
                    if dom else set()
            # the graph's older-English names, by hand: a verse test matched
            # them but also matched deafness to the plough (two roots spelled
            # חרשׁ) and hunger to Pharaoh's thin cows (famine in the verse)
            imgs |= {i for i in HAND.get(k, ()) if i in ents}
            return imgs, ids - imgs
        return ids, set()

    # ---- the original's words for an English word: the Strong's numbers the
    # Berean editors tagged on it and its inflections ("loved" as well as
    # "love", Deut 7:8; "shook" is not "earthquake" in English but is רָעַשׁ,
    # Ps 68:8 -- so a key may also be named outright)
    # Two sources, both already on disk: the Berean editors' Strong's tags
    # on their English (partial: Deut 7:8's "loved" carries none), and
    # MACULA's own English gloss on EVERY word ("loved" is אַהֲבָה there).
    # One table for the audit and the search: out/word-aliases.json
    # (tools/aliases.py), MACULA's glosses deciding and the Berean's tags only
    # where MACULA is silent -- the audit's first table took the Berean's
    # tags as equal, and they are displaced in places ("the earth" carries
    # כֹּל 151 times)
    tags = collections.defaultdict(collections.Counter)
    for w, ks in json.loads((OUT / "word-aliases.json").read_text(encoding="utf-8"))["forms"].items():
        for s, x in ks:
            tags[w][s] = x

    def keys_for(k):
        out = set(KEYS.get(k, ()))
        for w in WORDS.get(k, [k.replace("_", " ")]):
            if " " in w:
                continue
            # each form on its own tags: pooled, "root" swamps "rooted"
            # (ῥιζόω, Eph 3:17). A common rendering (3+ tags, a tenth of
            # them), or a rare word that carries a large share: ἑτεροζυγέω
            # is "unequally yoked" once (2Cor 6:14)
            for tok, c in tags.items():
                if tok == w or (tok.startswith(w) and len(tok) - len(w) <= 3):
                    n = sum(c.values())
                    out |= {s for s, x in c.items() if (x >= 3 and x / n >= 0.1) or x / n >= 0.3}
        return out

    # ---- an anchor its own node's name does not render: concept-anchors
    # gives image_dust אֶרֶץ "earth" (its aka "dust of the earth" outvoting
    # "dust"), and image_harvest the same. Such a node is not matched by its
    # anchor here, and is reported: its card lists the wrong word's verses.
    bad_anchor = {}
    for i, tops in top_anchor.items():
        nm = re.sub(r"\s*\(as an image\)", "", ents[i]["name"].lower())
        own = set()
        for w in re.findall(r"[a-z']+", nm):
            if w in ("the", "a", "an", "of", "as", "and", "his", "her", "their", "my", "your"):
                continue
            # the name word and its inflections ("anointing" is מָשַׁח's
            # "anoint"; a stem cut back to four letters reaches it)
            stem = w[:max(4, len(w) - 3)]
            for tok, c in tags.items():
                if tok == w or (tok.startswith(stem) and abs(len(tok) - len(w)) <= 3):
                    n = sum(c.values())
                    own |= {s for s, x in c.items() if x / n >= 0.1 or x >= 5}
        if own and not (tops & own):
            bad_anchor[i] = sorted(tops)

    phrase_cache = {}

    def word_verses(k):
        """the verses the key's words stand in: the Berean's words and,
        through them, the Hebrew and Greek the Berean renders so"""
        if k not in phrase_cache:
            vs = set()
            for w in WORDS.get(k, [k.replace("_", " ")]):
                e, _sig, orig = C.find(re.findall(r"[a-z']+", w.lower()))
                vs |= {v for v, trs in e.items() if "BSB" in trs} | set(orig)
            phrase_cache[k] = vs
        return phrase_cache[k]

    def has_word(v, keys_, k):
        if keys_ and any(kk in keys_ for _p, kk, *_ in C.words.get(C.mac(v), [])):
            return True
        return v in word_verses(k)

    STOP = set("the a an and of to in is are was were be his her their our your my you he she it they we i "
               "who that this with for on as by from not no all will shall have has had".split())
    results = {}
    for k in keys:
        kind = kind_of(k, labels)
        main_ids, other_ids = nodes_for(k, kind)
        ev = set()
        for i in main_ids:
            ev |= ref_verses(ents[i].get("refs"))
            for r in edges.get(i, []):
                ev |= ref_verses(r.get("refs"))
        for tid in CONCEPT_THEMES.get(k, []):
            ev |= theme_verses[tid]
        akeys = set().union(*(anchors.get(i, set()) for i in main_ids)) if main_ids else set()
        akeys |= keys_for(k)
        rows = []
        for it in (x for x in items if x["key"] == k):
            if not it["spans"]:
                rows.append(dict(it, grade="bad reference", size=0, hits=[], quote=None))
                continue
            vs = []
            for c, a, b in it["spans"]:
                vs += verses({"book": c, "start": a, "end": b})
            vs = [v for v in vs if C.shown(v)]
            hit = [v for v in vs if v in ev]
            if hit:
                grade = "in the graph"
            elif len(vs) > 6:
                # a chapter holds the word by default ("Exod 19-20" has a
                # mountain in it): not a verse the graph could have keyed
                grade = "broad passage"
            elif any(has_word(v, akeys, k) for v in vs):
                grade = "word there"
            else:
                grade = "not named"
            word_at = [v for v in vs if has_word(v, akeys, k)][:4]
            # the quotation against the Berean's words
            q = None
            quotes = re.findall(r"[\"“]([^\"”]{6,})[\"”]", it["claim"])
            if quotes and len(vs) <= 12:
                bsb = " ".join(C.shown(v) for v in vs).lower()
                bw = set(re.findall(r"[a-z']+", bsb))
                qw = [w for qq in quotes for w in re.findall(r"[a-z']+", qq.lower()) if w not in STOP and len(w) > 2]
                if qw:
                    q = round(sum(1 for w in qw if w in bw) / len(qw), 2)
            rows.append(dict(it, grade=grade, size=len(vs), hits=hit[:4], word_at=word_at, quote=q))
        cited = set()
        for r in rows:
            for c, a, b in r["spans"]:
                cited |= set(verses({"book": c, "start": a, "end": b}))
        results[k] = {"key": k, "kind": kind, "nodes": sorted(main_ids), "other_nodes": sorted(other_ids)[:6],
                      "anchors": sorted(akeys), "graph_verses": len(ev),
                      "graph_only": sorted(ev - cited, key=vkey), "rows": rows}
        g = collections.Counter(r["grade"] for r in rows)
        print(f"  {kind:7} {k:24} nodes {len(main_ids):2} ev {len(ev):4}  "
              + ", ".join(f"{a} {b}" for a, b in g.most_common()), flush=True)
    # ---- the other direction: the graph's images the list never names
    named = {i for x in results.values() for i in x["nodes"]}
    unnamed = sorted((i for i, e in ents.items() if e["type"] == "image" and i not in named),
                     key=lambda i: -(len(ents[i].get("refs") or []) + len(edges.get(i, []))))
    extra = [{"id": i, "name": ents[i]["name"], "refs": len(ents[i].get("refs") or []),
              "edges": len(edges.get(i, []))} for i in unnamed]
    bad = [{"id": i, "name": ents[i]["name"], "anchor": a} for i, a in sorted(bad_anchor.items())]
    json.dump({"results": results, "graph_only_images": extra, "bad_anchors": bad},
              open(OUT / "images-audit.json", "w", encoding="utf-8"), ensure_ascii=False)
    write_report(results, labels, C, extra, bad)


def write_report(results, labels, C, extra, bad):
    allrows = [r for x in results.values() for r in x["rows"]]
    g = collections.Counter(r["grade"] for r in allrows)
    L = ["# Images audit: the Copilot list against the graph (2026-09-30)", "",
         "Source: ontology/themes/images.md (a Copilot thread; an audit list, not a build list). "
         "Built by `tools/themes/images_audit.py`. Nothing here changes the graph.", "",
         "Grades, per reference: **in the graph** (the graph keys that passage to the image); "
         "**word there** (the image's word stands there in the Hebrew/Greek, but the graph does "
         "not key it -- a candidate gap, unread); **not named** (the word is not in the passage: "
         "Copilot's association); **bad reference**. *quote* is the share of Copilot's quoted content "
         "words found in the Berean text of the passage.", "",
         f"References: {len(allrows)} -- " + ", ".join(f"{a} {b}" for a, b in g.most_common()), ""]
    for kind, title in (("image", "Images"), ("concept", "Concepts the thread drifted into"),
                        ("person", "People the thread drifted into")):
        xs = [x for x in results.values() if x["kind"] == kind]
        L += [f"## {title}", "", "| key | graph node | keyed verses | refs | in graph | word there | broad | not named | bad | graph-only |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for x in xs:
            gg = collections.Counter(r["grade"] for r in x["rows"])
            L.append(f"| {x['key']} | {', '.join(x['nodes'][:3]) or '**none**'} | {x['graph_verses']} | "
                     f"{len(x['rows'])} | {gg['in the graph']} | {gg['word there']} | {gg['broad passage']} | "
                     f"{gg['not named']} | {gg['bad reference']} | {len(x['graph_only'])} |")
        L.append("")
    L += [f"## The graph's images the list does not name ({len(extra)})", "",
          "Not Copilot's omissions: 2026-09-30, the list Copilot worked on was originally "
          "generated with a bound, so it is not expected to be comprehensive. The list "
          "tests the graph; these are what the list's bound left out.", "",
          "Most cited first (own references + edges): " + "; ".join(
              f"{e['name']} ({e['refs']}+{e['edges']})" for e in extra[:60]), ""]
    L += ["## Image nodes anchored to a word that is not their own", "",
          "Found by this audit, a fault in out/concept-anchors.jsonl.gz, not in the list: the node's "
          "leading anchored word is one its own name never renders (image_dust anchored to אֶרֶץ "
          "'earth' through its alias 'dust of the earth'). The card's \"Where the text speaks of it\" "
          "reads these anchors, so it lists the wrong word's verses (the dust card: 2,476 verses).", "",
          "**Verified by reading (6):** dust -> אֶרֶץ 'earth'; harvest -> אֶרֶץ; stars -> שָׁמַיִם "
          "'heaven'; mirror -> רָאָה 'see'; harbor -> יָם 'sea'; one viper -> דּוֹר 'generation'.", "",
          f"The automatic check that surfaced them flags more ({len(bad)} on this run) and is only a "
          "way to find candidates: it compares a node's leading word with the words its own name "
          "renders, and misses correct ones (ox -> שׁוֹר, refuge -> חָסָה are right). Candidates: "
          + "; ".join(f"{b['name']} ({', '.join(b['anchor'])})" for b in bad), "",
          "## Detail", ""]
    for x in results.values():
        L.append(f"### {x['key']} ({x['kind']})")
        L.append(f"Graph: {', '.join(x['nodes']) or 'no node'}"
                 + (f" · also {', '.join(x['other_nodes'])}" if x["other_nodes"] else "")
                 + f" · anchors {', '.join(x['anchors'][:6]) or '—'} · {x['graph_verses']} keyed verses")
        for r in x["rows"]:
            extra = ""
            if r["grade"] == "word there":
                extra = " · word at " + ", ".join(r["word_at"])
            if r.get("quote") is not None and r["quote"] < 0.5:
                extra += f" · **quote {r['quote']}**"
            L.append(f"- [{r['pass']}] {r['ref']} -- *{r['grade']}*{extra} -- {r['claim'][:70]}")
        if x["graph_only"]:
            L.append(f"- graph keys, list never cites ({len(x['graph_only'])}): "
                     + ", ".join(x["graph_only"][:12]))
        L.append("")
    (ROOT / "docs" / "review" / "IMAGES-AUDIT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("references", len(allrows), dict(g))


if __name__ == "__main__":
    main()
