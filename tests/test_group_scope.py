"""The Jewish people's card says which of the people each relation is about (the owner's ruling of 2026-10-29: "keep
what the text clearly states, annotate it to distinguish the Jews as a whole from a representation within the group";
docs/review/card-panel-appeal/RULINGS-2026-10-29-jews.md, group/jews-scopes-judge.md).

  - DATA: every relation on `jews` (held or not) carries a scope, people or part; the 25 records are 8 people and 17
    part (one held); a part names its party in the Berean's own words (a contiguous part of the cited verse, or of the
    verse it is read from), and none is a pronoun alone; the retypes stand (rebuked -> spoke_to for John 8:31 and 8:39,
    persecuted -> conspired_against for Acts 9:23 and 23:12-13); a verse that says "the Jews" outright stays explicit
    (John 5:18, 7:1, 10:31, Acts 9:23, 22:30, 25:7, Dan 3:8: never demoted to implied by the scope)
  - DISPLAY: a "part" relation prints its party ("some of the Jews: <the verse's words>") and never the people's bare
    name, on the card of whoever stands at its other end (Jesus, Paul, Festus, Moses, Abraham, the Chaldeans, Esther)
    and on the group's own page and card; a "people" relation prints as it is; the headline counts the whole people
    apart from the parts
  - JOHN 8:44: held off the group card: on no card of either end, not on the group's page, in no JSON-LD, while its
    verse still prints on its own page
  - ROMANS 11:28: one sentence, never split into two relations, printed whole with "they" resolved in a bracket and
    its companions beside it; Rom 2:28-29, Rev 2:9 and 3:9 are in no relation and never filed on the people
  - JSON-LD: nothing from a part relation, no party and no John 8:44, in the group's page or in any card of an end
  - THE VALIDATOR refuses a part with no party, a party that is not in its verse, a bare pronoun as party, and an
    unscoped relation on a group flagged scope_required

Every check is proved by a planted fault: a check that cannot fail is not a check.
In process, after the graph loads (~1 minute). Run: python tests/test_group_scope.py"""
import html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "src"))
import server as S  # noqa: E402
from bibleont import validate as V  # noqa: E402
from bibleont.schema import Relation, load_persons, load_vocabulary  # noqa: E402

fails = []
planted = []
GROUP = "jews"
PART_WHO = "some of the Jews"
BARE_NAME = "the Jewish people"
HELD_REF = "John 8:44"


def check(ok, msg):
    if not ok:
        fails.append(msg)


def caught(name, fn):
    """A planted fault: `fn` must report at least one fault."""
    got = fn()
    planted.append((name, bool(got)))
    if not got:
        fails.append(f"planted fault NOT caught: {name}")


def fresh():
    """The server keeps recent answers; a planted fault must be read through, not from them."""
    S._RECENT.clear()
    S._RECENT_BYTES = 0


d = S.load()
RECS = []
for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            r = json.loads(ln)
            if GROUP in (r["src"], r["dst"]):
                RECS.append(r)
PEOPLE = [r for r in RECS if r.get("scope") == "people"]
PART = [r for r in RECS if r.get("scope") == "part"]
SHOWN_PART = [r for r in PART if not r.get("held")]
HELD = [r for r in RECS if r.get("held")]
corpus = V._berean()


def other_end(r):
    return r["dst"] if r["src"] == GROUP else r["src"]


def card(eid):
    return json.loads(S.answer("/api/entity", f"id={eid}"))


def items_of(c, other=None):
    return [it for g in c.get("groups") or [] for it in g["items"] if other is None or it.get("other") == other]


def match(r, items):
    """the item of a card that is this record (the same verses)"""
    return [it for it in items if set(it.get("refs") or []) == set(r["refs"]) and it["label"]]


def text_of(frag):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", frag)))


def connections(body):
    """the text of each connection on a page, in order"""
    seg = body.split("<h2>Connections</h2>", 1)[-1]
    return [text_of(x) for x in re.findall(r"<li>(.*?)</li>", seg, re.S)]


