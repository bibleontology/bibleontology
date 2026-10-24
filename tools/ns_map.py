"""THE SCHEMA MAP: the four vocabularies as pictures, drillable from the layers
down to each kind, every box a link to its entry on the /ns pages
(2026-10-20: a comprehensive, drillable, multi-layer schema; understandable to
someone who knows nothing about RDF or the semantic web; the same view
meaningful to practitioners; multi-level given the size of the schema, with
grouping because it is a lot; and, the text-based view already being on the
site, not a lot of lists in this diagram but links to those views at each
spot).

So: pictures only. Every box links to the term's entry at /ns/<vocabulary>
(the text view the site already has) or to the next picture down; hovering a
box shows its plain definition. Nothing here is a list of terms.

  level 0   the four layers
  level 1   each layer: the text's five families of part and its link
            families; the broadest kinds of thing; six groups of links; what
            a claim carries and the scales it draws from
  level 2   inside each: the kinds of part, a kind's subtree, a group's
            families, a family of links' kinds

Generated, never drawn by hand, so it cannot drift: the vocabularies as the
1.2.0 release publishes them (the generators run into memory, the served files
restored), the relation families from relationship_types.yaml, live counts
from the store. A term not reachable from the map is reported.

    python tools/ns_map.py [out.html]     -> docs/review/schema-map.html (default)
"""
import collections
import datetime
import html
import json
import math
import re
import sys
from pathlib import Path

import rdflib
import yaml
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ns_common  # noqa: E402
import ns_relation  # noqa: E402
import vocab_inventory as V  # noqa: E402

e = html.escape
BASES = V.BASES
SITE = "https://bibleontology.org"
LAYERS = [
    ("structure", "The text", "words, phrases, clauses, speeches and passages, read from the original languages",
     "How each verse is built, read from the Hebrew, Aramaic and Greek: its parts, and the links between them "
     "(because, so that, when)."),
    ("meaning", "What it is about", "people, places, groups, concepts, images and events: the cards",
     "The kinds of thing the text speaks of, each a card, and the readings made of them."),
    ("relation", "What the text says", "the links between cards, each with its verse",
     "The kinds of link between two cards, each pointing to its verse: family, rule, travel, speech, and the "
     "statements read from single clauses."),
    ("claim", "Who says it, and how sure", "who says each link, how sure it is, stated or only described",
     "Every link is a claim: who says it (the narrator, a speaker, a reader), how sure it is, and whether it is "
     "stated or only described (a promise, a command)."),
]


def lit(g, s, *ps):
    for p in ps:
        for o in g.objects(s, p):
            return str(o)
    return ""


def local(u):
    return re.split(r"[#/]", str(u))[-1]


def label(g, s):
    return lit(g, s, RDFS.label, SKOS.prefLabel) or local(s)


def tip(g, s):
    return lit(g, s, SKOS.definition, RDFS.comment)


def page(vocab, s):
    return f"{SITE}/ns/{vocab}#{local(s)}"


def load():
    gen, _notes = V.generated()
    g = {n: rdflib.Graph().parse(data=gen[n].decode("utf-8"), format="turtle") for n in ("structure", "relation", "meaning")}
    g["claim"] = rdflib.Graph().parse(ROOT / "ontology" / "claim" / "claim.ttl")
    # every published check, as /ns/shapes will hold them from 1.2.0
    shapes = rdflib.Graph().parse(data=gen["structure-shapes"].decode("utf-8"), format="turtle")
    shapes += ns_relation.shapes()[0]
    shapes += rdflib.Graph().parse(ROOT / "ontology" / "claim" / "shapes.ttl")
    shapes += rdflib.Graph().parse(ROOT / "ontology" / "meaning" / "shapes.ttl")
    # the structure shapes run on no published data yet (D7): counted apart
    SH = rdflib.URIRef("http://www.w3.org/ns/shacl#NodeShape")
    n_struct = len(set(rdflib.Graph().parse(data=gen["structure-shapes"].decode("utf-8"),
                                            format="turtle").subjects(RDF.type, SH)))
    return g, shapes, n_struct


def arrow(x1, y1, x2, y2, text="", dashed=False):
    """A labelled arrow, drawn with its own head (no markers, which some
    renderers drop)"""
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(a), y2 - 9 * math.sin(a)
    px, py = 5 * math.sin(a), -5 * math.cos(a)
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    out = (f'<path d="M{x1:.0f} {y1:.0f} L{hx:.0f} {hy:.0f}" style="stroke:var(--muted);stroke-width:1.6;fill:none"{dash}/>'
           f'<path d="M{x2:.0f} {y2:.0f} L{hx + px:.0f} {hy + py:.0f} L{hx - px:.0f} {hy - py:.0f} z" style="fill:var(--muted)"/>')
    if text:
        out += (f'<text class="sm" x="{(x1 + x2) / 2:.0f}" y="{(y1 + y2) / 2 - 6:.0f}" text-anchor="middle">'
                f'{e(text)}</text>')
    return out


