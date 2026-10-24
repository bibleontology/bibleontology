"""THE 1.2.0 INVENTORY (plan 8.1e, part 1; 2026-10-18: build the 1.2.0
inventory).

Everything that would enter 1.2.0, computed rather than remembered: each
vocabulary as the generators would publish it now, diffed term by term
against the released 1.1.1 (out/ns/versions/*-2026-10-17.ttl, kept forever).
The generators write to out/ns, which is served, so every served file is
snapshotted first and restored byte for byte afterwards, whatever happens.

    python tools/vocab_inventory.py   -> docs/review/inventory-1.2.0.html
"""
import html
import json
import subprocess
import sys
from pathlib import Path

import rdflib
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
NS = ROOT / "out" / "ns"
REL = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))
RELEASED = REL["date"]
BASES = {"structure": "https://bibleontology.org/ns/structure#", "relation": "https://bibleontology.org/ns/relation#",
         "meaning": "https://bibleontology.org/ns/meaning#", "claim": "https://bibleontology.org/ns/claim#"}
SHOWN = [(RDF.type, "type"), (RDFS.label, "label"), (SKOS.definition, "definition"), (RDFS.domain, "domain"),
         (RDFS.range, "range"), (RDFS.subPropertyOf, "under"), (RDFS.subClassOf, "a kind of"),
         (OWL.deprecated, "deprecated")]
e = html.escape
import yaml  # noqa: E402
RELATION_TYPES = set((yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml")
                                     .read_text(encoding="utf-8")).get("types") or {}))
STATES_DEF = json.loads((ROOT / "ontology" / "schema" / "relation_definitions.json").read_text(encoding="utf-8"))

# WHERE EACH ADDITION WAS DECIDED. A term not listed here says "not traced":
# the inventory is the place to find a change nobody ruled on.
SHEET = "the 1.2.0 sheet, approved 2026-10-18 ('approve of the sheet')"
DECIDED = {
    **{t: SHEET for t in ("when", "comes_true", "means", "List", "heading", "item", "attached", "indirect",
                          "presented", "setting", "movement", "toward_someone", "grounds", "how", "between_things",
                          "place", "presence", "time", "circumstance", "sphere", "direction", "source", "extent",
                          "recipient", "beneficiary", "target", "opposition", "dominion", "cause", "purpose",
                          "authority", "manner", "agent", "accompaniment", "possession", "reference", "comparison",
                          "between", "without", "prep_relation")},
    "rests_on": "Doug, 2026-10-17: 'rename basis to rests_on'",
    "composed_of": "P-2026-10-18-9 (Doug's word, Matthew 3:4)",
    "according_to": "P-2026-10-18-10 ('name it according_to under grounds')",
    "partitive": "Doug, 2026-10-18: 'go with partitive' (shared across two levels)",
    "Generic": "plan 1.43 (P-2026-10-18-11, built as P-2026-10-18-14)",
    "Together": "plan 1.43 (P-2026-10-18-11, built as P-2026-10-18-14)",
    "clause_link": "plan 8.1b: range widened to Unit (P-2026-10-18-16)",
    "member_of_group": "plan 8.1b: range widened to Unit (P-2026-10-18-16)",
    "group_role": "P-2026-10-18-15 (the name kept by Doug on the 1.2.0 inventory)",
    "says": "plan 8.1d (P-2026-10-18-7, built as -17)",
    "reader": "P-2026-10-18-18: aligned with PROV (from a reply on r/semanticweb)",
    "reportedBy": "plan 8.1d (P-2026-10-18-7, built as -17)",
    # since the sheet's approval (built 2026-10-19/20, plan 1.2.0 steps 2 to 4)
    "states": "plan 2.19 lift 1: verb statements (P-2026-10-19-11)",
    "spoke_to": "G1, approved on the refreshed 1.2.0 inventory (2026-10-20)",
    "modality_foretold": "G2, approved on the refreshed 1.2.0 inventory (2026-10-20)",
    **{t: "plan 8.1f: the filter as data (Doug chose 'Card words + navigator', 2026-10-19)"
       for t in ("CardWord", "Tie", "Tier", "card", "cardWordShare", "default", "filterPolicy", "label",
                 "navigatorFloor", "navigatorTieStrength", "onRequest", "relation", "salience", "tier", "word",
                 "wordBasis")},
    **{t: "plan 2.17 step 3: the verb-statement terms (P-2026-10-19-11)"
       for t in ("Modality", "VerbFamily", "clause", "evidencedBy", "family", "familyFrom", "grammaticalVoice",
                 "modalities", "modality", "modalityFrom", "mood", "negated", "person", "stem", "verb",
                 "verbFamilies", "verbLabel")},
}
DECIDED.update({t: "plan 2.17 step 3: the verb-statement terms (P-2026-10-19-11)"
                for t in [f"family_verb_{x}" for x in ("body", "change", "cognition", "communication", "competition",
                                                        "consumption", "contact", "creation", "emotion", "motion",
                                                        "perception", "possession", "social", "stative", "weather")]
                + [f"modality_{x}" for x in ("asked", "commanded", "commanded_or_wished", "nonfinite", "promised",
                                             "stated", "urged", "wished")]})