# ---------------------------------------------------------------- the data
check(len(RECS) == 25, f"{len(RECS)} relations on {GROUP}, expected the 25 of the judged split")
check(all(r.get("scope") in ("people", "part") for r in RECS),
      "a relation on the group has no scope: " + "; ".join(f"{r['src']}-{r['type']}-{r['dst']} {r['refs']}" for r in RECS
                                                         if r.get("scope") not in ("people", "part")))
check((len(PEOPLE), len(PART), len(HELD)) == (8, 17, 1), f"people/part/held {(len(PEOPLE), len(PART), len(HELD))}, expected (8, 17, 1)")
check(len(HELD) == 1 and HELD[0]["refs"] == [HELD_REF] and HELD[0]["scope"] == "part",
      "the one held record is John 8:44, scoped part")


def data_faults(recs):
    out = []
    for r in recs:
        for code, msg in V.scope_problems(r.get("scope", ""), r.get("scope_party", ""), r.get("scope_ref") or [],
                                          r.get("scope_basis", ""), r["refs"], r.get("held"), corpus):
            out.append(f"{r['src']}-{r['type']}-{r['dst']} {r['refs']}: {code} {msg}")
        if r.get("scope") == "part" and r.get("scope_party", "").lower() in V.BARE_PRONOUNS and not r.get("held"):
            out.append(f"{r['refs']}: party is a pronoun alone")
    return out


bad = data_faults(RECS)
check(not bad, "scope parties: " + "; ".join(bad[:5]))
caught("a scope party that is not in its verse (the Oxford comma dropped)",
       lambda: data_faults([{**SHOWN_PART[0], "scope_party": "Shadrach, Meshach and Abednego", "scope_basis": "neighbor",
                             "scope_ref": ["Dan 3:12"], "refs": ["Dan 3:8"]}]))
caught("a part with no party", lambda: data_faults([{**SHOWN_PART[0], "scope_party": ""}]))
caught("a bare-pronoun party on a shown relation",
       lambda: data_faults([{**SHOWN_PART[0], "scope_party": "you", "scope_basis": "pronoun", "scope_ref": ["John 8:31"],
                             "refs": ["John 8:39"], "held": None}]))


def by(refs, typ=None):
    return [r for r in RECS if r["refs"] == refs and (typ is None or r["type"] == typ)]


for refs, typ in [(["John 8:31"], "spoke_to"), (["John 8:39"], "spoke_to"), (["Acts 9:23"], "conspired_against"),
                  (["Acts 23:12-13"], "conspired_against")]:
    check(len(by(refs, typ)) == 1, f"{refs} should be one {typ} record")
check(not any(r["type"] == "rebuked" and r["refs"] != [HELD_REF] for r in RECS), "a rebuked record on the group other than the held one")
check(len([r for r in RECS if "John 10:31" in r["refs"]]) == 1, "John 10:31 is one stoning, one record")
for refs in (["John 5:18", "John 5:16"], ["John 7:1"], ["John 10:31", "John 10:33"], ["Acts 9:23"], ["Acts 22:30"],
             ["Acts 25:7"], ["Dan 3:8"]):
    rr = by(refs)
    check(len(rr) == 1 and rr[0]["certainty"] == "explicit",
          f"{refs}: a verse that says 'the Jews' outright must stay explicit, not be demoted by its scope")

# ------------------------------------------------- the cards of the other ends
fresh()


def bare_on_ends():
    """a part relation whose group end prints the group's bare name, on the card of the other end"""
    out = []
    for r in SHOWN_PART:
        eid = other_end(r)
        its = match(r, items_of(card(eid), GROUP))
        if not its:
            out.append(f"{eid}: no item for {r['refs']}")
        for it in its:
            want = f"{PART_WHO}: “{r['scope_party']}”"
            if it["name"] == BARE_NAME or not it["name"].startswith(want):
                out.append(f"{eid} {r['refs']}: prints {it['name']!r}, not {want!r}")
    return out


bad = bare_on_ends()
check(not bad, "a part relation printed bare on an end's card: " + "; ".join(bad[:4]))


def people_as_is():
    out = []
    for r in PEOPLE:
        eid = other_end(r)
        for it in match(r, items_of(card(eid), GROUP)):
            if it["name"] != BARE_NAME or it.get("scope"):
                out.append(f"{eid} {r['refs']}: a whole-people relation prints {it['name']!r}")
    return out


