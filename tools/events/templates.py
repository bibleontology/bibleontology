"""Event templates (plan A.9, P-59): Copilot's templates, confirmed against
the text, and the generic templates tested over every event.

2026-09-30: confirm them and check whether they are applied to events as is,
as their own stand-alone thing; the generic templates are nodes and effectively
become part of the event classification system; then analyse these event
groupings, given the primitive nodes, and propose enhancements or optionality
to these event patterns.

Source: ontology/events/event-templates.md (Microsoft Copilot, verbatim).

1. CONFIRM each application. For every stage: its verse range is real (the
   Berean text), inside or next to the event, in the order the template
   states, not overlapping the next stage -- and the TEXT SUPPORTS IT, from
   two primitive layers:
     - the clause tags (DeepSeek Flash, medium or high) on those verses: a
       "deliverance" stage should carry deliverance;
     - the original words in the range, by their lexicon gloss: a
       "judgment" stage should have words for judging, striking, destroying.
   A stage with neither is unsupported; the reading is made by hand.
2. GENERALISE. Each template's stages are a sequence of stage KINDS; the
   distinct sequences are the generic templates (the candidate nodes).
3. TEST OVER EVERY EVENT. For each of the 307 event cards and each generic
   template: are all its stages evidenced in the event's tellings, in order?
   Which events fit a template Copilot did not give them; which stage is the
   one usually missing (optional); which extra stage usually stands between
   two (a candidate enhancement -- intercession between judgment and mercy?).

    python tools/events/templates.py  -> out/event-templates.json
                                         docs/review/EVENT-TEMPLATES.md
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SRC = ROOT / "ontology" / "events" / "event-templates.md"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
from theme_map import CANON, check, label, spans_in  # noqa: E402
from event_nodes import FROM_MACULA, TO_MACULA, verses, vkey  # noqa: E402

# STAGE KINDS: what the text should show for each. Stamps are the clause
# tags' own names; words are gloss words of the original (lexicon), matched
# on a word of the gloss. Extra kinds not in Copilot's vocabulary
# (intercession, repentance, cry) are tested as candidate insertions.
KINDS = {
    "bondage": ({"slave_bondservant", "captivity", "siege", "persecution", "enemy_adversary"},
                {"oppress", "afflict", "bind", "bound", "captive", "slave", "pursue", "besiege",
                 "prison", "chain"}),
    "deliverance": ({"deliverance", "sea_crossing", "victory_procession", "weak_defeats_strong"},
                    {"save", "deliver", "rescue", "redeem", "escape", "salvation"}),
    "judgment": ({"judgment", "judgment_ev", "curse", "woe_pronouncement", "plagues",
                  "judgment_mechanism", "day_of_the_lord"},
                 {"judge", "judgment", "punish", "curse", "plague", "destroy", "strike", "wrath"}),
    "mercy": ({"mercy_restoration", "priestly_intercession", "healing"},
              {"mercy", "compassion", "pity", "relent", "forgive", "gracious", "heal"}),
    "restoration": ({"mercy_restoration", "return_from_exile", "rebuilding", "healing",
                     "blessing_ev"},
                    {"restore", "heal", "rebuild", "renew", "bless"}),
    "fall": ({"transgression", "idolatry", "covenant_crisis", "insider_fails"},
             {"sin", "transgress", "rebel", "corrupt", "murder", "iniquity", "idol"}),
    "exile": ({"exile_ev", "wilderness_wandering", "stranger_sojourner", "captivity"},
              {"exile", "drive", "banish", "wander", "fugitive", "scatter", "sojourn"}),
    "covenant": ({"covenant", "oath_swearing", "covenant_meal", "promise_faithfulness",
                  "blessing_commission", "covenant_at_sinai"},
                 {"covenant", "oath", "swear", "promise", "memorial"}),
    "testing": ({"temptation", "trial_contest", "covenant_crisis"},
                {"test", "tempt", "prove", "try", "trial"}),
    "death": ({"burial", "death_produces_life"}, {"die", "death", "dead", "slay", "kill"}),
    "resurrection": ({"resurrection", "resurrection_ev", "death_produces_life"},
                     {"alive", "revive", "rise", "raise", "life"}),
    "anointing": ({"anointing", "prophetic_call", "theophany"},
                  {"anoint", "call", "appear", "consecrate"}),
    "empowerment": ({"spirit", "miracles", "commissioning", "blessing_ev"},
                    {"strength", "power", "sign", "wonder", "spirit"}),
    "mission": ({"commissioning", "sending", "prophetic_call"}, {"send", "commission", "sent"}),
    "creation": ({"creation", "creation_ev", "new_creation"}, {"create", "form", "fashion"}),
    "order": ({"creation", "law_giving", "builder", "rebuilding", "tabernacle_furnishings"},
              {"build", "order", "arrange", "establish", "number", "make"}),
    "chaos": ({"cosmic_collapse", "sea_crossing", "siege", "battle"},
              {"flood", "overflow", "tumult", "ruin", "waste", "desolate"}),
    "word": ({"prophetic_word", "law_giving", "promise_oracle"},
             {"command", "word", "speak", "decree", "instruct"}),
    "presence": ({"temple_presence", "theophany"}, {"glory", "dwell", "cloud", "presence"}),
    "descent": ({"humiliation_to_vindication", "exile_ev", "captivity"},
                {"descend", "flee", "prison", "afflict", "leper", "humble"}),
    "ascent": ({"exile_to_exaltation", "theophany"}, {"exalt", "lift", "answer", "whirlwind"}),
    "exaltation": ({"exile_to_exaltation", "humiliation_to_vindication", "coronation"},
                   {"exalt", "promote", "honor", "prosper", "great"}),
    "return": ({"return_from_exile", "pilgrim"}, {"return"}),
    "promise": ({"promise_oracle", "promise_faithfulness", "oath_to_the_fathers"},
                {"promise", "swear", "oath"}),
    "fulfillment": ({"promise_faithfulness", "barren_woman_conceives"},
                    {"fulfil", "fulfill", "bear", "born", "conceive"}),
    "provision": ({"famine_to_provision", "miracles"}, {"provide", "feed", "supply", "food"}),
    "victory": ({"battle", "victory_procession", "weak_defeats_strong"},
                {"defeat", "victory", "conquer", "rout", "flee"}),
    "wisdom": ({"law_wisdom", "council_discernment"}, {"wise", "wisdom", "discern", "understand"}),
    "commissioning": ({"commissioning", "sending", "prophetic_call"},
                      {"send", "commission", "go", "appoint"}),
    "blessing": ({"blessing_ev", "blessing_commission"}, {"bless", "blessing"}),
    "reversal": ({"humiliation_to_vindication", "last_shall_be_first", "exile_to_exaltation"},
                 {"turn", "overturn", "reverse"}),
    "warning": ({"prophetic_word", "woe_pronouncement"}, {"warn", "beware", "watch"}),
    "purification": ({"sacrificial_system", "revival_repentance"},
                     {"clean", "purify", "fear", "holy"}),
    "failure": ({"insider_fails", "transgression", "covenant_crisis"},
                {"rebel", "grumble", "murmur", "refuse", "fail", "sin"}),
    "humility": ({"revival_repentance", "humiliation_to_vindication"},
                 {"humble", "obey", "wash"}),
    "faithfulness": ({"promise_faithfulness", "revival_repentance"},
                     {"faithful", "trust", "obey", "fast"}),
    "reassurance": ({"theophany", "promise_oracle"}, {"sign", "dew", "fleece", "assure"}),
    "preparation": ({"stranger_sojourner", "servant"}, {"shepherd", "flock", "keep", "tend"}),
    "vocation": ({"marriage_covenant", "blessing_commission"}, {"wife", "cleave", "helper", "flesh"}),
    "striving": ({"builder", "idolatry"}, {"build", "city", "name"}),
    "divine overruling": ({"theophany", "trial_contest"}, {"angel", "oppose", "open", "donkey"}),
    # CANDIDATE INSERTIONS, not in Copilot's vocabulary
    "intercession": ({"priestly_intercession"}, {"pray", "intercede", "plead", "entreat"}),
    "repentance": ({"revival_repentance", "fasting"}, {"repent", "turn", "confess", "fast",
                                                        "sackcloth"}),
    "cry": ({"cry"}, {"cry", "groan", "call"}),
}
SYNONYM = {"divine order": "order", "human striving": "striving",
           "judgment/mercy": "judgment", "covenant renewal": "covenant",
           "resurrection (symbolic)": "resurrection", "restoration (for saints)": "restoration",
           "fulfilment": "fulfillment", "exile/impurity": "exile", "return & purge": "return",
           "death motif": "death", "resurrection motif": "resurrection", "exile context": "exile"}
EXTRA = ["intercession", "repentance", "cry"]


def vv(s):
    """a span tuple (book, (c, v), (c, v)) from spans_in -> its verses"""
    return verses({"book": s[0], "start": list(s[1]), "end": list(s[2])}) if s[1] else []


def kind_of(name):
    n = name.lower().strip()
    n = re.sub(r"\s*\(.*?\)", "", n).strip()
    n = SYNONYM.get(n, n)
    return n if n in KINDS else None


def parse(text, problems):
    """-> [{title, event_ref(spans), template[kinds], stages[{name, kind, spans, note}]}]"""
    out, cur = [], None
    # the file abbreviates two books the reference reader does not know
    text = re.sub(r"\bEst (\d)", r"Esther \1", text)
    text = re.sub(r"\bJon (\d)", r"Jonah \1", text)
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("<!--") or s.startswith("-->"):
            continue
        m = re.match(r"^(.+?)\s*\(([^()]*\d[^()]*)\)\s*$", s)
        if m and not s.startswith("*") and not s.startswith("Template"):
            cur = {"title": m.group(1).strip(), "where": m.group(2),
                   "spans": [x for x in spans_in(m.group(2), problems) if check(x, problems, s)],
                   "template": [], "stages": []}
            out.append(cur)
            continue
        if s.startswith("Template:") and cur:
            cur["template"] = [t.strip() for t in s[9:].split("→")]
            continue
        if s.startswith("*") and cur:
            mm = re.match(r"^\*\s*([^:]+):\s*(.*)$", s)
            if not mm:
                continue
            name, refs = mm.group(1).strip(), mm.group(2)
            note = re.findall(r"\((.*?)\)", name + " " + refs)
            implied = "implied" in refs or "background" in refs
            sp = [x for x in spans_in(re.sub(r"\(.*?\)", "", refs), problems)
                  if check(x, problems, f"{cur['title']} / {name}")]
            cur["stages"].append({"name": re.sub(r"\s*\(.*?\)", "", name).strip(),
                                  "kind": kind_of(name), "spans": sp, "note": note,
                                  "implied": implied})
    return out


def main():
    problems = []
    tpls = parse(SRC.read_text(encoding="utf-8"), problems)
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}

    def mac(v):
        b, c, n = v.split(".")
        r = f"{TO_MACULA[b]}.{c}.{n}"
        return to_mac.get(r, r)

    # the primitive layers, per verse (MACULA numbering)
    stamps = collections.defaultdict(collections.Counter)
    for ln in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r.get("kind") == "stamp" and r.get("strength") in ("high", "medium"):
            stamps[r["clause"].split("#")[0]][r["tag"]] += 1
    lex = json.loads((ROOT / "data" / "raw" / "stepbible" / "lexicon.json")
                     .read_text(encoding="utf-8"))
    gloss = {}
    for code, v in lex.items():
        if isinstance(v, list) and len(v) >= 4:
            gloss[code[0].lower() + re.sub(r"^0+", "", code[1:])] = set(
                re.findall(r"[a-z]+", str(v[3]).lower()))
    words = collections.defaultdict(list)
    for ln in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r.get("word") and r.get("strong"):
            s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", r["strong"]))
            if s:
                words[r["ref"]].append((r.get("lang") or "")[:1] + s)

    def evidence(kind, vs):
        """-> (stamps found, gloss words found) for a stage kind over verses"""
        st, gw = KINDS[kind]
        fs, fw = collections.Counter(), collections.Counter()
        for v in vs:
            m = mac(v)
            for t, n in stamps.get(m, {}).items():
                if t in st:
                    fs[t] += n
            for k in words.get(m, []):
                hit = gloss.get(k, set()) & gw
                for h in hit:
                    fw[h] += 1
        return fs, fw

    ev = json.loads((OUT / "event-nodes.json").read_text(encoding="utf-8"))["events"]

    def ev_verses(e):
        out = []
        for t in e["tellings"]:
            b, c1, v1 = t["first"].split(".")
            _b, c2, v2 = t["last"].split(".")
            out += verses({"book": b, "start": [int(c1), int(v1)], "end": [int(c2), int(v2)]})
        return out

    # ---- 1. confirm each application
    confirm = []
    for t in tpls:
        tv = {v for s in t["spans"] for v in vv(s)}
        # the event card it belongs to: the most overlap
        best, bn = None, 0
        for eid, e in ev.items():
            n = len(tv & set(ev_verses(e)))
            if n > bn:
                best, bn = eid, n
        rows, prev_end, issues = [], None, []
        for i, st in enumerate(t["stages"]):
            vs = sorted({v for s in st["spans"] for v in vv(s)}, key=vkey)
            if not st["kind"]:
                issues.append(f"stage '{st['name']}' has no kind to test")
            if not vs:
                rows.append(dict(st, verses=0, stamps={}, words={}, supported=None,
                                 labels=[label(s) for s in st["spans"]]))
                continue
            if prev_end and vkey(vs[0]) < vkey(prev_end):
                issues.append(f"'{st['name']}' starts before the previous stage ends")
            prev_end = vs[-1]
            if tv and not (set(vs) & tv):
                issues.append(f"'{st['name']}' lies outside the event's own passage "
                              f"({', '.join(label(s) for s in st['spans'])})")
            fs, fw = evidence(st["kind"], vs) if st["kind"] else ({}, {})
            rows.append(dict(st, verses=len(vs), stamps=dict(fs.most_common(4)),
                             words=dict(fw.most_common(4)),
                             supported=bool(fs or fw) if st["kind"] else None,
                             labels=[label(s) for s in st["spans"]]))
        # does the stage list match the template line?
        tk = [kind_of(x) for x in t["template"]]
        sk = [s["kind"] for s in t["stages"]]
        if [x for x in tk if x] != [x for x in sk if x]:
            issues.append("the stages listed do not match the template line "
                          f"({' → '.join(t['template'])} vs {' → '.join(s['name'] for s in t['stages'])})")
        n_sup = sum(1 for r in rows if r["supported"])
        n_test = sum(1 for r in rows if r["supported"] is not None)
        confirm.append({"title": t["title"], "where": t["where"],
                        "template": t["template"], "kinds": tk, "event": best,
                        "event_title": ev[best]["title"] if best else None,
                        "stages": rows, "issues": issues,
                        "support": f"{n_sup}/{n_test}"})

    # ---- 2. the generic templates
    generic = collections.defaultdict(list)
    for c in confirm:
        key = tuple(k for k in c["kinds"] if k)
        if key:
            generic[key].append(c["title"])

    # ---- 3. every event against every generic template
    # WRONG TURN, KEPT: the first version of this test took each stage's FIRST
    # verse with a matching stamp OR a matching word gloss. Over whole events
    # nearly everything fit ("promise -> fulfillment" in 132 of 307 events,
    # "judgment -> warning" in 96): some word in a long passage is glossed
    # "strike", "bear" or "call", and a stray early one sets the order. Over
    # whole events only the clause STAMPS count (the reading said what the
    # clause is about), a stage needs two stamped verses (one in a short
    # event), and its place is its MIDDLE verse, not its first.
    def first_positions(vs):
        """kind -> the middle index (text order) of the verses stamped with it"""
        hits = collections.defaultdict(list)
        for i, v in enumerate(vs):
            sv = stamps.get(mac(v), {})
            for kind, (st, _gw) in KINDS.items():
                if any(t in st for t in sv):
                    hits[kind].append(i)
        need = 1 if len(vs) < 12 else 2
        return {k: ix[len(ix) // 2] for k, ix in hits.items() if len(ix) >= need}

    fits = collections.defaultdict(list)
    near = collections.defaultdict(lambda: collections.Counter())
    extra = collections.defaultdict(lambda: collections.Counter())
    per_event = {}
    for eid, e in ev.items():
        vs = sorted(set(ev_verses(e)), key=vkey)
        if not vs or len(vs) > 400:
            continue
        pos = first_positions(vs)
        per_event[eid] = pos
        for key in generic:
            have = [k in pos for k in key]
            ordered = all(pos[a] <= pos[b] for a, b in zip(key, key[1:])
                          if a in pos and b in pos)
            if all(have) and ordered:
                fits[key].append(eid)
                # what stands between two stages, of the candidate insertions
                for a, b in zip(key, key[1:]):
                    for x in EXTRA:
                        if x in pos and pos[a] <= pos[x] <= pos[b]:
                            extra[key][(a, x, b)] += 1
            elif sum(have) == len(key) - 1 and ordered and len(key) > 2:
                missing = key[have.index(False)]
                near[key][missing] += 1

    result = {"confirm": confirm, "problems": problems,
              "generic": [{"template": list(k), "given_for": v,
                           "fits": [{"id": x, "title": ev[x]["title"]} for x in fits[k]],
                           "optional": dict(near[k]),
                           "between": {" → ".join(t): n for t, n in extra[k].most_common(6)}}
                          for k, v in sorted(generic.items(), key=lambda kv: -len(fits[kv[0]]))]}
    (OUT / "event-templates.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    report(result, ev)
    print(f"templates {len(confirm)}; generic {len(generic)}; problems {len(problems)}")
    for c in confirm:
        print(f"  {c['support']:>5}  {c['title'][:44]:44}  "
              f"{' → '.join(c['template'])[:46]:46}  {len(c['issues'])} issues")


def report(res, ev):
    L = ["# Event templates — confirmed against the text", "",
         "Microsoft Copilot's templates (ontology/events/event-templates.md), each stage "
         "tested against the text by `tools/events/templates.py`: its verses are real, in "
         "order, inside the event; and the clause tags or the original words in its range "
         "show what the stage claims. Then each generic template is run over every event "
         "card.", ""]
    L += ["## Each application", ""]
    for c in res["confirm"]:
        L.append(f"### {c['title']} ({c['where']}) — {' → '.join(c['template'])}")
        L.append(f"- event card: {c['event_title'] or '— none —'} · stages supported by "
                 f"the text: {c['support']}")
        for s in c["stages"]:
            ev_ = ", ".join(list(s["stamps"]) + [f"‘{w}’" for w in s["words"]]) or "nothing"
            mark = "✓" if s["supported"] else ("·" if s["supported"] is None else "✗")
            L.append(f"  - {mark} **{s['name']}** ({'; '.join(s['labels']) or 'no verses'}"
                     f"{', implied' if s['implied'] else ''}) — {ev_}")
        for i in c["issues"]:
            L.append(f"  - ⚠ {i}")
        L.append("")
    L += ["## The generic templates, over every event", ""]
    for g in res["generic"]:
        L.append(f"### {' → '.join(g['template'])}")
        L.append(f"- given by Copilot for: {', '.join(g['given_for'])}")
        L.append(f"- events that show every stage, in order ({len(g['fits'])}): "
                 + ", ".join(f['title'] for f in g["fits"][:25])
                 + (f" … +{len(g['fits']) - 25}" if len(g["fits"]) > 25 else ""))
        if g["optional"]:
            L.append("- one stage short, all else in order — the stage missing: "
                     + ", ".join(f"{k} ({n})" for k, n in sorted(g["optional"].items(),
                                                                 key=lambda kv: -kv[1])))
        if g["between"]:
            L.append("- standing between two stages: "
                     + "; ".join(f"{k} ({n})" for k, n in g["between"].items()))
        L.append("")
    (ROOT / "docs" / "review" / "EVENT-TEMPLATES.md").write_text("\n".join(L) + "\n",
                                                                 encoding="utf-8")


if __name__ == "__main__":
    main()