# THE DECISIONS IN PLAIN WORDS (2026-10-18: the lines were cryptic, and it is
# better treated like an override scenario). Each: what it changes, an
# example, what Claude recommends and why. `match` picks its terms by the
# trace text; every term must land in exactly one, or the sheet is not written.
PLAIN = [
    {"id": "parents", "match": ["parent link"], "title": "Every relation says which family it belongs to",
     "what": "Each relation is published under its parent: a link between clauses under 'clause link', a part of a group under 'group member', and so on. A query for the family finds every relation in it.",
     "example": "'purpose' sits under 'clause link' and also under the phrase family 'grounds', so one query finds the aim of an act whether it is a clause ('so that ...') or a phrase ('for an offering').",
     "rec": "Include.", "why": "It is what makes the vocabulary navigable, and it was checked: every relation's ends fit inside its parent's. That check found five that did not, and the parents were widened (the next decision but one)."},
    {"id": "deferred", "match": ["deferred: plan 1.42", "the fifth status"], "title": "36 kinds marked 'deferred' instead of 'built', and the status list that names it",
     "what": "The kinds the earlier builder made and the current one does not yet make are published as 'deferred', a status you named on 15 October, and the status list says so. Today they would be published as 'built', which is false.",
     "example": "'Parallel', two lines of poetry that say the same thing twice. Readers still see these, supplied by the structure sweep as automated analysis, and the reason published with each says so.",
     "rec": "Include.", "why": "The published status should be true. See question 4 for whether 'shown from the readings' deserves its own word."},
    {"id": "status_other", "match": ["now built: plan 1.42", "withdrawn: plan 1.42", "Verb under Word"], "title": "Four small corrections from the closed-world check",
     "what": "'Question' and 'undecided' are now built (the builder makes them); the old 'flat' layer is withdrawn (it was retired); a verb is now declared a kind of word occurrence.",
     "example": "'flat' was the first layer, before clauses existed; nothing has used it since the clean builder.",
     "rec": "Include.", "why": "Each makes the vocabulary say what the graph is."},
    {"id": "widened", "match": ["range widened", "widened in plan 1.42"], "title": "Four relations accept any unit at their far end",
     "what": "'clause link' and 'group member' (as parents), and 'qualifier' and the verb role, may now point at any unit, not only a clause or a word.",
     "example": "What a speech says ('content') is often a command together with what it governs, a group, not a single clause. With the narrow range, a reasoner would have concluded that the group was a clause.",
     "rec": "Include, and let the committee settle question 1 (whether this is a minor or a major version).",
     "why": "The narrow range was false of the data. Widening makes the term claim less, not something different."},
    {"id": "sheet", "match": ["the 1.2.0 sheet", "rests_on"], "title": "What you approved on the 1.2.0 sheet",
     "what": "New clause links ('when', 'comes true', 'by means of'), the list group (heading and items), 'attached', two marks ('presented' for 'behold', 'indirect' for reported speech), 'content' widened to indirect speech, and the prepositional phrase relations: six families and their types, with 'basis' renamed 'rests_on'.",
     "example": "Acts 1:10, 'as He was going', is 'when'; Acts 2:9-11's peoples are a list.",
     "rec": "Include.", "why": "Approved on 18 October ('approve of the sheet') and since built."},
    {"id": "new_types", "match": ["P-2026-10-18-9", "P-2026-10-18-10", "go with partitive"], "title": "Three phrase types from today",
     "what": "'composed of' (what a thing is made of), 'according to' (the standard something is in keeping with), and 'partitive' (one of, or some of) shared between phrases and people.",
     "example": "'a garment of camel's hair' (Matthew 3:4); 'according to your faith' (Matthew 9:29); 'a priest' as one of 'the priests' (Leviticus 21:1).",
     "rec": "Include.", "why": "Your words and rulings today; 'according to' took 170 of 210 scattered answers to one name."},
    {"id": "readings_kinds", "match": ["plan 1.43"], "title": "Two kinds only the model's readings make",
     "what": "'Generic' (someone the text describes but does not name) and 'Together' (one 'we' standing for several people named apart).",
     "example": "Matthew 20:18's 'we' is Jesus and the twelve of 20:17.",
     "rec": "Include.", "why": "Readers see them on every verse panel; declaring them lets the check hold the model's layer to the vocabulary."},
    {"id": "group_role", "match": ["P-2026-10-18-15"], "title": "A parent for who takes part in a group",
     "what": "Who speaks a turn, to whom, and whom every line of a collection is about, under one parent, so a query for a group's participants finds them.",
     "example": "In 'Then the LORD said to Satan' (Job 2:3) the sender is the LORD and the addressee Satan.",
     "rec": "Include, with your name for it (question 2). 'group_role' is a placeholder; 'participant' is already taken by the clause roles.", "why": "Without a parent, these three are the only relations that belong to no family."},
    {"id": "warning", "match": ["go ahead and include"], "title": "'warning' becomes a kind the readings make",
     "what": "From 'proposed' to built by the readings: what follows if a command is refused. It points at a clause, not only at an if/then. Shown only where two judges agree (86 of the sweep's 196); warnings nobody proposed are not yet looked for, and the definition says so.",
     "example": "'Do not go up, lest you be struck down by your enemies' (Numbers 14:42).",
     "rec": "Include.", "why": "Your ruling (2026-10-18), after the two-judge check: 16 of 16 right on a fresh sample."},
    {"id": "prov", "match": ["aligned with PROV"], "title": "Claims attributed the PROV way",
     "what": "A claim is a PROV entity; who says it (claimed by) and whose voice a graph is (voice of) are kinds of PROV attribution; a reader becomes an agent (claim:reader) beside its name (read by). The export also states prov:wasAttributedTo on each attributed claim, so a plain PROV query works without a reasoner.",
     "example": "Ask a store with no reasoning 'to whom are the claims about Job attributed?' and it answers Job 47, Eliphaz 17, God 8, Elihu 5 (Jena and RDF4J alike).",
     "rec": "Include, and have the committee confirm one point: under RDFS this types every speaker as a PROV agent, divine persons included, beside a reasoning policy that says nothing about the records of God, the Father, Jesus or the Holy Spirit is derived by inference (it forbids derivations, not descriptions; reworded neutrally, 2026-10-19, at the committee's suggestion).",
     "why": "Your approval (P-2026-10-18-18), from the r/semanticweb reply; alignment brings the interoperability the expert in your brief values."},
    {"id": "claims", "match": ["plan 8.1d"], "title": "Two claim terms for speech within speech",
     "what": "'reported by' (whose report a voice is) and 'says' (a speaker's claim that another speaker says something).",
     "example": "Jeremiah 32:7: the LORD's word, as Jeremiah reports it. In RDF 1.2: Jeremiah claims <<( the LORD says <<( Shallum is Hanamel's father )>> )>>, a triple term nested in another.",
     "rec": "Include.", "why": "Built and checked in Jena and RDF4J today; it is RDF 1.2 used where it fits, the showcase you asked for."},
    {"id": "step5", "approved": "2026-10-20", "match": ["approved on the refreshed 1.2.0 inventory"],
     "title": "Two terms the worked lifts found",
     "what": "'spoke to' (who speaks to whom, the narrator's statement, the turn its evidence) and the force 'foretold' (a prediction of another, described, never stated).",
     "example": "Isaac spoke to Abraham (Gen 22:7); 'you will deny Me three times' (John 13:38) is foretold.",
     "rec": "Include.", "why": "Approved as G1 and G2 on the refreshed sheet."},
    # ---- NEW SINCE THE SHEET'S APPROVAL (2026-10-18): marked "new", shown first
    {"id": "states", "new": True, "match": ["plan 2.19 lift 1"], "title": "The relation type 'states', and its definition",
     "what": "One relation type for every verb statement lifted from a clause, labelled by its own verb, so 'God loved the world' is on God's card and the world's without a relation type per verb. Its public definition is a draft of mine, below; it is the one text on this sheet you have not seen.",
     "example": "John 3:16: God — loved — world. 792 statements are shown; 287 are held (speaker unknown, or a verb whose form does not say it happened).",
     "rec": "Include, with the definition as drafted (or reworded by you).",
     "why": "The alternative, a relation type per verb, would add hundreds of types the vocabulary would have to define one by one."},
    {"id": "verb_terms", "new": True, "match": ["plan 2.17 step 3"], "title": "What a verb statement carries",
     "what": "The verb as the Berean renders it, its Hebrew or Greek word, its grammar (stem, mood, person, voice, negation), the force it is said with (stated, commanded, promised, asked, wished, urged, non-finite) and the broad kind of act (WordNet's fifteen verb families), the clause it was lifted from, and 'evidenced by' where it confirms a relation built by hand.",
     "example": "John 3:16: verb 'loved' (ἀγαπάω), aorist indicative, active, stated by its form, family 'feeling', clause Jhn.3.16#cl0. 'Samuel anointed David', built by hand, gains 1 Sam 16:13's clause as its evidence (54 such).",
     "rec": "Include.", "why": "The terms that make a statement checkable: a reader or a query can see why it is asserted, or why it is not."},
    {"id": "filter", "new": True, "match": ["plan 8.1f"], "title": "The filter, published as data",
     "what": "A card's words with their strength (a DQV quality measurement) and tier (shown by default, or on request); each navigator tie with its strength and each centre's floor; the policy itself as a dqv:QualityPolicy, with a SHACL shape the shown words pass and a published query that rebuilds the shown view exactly.",
     "example": "David's navigator floor is 5.413942 in the data and in the page; the published CONSTRUCT returns the 22,913 triples of the shown card words, isomorphic to the shown graph.",
     "rec": "Include.", "why": "Your aim: the filtering is self-evident in the graph, not only a UI feature."},
    {"id": "owl", "new": True, "match": ["OWL typing of /ns/meaning"], "title": "/ns/meaning typed for OWL tools",
     "what": "Every class published as owl:Class and every property as an object or datatype property (22 datatype, 38 object, 63 classes); no term left as a bare rdf:Property. Nothing is renamed and no definition changes.",
     "example": "bom:inField was a plain property; it is now an object property, so an OWL editor shows it as a link between things.",
     "rec": "Include.", "why": "The committee's profile check (B2); it changes how tools read the terms, not what they mean."},
    {"id": "domrange", "new": True, "match": ["domain and range from the one class"], "title": "Relations given a real domain and range",
     "what": "Where every kind a relation allows at one end is one class of the meaning vocabulary, that class is published as its domain or range (30 domains, 31 ranges). Where an end allows several classes, none is stated: in RDFS two domains mean both, not either, and the closed-world check keeps enforcing the list.",
     "example": "'went to' (traveled_to) now has range Place; 'in theme' has range Concept.",
     "rec": "Include.", "why": "The committee's profile check (B2): a reasoner can now type a relation's ends, and only where the type is certain."},
]
QUESTIONS = [
    ("q1", "Is widening a range a minor or a major change?", "The versioning rule: additions raise the minor version (1.2.0), a change of meaning the major (2.0.0). The four widened relations claim less, not something else.", "Treat it as minor (1.2.0), and have the committee confirm."),
    ("q2", "Your name for the parent of sender, addressee and the collection's subject.", "'participant' is taken (the clause roles).", "'group_role' unless you prefer another; 'party' and 'role_in_group' are alternatives."),
    ("q3", "'warning': settled.", "You asked what getting it right would cost; two judges were run, and 86 of 196 kept (see the decision above).", "Included, by your ruling of 2026-10-18."),
    ("q4", "Does 'deferred in the builder, shown from the readings' need its own status word?", "36 kinds are deferred, and readers see 21 of them from the model's readings. The reason on each says so.", "Not for 1.2.0: the reason text is accurate. A word of its own is a question for the committee."),
    ("q5", "RDF 1.2 published at Candidate Recommendation", "Your position: a showcase of the spec where it fits, refactoring accepted. The 13 October evaluation said wait for Recommendation.", "Keep the position, and state it in the release notes and the blog."),
]
# NEW SINCE THE APPROVAL: the decisions step 5's worked lifts found
# (docs/review/lift-shapes-1.2.0.md; P-2026-10-20-1 and -2)
NEW_QUESTIONS = [
    ("g1", "Who speaks to whom has no relation type. Add 'spoke to'?",
     "Lift 3 (Isaac said to Abraham, Gen 22:7). 'told' is who gave a picture (its object a text); 'answered' is speech answering speech. The turns already hold sender and addressee.",
     "Add spoke_to (person, being or group to the same), 'spoke to' / 'was spoken to by': the narrator's statement, the turn as its evidence."),
    ("g2", "A prediction about someone else has no force to record. Add 'foretold'?",
     "'You will deny Me three times' (John 13:38) is not a promise (the speaker binding himself) and not a statement. Described, never stated; that it came true is the narrator's own statement (Mark 14:72).",
     "Add claim:modality_foretold to the forces."),
    ("g4", "Evidence that is not a clause: widen 'evidenced by'?",
     "Places ('to Bethel', Gen 13:3) and family from apposition ('Saul son of Kish', 1 Sam 10:21) rest on a phrase; speech rests on a turn. The definition says 'a clause'.",
     "Widen the definition to 'a part of the text's structure: a clause, a phrase in it, or a speech turn'. No new term."),
    ("g5", "The structure's addresses: one book code, declared",
     "Claims point to clauses as structure/Jhn.3.16#cl0 (MACULA's book codes) and to verses as p/John.3.16 (the site's). Nothing published says what a clause's address is, and the reasons lift (because, so that) is a join through it.",
     "Use the site's book codes for both (structure/John.3.16#cl0), and state the pattern in claim:clause's definition, before 1.2.0 and before the structure layer is published."),
    ("g6", "A command's label: the verb's plain form, not the past tense?",
     "'loved' is right for John 3:16; for 'you shall love the LORD' (Deut 6:5) it would say something that did not happen.",
     "A described statement's label is the plain form ('love'); only an asserted one is put in the past tense."),
    ("time", "Read the time of the 197 held statements (P-2026-10-20-1)",
     "Held because the verb's form does not say the thing happened: 'God put enmity' (Gen 3:15, 'I will put'), 'Jesus saved the world' (John 12:47, 'that I might save'). Some are true pasts or general truths ('The LORD tests the righteous', Ps 11:5).",
     "Two judges (Haiku, Sonnet where they differ) ask: did it happen or is it so, or is it a future, command, wish, purpose or condition? Release the first as stated; the rest become described claims with their force."),
]