check(not people_as_is(), "people relations: " + "; ".join(people_as_is()[:3]))
check(any(match(r, items_of(card(other_end(r)), GROUP)) for r in PEOPLE), "no people relation found on an end's card")
_orig = S._scope_item
S._scope_item = lambda *a: (None, None)
fresh()
caught("a part relation printed bare on the card of its other end (Jesus, Paul, Festus)", bare_on_ends)
S._scope_item = _orig
fresh()

# ------------------------------------------------------- the group's own card
gc = card(GROUP)
gi = items_of(gc)
check(len(gi) == 24, f"{len(gi)} relations shown on the group's card, expected 24 (25 less the held)")


def bare_on_group_card(c):
    out = []
    for r in SHOWN_PART:
        for it in match(r, items_of(c, other_end(r))):
            sc = it.get("scope") or {}
            if sc.get("party") != r["scope_party"] or sc.get("who") != PART_WHO:
                out.append(f"{r['refs']}: no party on the group's own row")
    return out


bad = bare_on_group_card(gc)
check(not bad, "group card rows with no party: " + "; ".join(bad[:3]))
check(gc["scope_card"] and gc["scope_card"]["people"] == 8 and gc["scope_card"]["part"] == 16,
      f"scope_card counts {gc['scope_card'] and (gc['scope_card']['people'], gc['scope_card']['part'])}, expected 8 and 16")
stripped = json.loads(json.dumps(gc))
for g in stripped["groups"]:
    for it in g["items"]:
        it.pop("scope", None)
caught("a part relation printed bare on the group's own card (no party)", lambda: bare_on_group_card(stripped))

head, body, _addr = S.card_page(GROUP)
rows = connections(body)


def row_refs(x):
    """the sets of verses in each parenthesis of a connection's text: "(John 5:18, John 5:16)" """
    return [set(m.split(", ")) for m in re.findall(r"\(([A-Z0-9][^()]*\d)\)", x)]


def page_faults(rows_, recs=SHOWN_PART):
    out = []
    for r in recs:
        want = f"{PART_WHO}: “{r['scope_party']}”"
        hit = [x for x in rows_ if set(r["refs"]) in row_refs(x)]
        if not any(want in x for x in hit):
            out.append(f"page: {r['refs']} not printed with {want!r}")
    return out


check(not page_faults(rows), "the group's page: " + "; ".join(page_faults(rows)[:3]))
caught("a part relation printed bare on the group's page",
       lambda: page_faults([x.replace(PART_WHO + ": ", "") for x in rows]))
check("8 are of the Jewish people as a whole and 16 are of a part of it" in text_of(body),
      "the page does not count the whole people apart from the parts")

# ----------------------------------------------------------------- John 8:44
fresh()
pages = {GROUP: (head, body)}
for eid in sorted({other_end(r) for r in RECS} | {GROUP}):
    if eid not in pages:
        got = S.card_page(eid)
        if got:
            pages[eid] = (got[0], got[1])
shown_text = {eid: text_of(b) for eid, (_h, b) in pages.items()}


def held_faults(cards_, pages_text):
    out = []
    for eid, c in cards_.items():
        for it in items_of(c) if eid == GROUP else items_of(c, GROUP):
            if HELD_REF in (it.get("refs") or []):
                out.append(f"{eid}'s card lists {HELD_REF}")
    for eid, t in pages_text.items():
        if eid == GROUP and (HELD_REF in t or "You belong to your father" in t):
            out.append(f"{eid}'s page prints {HELD_REF}")
    return out


cards_now = {eid: card(eid) for eid in pages}
check(not held_faults(cards_now, shown_text), "John 8:44 on a card: " + "; ".join(held_faults(cards_now, shown_text)))
vtext = d["verses"].get(("John", 8, 44)) or ""
vp = S.passage_page("John.8.44")
check("You belong to your father" in vtext and vp and "You belong to your father" in text_of(vp[1]),
      "the verse of John 8:44 must still print on its own page")
# plant: the held row shown on the Jews' and Jesus's cards
d["rels"][GROUP].append({"dir": "in", "type": "rebuked", "other": "jesus", "refs": [HELD_REF], "certainty": "implied",
                         "scope": {"kind": "part", "party": "you", "ref": ["John 8:37"], "basis": "pronoun"}})
