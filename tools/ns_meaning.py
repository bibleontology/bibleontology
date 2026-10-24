"""The meaning layer as published: out/ns/meaning.ttl, from ontology/meaning/
meaning.ttl (OWL evaluation Phase 0, 2026-10-14).

meaning.ttl is the working file, written by hand, and its comments carry the
project's history: who decided what and when, which tool caught what, which
file holds the data. Served as-is, 26 of its published comments pointed into
the project (files, rule numbers, dated rulings) and six quoted the owner --
who is never named outside the About page. A blanket filter, tried first,
emptied the Lexeme comment and cut assumedFormOf's substance, so each of the
26 has its public text written here; the working file keeps its history. A
new comment that points inside the project fails the build until it is given
a public text.

    python tools/ns_meaning.py
"""
import collections
import re
import sys
from pathlib import Path

import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ontology" / "meaning" / "meaning.ttl"
OUT = ROOT / "out" / "ns" / "meaning.ttl"
BOM, BOW = "https://bibleontology.org/ns/meaning#", "https://bibleontology.org/ns/word#"
INTERNAL = re.compile(r"Doug|tools/|out/|\.jsonl|PRINCIPLES|BACKLOG|JOURNAL|kinds\.json|docs/|\bplan\b|"
                      r"\b\d{4}-\d\d-\d\d\b|\b44a\b|\bS6\b|Copilot|BibleProject")

PUBLIC = {
    "Communication": "Word, law, name, song, letter, as things; a speech act is structure (the structure layer's Communication).",
    "Concept": "An idea the text names and returns to: adoption, holiness, the fear of the LORD. A SKOS concept (it is a meaning, not a thing in the story), linked to the senses that express it (skos:related) and placed under a top category. The graph's concept records land here unchanged.",
    "Contested": "Readers divide on whether the use is literal or figurative, and the text does not settle it: 'This is My body' (Mat 26:26), the bread is his body, or a sign of it; Ezekiel's temple (Ezk 40–48), a temple to be built, or God's presence among his people. The graph decides nothing: each side is a UsageReading credited to its reader, and a view can take the graph as either reads it, both kept and neither resolved. Not the same as Unmarked (no one has claimed anything), and not used where the text itself settles it: 'He was speaking about the temple of His body' (Jhn 2:21) is a stated figure.",
    "Entity": "Anything a word can be about. Abstract: every entity is one of the classes below, or, where the text's own categorizations conflict, left a bare Entity, with the conflict visible in its predications.",
    "Image": "A recurring vehicle as one node: 'the sword', 'light', 'the shepherd'. It gathers its figurative uses and nothing more. Two images are not related because their tenors coincide (seed and sword are both applied to the word of God, and that does not join them).",
    "ImageField": "Images used together in one passage, as one picture: shepherd, sheep, pasture, still waters, rod and staff (Psa 23). A field is found by co-occurrence inside a structure group, with the group as evidence, never by similarity of meaning.",
    "Individual": "One referent across its mentions: Abraham, Jerusalem, Goliath's sword. Typed by one class above (the least disputed). The graph's person, place, group, creature, object and event records map onto the classes; 'being' and 'image', which make claims, become predications and figures.",
    "PersonalBeing": "Anyone the text treats as a person: a human, God, an angel, a spirit addressed or speaking. One class over all of them, with subclasses. WordNet files God under noun.person too.",
    "Predication": "Somebody in the text says X is (or is called) a Y: 'the LORD is a man of war' (Exo 15:3), 'my Lord and my God' (Jhn 20:28), 'that ancient serpent, who is called the devil' (Rev 12:9). The saying is the fact. What kind of thing X is, is answered by collecting these, the text's own categorization, every one cited, rather than by one type.",
    "Reading": "One reader's claim about the text, with the reader (prov:wasAttributedTo) and the evidence it points at. Readings may disagree, and all are kept.",
    "Sign": "A real thing in the scene that also stands for something, where the text says so: the bow in the cloud is a bow and 'the sign of the covenant' (Gen 9:13); the stones from the Jordan are stones and 'a sign among you' (Jos 4:6). Repetition, extra attention, contrast or cultural meaning do not make a use a sign: Exodus repeats the tabernacle's boards for chapters, and they are boards. A Sign carries a FigurativeUse with tenorBasis 'stated'.",
    "ToldWorld": "Opened by a parable, dream, vision or sign-act: a Communication whose content is a told world.",
    "assumedFormOf": "The form is the subject, the one who assumed it the object: the incarnate Jesus assumed form of Jesus (Php 2:6-8); the three men at Mamre assumed form of the LORD (Gen 18:1-2). The incarnate node carries the Human membership the text argues for; the relation says whose form it is.",
    "categories": "Top level: WordNet's lexicographer files (26 noun, 15 verb), free, standard, and complete by construction: every WordNet sense sits in exactly one. Below it, WordNet synsets reached through English glosses, as an overlay. Proper names are typed in layer 3, not here.",
    "derivedVia": "'English' where a fact came through an English gloss, so a reader can discount it and a query can ask for what rests on the original languages only.",
    "extendedFrom": "Sense to the sense it grew from by a conventional figure: heart (the inner self) from heart (the organ); face (presence) from face; arm (power) from arm; flesh (the fallen self, in Paul) from flesh; way (conduct) from way; tongue and lips (speech) from the organs. Decided word by word.",
    "legacyType": "The type a record carried before this ontology (person, place, concept, image ...), kept verbatim on whatever it becomes here. Nothing is re-typed silently: every move is a rule with a count.",
    "marker": "What in the form shows it: 'category clash in a copular clause', 'comparative כְּ / ὡς', 'relative which-is', 'genitive of apposition', 'an explanation in a told world'. A use found by a rule that judges (the clash rule) carries bom:status 'flagged' until read.",
    "polarity": "positive | negative | neutral, of a quality sense.",
    "status": "built | proposed | withdrawn: whether the graph has instances of the term yet.",
    "tenor": "What the image is applied to: an individual ('the LORD'), a stated meaning ('the word of God', Eph 6:17), or absent where the text does not say. On a FigurativeUse when the text states it; on a SymbolReading when a reader supplies it. Deliberately no rdfs:domain: with one, RDFS inference would turn every reader's SymbolReading into a figure of the text.",
    "usage": "Of an occurrence: bom:Literal, bom:Figurative, or bom:Unmarked. No default: an occurrence is Figurative only where a FigurativeUse exists, Literal only where something marks it so, and otherwise Unmarked, which is most words, and says nothing.",
    "Lexeme": "A Hebrew, Aramaic or Greek dictionary word.",
    "Occurrence": "One MACULA word (morpheme) at one place: the node the structure already has (the structure layer's Word), keyed by MACULA xml:id. Everything below hangs off occurrences, never off verses.",
    "Sense": "One distinguishable use of a lexeme. Induced, not given: from the English glosses MACULA gives it (every variant kept), and later from clusters of how the word is used. A sense carries its own provenance.",
    "septuagintRendering": "Hebrew lexeme to the Greek lexeme MACULA aligns to it in the Septuagint, with a count: the cross-language bridge, an independent check on English glosses.",
}


