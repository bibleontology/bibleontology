"""THE ALIGNMENT FILE: our terms mapped to their nearest standard equivalents
(plan 8.1e; approved 2026-10-20), published at
/ns/alignment from release 1.2.0, as Turtle and as a readable page.

Two kinds of alignment, kept apart because they commit a reader to different
things:

  - STATED IN THE VOCABULARIES THEMSELVES: rdfs:subClassOf or
    rdfs:subPropertyOf to a standard term (bom:Lexeme under
    ontolex:LexicalEntry, claim:claimedBy under prov:wasAttributedTo). These
    are part of the vocabularies and an RDFS reasoner acts on them. Read from
    the vocabularies, not repeated in the file.
  - MAPPED HERE: skos:closeMatch, broadMatch, narrowMatch, relatedMatch to
    schema.org, FOAF, CIDOC CRM, OntoLex and Web Annotation, from
    ontology/align/alignment.yaml. A closeMatch says "near enough for most
    queries", never "the same". No exactMatch, by policy. A mapping commits a
    reasoner to nothing beyond typing both ends as skos:Concept (SKOS entails
    it; punning, permitted in OWL 2), and the file declares the four mapping
    properties as owl:AnnotationProperty so OWL tools read them as annotations
    (the committee's third sitting, D7).

Every target is checked against its specification (ontology/align/targets.json,
with the date and page it was checked on); tests/test_alignment.py fails on one
that is not, and on one of ours the vocabularies do not define.

    python tools/ns_align.py     -> out/ns/alignment.ttl + .html (from 1.2.0),
                                    or docs/review/alignment/ before it
"""
import json
import sys
from html import escape
from pathlib import Path

import rdflib
import yaml
from rdflib import URIRef
from rdflib.namespace import OWL, RDFS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ns_common as NC  # noqa: E402
import ns_docs  # noqa: E402

SITE = "https://bibleontology.org"
SRC = ROOT / "ontology" / "align" / "alignment.yaml"
TARGETS = ROOT / "ontology" / "align" / "targets.json"
SKOSM = {"close": "closeMatch", "broad": "broadMatch", "narrow": "narrowMatch", "related": "relatedMatch"}
PLAIN = {"close": "close match", "broad": "theirs is broader", "narrow": "theirs is narrower", "related": "related"}
OURS = {"meaning": f"{SITE}/ns/meaning#", "structure": f"{SITE}/ns/structure#",
        "relation": f"{SITE}/ns/relation#", "claim": f"{SITE}/ns/claim#", "word": f"{SITE}/ns/word#"}
VOCABS = [("schema", "schema.org", "https://schema.org/"),
          ("foaf", "FOAF", "http://xmlns.com/foaf/spec/"),
          ("crm", "CIDOC CRM", "https://cidoc-crm.org/"),
          ("ontolex", "OntoLex-Lemon", "https://www.w3.org/2016/05/ontolex/"),
          ("oa", "Web Annotation", "https://www.w3.org/TR/annotation-vocab/")]
STANDARD = {"prov": "http://www.w3.org/ns/prov#", "ontolex": "http://www.w3.org/ns/lemon/ontolex#",
            "skos": "http://www.w3.org/2004/02/skos/core#", "dqv": "http://www.w3.org/ns/dqv#",
            "schema": "https://schema.org/", "foaf": "http://xmlns.com/foaf/0.1/",
            "crm": "http://www.cidoc-crm.org/cidoc-crm/", "oa": "http://www.w3.org/ns/oa#",
            "dcterms": "http://purl.org/dc/terms/"}


def load():
    spec = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    pre = spec["prefixes"]

    def iri(c):
        p, _, l_ = c.partition(":")
        return pre[p] + l_
    rows = [dict(m, ours_iri=iri(m["ours"]), theirs_iri=iri(m["theirs"])) for m in spec["mappings"]]
    unmapped = [(k, iri(k), v) for k, v in (spec.get("unmapped") or {}).items()]
    return pre, rows, unmapped


def ours_page(u):
    """Our term's entry on its vocabulary page (bow: terms are on /ns/meaning)."""
    for name, base in OURS.items():
        if u.startswith(base):
            return f"{SITE}/ns/{'meaning' if name == 'word' else name}#{u[len(base):]}"
    return u