def standards_view(g, shapes, n_struct):
    """BUILT ON OPEN STANDARDS (2026-10-20: built after the
    survey): a second view of the same map, one picture per standard showing
    where it applies, each box linking into our terms and each standard to its
    specification. Counts are computed; the examples are real records."""
    import gzip
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    DQV = rdflib.Namespace("http://www.w3.org/ns/dqv#")
    claims = gzip.open(ROOT / "out" / "export" / "claims-rdf12.trig.gz", "rt", encoding="utf-8").read()
    n_claims = claims.count("a claim:Claim")
    n_gen = claims.count("prov:wasGeneratedBy")
    n_attr = claims.count("prov:wasAttributedTo")
    cw = gzip.open(ROOT / "out" / "export" / "card-words.trig.gz", "rt", encoding="utf-8").read()
    n_meas = cw.count("dqv:QualityMeasurement")
    n_shapes = len(set(shapes.subjects(RDF.type, SH.NodeShape)))
    n_class = sum(1 for n in g for s in g[n].subjects(RDF.type, OWL.Class) if str(s).startswith(BASES[n]))
    n_obj = sum(1 for n in g for s in g[n].subjects(RDF.type, OWL.ObjectProperty) if str(s).startswith(BASES[n]))
    n_dat = sum(1 for n in g for s in g[n].subjects(RDF.type, OWL.DatatypeProperty) if str(s).startswith(BASES[n]))
    gr = g["relation"]
    n_dom = len({s for s, _o in gr.subject_objects(RDFS.domain) if str(s).startswith(BASES["relation"])})
    n_rng = len({s for s, _o in gr.subject_objects(RDFS.range) if str(s).startswith(BASES["relation"])})
    gc, gm = g["claim"], g["meaning"]
    schemes = sorted(gc.subjects(RDF.type, SKOS.ConceptScheme), key=lambda u: local(u))
    n_concepts = sum(len(list(gc.subjects(SKOS.inScheme, s))) for s in schemes)
    metrics = sorted(gm.subjects(RDF.type, DQV.Metric), key=lambda u: local(u))
    C, M, R = (lambda t: f"{SITE}/ns/claim#{t}"), (lambda t: f"{SITE}/ns/meaning#{t}"), (lambda t: f"{SITE}/ns/relation#{t}")
    STD = [
        ("rdf12", "RDF 1.2 (and 1.1)", "triple terms: describe a statement without asserting it",
         f"{n_claims:,} claims, each reifying its triple", "https://www.w3.org/TR/rdf12-concepts/"),
        ("prov", "PROV-O", "who said it, and which run produced it",
         f"{n_attr:,} claims attributed · {n_gen:,} tied to a run", "https://www.w3.org/TR/prov-o/"),
        ("shacl", "SHACL", "published checks the data must pass",
         f"{n_shapes} shapes; {n_shapes - n_struct} run on the data, with planted faults", "https://www.w3.org/TR/shacl/"),
        ("skos", "SKOS", "controlled lists: how sure, said as, kind of act",
         f"{len(schemes)} lists · {n_concepts} values", "https://www.w3.org/TR/skos-reference/"),
        ("dqv", "DQV", "the filter as data: a measurement on every card word",
         f"{n_meas:,} measurements · {len(metrics)} metrics · 1 policy", "https://www.w3.org/TR/vocab-dqv/"),
        ("owl", "OWL 2", "classes and properties typed for tools",
         f"{n_class} classes · {n_obj + n_dat} properties", "https://www.w3.org/TR/owl2-overview/"),
    ]
    # MACULA is data, not a standard (the committee's third sitting, D9): it
    # leads "The sources it is read from" instead
    out = []
    tiles = [(name, f"{plain} · {count}", f"#std-{k}", plain) for k, name, plain, count, _u in STD]
    tiles.append(("Maps to", "schema.org, FOAF, CIDOC CRM, OntoLex, Web Annotation: the alignment file",
                  "#std-maps", ""))
    tiles.append(("The sources it is read from", "MACULA's Hebrew and Greek, the Berean Standard Bible, STEP Bible, "
                  "Strong's numbers, WordNet", "#std-sources", ""))
    c, h = grid(tiles, cols=3, h=60)
    out.append(section("standards", "Built on open standards", [],
                       "The same schema, seen by the standards it is built on. Each box opens a picture of where that "
                       "standard applies; its boxes open our terms, and its heading links the standard itself.")
               + svg(c, h, "The open standards the schema is built on"))

    def head(k, name, url):
        return (f'<h2 id="std-{k}">{e(name)} <a class="master" href="{e(url)}">the standard ›</a></h2>'
                f'<p class="crumbs"><a href="#standards">Built on open standards</a> › {e(name)}</p>')
    # RDF 1.2: one claim stated, one only described
    # the stated example is a plain narrative clause (D2(a): John 3:16 stands
    # inside Jesus's words as the Berean marks them, a crux either way)
    pic = [box(10, 20, 250, 60, "Saul loved David", "1 Samuel 16:21 · the narrator's claim", C("Claim"), ""),
           box(340, 20, 260, 60, "Saul · states · David", "a triple term: <<( … )>>", "", "the statement, described"),
           box(700, 20, 190, 60, "the default graph", "stated as fact", C("narrator"), ""),
           arrow(260, 50, 338, 50, "rdf:reifies"), arrow(600, 50, 698, 50, "also asserted"),
           box(10, 120, 250, 60, "Job, condemned by his own mouth", "Job 15:6 · Eliphaz's claim", C("claimedBy"), ""),
           box(340, 120, 260, 60, "Job · described as · condemned by his own mouth", "a triple term: <<( … )>>", "",
               "the statement, described"),
           box(700, 120, 190, 60, "asserted nowhere", "his claim; the narrator does not state it", "", ""),
           arrow(260, 150, 338, 150, "rdf:reifies"), arrow(600, 150, 698, 150, "not asserted", dashed=True)]
    out.append(head("rdf12", "RDF 1.2, and 1.1 beside it", "https://www.w3.org/TR/rdf12-concepts/")
               + f'<p class="lead">Every claim reifies its statement as a triple term, so the statement can be described '
                 f'without being asserted. Only what the text itself states is also asserted; a speaker\'s claim, '
                 f'a reader\'s reading, a promise or a command stays described. {n_claims:,} claims. RDF 1.2 is a W3C '
                 f'Candidate Recommendation, so the same claims are also published in RDF 1.1, for stores without '
                 f'triple terms: there each voice is a named graph, and a speaker\'s claim stays apart from the '
                 f'narrator\'s only if the store keeps its default graph apart from the named ones (Apache Jena does; '
                 f'RDF4J joins them). Everything else (the vocabularies, the checks, the typed records) is RDF 1.1 '
                 f'Turtle.</p>'
               + svg("".join(pic), 200, "RDF 1.2 triple terms: stated and described"))
    # PROV-O
    pic = [box(10, 10, 250, 60, "Job, condemned by his own mouth", "Job 15:6 · a claim", C("Claim"), ""),
           box(480, 10, 240, 60, "Eliphaz the Temanite", "who says it", C("claimedBy"), ""),
           arrow(260, 40, 478, 40, "claimedBy ⊑ wasAttributedTo"),
           box(10, 110, 250, 60, "Saul loved David", "1 Samuel 16:21 · a claim", C("Claim"), ""),
           box(400, 110, 240, 60, "lift-2026-10-19", "prov:Activity · the run", "",
               "statements lifted from the clauses, judged by two models, every end checked"),
           box(700, 110, 190, 60, "Claude Sonnet 5.5, Claude Haiku 5.5", "prov:SoftwareAgent", "", "the models that judged"),
           arrow(260, 140, 398, 140, "prov:wasGeneratedBy"), arrow(640, 140, 698, 140, "associated")]
    out.append(head("prov", "PROV-O", "https://www.w3.org/TR/prov-o/")
               + f'<p class="lead">Who says a claim is a PROV attribution: claim:claimedBy, claim:reader and '
                 f'claim:voiceOf are kinds of prov:wasAttributedTo, and the export also states prov:wasAttributedTo '
                 f'outright, for tools without a reasoner. A claim a run produced names the run, and the run names '
                 f'its models. {n_attr:,} claims attributed; {n_gen:,} tied to a run.</p>'
               + svg("".join(pic), 210, "PROV-O in the claims"))
    # SHACL
    told = rdflib.URIRef(R("told_subjectShape"))
    allowed = [shapes.value(b, SH["class"]) for b in rdflib.collection.Collection(shapes, shapes.value(told, SH["or"]))]
    allowed = sorted((label(gm, u) for u in allowed), key=str.lower)
    pic = [box(330, 70, 240, 56, "told", "a kind of link", R("told"), tip(gr, rdflib.URIRef(R("told")))),
           box(10, 64, 250, 60, "its subject is one of:", " · ".join(allowed), "", "the shape's list, sh:or")]
    pic.append(arrow(260, 98, 328, 98, "sh:or"))
    pic += [box(640, 10, 250, 70, "a person told", "passes", "", ""),
            box(640, 110, 250, 70, "a place told", "rejected: the test's planted fault", "", ""),
            arrow(570, 90, 638, 45, ""), arrow(570, 108, 638, 145, "", dashed=True)]
    out.append(head("shacl", "SHACL", "https://www.w3.org/TR/shacl/")
               + f'<p class="lead">Where RDFS cannot say "either", a published shape can: the subject of "told" must be '
                 f'one of {len(allowed)} kinds. {n_shapes} shapes are published at '
                 f'<a href="{SITE}/ns/shapes">/ns/shapes</a>; {n_shapes - n_struct} of them run against the published '
                 f'data, each test planting a fault that must be caught, and the {n_struct} structure shapes wait for '
                 f'the structure export.</p>'
               + svg("".join(pic), 200, "A SHACL either/or rule"))
    # SKOS
    sitems = [(label(gc, s).capitalize(), f"{len(list(gc.subjects(SKOS.inScheme, s)))} values: "
               + ", ".join(sorted(label(gc, m) for m in gc.subjects(SKOS.inScheme, s))[:4]) + "…",
               f"#sch-{local(s)}", tip(gc, s)) for s in schemes]
    c, h = grid(sitems, cols=3, h=70)
    out.append(head("skos", "SKOS", "https://www.w3.org/TR/skos-reference/")
               + '<p class="lead">The values a claim may take are controlled lists, each a concept scheme with a '
                 'definition per value: how sure a claim is, the force it is said with, the broad kind of act its '
                 'verb names.</p>' + svg(c, h, "The SKOS concept schemes"))
    # DQV
    pic = [box(10, 70, 190, 60, "ἀγάπη on “love”", "a card word", M("CardWord"), "a word anchoring a card"),
           box(250, 70, 200, 60, "measured: 0.16", "dqv:QualityMeasurement", "",
               "the share of the word's renderings that render the card's name"),
           box(620, 10, 270, 60, "card word share", "dqv:Metric", M("cardWordShare"), tip(gm, rdflib.URIRef(M("cardWordShare")))),
           box(620, 130, 270, 60, "the filter policy: cut 0.15", "dqv:QualityPolicy · so ἀγάπη is shown by default",
               M("filterPolicy"), ""),
           arrow(200, 100, 248, 100), arrow(450, 90, 618, 40, "dqv:isMeasurementOf"),
           arrow(450, 110, 618, 160, "0.16 ≥ 0.15")]
    out.append(head("dqv", "DQV", "https://www.w3.org/TR/vocab-dqv/")
               + f'<p class="lead">What a card shows first is decided by a published rule, not hidden in code: every '
                 f'card word carries its measured share and the tier it is shown in, and the policy names the cut. A '
                 f'published query rebuilds the shown view exactly, and a published shape checks that no word shown '
                 f'by default falls under the cut; a planted weak word must fail it. {n_meas:,} measurements.</p>' + svg("".join(pic), 210, "DQV: the filter as data"))
    # OWL
    c, h = grid([("Classes", f"{n_class} typed as owl:Class", f"{SITE}/ns/meaning", ""),
                 ("Properties", f"{n_obj} object · {n_dat} datatype", f"{SITE}/ns/relation", ""),
                 ("Domains and ranges", f"only where one class is certain: {n_dom} and {n_rng} on links",
                  f"{SITE}/ns/relation", ""),
                 ("No inference relied on", "checking is SHACL's work, not a reasoner's", f"{SITE}/ns/shapes", "")],
                cols=2, w=436, h=56)
    out.append(head("owl", "OWL 2", "https://www.w3.org/TR/owl2-overview/")
               + '<p class="lead">Every term is typed so OWL tools read it rightly. Nothing is derived by a reasoner: '
                 'where a link may join several kinds, the list is a SHACL shape, because in RDFS two domains mean '
                 'both, not either.</p>' + svg(c, h, "OWL typing"))
    # MAPS TO and THE SOURCES follow; MACULA, the first source, is drawn there
    # MAPS TO (the alignment file, tools/ns_align.py; the alignment file
    # later adds its "maps to" part): how many of our terms map to each
    # standard, and how near, each box opening that standard's table
    import ns_align
    _pre, arows, _un = ns_align.load()
    built = ns_align.stated(g)
    items = []
    for pre, name, _home in ns_align.VOCABS:
        mine = [m for m in arows if m["theirs"].startswith(pre + ":")]
        own = [b for b in built if b[2].startswith(pre + ":")]
        kinds = collections.Counter(m["match"] for m in mine)
        items.append((f"{name} · {len(mine) + len(own)}",
                      ", ".join(f"{n} {ns_align.PLAIN[k]}" for k, n in kinds.most_common())
                      + (f", {len(own)} built into the vocabularies" if own else ""),
                      f"{SITE}/ns/alignment#{pre}", ""))
    c, h = grid(items, cols=3, h=60)
    out.append(f'<h2 id="std-maps">Maps to <a class="master" href="{SITE}/ns/alignment">the alignment file: '
               f'/ns/alignment ›</a></h2>'
               '<p class="crumbs"><a href="#standards">Built on open standards</a> › Maps to</p>'
               f'<p class="lead">Where a term here has a near equivalent in a standard vocabulary, the alignment file '
               f'says which and how near, as SKOS mappings: {len(arows)} mappings, every target checked against its '
               f'specification, and no exact matches. A mapping commits a reasoner to nothing beyond typing both ends '
               f'as skos:Concept, which SKOS itself entails.</p>'
               + svg(c, h, "What the schema maps to"))
    # THE OTHER SOURCES (2026-10-20: the other sources after MACULA, such as
    # Strong's and the Berean, are mentioned): said as About credits them, each
    # in its licence's words (About is the authority; change one, change both)
    SRC = [("Berean Standard Bible", "the English shown, with its editors' headings, quotation notes and parallels · "
            "public domain", "https://bereanbible.com"),
           ("STEP Bible lexicons", "the Translators Brief lexicon entry on every word card · Tyndale House, Cambridge · "
            "CC BY 4.0", "https://www.STEPBible.org"),
           ("TIPNR, STEP Bible's names", "which James a verse means · Tyndale House, Cambridge · CC BY 4.0",
            "https://www.STEPBible.org"),
           ("Strong's numbers", "James Strong (1890): the numbering that lets every one of these datasets speak to the "
            "others", ""),
           ("WordNet", "the broad classes of things and the kinds of act a verb names, reached through each word's "
            "English gloss · Princeton University", "https://wordnet.princeton.edu"),
           ("ASV, WEB and YLT", "the other English the phrase search reads · public domain", "https://ebible.org")]
    c, h = grid([(t, s, u, "") for t, s, u in SRC], cols=3, h=60)
    # MACULA, first: the original languages, which decide wherever a
    # translation differs ("the original arbitrates"); its texts named (D9)
    pic = [box(10, 50, 230, 60, "וַיֶּאֱהָבֵהוּ", "a word of 1 Samuel 16:21", "", ""),
           box(320, 50, 260, 60, "אָהֵב · qal wayyiqtol", "lemma, Strong's, morphology", f"{SITE}/word/H157", ""),
           box(660, 50, 230, 60, "the clause, the statement", "everything above, read from it", "#L-structure", ""),
           arrow(240, 80, 318, 80, "MACULA"), arrow(580, 80, 658, 80, "the floor")]
    out.append('<h2 id="std-sources">The sources it is read from</h2>'
               '<p class="crumbs"><a href="#standards">Built on open standards</a> › The sources</p>'
               '<h3 id="std-macula">MACULA <a class="master" href="https://github.com/Clear-Bible/macula-hebrew">'
               'Hebrew ›</a> <a class="master" href="https://github.com/Clear-Bible/macula-greek">Greek ›</a></h3>'
               '<p class="lead">Every word, its grammar and its sentence structure come from the MACULA Hebrew and '
               'Greek Linguistic Datasets, © Biblica, Inc., CC BY 4.0, and the original they give decides wherever a '
               'translation differs. Their texts are the Westminster Leningrad Codex and the Nestle 1904 Greek New '
               'Testament, with the J. Alan Groves Center\'s Hebrew syntax and the Open Scriptures Hebrew Bible '
               'morphology. The structure layer is read from them.</p>' + svg("".join(pic), 130, "MACULA as the data")
               + '<h3>Beside it</h3><p class="lead">Each under its own terms.</p>'
               + svg(c, h, "The sources the graph is read from"))
    return out