d["rels"]["jesus"].append({"dir": "out", "type": "rebuked", "other": GROUP, "refs": [HELD_REF], "certainty": "implied",
                           "scope": {"kind": "part", "party": "you", "ref": ["John 8:37"], "basis": "pronoun"}})
fresh()
try:
    caught("John 8:44 shown on the group's card", lambda: held_faults({GROUP: card(GROUP), "jesus": card("jesus")}, {}))
finally:
    d["rels"][GROUP].pop()
    d["rels"]["jesus"].pop()
    fresh()
caught("John 8:44 printed on the group's page", lambda: held_faults({}, {GROUP: shown_text[GROUP] + " John 8:44"}))

# ------------------------------------------------------------------ JSON-LD
PARTIES = [r["scope_party"] for r in PART]


def ld_faults(heads):
    out = []
    for eid, h in heads.items():
        for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            t = html.unescape(blk)
            if eid == GROUP and (HELD_REF in t or "You belong to your father" in t):
                out.append(f"{eid}: JSON-LD carries {HELD_REF}")
            for p in PARTIES:
                if p in t:
                    out.append(f"{eid}: JSON-LD carries the party {p!r}")
            if eid == GROUP and re.search(r'"(persecuted|accused|attacked|conspired|besought)', t):
                out.append(f"{eid}: JSON-LD gives the people a predicate of a part's act")
    return out


check(not ld_faults({e: h for e, (h, _b) in pages.items()}), "JSON-LD: " + "; ".join(ld_faults({e: h for e, (h, _b) in pages.items()})[:3]))
caught("a part relation emitted as a JSON-LD predicate of the people",
       lambda: ld_faults({GROUP: head + '<script type="application/ld+json">{"@id":"/e/jews","persecuted":{"@id":"/e/jesus"}}</script>'}))
caught("John 8:44 in the group's JSON-LD",
       lambda: ld_faults({GROUP: head + '<script type="application/ld+json">{"citation":"John 8:44"}</script>'}))

# -------------------------------------------------------- Romans 11:28 and senses
vs = (d["ents"][GROUP].get("attrs") or {}).get("verse_scopes") or []
rom = [v for v in vs if v["ref"] == "Rom 11:28"]


def roman_faults(recs, verse_scopes, page_text):
    out = []
    if len([v for v in verse_scopes if v["ref"] == "Rom 11:28"]) != 1:
        out.append("Rom 11:28 is not exactly one unit")
    if any("Rom 11:28" in r["refs"] for r in recs):
        out.append("Rom 11:28 is split into relations")
    if "they [" not in page_text or "but regarding election, they are loved" not in page_text:
        out.append("Rom 11:28 is not printed whole with 'they' resolved")
    return out


check(not roman_faults(RECS, vs, shown_text[GROUP]), "Romans 11:28: " + "; ".join(roman_faults(RECS, vs, shown_text[GROUP])))
check(rom and rom[0]["scope"] == "people" and rom[0]["scope_basis"] == "pronoun"
      and set(rom[0]["scope_ref"]) >= {"Rom 11:1", "Rom 11:2", "Rom 11:26"}, "Rom 11:28 is people, read through 11:1-2 and 11:26")
check(all(c in shown_text[GROUP] for c in ("Rom 9:6", "Rom 11:17-24", "Rom 11:29")), "Rom 11:28's companions are not beside it")
check("neither does this card" in rom[0].get("note", "") if rom else False, "the note must say the verse speaks of no later body")
caught("Rom 11:28 split into an enemies row and a loved row",
       lambda: roman_faults(RECS + [{"refs": ["Rom 11:28"]}], vs, shown_text[GROUP]))


def sense_faults(recs, page_text):
    out = []
    for ref in ("Rev 2:9", "Rev 3:9", "Rom 2:28-29", "Rom 2:17"):
        if any(ref in r["refs"] for r in recs):
            out.append(f"{ref} is filed in a relation")
    for ref in ("Rev 2:9", "Rev 3:9"):
        if re.search(rf"\b{re.escape(ref)}\)", page_text):
            out.append(f"{ref} is printed as a connection")
    return out