def main():
    g = rdflib.Graph()
    g.parse(SRC, format="turtle")
    done, left = set(), []
    for s, p, o in list(g):
        if p not in (RDFS.comment, SKOS.definition) or not isinstance(o, Literal) or not INTERNAL.search(str(o)):
            continue
        name = str(s).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        if name in PUBLIC and str(s) in (BOM + name, BOW + name):
            g.remove((s, p, o))
            g.add((s, p, Literal(PUBLIC[name])))
            done.add(name)
        elif s == URIRef("https://bibleontology.org/ns/meaning"):
            continue        # the ontology's own header: policy and versioning only
        else:
            left.append((name, str(o)))
    for name in sorted(set(PUBLIC) - done):
        left.append((name, "(a public text written for a comment no longer found)"))
    for name, text in PUBLIC.items():
        if INTERNAL.search(text):
            left.append((name, "PUBLIC text itself points inside: " + text[:80]))
    # OWL TYPING, so an owl:Ontology holds OWL terms (plan 8.1e item 4; the
    # committee's ontology expert counted 52 bare rdf:Property): a property is
    # a datatype property where its range is a datatype or the examples give it
    # literal values, an object property otherwise; a class is an owl:Class.
    # The working file keeps its plain RDFS; the published one gains the types
    from rdflib.namespace import OWL, RDF, XSD
    ex = rdflib.Graph()
    exp = ROOT / "ontology" / "meaning" / "examples.ttl"
    if exp.exists():
        ex.parse(exp, format="turtle")
    typed = collections.Counter()
    for p in set(g.subjects(RDF.type, RDF.Property)):
        rng = g.value(p, RDFS.range)
        used_literal = any(isinstance(o, Literal) for o in ex.objects(None, p))
        if (rng is not None and (str(rng).startswith(str(XSD)) or rng == RDFS.Literal)) or (rng is None and used_literal):
            g.add((p, RDF.type, OWL.DatatypeProperty))
            typed["datatype"] += 1
        else:
            g.add((p, RDF.type, OWL.ObjectProperty))
            typed["object"] += 1
    for c in set(g.subjects(RDF.type, RDFS.Class)):
        g.add((c, RDF.type, OWL.Class))
        typed["class"] += 1
    print(f"  OWL typing added: {dict(typed)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("# Bible Ontology -- meaning. Published from ontology/meaning/meaning.ttl by tools/ns_meaning.py.\n"
                   + g.serialize(format="turtle"), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(g)} triples; {len(done)} comments given their public text")
    for name, t in left:
        print(f"  NEEDS A PUBLIC TEXT: {name} | {t[:160]}")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