def store_facts():
    ents, counts = {}, collections.Counter()
    # every entity file, as the entities export reads them (2026-10-22): the
    # events, themes and patterns kept apart are records too
    first = ROOT / "ontology" / "entities" / "entities.jsonl"
    for p in [first] + sorted(q for q in first.parent.glob("*.jsonl") if q != first):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                ents.setdefault(x["id"], x)
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if not (r.get("held") or r.get("described")):
                    counts[r.get("type")] += 1
    return counts, collections.Counter(x.get("type") for x in ents.values())


# TEXT THAT FITS (not all text fit in the boxes): a box's words wrap
# to its width, by an average glyph width for each font, and the box grows to
# hold them, rather than being cut off
TITLE_PX, SUB_PX = 7.6, 6.5


def wrap(s, n, most=3):
    words, lines, cur = str(s).split(), [], ""
    for w_ in words:
        if cur and len(cur) + 1 + len(w_) > n:
            lines.append(cur)
            cur = w_
        else:
            cur = f"{cur} {w_}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > most:
        lines = lines[:most]
        lines[-1] = lines[-1][:max(1, n - 1)] + "…"
    return [ln if len(ln) <= n else ln[:n - 1] + "…" for ln in lines]


def lines_for(w, title, sub):
    return wrap(title, int((w - 24) / TITLE_PX)), (wrap(sub, int((w - 24) / SUB_PX)) if sub else [])


