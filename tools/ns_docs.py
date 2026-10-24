"""Readable pages for the published ontology: bibleontology.org/ns/<name> in a browser.

2026-10-11, before the r/semanticweb post: the ontology addresses
served only Turtle, which a browser shows as raw text. The standard practice
is one address, two forms: a documentation page for people, Turtle for tools.
This writes out/ns/<name>.html from out/ns/<name>.ttl (and meaning.ttl); the
server picks by the request's Accept header (app2/server.py).

No scripts, no external files: a plain page, every term an anchor
(/ns/structure#Clause), every class or property it mentions a link.

    python tools/ns_docs.py        (after tools/ns_relation.py, tools/ns_structure.py)
"""
from html import escape
from pathlib import Path

import rdflib
from rdflib import URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {"meaning": ROOT / "out/ns/meaning.ttl",       # the public copy (tools/ns_meaning.py)
           "structure": ROOT / "out/ns/structure.ttl",
           "relation": ROOT / "out/ns/relation.ttl",
           "claim": ROOT / "out/ns/claim.ttl"}               # plan 8.1a, from 1.1.0
SITE = "https://bibleontology.org"
NAMES = {"meaning": "Meaning", "structure": "Structure", "relation": "Relations", "claim": "Claims"}

CSS = """
:root{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#D9DFE7;--link:#2F5D8A}
@media (prefers-color-scheme:dark){:root{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2A3542;--link:#8FB6E0}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.55 Georgia,"Times New Roman",serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--link)}h1{font-size:28px;margin:8px 0 4px}h2{font-size:20px;margin:32px 0 8px;
border-bottom:1px solid var(--rule);padding-bottom:4px}
.meta,.g{color:var(--muted);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
nav{font:14px system-ui,sans-serif;margin-bottom:12px}nav a{margin-right:14px}
.term{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:10px 14px;margin:10px 0}
.term h3{margin:0 0 2px;font-size:17px}.term code{font-size:13px;color:var(--muted)}
.term p{margin:6px 0 0}dl{margin:6px 0 0;font:14px/1.5 system-ui,sans-serif}
dt{float:left;clear:left;width:110px;color:var(--muted)}dd{margin:0 0 2px 120px}
.toc{columns:3 180px;font:14px/1.7 system-ui,sans-serif}.toc a{display:block}
"""


def local(u):
    s = str(u)
    return s.split("#", 1)[1] if "#" in s else s.rsplit("/", 1)[-1]


def link(u, here):
    s = str(u)
    for name in SOURCES:
        base = f"{SITE}/ns/{name}#"
        if s.startswith(base):
            t = s[len(base):]
            return f'<a href="#{escape(t)}">{escape(t)}</a>' if name == here else \
                f'<a href="/ns/{name}#{escape(t)}">{name}:{escape(t)}</a>'
    if s.startswith(f"{SITE}/ns/word#"):
        return f'<a href="/ns/meaning#{escape(local(s))}">word:{escape(local(s))}</a>'
    return f'<a href="{escape(s)}">{escape(local(s))}</a>' if s.startswith("http") else escape(s)


def _from_120():
    import json
    v = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))["version"]
    return tuple(int(x) for x in v.split(".")) >= (1, 2, 0)