def stated(graphs):
    """The alignments the vocabularies state themselves: a subclass or
    subproperty of a standard term."""
    out = []
    for name, g in graphs.items():
        for p in (RDFS.subClassOf, RDFS.subPropertyOf):
            for s, o in g.subject_objects(p):
                if not isinstance(o, URIRef) or not any(str(s).startswith(b) for b in OURS.values()):
                    continue
                pre = next((k for k, b in STANDARD.items() if str(o).startswith(b)), None)
                if pre:
                    out.append((str(s), "rdfs:" + str(p).rsplit("#", 1)[1], f"{pre}:{str(o)[len(STANDARD[pre]):]}",
                                str(o)))
    return sorted(set(out), key=lambda r: (r[2].split(":")[0], r[0]))


def curie(u):
    for name, base in OURS.items():
        if u.startswith(base):
            return {"meaning": "bom", "structure": "bos", "relation": "bor", "claim": "claim", "word": "bow"}[name] \
                + ":" + u[len(base):]
    return u


def turtle(pre, rows):
    lines = ["# Bible Ontology -- alignment: our terms mapped to their nearest equivalents in five standard",
             "# vocabularies, as SKOS mapping properties, declared here as owl:AnnotationProperty.",
             "# Each mapping's reason is the comment above it; the page is https://bibleontology.org/ns/alignment",
             ""]
    lines += [f"@prefix {p}: <{u}> ." for p, u in sorted(pre.items())]
    lines += ["@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
              "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
              "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
              "@prefix dcterms: <http://purl.org/dc/terms/> .",
              "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    onto = f"{SITE}/ns/alignment"
    head = [f"<{onto}> a owl:Ontology",
            '    dcterms:title "Bible Ontology — alignment"',
            '    rdfs:label "Bible Ontology — alignment"',
            '    dcterms:creator "Doug Egge"',
            f'    owl:versionInfo "{NC.VERSION}"',
            f"    owl:versionIRI <{onto}/{NC.DATE}>",
            f'    dcterms:modified "{NC.DATE}"^^xsd:date',
            f"    dcterms:rights {json.dumps(NC.RIGHTS, ensure_ascii=False)}"]
    if NC.LICENSE:
        head.append(f"    dcterms:license <{NC.LICENSE}>")
    head.append('    rdfs:comment "Our terms mapped to their nearest equivalents in schema.org, FOAF, CIDOC CRM, '
                'OntoLex-Lemon and Web Annotation, as SKOS mapping properties: closeMatch (near enough for most '
                'queries, never the same), broadMatch (theirs is broader), narrowMatch (theirs is narrower), '
                'relatedMatch (associated, not interchangeable). No exactMatch. A mapping commits a reasoner to '
                'nothing beyond typing both ends as skos:Concept, which SKOS entails (punning, permitted in OWL 2); '
                'here the four mapping properties are declared as annotation properties. A mapping says how the text '
                'presents a person, place or event; none takes a view on historicity. The alignments the '
                'vocabularies state themselves (subclasses and subproperties of PROV, OntoLex and SKOS terms; DQV '
                'terms are used only as types) are in the vocabularies."')
    head.append(f"    rdfs:seeAlso <{SITE}/ns/meaning>, <{SITE}/ns/structure>, <{SITE}/ns/relation>, <{SITE}/ns/claim>")
    lines.append(" ;\n".join(head) + " .")
    lines.append("")
    # declared, so Protégé and the OWL API read them as annotations, not guess
    # (the committee's practitioner, P3; the ontology expert's B1)
    lines += [f"skos:{p} a owl:AnnotationProperty ." for p in ("closeMatch", "broadMatch", "narrowMatch",
                                                               "relatedMatch")]
    lines.append("")
    for m in rows:
        lines.append(f"# {m['why']}")
        lines.append(f"{m['ours']} skos:{SKOSM[m['match']]} {m['theirs']} .")
    return "\n".join(lines) + "\n"


def page(rows, unmapped, built):
    css = ns_docs.CSS + "table{border-collapse:collapse;width:100%;font:14px/1.45 system-ui,sans-serif}" \
        "td,th{border-bottom:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}" \
        "th{color:var(--muted);font-weight:600}td.m{white-space:nowrap;color:var(--muted)}"
    url = f"{SITE}/ns/alignment"
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
           f"<meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Bible Ontology — alignment</title>"
           f'<link rel="canonical" href="{url}"><link rel="alternate" type="text/turtle" href="{url}.ttl">'
           f"<style>{css}</style></head><body><main>",
           "<nav>" + "".join(f'<a href="/ns/{n}">{escape(ns_docs.NAMES[n])}</a>' for n in ns_docs.SOURCES)
           + '<a href="/ns/alignment">Alignment</a><a href="/ns/map">Map</a><a href="/">bibleontology.org</a></nav>',
           "<h1>Bible Ontology — alignment</h1>",
           f"<p class=meta>Version {escape(NC.VERSION)} · view: <b>formatted</b> · "
           f'<a href="/ns/alignment.txt">Turtle text</a></p>',
           "<p>Where a term here has a near equivalent in a standard vocabulary, this says which, and how near, so "
           "a tool that knows the standard can read our data. The mappings are SKOS mapping properties: a "
           "<b>close match</b> is near enough to use one for the other in most queries, never the same term; "
           "<b>theirs is broader</b> and <b>theirs is narrower</b> say which way the difference runs; "
           "<b>related</b> says the two belong together but are not interchangeable, and the note says how. "
           "There is no exact match: none of these terms was made for the same corpus. A mapping commits a "
           "reasoner to nothing beyond typing both ends as a SKOS concept, which SKOS itself entails; OWL tools read "
           "the mappings as annotations. A mapping says how the text presents a person, place or event; none takes "
           "a view on historicity. Every target was checked against its specification.</p>"]
    out.append(f"<h2>Stated in the vocabularies themselves · {len(built)}</h2>"
               "<p>These are part of the vocabularies, as a subclass or subproperty of a standard term, and an RDFS "
               "reasoner acts on them.</p><table><tr><th>Ours</th><th></th><th>Standard</th></tr>"
               + "".join(f'<tr><td><a href="{escape(ours_page(s))}">{escape(curie(s))}</a></td>'
                         f'<td class=m>{escape(p)}</td><td><a href="{escape(o)}">{escape(c)}</a></td></tr>'
                         for s, p, c, o in built) + "</table>")
    for pre, name, home in VOCABS:
        mine = [m for m in rows if m["theirs"].startswith(pre + ":")]
        if not mine:
            continue
        out.append(f'<h2 id="{pre}">{escape(name)} · {len(mine)}</h2>'
                   f'<p class=meta><a href="{escape(home)}">{escape(home)}</a></p>'
                   "<table><tr><th>Ours</th><th></th><th>Theirs</th><th>Why</th></tr>"
                   + "".join(f'<tr id="{escape(m["ours"].replace(":", "-") + "--" + m["theirs"].replace(":", "-"))}">'
                             f'<td><a href="{escape(ours_page(m["ours_iri"]))}">{escape(m["ours"])}</a></td>'
                             f'<td class=m>{escape(PLAIN[m["match"]])}</td>'
                             f'<td><a href="{escape(m["theirs_iri"])}">{escape(m["theirs"])}</a></td>'
                             f'<td>{escape(m["why"])}</td></tr>' for m in mine) + "</table>")
    out.append("<h2>Not mapped, and why</h2><table><tr><th>Ours</th><th>Why there is no mapping</th></tr>"
               + "".join(f'<tr><td><a href="{escape(ours_page(u))}">{escape(c)}</a></td><td>{escape(w)}</td></tr>'
                         for c, u, w in unmapped) + "</table>")
    out.append("</main></body></html>")
    return "\n".join(out)


def main(graphs=None, dest=None):
    pre, rows, unmapped = load()
    if graphs is None:
        import vocab_inventory as V
        gen, _ = V.generated()
        graphs = {n: rdflib.Graph().parse(data=gen[n].decode("utf-8"), format="turtle")
                  for n in ("structure", "relation", "meaning", "claim")}
    built = stated(graphs)
    released = tuple(int(x) for x in NC.VERSION.split(".")) >= (1, 2, 0)
    dest = Path(dest) if dest else (ROOT / "out" / "ns" if released else ROOT / "docs" / "review" / "alignment")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "alignment.ttl").write_text(turtle(pre, rows), encoding="utf-8")
    (dest / "alignment.html").write_text(page(rows, unmapped, built), encoding="utf-8")
    by = {p: sum(m["theirs"].startswith(p + ":") for m in rows) for p, _n, _h in VOCABS}
    print(f"{len(rows)} mappings ({', '.join(f'{p} {n}' for p, n in by.items())}); {len(built)} stated in the "
          f"vocabularies; {len(unmapped)} unmapped with a reason -> {dest}")
    return rows, built


if __name__ == "__main__":
    main()