def need(w, title, sub):
    t, s = lines_for(w, title, sub)
    return 14 + 17 * len(t) + 15 * len(s) + 8


def box(x, y, w, h, title, sub="", href="", hint="", strong=False, color=None, dim=False):
    style = f' style="stroke:{color};stroke-width:2"' if color else (' style="stroke:var(--accent);stroke-width:2"' if strong else "")
    tl, sl = lines_for(w, title, sub)
    h = max(h, need(w, title, sub))
    ty = y + 20 if sub or len(tl) > 1 else y + h / 2 + 5
    parts = [f'<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}" rx="9"{style}/>']
    for i, ln in enumerate(tl):
        parts.append(f'<text x="{x + 12}" y="{ty + 17 * i:.0f}" style="font-weight:600;font-size:14px">{e(ln)}</text>')
    for i, ln in enumerate(sl):
        parts.append(f'<text class="sm" x="{x + 12}" y="{ty + 17 * len(tl) + 15 * i + 1:.0f}">{e(ln)}</text>')
    t = "".join(parts)
    if hint:
        t = f"<title>{e(hint)}</title>" + t
    # NOT BUILT, FADED (2026-10-20: proposed, withdrawn and deferred terms are
    # shaded; the built ones are the ones to highlight): still there and
    # still a link, its status still written on it
    if dim:
        t = f'<g class="dim">{t}</g>'
    return f'<a href="{e(href)}">{t}</a>' if href else f"<g>{t}</g>"