def page(name, path, dest=None):
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    onto = URIRef(f"{SITE}/ns/{name}")
    title = str(g.value(onto, DCTERMS.title) or g.value(onto, RDFS.label) or f"Bible Ontology — {name}")
    creator = g.value(onto, DCTERMS.creator)
    # the licence, as the vocabulary itself states it (none until granted:
    # ontology/ns-version.json, "license")
    lic = g.value(onto, DCTERMS.license)
    # the ontology's comments: its description, then the two policies, each
    # under its own heading (OWL evaluation Phase 0)
    comments = [str(c) for c in g.objects(onto, RDFS.comment)]
    policies = [c for c in comments if c.startswith(("Reasoning policy.", "Versioning."))]
    policies.sort(key=lambda c: not c.startswith("Reasoning"))
    comment = next((c for c in comments if c not in policies), None)
    version, viri = g.value(onto, OWL.versionInfo), g.value(onto, OWL.versionIRI)
    kinds = [("Classes", {OWL.Class, RDFS.Class}),
             ("Properties", {OWL.ObjectProperty, RDF.Property, OWL.DatatypeProperty}),
             # used on every term and, until now, documented on none
             ("Annotation properties", {OWL.AnnotationProperty})]
    seen, sections = set(), []
    for head, types in kinds:
        terms = sorted({s for t in types for s in g.subjects(RDF.type, t)
                        if isinstance(s, URIRef) and "#" in str(s)} - seen, key=lambda u: local(u).lower())
        seen |= set(terms)
        if terms:
            sections.append((head, terms))
    # EVERY TERM AN ANCHOR, VALUES TOO (2026-10-20: not all deeplinks
    # worked): a list's values (claim:explicit, the verb families), a voice
    # (claim:narrator), a metric or policy (bom:cardWordShare) are terms of the
    # namespace with no class or property type, and had no entry to link to
    base = f"{SITE}/ns/{name}#"
    values = sorted({s for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(base)
                     and str(s) != base} - seen, key=lambda u: local(u).lower())
    if values:
        sections.append(("Named values", values))
    # FOUND BY THE PEOPLE WHO LOOK FOR ONTOLOGIES (2026-10-11: one
    # niche hit could be worth a hundred passers-by): a description, the
    # canonical address, the Turtle as an alternate, and schema.org data --
    # a DefinedTermSet, and a Dataset whose download is the Turtle, which is
    # what Google's Dataset Search reads, with the licence once one is granted.
    n_terms = sum(len(t) for _, t in sections)
    desc = (f"{title}: {n_terms} terms of the Bible Ontology, a knowledge graph of the Bible built from the "
            f"Hebrew and Greek. An RDF vocabulary (RDFS and OWL terms) in Turtle, with definitions.")
    url = f"{SITE}/ns/{name}"
    ld = {"@context": "https://schema.org", "@type": ["DefinedTermSet", "Dataset"],
          "name": title, "description": (str(comment) if comment else desc)[:5000], "url": url,
          "creator": {"@type": "Person", "name": str(creator or "Doug Egge")},
          # no isPartOf (Google's Rich Results test, 2026-10-20, on /ns/meaning
          # and /ns/relation: "Invalid object type for field isPartOf"): for a
          # Dataset it must be a parent dataset or a URL, never a WebSite; the
          # page's nav already links the site
          "keywords": ["ontology", "RDF", "RDFS", "knowledge graph", "Bible", "semantic web", "linked data"],
          "distribution": {"@type": "DataDownload", "encodingFormat": "text/turtle", "contentUrl": f"{url}.ttl"},
          **({"license": str(lic)} if lic else {})}
    import json
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
           f"<meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>{escape(title)}</title>"
           f'<meta name="description" content="{escape(desc)}">'
           f'<link rel="canonical" href="{url}">'
           f'<link rel="alternate" type="text/turtle" href="{url}.ttl">'
           f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>'
           f"<style>{CSS}</style></head><body><main>",
           "<nav>" + "".join(f'<a href="/ns/{n}">{escape(NAMES[n])}</a>' for n in SOURCES)
           # the alignment file joins the family with 1.2.0 (tools/ns_align.py)
           + ('<a href="/ns/alignment">Alignment</a><a href="/ns/map">Map</a>' if _from_120() else "")
           + f'<a href="/">bibleontology.org</a></nav>',
           f"<h1>{escape(title)}</h1>",
           f'<p class=meta>Namespace <code>{SITE}/ns/{name}#</code>'
           + (f" · by {escape(str(creator))}" if creator else "")
           + (f' · <a href="{escape(str(lic))}" rel="license">CC BY 4.0</a>'
              if lic and "/by/4.0" in str(lic) else (f' · <a href="{escape(str(lic))}" rel="license">licence</a>' if lic else ""))
           + (f' · version {escape(str(version))}' if version else "")
           + (f' (<a href="{escape(str(viri))}.txt">this release, kept</a>)' if viri else "")
           + f' · view: <b>formatted</b> · <a href="/ns/{name}.txt">Turtle text</a>'
           + ' · <a href="/ns/shapes.txt">shapes</a></p>']
    if comment:
        out.append(f"<p>{escape(str(comment))}</p>")
    for c in policies:
        h, _, rest = c.partition(". ")
        out.append(f"<h2>{escape(h)}</h2><p>{escape(rest)}</p>")
    for head, terms in sections:
        out.append(f"<h2>{head} · {len(terms)}</h2><div class=toc>"
                   + "".join(f'<a href="#{escape(local(t))}">{escape(local(t))}</a>' for t in terms) + "</div>")
    for head, terms in sections:
        out.append(f"<h2>{head}</h2>")
        for t in terms:
            lab = g.value(t, RDFS.label)
            dfn = g.value(t, SKOS.definition) or g.value(t, RDFS.comment)
            rows = []
            for p, name_ in ((RDFS.subClassOf, "subclass of"), (RDFS.domain, "from"), (RDFS.range, "to")):
                vs = [link(o, name) for o in g.objects(t, p) if isinstance(o, URIRef)]
                if vs:
                    rows.append((name_, ", ".join(vs)))
            for o in g.objects(t, RDF.type):
                if o in (OWL.SymmetricProperty, OWL.FunctionalProperty):
                    rows.append(("kind", local(o)))
            if head == "Named values":
                vs = [link(o, name) for o in g.objects(t, RDF.type) if isinstance(o, URIRef) and o != OWL.NamedIndividual]
                if vs:
                    rows.append(("a", ", ".join(vs)))
                vs = [link(o, name) for o in g.objects(t, SKOS.inScheme)]
                if vs:
                    rows.append(("in the list", ", ".join(vs)))
            if g.value(t, OWL.deprecated):
                rows.append(("status", "deprecated: kept at this address, no longer used"))
            for p in g.predicates(t, None):
                if str(p).startswith(f"{SITE}/ns/") and p not in (RDFS.label,):
                    vs = [escape(str(o)) for o in g.objects(t, p)]
                    rows.append((local(p), ", ".join(vs)))
            out.append(f'<div class=term id="{escape(local(t))}"><h3>{escape(str(lab or local(t)))}</h3>'
                       f"<code>{escape(local(t))}</code>"
                       + (f"<p>{escape(str(dfn))}</p>" if dfn else "")
                       + ("<dl>" + "".join(f"<dt>{escape(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>" if rows else "")
                       + "</div>")
    out.append("</main></body></html>")
    dest = Path(dest) if dest else ROOT / "out" / "ns" / f"{name}.html"
    dest.write_text("\n".join(out), encoding="utf-8")
    return dest, sum(len(t) for _, t in sections)


def main():
    for name, path in SOURCES.items():
        dest, n = page(name, path)
        print(f"{dest.relative_to(ROOT)}: {n} terms")


if __name__ == "__main__":
    main()
