"""What the three published vocabularies share: their version, and the
reasoning policy each states (OWL evaluation Phase 0, docs/review/
OWL-EVALUATION.md; every item approved 2026-10-13).

Used by tools/ns_structure.py and tools/ns_relation.py; meaning.ttl is written
by hand and carries the same text, which tools/ns_freeze.py checks.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))
VERSION, DATE = V["version"], V["date"]

# THE LICENCE, ONE SWITCH (2026-10-15: CC BY 4.0 chosen). Off until
# the copyright filing is received; see ns-version.json's "license" for why.
# Granted, every vocabulary says it twice: dcterms:license, which tools and
# Google's Dataset Search read, and the rights line, which people read.
_L = V.get("license") or {}
LICENSE = _L["uri"] if _L.get("granted") else None
RIGHTS = ("© 2026 Doug Egge. Licensed under CC BY 4.0: share and adapt, with credit to "
          "Bible Ontology by Doug Egge (bibleontology.org)." if LICENSE
          else "© 2026 Doug Egge. All rights reserved.")

# THE GRAPH'S LICENCE, ITS OWN SWITCH (plan 8.3a, 2026-10-21: CC BY 4.0,
# "granted for the graph at the cut"). The exports (out/export/) say what it
# is in their first lines; LICENSE-DATA says it in the public repository. Set
# graph_license.granted in ns-version.json on the day the repository is
# published, rebuild the exports, and both say the same thing.
_G = V.get("graph_license") or {}
GRAPH_LICENSE = _G.get("uri") if _G.get("granted") else None
MACULA_CREDIT = ("MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; "
                 "MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; "
                 "© Biblica, Inc., CC BY 4.0")


def shapes_head(what: str) -> str:
    """The comment lines a shapes file opens with, as /ns/shapes does: what it
    is, the version, the rights and the licence (the code review, 2026-10-22:
    relation-shapes.ttl and structure-shapes.ttl, published in the repository,
    said none of it)."""
    return (f"# Bible Ontology -- {what}, version {VERSION} ({DATE}). Merged into /ns/shapes.\n"
            "# " + RIGHTS.replace("©", "(c)") + "\n"
            + (f"# Licence: {LICENSE}\n" if LICENSE else "") + "\n")


def gz_text(path):
    """A published export, opened for writing as reproducible gzip text: LF
    line ends on every platform, and no timestamp in the header (the
    correctness review, 2026-10-22: gzip.open(..., "wt") wrote CRLF on Windows
    and the time of the run, so the same graph gave different bytes)."""
    import gzip
    import io
    # GzipFile opens (and so closes) the file itself; the header keeps the
    # file's base name, the same on every machine
    return io.TextIOWrapper(gzip.GzipFile(filename=str(path), mode="wb", mtime=0),
                            encoding="utf-8", newline="\n")


WORDNET_LINE = ('# Verb classes ("familyFrom WordNet") from WordNet 3.0, Copyright 2006 by Princeton University. '
                'All rights reserved. Provided "as is"; Princeton makes no representations or warranties. '
                'Full notice: NOTICE.')


def export_rights(wordnet: bool = False) -> list[str]:
    """The comment lines every published export carries: its terms and its
    sources, MACULA's credit in MACULA's words; and WordNet's notice on the
    files that carry its verb classes (the claims; the legal seat, 2026-10-22:
    WordNet asks for its notice on ALL copies, and these are downloaded alone)."""
    lines = _export_rights()
    return lines + [WORDNET_LINE] if wordnet else lines


def _export_rights() -> list[str]:
    if GRAPH_LICENSE:
        terms = [f"# (c) 2026 Doug Egge. Licensed under CC BY 4.0 ({GRAPH_LICENSE}):",
                 "# share and adapt, with credit to Bible Ontology by Doug Egge (bibleontology.org)."]
    else:
        terms = ["# (c) 2026 Doug Egge. All rights reserved.",
                 "# A CC BY 4.0 licence, as the vocabularies have, is granted when the repository is published."]
    return terms + [f"# Structure from {MACULA_CREDIT}.",
                    "# English: the Berean Standard Bible (public domain)."]

# THE REASONING POLICY, said on every ontology. The evaluation proved on real
# rows what a reasoner does here without it: an inverse-functional father_of
# makes the two fathers named for Joseph one man. Describe what is built only.
POLICY = (
    "Reasoning policy. These terms describe the graph; they are not built for automated "
    "inference over it. Every relation in the graph is a claim that carries its verse, its "
    "certainty and, where someone in the text says it, its speaker, and a reasoner that ignores "
    "those turns a character's claim into the narrator's or a reading into a fact. So: no "
    "owl:sameAs between records (possibly_same_as and spoken_of_as are readings and names, never "
    "identities); no functional or inverse-functional kinship (the accounts name more than one "
    "father or mother for some people, and the graph keeps both); no transitive chaining of "
    "images, figures, symbols or places; and nothing about the records of God, the Father, Jesus "
    "or the Holy Spirit is derived by inference: they change only by a recorded editorial "
    "decision, as the accounts give them. The policy forbids derivations, not descriptions. "
    "Constraints are checked, closed-world, by the SHACL shapes at "
    "https://bibleontology.org/ns/shapes, not inferred.")

VERSIONING = (
    "Versioning. A term's address never changes and is never reused. A term whose meaning "
    "changes gets a new address, and the old one is marked owl:deprecated with dcterms:isReplacedBy. "
    "Additions raise the minor version; a change of meaning raises the major. Each release is kept "
    "forever at its dated version IRI; the undated address serves the latest.")


def header(g, onto, base, prefix, OWL, DCTERMS, Literal, URIRef, XSD, RDFS):
    """The version block and the two policies, on an ontology node."""
    g.add((onto, URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix"), Literal(prefix)))
    g.add((onto, OWL.versionIRI, URIRef(f"{base}/{DATE}")))
    g.add((onto, OWL.versionInfo, Literal(VERSION)))
    if V.get("prior"):
        g.add((onto, OWL.priorVersion, URIRef(f"{base}/{V['prior']}")))
    g.add((onto, DCTERMS.modified, Literal(DATE, datatype=XSD.date)))
    g.add((onto, DCTERMS.rights, Literal(RIGHTS)))
    if LICENSE:
        g.add((onto, DCTERMS.license, URIRef(LICENSE)))
    g.add((onto, URIRef("http://purl.org/vocab/vann/preferredNamespaceUri"), Literal(base + "#")))
    g.add((onto, RDFS.comment, Literal(POLICY)))
    g.add((onto, RDFS.comment, Literal(VERSIONING)))