def unbuilt(g, s, n):
    """A term's status where it is not built: proposed, deferred, withdrawn, or
    deprecated (kept at its address, no longer used). None when built."""
    if (s, OWL.deprecated, None) in g:
        return "deprecated"
    st = lit(g, s, rdflib.URIRef(BASES[n] + "status"))
    return st if st and st != "built" else None


def grid(items, cols=3, w=286, h=56, gap=10, top=10):
    """items: (title, sub, href, hint[, color]) -> (svg, height); every box in
    a row as tall as the row's tallest"""
    out, y = [], top
    for r in range(0, len(items), cols):
        row = items[r:r + cols]
        rh = max([h] + [need(w, it[0], it[1]) for it in row])
        for i, it in enumerate(row):
            title, sub, href, hint = it[:4]
            color = it[4] if len(it) > 4 else None
            dim = it[5] if len(it) > 5 else False
            out.append(box(10 + i * (w + gap), y, w, rh, title, sub, href, hint, color=color, dim=dim))
        y += rh + gap
    return "".join(out), y + 4


def svg(content, height, label_):
    return (f'<div class="svgwrap"><svg viewBox="0 0 900 {max(60, int(height))}" role="img" aria-label="{e(label_)}">'
            f"{content}</svg></div>")


def section(anchor_, title, crumbs, lead="", master=None):
    """A heading, its trail back up, and -- beside the heading (the master links
    sit next to the section headers) -- the vocabulary page that
    lists every term of this layer as text."""
    trail = " › ".join(f'<a href="#{a}">{e(t)}</a>' for a, t in crumbs)
    # the vocabulary page, where a reader can switch to the plain text view
    m = (f' <a class="master" href="{SITE}/ns/{master}">the vocabulary page: /ns/{master} ›</a>' if master else "")
    return (f'<h2 id="{anchor_}">{e(title)}{m}</h2><p class="crumbs">{trail}{" › " if trail else ""}{e(title)}</p>'
            + (f'<p class="lead">{lead}</p>' if lead else ""))


CSS = """
:root{--paper:#F4F2EE;--surface:#fff;--ink:#1B2430;--muted:#5E6875;--rule:#D3CEC4;--accent:#2F5F7F;--soft:#EEF3F6;
  --found:#F3E9D8;--found-edge:#B8925A}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--paper:#12161C;--surface:#1A2029;--ink:#E6EAF0;
  --muted:#9AA5B2;--rule:#2E3845;--accent:#86B6D6;--soft:#1E2833;--found:#2B2418;--found-edge:#C9A46A}}
:root[data-theme="dark"]{--paper:#12161C;--surface:#1A2029;--ink:#E6EAF0;--muted:#9AA5B2;--rule:#2E3845;--accent:#86B6D6;
  --soft:#1E2833;--found:#2B2418;--found-edge:#C9A46A}
*{box-sizing:border-box} body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Georgia,serif}
main{max-width:1100px;margin:0 auto;padding:16px} a{color:var(--accent)}
h1{font-size:26px;margin:8px 0 2px} h2{font-size:20px;margin:34px 0 2px}
.lead{color:var(--muted);max-width:74ch;margin:4px 0} .crumbs{font:13px system-ui,sans-serif;color:var(--muted);margin:0 0 4px}
.crumbs a{text-decoration:none}
.svgwrap{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:8px;margin:8px 0}
svg{display:block;width:100%;height:auto;min-width:620px} svg text{font-family:Georgia,serif;fill:var(--ink)}
svg .sm{font:12px system-ui,sans-serif;fill:var(--muted)} svg .lbl{font:600 14px system-ui,sans-serif}
svg .box{fill:var(--surface);stroke:var(--rule);stroke-width:1.5} svg a:hover .box{stroke:var(--accent);stroke-width:2.5}
svg .band{fill:var(--soft)} svg a:hover .band{stroke:var(--accent);stroke-width:2}
svg .found{fill:var(--found);stroke:var(--found-edge);stroke-width:1.5} svg a:hover .found{stroke-width:2.5}
svg .dim{opacity:.5} svg .dim .box{fill:var(--paper);stroke-dasharray:5 4} svg a:hover .dim{opacity:.85}
.key{font:13px system-ui,sans-serif;color:var(--muted)} .key i{display:inline-block;width:26px;height:12px;
  vertical-align:-1px;border-radius:3px;margin:0 4px 0 10px;border:1.5px solid var(--rule);background:var(--surface)}
.key i.d{border-style:dashed;background:var(--paper);opacity:.6}
svg .wire{stroke:var(--rule);stroke-width:1.5;fill:none}
.note{font:13px system-ui,sans-serif;color:var(--muted);border-top:1px solid var(--rule);margin-top:30px;padding-top:10px}
h2 .master{font:400 13px system-ui,sans-serif;margin-left:12px;white-space:nowrap}
.views{font:14px system-ui,sans-serif;margin:10px 0 0} .views a,.views b{margin-right:6px}
"""