# A released term changed by one ruling of its own, whatever changed in it
PROV = "P-2026-10-18-18: aligned with PROV (from a reply on r/semanticweb)"
CHANGED_BY = {"warning": "Doug, 2026-10-18: 'go ahead and include' (two judges agreeing, 86 kept)",
              **{t: PROV for t in ("Claim", "claimedBy", "voiceOf", "readBy")}}


def trace_change(t, d):
    """Where a CHANGE to a released term was decided, by what changed."""
    if t in CHANGED_BY:
        return CHANGED_BY[t]
    why = []
    if "under" in d:
        why.append("parent link: plan 8.1b (P-2026-10-17-8, built as P-2026-10-18-16)")
    if "status" in d:
        a, b = d["status"]
        why.append({("built", "deferred"): "deferred: plan 1.42 (built 2026-10-18, P-2026-10-18-3)",
                    ("proposed", "built"): "now built: plan 1.42",
                    ("superseded", "withdrawn"): "withdrawn: plan 1.42"}.get((a[0] if a else "", b[0] if b else ""),
                                                                              "status change: not traced"))
    if "range" in d or "domain" in d:
        why.append(DECIDED.get(t) or {"qualifier": "widened in plan 1.42 (known_fault note)",
                                      "v": "widened in plan 1.42 (known_fault note)"}.get(t)
                   or ("domain and range from the one class its kinds allow: plan 8.1e item 4"
                       if t in RELATION_TYPES else "range change: not traced"))
    if set(d) == {"type"}:
        why.append("OWL typing of /ns/meaning: plan 8.1e item 4 (the committee)")
    if "a kind of" in d:
        why.append("Verb under Word: plan 1.42" if t == "Verb" else "parent class change: not traced")
    if "definition" in d:
        why.append(SHEET if t == "content" else "definition reworded: not traced")
    if "label" in d:
        why.append("the fifth status, 'deferred': plan 1.42 (Doug's word of 2026-10-15)" if t == "status"
                   else "label change: not traced")
    return "; ".join(why) or "not traced"