check(not sense_faults(RECS, " ".join(connections(body))), "sense verses: " + "; ".join(sense_faults(RECS, " ".join(connections(body)))))
check({v["ref"] for v in vs if v["scope"] == "sense"} == {"Rom 2:28-29", "Rev 2:9", "Rev 3:9"}, "the sense verses are Rom 2:28-29, Rev 2:9, Rev 3:9")
check(not any(v["ref"] == "Rom 2:17" for v in vs), "Rom 2:17 takes no scope")
check("Paul on who is a Jew" in shown_text[GROUP] and "false claim to the name" in shown_text[GROUP],
      "the sense verses are not printed under their neutral labels")
caught("a sense verse (Rev 2:9) filed as a relation of the people", lambda: sense_faults(RECS + [{"refs": ["Rev 2:9"]}], ""))

# --------------------------------------------------------------- the validator
people = load_persons()
vocab = load_vocabulary()
sub = {k: people[k] for k in (GROUP, "jesus")}


def validator_refuses(code, rel, flagged=True):
    """the validator's issue codes for one relation on the group; the fault is it NOT refusing"""
    attrs = dict(sub[GROUP].attrs)
    sub[GROUP].attrs = {**attrs, "scope_required": flagged}
    try:
        # the relation's own issues: the group's quoted verses are checked by the same rule and would answer too
        codes = {i.code for i in V.validate(people=sub, relations=[rel], vocab=vocab, corpus=corpus)
                 if i.subject.startswith("jesus -")}
    finally:
        sub[GROUP].attrs = attrs
    return [] if code in codes else [f"the validator accepted it ({code} not raised)"]


base = dict(src="jesus", type="spoke_to", dst=GROUP, refs=["John 8:31"], certainty="explicit")
for code, rel in [("rel.unscoped", Relation(**base)),
                  ("rel.part_without_party", Relation(**base, scope="part", scope_basis="verse")),
                  ("rel.party_not_in_verse", Relation(**base, scope="part", scope_party="Shadrach, Meshach, and Abednego",
                                                      scope_basis="verse")),
                  ("rel.party_is_pronoun", Relation(**{**base, "refs": ["John 8:39"]}, scope="part", scope_party="you",
                                                    scope_basis="pronoun", scope_ref=["John 8:31"])),
                  ("rel.bad_scope", Relation(**base, scope="all"))]:
    check(not validator_refuses(code, rel), f"the validator must raise {code}")
check(not [i for i in V.validate(people=sub, relations=[Relation(**base, scope="part", scope_party="the Jews who had believed Him",
                                                               scope_basis="verse")], vocab=vocab, corpus=corpus)
           if i.level == "error"], "a well-formed part relation must validate")
# planted: the validator's rule switched off
caught("an unscoped relation on a scope_required group accepted", lambda: validator_refuses("rel.unscoped", Relation(**base), flagged=False))
_t = V._text_of
V._text_of = lambda c, refs: "shadrach, meshach and abednego"
caught("a scope party not in its verse accepted",
       lambda: validator_refuses("rel.party_not_in_verse", Relation(**base, scope="part", scope_party="Shadrach, Meshach and Abednego",
                                                                    scope_basis="verse")))
V._text_of = _t
_bp = set(V.BARE_PRONOUNS)
V.BARE_PRONOUNS.clear()
caught("a bare-pronoun party accepted",
       lambda: validator_refuses("rel.party_is_pronoun", Relation(**{**base, "refs": ["John 8:39"]}, scope="part", scope_party="you",
                                                                 scope_basis="pronoun", scope_ref=["John 8:31"])))
V.BARE_PRONOUNS.update(_bp)
_sp = V.scope_problems
V.scope_problems = lambda *a: [x for x in _sp(*a) if x[0] != "rel.part_without_party"]
caught("a part with no party accepted",
       lambda: validator_refuses("rel.part_without_party", Relation(**base, scope="part", scope_basis="verse")))
V.scope_problems = _sp

print(f"group scope: {len(RECS)} relations on {GROUP}: {len(PEOPLE)} people, {len(PART)} part (1 held); "
      f"planted faults caught: {sum(1 for _n, ok in planted if ok)} of {len(planted)}; {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