def main(out=None):
    g, shapes, n_struct = load()
    counts, kinds = store_facts()
    spec = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8"))
    cats = spec.get("categories") or {}
    rtypes = spec.get("types") or {}
    terms = {n: sorted({s for s in g[n].subjects() if str(s).startswith(BASES[n])}, key=lambda u: local(u).lower())
             for n in BASES}
    reached = set()                         # every term a box links to

    def is_class(gr, s):
        return any(o in (OWL.Class, RDFS.Class) for o in gr.objects(s, RDF.type))
    body = []

    # ---------------- LEVEL 0
    bands = []
    for i, (n, title, tag, _full) in enumerate(LAYERS):
        y = 10 + i * 100
        bands.append(f'<a href="#L-{n}"><rect class="band" x="10" y="{y}" width="880" height="82" rx="12"/>'
                     f'<text class="lbl" x="30" y="{y + 30}">{i + 1} · {e(title)}</text>'
                     f'<text class="sm" x="30" y="{y + 52}">{e(tag)} · {len(terms[n])} terms · open ›</text></a>'
                     + (f'<path class="wire" d="M450 {y + 82} L450 {y + 100}"/>' if i < 3 else ""))
    # THE FOUNDATION (2026-10-20: below the 4 layers diagram, a foundation box
    # in a different colour that links to the standards section): what all four
    # layers stand on
    bands.append('<path class="wire" d="M450 392 L450 412"/>'
                 '<a href="#standards"><rect class="found" x="10" y="412" width="880" height="82" rx="12"/>'
                 '<text class="lbl" x="30" y="442">The foundation · Built on open standards</text>'
                 '<text class="sm" x="30" y="464">RDF 1.2 and 1.1, OWL, SHACL, SKOS, PROV-O, DQV · read from MACULA, '
                 'the Berean Standard Bible, STEP Bible, Strong\'s and WordNet · open ›</text></a>')
    body.append(section("top", "The four layers", [], "Read from top to bottom: the text, what it is about, what it says, "
                        "and who says it. Every box opens the next picture down, or the term's own entry on the "
                        "vocabulary pages; hover a box for its meaning.")
                + svg("".join(bands), 504, "The four layers of the schema, on their foundation"))

    # ---------------- THE TEXT
    n, gs = "structure", g["structure"]
    TOP = {"Word": "Words", "Composite": "Words", "Verb": "Words", "Unit": "Words",
           "Clause": "Clauses", "Content": "What a clause carries", "Group": "Groups of clauses",
           "Communication": "Speech and writing", "Author": "Speech and writing",
           "Generic": "Who a word stands for", "Together": "Who a word stands for"}
    FAM_PLAIN = {"Words": "a word, a phrase, a verb", "Clauses": "a statement, a command, a question",
                 "Who a word stands for": "someone described not named; several taken together",
                 "What a clause carries": "an action, a state, an effect",
                 "Groups of clauses": "an episode, a cause and effect, a condition",
                 "Speech and writing": "a turn of speech, an address, a writing"}

    def family(s):
        seen = set()
        while s is not None and s not in seen:
            seen.add(s)
            if local(s) in TOP:
                return TOP[local(s)]
            s = next((p for p in gs.objects(s, RDFS.subClassOf) if str(p).startswith(BASES[n])), None)
        return "Words"
    fams = collections.defaultdict(list)
    for s in terms[n]:
        if is_class(gs, s):
            fams[family(s)].append(s)
    order = [f for f in ("Words", "Who a word stands for", "Clauses", "What a clause carries", "Groups of clauses",
                         "Speech and writing") if fams.get(f)]
    props = [s for s in terms[n] if (s, RDF.type, OWL.ObjectProperty) in gs or (s, RDF.type, OWL.DatatypeProperty) in gs]
    parents = {p for s in props for p in gs.objects(s, RDFS.subPropertyOf) if str(p).startswith(BASES[n])}
    link_fams = collections.defaultdict(list)
    for s in props:
        if s in parents:
            continue
        par = next((p for p in gs.objects(s, RDFS.subPropertyOf) if str(p).startswith(BASES[n])), None)
        link_fams[par].append(s)
    items = [(f"{f} ({len(fams[f])})",
              f"{FAM_PLAIN[f]} · {sum(1 for s in fams[f] if not unbuilt(gs, s, n))} built", f"#fam-{i}", "")
             for i, f in enumerate(order)]
    items.append(("The links between parts", f"{len(link_fams)} families · {len(props)} kinds", "#links-structure",
                  "How clauses and their parts are joined: because, so that, when; who speaks; what a word does in its clause"))
    c, h = grid(items, cols=3, h=60)
    body.append(section("L-structure", "1 · The text", [("top", "The map")], e(LAYERS[0][3]), master="structure") + svg(c, h, "The parts of the text"))
    for i, f in enumerate(order):
        # built first, then the rest, faded
        c, h = grid([(label(gs, s), unbuilt(gs, s, n) or "built", page(n, s), tip(gs, s), None,
                      bool(unbuilt(gs, s, n)))
                     for s in sorted(fams[f], key=lambda u: (bool(unbuilt(gs, u, n)), local(u)))],
                    cols=4, w=212, h=52)
        reached |= set(fams[f])
        body.append(section(f"fam-{i}", f, [("top", "The map"), ("L-structure", "The text")]) + svg(c, h, f))
    lf_items = []
    for j, (par, ks) in enumerate(sorted(link_fams.items(), key=lambda kv: -len(kv[1]))):
        name = label(gs, par) if par is not None else "Other links"
        lf_items.append((name, f"{len(ks)} kinds", f"#lf-{j}", tip(gs, par) if par is not None else ""))
    c, h = grid(lf_items, cols=3, h=52)
    body.append(section("links-structure", "The links between parts", [("top", "The map"), ("L-structure", "The text")])
                + svg(c, h, "The families of links between parts"))
    for j, (par, ks) in enumerate(sorted(link_fams.items(), key=lambda kv: -len(kv[1]))):
        name = label(gs, par) if par is not None else "Other links"
        head = [(f"{name} (the family)", "its own entry", page(n, par), tip(gs, par), None,
                 bool(unbuilt(gs, par, n)))] if par is not None else []
        c, h = grid(head + [(label(gs, s), unbuilt(gs, s, n) or "", page(n, s), tip(gs, s), None, bool(unbuilt(gs, s, n)))
                            for s in sorted(ks, key=lambda u: (bool(unbuilt(gs, u, n)), local(u)))],
                    cols=4, w=212, h=40)
        reached |= set(ks) | ({par} if par is not None else set())
        body.append(section(f"lf-{j}", name, [("top", "The map"), ("L-structure", "The text"),
                                              ("links-structure", "The links between parts")]) + svg(c, h, name))

    # ---------------- WHAT IT IS ABOUT
    n, gm = "meaning", g["meaning"]
    classes = [s for s in terms[n] if is_class(gm, s)]
    kids, roots = collections.defaultdict(list), []
    for s in classes:
        par = [p for p in gm.objects(s, RDFS.subClassOf) if p in classes]
        (kids[par[0]] if par else roots).append(s)
    FROM = rdflib.URIRef(BASES["meaning"] + "fromEntityType")

    def size(s):
        return 1 + sum(size(k) for k in kids.get(s, []))

    def ncards(s):
        # EVERY kind a class takes in (D4): PersonalBeing takes "person" and
        # "being", and counting the first found showed 11 for ~1,674 people
        return sum(kinds.get(str(k), 0) for k in gm.objects(s, FROM))
    big = sorted([s for s in roots if kids.get(s)], key=lambda u: -size(u))
    small = sorted([s for s in roots if not kids.get(s)], key=lambda u: local(u))
    items = [(label(gm, s), f"{size(s) - 1} kinds inside", f"#mk-{local(s)}", tip(gm, s)) for s in big]
    items += [(label(gm, s), f"{ncards(s):,} cards" if ncards(s) else (unbuilt(gm, s, n) or ""), page(n, s), tip(gm, s),
               None, bool(unbuilt(gm, s, n))) for s in small]
    reached |= set(small)
    mprops = [s for s in terms[n] if not is_class(gm, s)]
    items.append(("What a card or reading carries", f"{len(mprops)} terms, on the vocabulary page", f"{SITE}/ns/meaning",
                  "The properties: a card's words, its senses, its readings and their measures"))
    reached |= set(mprops)
    c, h = grid(items, cols=3, h=56)
    body.append(section("L-meaning", "2 · What it is about", [("top", "The map")], e(LAYERS[1][3]), master="meaning")
                + svg(c, h, "The broadest kinds of thing"))
    for s in big:
        rows = []

        def walk(x, d):
            rows.append((x, d))
            for k in sorted(kids.get(x, []), key=lambda u: local(u)):
                walk(k, d + 1)
        walk(s, 0)
        tre = []
        for r, (x, d) in enumerate(rows):
            X, Y = 10 + d * 34, 10 + r * 40
            if d:
                tre.append(f'<path class="wire" d="M{X - 18} {Y - 22} L{X - 18} {Y + 16} L{X} {Y + 16}"/>')
            nc = ncards(x)
            ub = unbuilt(gm, x, n)
            tre.append(box(X, Y, 330, 32, label(gm, x) + (f" ({ub})" if ub else ""), "", page(n, x), tip(gm, x), dim=bool(ub))
                       + (f'<text class="sm" x="{X + 340}" y="{Y + 21}">{nc:,} cards</text>' if nc else ""))
        reached |= {x for x, _d in rows}
        body.append(section(f"mk-{local(s)}", label(gm, s), [("top", "The map"), ("L-meaning", "What it is about")])
                    + svg("".join(tre), 20 + len(rows) * 40, f"The kinds inside {label(gm, s)}"))

    # ---------------- WHAT THE TEXT SAYS
    n, gr = "relation", g["relation"]
    by_cat = collections.defaultdict(list)
    for s in terms[n]:
        if (s, RDF.type, OWL.ObjectProperty) in gr:
            by_cat[(rtypes.get(local(s)) or {}).get("category") or "other"].append(s)
    SUPER = [("people", "Between people", "family, rule, service, speech, conflict",
              lambda c_, d: d == "person" and c_ != "statement"),
             ("places", "Places and peoples", "where people went; the peoples they belong to",
              lambda c_, d: d in ("place", "group")),
             ("things", "Things, observances, covenants", "objects, feasts and rites, covenants",
              lambda c_, d: d in ("object", "observance", "covenant")),
             ("meaning", "Meaning", "what a passage speaks of, a figure, a verdict",
              lambda c_, d: d in ("concept", "image", "assessment")),
             ("text", "Stories and the text itself", "a story told again, a number, a quotation",
              lambda c_, d: d == "event" or (d is None and c_ != "statement")),
             ("statements", "What the text says", "a statement from one clause: Saul loved David",
              lambda c_, d: c_ == "statement")]

    def cat_meta(c_):
        return cats.get(c_) if isinstance(cats.get(c_), dict) else {}

    def cat_label(c_):
        return cat_meta(c_).get("label") or ns_relation.CAT_FALLBACK.get(c_) or c_.replace("_", " ").capitalize()
    grouped = collections.OrderedDict((k, []) for k, *_ in SUPER)
    for c_ in sorted(by_cat, key=lambda c_: -len(by_cat[c_])):
        k = next((k for k, _t, _p, test in SUPER if test(c_, cat_meta(c_).get("domain"))), "text")
        grouped[k].append(c_)
    items = []
    for k, title, plain, _t in SUPER:
        uses = sum(counts.get(local(s), 0) for c_ in grouped[k] for s in by_cat[c_])
        items.append((title, f"{len(grouped[k])} families · {uses:,} links", f"#sup-{k}", plain))
    c, h = grid(items, cols=3, h=60)
    body.append(section("L-relation", "3 · What the text says", [("top", "The map")], e(LAYERS[2][3]), master="relation")
                + svg(c, h, "The six groups of links"))
    for k, title, _p, _t in SUPER:
        fitems = [(cat_label(c_), f"{len(by_cat[c_])} kinds · {sum(counts.get(local(s), 0) for s in by_cat[c_]):,} links",
                   f"#cat-{c_}", "", cat_meta(c_).get("color")) for c_ in grouped[k]]
        c, h = grid(fitems, cols=3, h=56)
        body.append(section(f"sup-{k}", title, [("top", "The map"), ("L-relation", "What the text says")])
                    + svg(c, h, title))
        for c_ in grouped[k]:
            titems = []
            for s in sorted(by_cat[c_], key=lambda u: -counts.get(local(u), 0)):
                t = rtypes.get(local(s)) or {}
                src = t.get("src_type"); dst = t.get("dst_type")
                fmt = (lambda v: " or ".join(v) if isinstance(v, list) else (v or "anything"))
                titems.append((label(gr, s), f"{counts.get(local(s), 0):,} links · {fmt(src)} → {fmt(dst)}",
                               page(n, s), tip(gr, s)))
            reached |= set(by_cat[c_])
            c, h = grid(titems, cols=3, h=54)
            body.append(section(f"cat-{c_}", cat_label(c_), [("top", "The map"), ("L-relation", "What the text says"),
                                                              (f"sup-{k}", title)]) + svg(c, h, cat_label(c_)))
    rest = [s for s in terms[n] if s not in reached]
    reached |= set(rest)                    # the vocabulary's own annotations, on its page

    # ---------------- WHO SAYS IT, AND HOW SURE
    n, gc = "claim", g["claim"]
    C = BASES["claim"]
    spokes = [("subject", "what it is about"), ("relation", "the kind of link"), ("object", "what it points to"),
              ("verse", "the verses"), ("certainty", "how sure"), ("voice", "whose voice"), ("claimedBy", "said by"),
              ("reader", "read by"), ("modality", "said as"), ("verb", "the verb"), ("family", "kind of act"),
              ("clause", "the clause"), ("evidencedBy", "evidence")]
    # SPREAD (2026-10-20: the section 4 claim diagram spread out slightly so
    # the boxes on top and bottom do not overlap): a wider, taller
    # ring, narrower boxes, and turned half a step so no box sits at the top
    spk, cx, cy, RX, RY, BW = [], 450, 262, 370, 232, 148
    for i, (p, plain) in enumerate(spokes):
        a = 2 * math.pi * (i + 0.5) / len(spokes) - math.pi / 2
        x, y = cx + RX * math.cos(a), cy + RY * math.sin(a)
        u = rdflib.URIRef(C + p)
        spk.append(f'<path class="wire" d="M{cx} {cy} L{x:.0f} {y:.0f}"/>'
                   + box(round(x - BW / 2), round(y - 27), BW, 54, plain, f"claim:{p}", page(n, u), tip(gc, u)))
        reached.add(u)
    cl = rdflib.URIRef(C + "Claim")
    spk.append(box(cx - 80, cy - 28, 160, 56, "a claim", "", page(n, cl), tip(gc, cl), strong=True))
    reached.add(cl)
    schemes = [s for s in terms[n] if (s, RDF.type, SKOS.ConceptScheme) in gc]
    sitems = []
    for sch in schemes:
        members = list(gc.subjects(SKOS.inScheme, sch))
        sitems.append((label(gc, sch).capitalize(), f"{len(members)} values", f"#sch-{local(sch)}", tip(gc, sch)))
    c, h = grid(sitems, cols=3, h=52, top=540)
    body.append(section("L-claim", "4 · Who says it, and how sure", [("top", "The map")],
                        e(LAYERS[3][3]) + " A claim is stated as fact only when it is made outright; anything else is "
                        "described and never stated. Below the claim, the scales and lists it draws from.", master="claim")
                + svg("".join(spk) + c, h, "What a claim carries, and its scales"))
    for sch in schemes:
        members = sorted(gc.subjects(SKOS.inScheme, sch), key=lambda u: local(u))
        c, h = grid([(label(gc, m), "", page(n, m), tip(gc, m)) for m in members], cols=4, w=212, h=40)
        reached |= set(members) | {sch}
        body.append(section(f"sch-{local(sch)}", label(gc, sch).capitalize(), [("top", "The map"),
                                                                              ("L-claim", "Who says it")]) + svg(c, h, label(gc, sch)))
    rest_c = [s for s in terms[n] if s not in reached]
    reached |= set(rest_c)                  # the remaining claim terms, on the vocabulary page

    # ---------------- THE SAME SCHEMA, BY THE STANDARDS IT IS BUILT ON
    body += standards_view(g, shapes, n_struct)

    total = sum(len(v) for v in terms.values())
    unreached = {k: [local(s) for s in v if s not in reached] for k, v in terms.items()}
    html_ = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
             f'content="width=device-width,initial-scale=1"><title>Schema map</title>'
             f'<link rel="canonical" href="{SITE}/ns/map"><style>{CSS}</style></head><body><main>'
             # the same bar as the vocabulary pages (tools/ns_docs.py), so a
             # reader moves between the pictures and the text
             f'<nav class="crumbs">' + " · ".join(
                 f'<a href="{SITE}/ns/{v}">{t}</a>' for v, t in (("meaning", "Meaning"), ("structure", "Structure"),
                                                                 ("relation", "Relations"), ("claim", "Claims"),
                                                                 ("alignment", "Alignment")))
             + f' · <b>Map</b> · <a href="{SITE}/">bibleontology.org</a></nav>'
             f'<h1>The Bible Ontology schema, as a map</h1>'
             f'<p class="lead">The four published vocabularies ({total} terms) as pictures, from the four layers down to each '
             f'kind. Every box opens the next picture or the term\'s own entry at '
             f'<a href="{SITE}/ns/structure">/ns/structure</a>, <a href="{SITE}/ns/meaning">/ns/meaning</a>, '
             f'<a href="{SITE}/ns/relation">/ns/relation</a> and <a href="{SITE}/ns/claim">/ns/claim</a>; hover for its '
             # the version from the version file and the counts dated (D8):
             # a fixed "1.2.0" would be false at 1.2.1, and the counts are a
             # snapshot while About's are live
             f'meaning. Vocabulary release {e(ns_common.VERSION)} ({e(ns_common.DATE)}); the counts are as of '
             f'{datetime.date.today().isoformat()}.</p>'
             f'<p class="views"><b>The map</b> · <a href="#standards">Built on open standards</a></p>'
             f'<p class="key">Key:<i></i>built<i class="d"></i>not built: proposed, deferred, withdrawn or '
             f'deprecated (each says which)</p>'
             + "".join(body) +
             f'<p class="note">Generated by tools/ns_map.py · {total} terms, every one reached from a picture or its '
             f'vocabulary page.</p></main></body></html>')
    dest = Path(out) if out else ROOT / "docs" / "review" / "schema-map.html"
    dest.write_text(html_, encoding="utf-8")
    # PUBLISHED WITH 1.2.0 at /ns/map (plan 8.1e): the release writes the
    # served copy; before it, only the review copy exists and /ns/map is a 404
    if not out and tuple(int(x) for x in ns_common.VERSION.split(".")) >= (1, 2, 0):
        (ROOT / "out" / "ns" / "map.html").write_text(html_, encoding="utf-8")
    print(f"{total} terms; boxes reach {total - sum(len(v) for v in unreached.values())}; "
          f"left to the vocabulary pages: relation {len(rest)}, claim {len(rest_c)} -> {dest}")
    return unreached


if __name__ == "__main__":
    main(*sys.argv[1:])