def run(script):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / script)], capture_output=True, text=True,
                       encoding="utf-8", cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip().splitlines()[-1:] or [""]


def generated():
    """Each vocabulary as it would be published now; out/ns restored after."""
    snap = {p: p.read_bytes() for p in NS.glob("*.ttl")}
    try:
        notes = {s: run(s)[0] for s in ("ns_structure.py", "ns_relation.py", "ns_meaning.py")}
        g = {n: (NS / f"{n}.ttl").read_bytes() for n in ("structure", "relation", "meaning")}
        g["structure-shapes"] = (NS / "structure-shapes.ttl").read_bytes()
    finally:
        for p, b in snap.items():
            p.write_bytes(b)
        for p in NS.glob("*.ttl"):
            if p not in snap:
                p.unlink()
    g["claim"] = (ROOT / "ontology" / "claim" / "claim.ttl").read_bytes()
    g["claim-shapes"] = (ROOT / "ontology" / "claim" / "shapes.ttl").read_bytes()
    return g, notes


def graph(data):
    return rdflib.Graph().parse(data=data.decode("utf-8"), format="turtle")


def short(x):
    s = str(x)
    for b in BASES.values():
        if s.startswith(b):
            return s[len(b):]
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1] if s.startswith("http") else s


def terms(g, base):
    out = {}
    for s in set(g.subjects()):
        if isinstance(s, rdflib.URIRef) and str(s).startswith(base):
            out[str(s)[len(base):]] = {name: sorted(short(o) for o in g.objects(s, p)) for p, name in SHOWN}
            out[str(s)[len(base):]]["status"] = sorted(str(o) for o in g.objects(s, rdflib.URIRef(BASES["structure"] + "status")))
    return out


def diff(old, new):
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for t in sorted(set(old) & set(new)):
        d = {k: (old[t][k], new[t][k]) for k in new[t] if old[t].get(k) != new[t][k]}
        if d:
            changed.append((t, d))
    return added, removed, changed


def main():
    gen, notes = generated()
    sections, counts = [], {}
    for name, base in BASES.items():
        old = terms(graph((NS / "versions" / f"{name}-{RELEASED}.ttl").read_bytes()), base)
        new = terms(graph(gen[name]), base)
        added, removed, changed = diff(old, new)
        counts[name] = (len(added), len(changed), len(removed))
        rows = []
        for t in added:
            x = new[t]
            rows.append(("new", t, DECIDED.get(t, "not traced: who decided this?"), f"{', '.join(x['type'])}{' · under ' + ', '.join(x['under']) if x['under'] else ''}"
                         f"{' · a kind of ' + ', '.join(x['a kind of']) if x['a kind of'] else ''}"
                         f"{' · ' + ' → '.join(filter(None, [', '.join(x['domain']), ', '.join(x['range'])])) if x['domain'] or x['range'] else ''}",
                         (x["definition"] or [""])[0]))
        for t, d in changed:
            what = "; ".join(f"{k}: {', '.join(a) or '—'} → {', '.join(b) or '—'}" if k != "definition"
                             else "definition reworded" for k, (a, b) in d.items())
            rows.append(("changed", t, trace_change(t, d), what, (new[t]["definition"] or [""])[0] if "definition" in d else ""))
        for t in removed:
            rows.append(("removed", t, "removed: not traced", "", ""))
        sections.append((name, base, rows))
    # the shapes: by shape subject
    sh_old = graph((NS / "versions" / f"shapes-{RELEASED}.ttl").read_bytes())
    sh_new = graph(gen["structure-shapes"]) + graph(gen["claim-shapes"]) + \
        rdflib.Graph().parse(ROOT / "ontology" / "meaning" / "shapes.ttl")
    so = {short(s) for s in sh_old.subjects(RDF.type, rdflib.URIRef("http://www.w3.org/ns/shacl#NodeShape"))}
    sn = {short(s) for s in sh_new.subjects(RDF.type, rdflib.URIRef("http://www.w3.org/ns/shacl#NodeShape"))}
    shapes_rows = [("new", s, "generated from kinds.json's lists of kinds (a relation joining several)", "a SHACL shape", "")
                   for s in sorted(sn - so)] + \
                  [("removed", s, "no longer generated: a relation's ends now one kind, or the relation changed", "a SHACL shape", "")
                   for s in sorted(so - sn)]
    claim_shape_changed = b"claim#says" in gen["claim-shapes"]

    # EVERY TERM IN EXACTLY ONE PLAIN DECISION, or nothing is written: a term
    # that lands in none is a change nobody has explained to the reviewer
    placed = {}
    for name, _b, rows in sections + [("shapes", None, shapes_rows)]:
        for kind, t, src, what, definition in rows:
            hits = [p["id"] for p in PLAIN if any(m in src for m in p["match"])]
            if "generated from kinds.json" in src or "no longer generated" in src:
                hits = ["shapes"]
            # a change traced to two decisions (a status move and a parent
            # link) is listed under each, so every decision's count is whole
            if not hits:
                raise SystemExit(f"{name}:{t} ({src}) belongs to no plain decision: explain it before the sheet is written")
            for h in hits:
                placed.setdefault(h, []).append((name, kind, t, src, what))
    plain = PLAIN + [{"id": "shapes", "title": "The published checks follow the vocabulary",
                      "what": "The SHACL shapes published beside the vocabulary are regenerated from it: where a relation joins one of several kinds, a shape lists which. The claim shape lets a reporting speaker's claim use 'says'.",
                      "example": "The shape for 'content' says its far end is a clause or a group.",
                      "rec": "Include.", "why": "They are generated, so they say what the vocabulary says."}]
    total_new = sum(a for a, _c, _r in counts.values())
    total_changed = sum(c for _a, c, _r in counts.values())

    def marks(mid):
        return (f"<div class=mk data-id='{e(mid)}'><label><input type=radio name='{e(mid)}' value=override> override</label>"
                f"<label><input type=radio name='{e(mid)}' value=discuss> discuss</label>"
                f"<label><input type=radio name='{e(mid)}' value=''> as recommended</label>"
                f"<input class=nt placeholder='what you would change, or want to talk about'></div>")

    def group(p, marked):
        ts = placed.get(p["id"], [])
        detail = "".join(f"<li><b>{e(t)}</b> <span class=k>({e(kind)} in /ns/{e(n)}) {e(w)} · {e(s)}</span></li>"
                         for n, kind, t, s, w in ts)
        extra = ""
        if p["id"] == "states":
            d = STATES_DEF["types"]["states"]
            extra = (f"<blockquote class=def>{e(d['definition'])}</blockquote>"
                     f"<p class=k>{e(d['by'])}; ontology/schema/relation_definitions.json</p>")
        return (f"<section><h2>{e(p['title'])} <span class=k>· {len(ts)} term{'s' if len(ts) != 1 else ''}</span></h2>"
                f"<p>{e(p['what'])}</p>{extra}<p class=ex><b>For example:</b> {e(p['example'])}</p>"
                f"<p class=rec><b>Recommended: {e(p['rec'])}</b> {e(p['why'])}</p>"
                f"<details><summary>Show the terms</summary><ul>{detail}</ul></details>"
                + (marks('decision:' + p['id']) if marked else f"<p class=k>Approved {p.get('approved', '2026-10-18')}.</p>")
                + "</section>")

    # NEW SINCE THE APPROVAL FIRST, then the decisions the worked lifts found,
    # then what was approved on 18 October, folded (2026-10-20: not too
    # time consuming)
    new_groups = [p for p in plain if p.get("new") and placed.get(p["id"])]
    old_groups = [p for p in plain if not p.get("new") and placed.get(p["id"])]
    body = ["<h2 class=part>New since you approved the sheet on 18 October</h2>"]
    body += [group(p, True) for p in new_groups]
    body.append("<section><h2>The claim export: what changed in its form</h2>"
                "<p>Each judged claim now names the run that produced it (prov:wasGeneratedBy, 1,017 claims; runs as "
                "prov:Activity, the models as prov:SoftwareAgent). 'says' has one range in both files (the reporter says "
                "the inner claim). The export itself refuses to state a command, promise, prediction, negated statement "
                "or a verb whose form does not say it happened: it is described, never asserted (21,707 claims).</p>"
                "<p class=ex><b>For example:</b> 'Jesus saved the world' (John 12:47, 'that I might save') is in no "
                "store as a fact; the worked examples test it with a command planted in a speaker's graph.</p>"
                "<p class=rec><b>Recommended: include.</b> Checked by the claim, statement and lift-shape tests. The "
                "RDF 1.2 file is re-checked in Jena and RDF4J before the tag.</p>"
                + marks("decision:export-r2") + "</section>")
    body.append("<section><h2>Decisions the worked lifts found <span class=k>· step 5</span></h2>"
                "<p class=k>One worked example of each future lift, tested against the shape "
                "(docs/review/lift-shapes-1.2.0.md). Five gaps, and the held statements.</p>" + "".join(
        f"<div class=q><p><b>{i}. {e(q)}</b></p><p class=k>{e(ctx)}</p><p class=rec><b>Recommended:</b> {e(rec)}</p>"
        f"{marks('question:' + qid)}</div>" for i, (qid, q, ctx, rec) in enumerate(NEW_QUESTIONS, 1)) + "</section>")
    body.append(f"<details class=old><summary><b>Approved on 18 October</b> <span class=k>· {len(old_groups)} groups and "
                f"{len(QUESTIONS)} questions, unchanged, for reference</span></summary>"
                + "".join(group(p, False) for p in old_groups)
                + "<section><h2>The questions you answered</h2>" + "".join(
                    f"<div class=q><p><b>{i}. {e(q)}</b></p><p class=rec><b>Recommended:</b> {e(rec)}</p></div>"
                    for i, (qid, q, ctx, rec) in enumerate(QUESTIONS, 1)) + "</section></details>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>1.2.0 inventory</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D;--warm:#96591A;--bad:#A23B3B}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F;--warm:#E2B04A;--bad:#E58A8A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:1040px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 14px;margin:14px 0;overflow-x:auto}}
h2{{font-size:18px;margin:6px 0}} .k{{color:var(--muted);font-size:13px}} .d{{font-size:13.5px;margin-top:2px}}
table{{border-collapse:collapse;width:100%}} td,th{{text-align:left;vertical-align:top;padding:6px;border-bottom:1px solid var(--rule)}} th{{font-size:12px;color:var(--muted);font-weight:normal}}
.tag{{font:12px/1.6 system-ui,sans-serif;border-radius:8px;padding:0 7px;border:1px solid var(--rule)}} .new{{color:var(--ok)}} .changed{{color:var(--warm)}} .removed{{color:var(--bad)}} .shape{{color:var(--accent)}}
.untraced{{color:var(--bad);font-weight:bold}} .mk{{font-size:13px;border-top:1px dashed var(--rule);margin-top:8px;padding-top:6px}} .mk label{{margin-right:10px}}
.lead{{font-size:15.5px}} .ex{{color:var(--muted)}} .rec{{border-left:3px solid var(--ok);padding-left:8px}} details{{margin:6px 0;font-size:13.5px}} .q{{border-bottom:1px solid var(--rule);padding:4px 0}}
.nt{{display:block;margin-top:4px;width:min(520px,100%);font:inherit;font-size:13px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
.part{{font-size:20px;margin:18px 0 0}} .def{{margin:6px 0;padding:6px 10px;border-left:3px solid var(--accent);background:var(--paper)}}
details.old > summary{{font-size:16px;margin:18px 0 6px;cursor:pointer}}
</style></head><body><main><h1>What would enter 1.2.0</h1>
<p class=lead>The refreshed sheet. Against what is published now (1.1.1, {RELEASED}), 1.2.0 has {total_new} new
terms and {total_changed} changed. Most you approved on 18 October; they are folded at the bottom. <b>What needs your eye
is the {len(new_groups)} groups built since, and {len(NEW_QUESTIONS)} decisions</b>, each with what it changes, an example,
and what I recommend. Mark only what you want to override or discuss; anything left unmarked goes as recommended.</p>
<p class=k>Computed by tools/vocab_inventory.py from the generators: {e('; '.join(notes.values()))}</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(body)}</main><script>
const KEY='inventory-1.2.0-r2'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id,s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt');n.value=s.note||'';n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
// the marks are always shown in a box, selected: a sandboxed viewer blocks both
// the clipboard and prompt(), and the button then did nothing (2026-10-19)
document.getElementById('exp').onclick=async()=>{{
 // read the marks from the page at the moment of copying, so a note typed in a
 // view without storage is never lost (the tithe note, 2026-10-20)
 document.querySelectorAll('.mk').forEach(m=>{{const r=m.querySelector('input[type=radio]:checked'),n=m.querySelector('.nt').value;
  if(r||n){{M[m.dataset.id]={{mark:r?r.value:'',note:n}}}}}});save();
 const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 let box=document.getElementById('out');
 if(!box){{box=document.createElement('textarea');box.id='out';box.rows=8;box.readOnly=true;
  box.style.cssText='display:block;width:100%;margin-top:6px;font:12px monospace;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px';
  document.getElementById('st').after(box)}}
 box.value=x;box.focus();box.select();let ok=false;
 try{{await navigator.clipboard.writeText(x);ok=true}}catch(e){{try{{ok=document.execCommand('copy')}}catch(e2){{}}}}
 document.getElementById('st').textContent=ok?'Copied: paste it into the chat.':'Press Ctrl+C to copy the selected marks below, then paste them into the chat.'}};
</script></body></html>"""
    dest = ROOT / "docs" / "review" / "inventory-1.2.0.html"
    dest.write_text(page, encoding="utf-8")
    print(json.dumps(counts), "->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
