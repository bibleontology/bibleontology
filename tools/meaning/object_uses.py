"""THE OBJECT AUDIT: what the text says was done with each significant object (2026-11-01).

Doug, 2026-11-01, on the staff card burying Moses and Aaron's events ("including the confrontation with Pharaoh and
striking of the rock"): "assign it to DeepSeek", then "maybe an entire significant object card audit". An object card
can only lead with what the graph ties to it, and the staff's card held no relation for any use of it. This asks, of
every object the text names in at least MIN verses (the MAX most-named): in which verses is it used, by whom, on what,
in which scene, commanded or done. DeepSeek V4.1 Flash, blind, thinking off; it sees verse text and the object's name
only. One call per object, each answer saved; nothing reaches the graph. Claude checks the answers against the
cards' relations afterwards and drafts the relations that hold.

    python tools/meaning/object_uses.py             (needs the local server on 8032 for the verses)
    -> docs/review/object-audit-2026-11-01/<id>.md
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
OUT = ROOT / "docs" / "review" / "object-audit-2026-11-01"
API = "http://localhost:8032"
MIN, MAX, VERSES = 1, 200, 160     # MAX was 60, and the 98 significant objects stopped at 60 (2026-11-02)
SIGNIFICANT = set("""rod_of_moses aarons_rod object_staff ark_of_the_covenant the_mercy_seat covering_of_the_ark brasen_serpent
tables_of_stone tabernacle vail the_candlestick the_shewbread the_altar_of_incense the_altar_of_burnt_offering the_laver
the_ephod the_urim_and_the_thummim the_ephod_of_gideon the_golden_pot_of_manna manna noahs_ark pillar_of_cloud
pillar_of_salt jacobs_stone jacobs_pillar pillar_at_bethel altar_at_bethel josephs_bones fleece the_sword_of_goliath
a_coat_of_many_colors a_crown_of_thorns mark_upon_cain corner_stone the_signet pharaohs_cup mantle
stones stone bones bow bread crown fire oil sword water""".split())
# the common words among them (stones, water, bread...) are named in hundreds of verses: their own phrase search
# finds the scenes the word layer's first 160 verses miss (Doug, 2026-11-01, on the stones card burying the lead)
PHRASE_COMMON = {"stones": r"\bstones\b", "stone": r"\bstone\b", "bones": r"\bbones\b", "bow": r"\bbow\b(?! down| low)",
                 "bread": r"\bbread\b", "crown": r"\bcrown\b", "fire": r"\bfire\b", "oil": r"\boil\b",
                 "sword": r"\bsword\b", "water": r"\bwater\b"}

TASK = """You read Bible verses (the Berean Standard Bible) and list what the text says was done WITH {name}.

The verses below are those where the graph finds a word for it; some will be about something else of the same word.
For each verse that says {name} was used, made, carried, placed, struck with, lifted, broken, moved, or acted on, give
one line of JSON:
{{"ref": "...", "which": "which one, as the verse says (whose, or which), or 'not said'", "who": "who did it, as the
verse names them", "act": "the verb, in the verse's words", "on": "what it was used on, over or with, if said",
"scene": "the scene in a few plain words", "commanded": true or false, "words": "the deciding words, copied exactly"}}

Rules: only what the verse says. "commanded": true where the verse is a command or instruction (the LORD tells someone
to do it), false where it reports it done. Skip verses where the word means something else, or the object is only
mentioned. Never guess whose it is. After the lines, list in plain words any verse you were unsure of, and why.

VERSES:
{verses}"""


# THE SIGNS (Doug, 2026-11-01: "if you can figure out if it has symbolic meaning - that is the key"). Only where the
# text itself says what the object stands for, or later Scripture takes it up as a figure: never a tradition's reading
# (structure yes, doctrine no). The graph's relation for it is `signifies`.
SIGN_TASK = """You read Bible verses (the Berean Standard Bible) about {name}. Question: does the TEXT say what it means
or stands for?

List only verses where the text itself:
- calls it a sign, a memorial, a reminder, a witness, a copy, a shadow, a pattern or a figure ("kept as a sign");
- says what it is for in God's purpose ("there I will meet with you");
- or, in a later book, takes it up as a picture of something else ("as Moses lifted up the snake in the
  wilderness, so the Son of Man must be lifted up");
- or tells of it doing or becoming what no ordinary object could: a staff that becomes a snake or buds, an ark
  that strikes down those who touch it, a bronze snake that heals, a cloak that parts a river (Doug, 2026-11-01:
  "things that would not normally happen in the material world"). Kind "wonder"; "means" is what happened, in the
  verse's words, never an explanation of it.

One line of JSON for each:
{{"ref": "...", "kind": "sign" | "memorial" | "purpose" | "figure in later Scripture" | "copy or shadow" | "wonder",
"means": "what the verse says it stands for, in the verse's words", "words": "the deciding words, copied exactly",
"by": "who says it (the narrator, the LORD, Jesus, Paul, the writer of Hebrews...)"}}

Rules: only what a verse says. A meaning that commentators or traditions give, and the verse does not state, is never
listed. If no verse states a meaning, answer exactly: none stated. After the lines, list any verse you were unsure of.

VERSES:
{verses}"""


# WHERE THE WORD LAYER HAS NO VERSES (the ark of the covenant, the bronze snake, the tablets: /api/entity-verses gives 0,
# their records carry no word card), the Berean is searched for the object's own phrase
PHRASE = {"ark_of_the_covenant": r"\bark\b", "the_mercy_seat": r"mercy seat|atonement cover", "covering_of_the_ark":
          r"atonement cover|mercy seat", "brasen_serpent": r"bronze snake|bronze serpent|Nehushtan|lifted up the snake",
          "tables_of_stone": r"\btablets\b", "tabernacle": r"\btabernacle\b", "vail": r"\bveil\b",
          "the_candlestick": r"\blampstand", "the_shewbread": r"Bread of the Presence|showbread|consecrated bread",
          "the_altar_of_incense": r"altar of incense|golden altar", "the_altar_of_burnt_offering": r"altar of burnt offering",
          "the_laver": r"\bbasin\b", "the_ephod": r"\bephod\b", "the_urim_and_the_thummim": r"\bUrim\b|\bThummim\b",
          "the_ephod_of_gideon": r"\bephod\b", "the_golden_pot_of_manna": r"jar of manna|pot of manna|\bmanna\b",
          "manna": r"\bmanna\b", "pillar_of_cloud": r"pillar of cloud|pillar of fire", "pillar_of_salt": r"pillar of salt",
          "josephs_bones": r"bones of Joseph|Joseph's bones|Joseph’s bones|carry my bones", "fleece": r"\bfleece\b",
          "the_sword_of_goliath": r"sword of Goliath|Goliath's sword|Goliath’s sword", "a_coat_of_many_colors":
          r"robe of many colors|ornate robe|Joseph's robe|Joseph’s robe", "a_crown_of_thorns": r"crown of thorns",
          "mark_upon_cain": r"\bmark on Cain\b|placed a mark", "corner_stone": r"cornerstone|corner stone",
          "jacobs_stone": r"\bstone\b", "jacobs_pillar": r"\bpillar\b", "pillar_at_bethel": r"\bpillar\b"}


# THE MAC'S TRIAGE DID NOT DISCRIMINATE (2026-11-02: 270 of 303 "significant", knees and corn among them), so DeepSeek
# ranked the 303 by name in one call (docs/review/object-audit-2026-11-01/ranked-by-deepseek.jsonl, 56 kept)
_R = ROOT / "out" / "grunt" / "object-ranked.json"
RANKED = set(json.loads(_R.read_text())) if _R.exists() else set()
SIGNIFICANT |= RANKED


def berean(rx):
    import re
    out = []
    for l in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if "t" in r and re.search(rx, r["t"], re.I):
            out.append(f"{r['b']} {r['c']}:{r['v']} {r['t']}")
    return out


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read())


def main():
    import deepseek_judge as dj
    from bibleont import delegate
    OUT.mkdir(parents=True, exist_ok=True)
    ents = [json.loads(l) for p in sorted((ROOT / "ontology" / "entities").glob("*.jsonl"))     # every entity file,
            for l in open(p, encoding="utf-8") if l.strip()]                                     # not entities.jsonl only
    # SIGNIFICANT, chosen by name: the first run took the 40 most-named and got body, eye, hand and water, not the
    # staff, the ark or the bronze snake (2026-11-01). Word frequency is not significance.
    objs = []
    for e in ents:
        if e.get("type") != "object" or e["id"] not in SIGNIFICANT:
            continue
        try:
            v = get(f"/api/entity-verses?id={e['id']}")
        except Exception:
            continue
        if (not v.get("total") and e["id"] in PHRASE) or e["id"] in PHRASE_COMMON or (not v.get("total") and e["id"] in RANKED):
            found = berean(PHRASE.get(e["id"]) or PHRASE_COMMON.get(e["id"])
                           or r"\b" + __import__("re").escape(e["name"].split()[-1]) + r"\b")
            v = {"total": len(found), "books": [{"items": [{"eref": x.split(" ", 2)[0] + " " + x.split(" ", 2)[1],
                                                             "text": x.split(" ", 2)[2]} for x in found]}]}
        if (v.get("total") or 0) >= MIN:
            objs.append((v["total"], e, v))
    objs.sort(key=lambda x: -x[0])
    spent = 0.0
    signs = "signs" in sys.argv[1:]
    for total, e, v in objs[:MAX]:
        f = OUT / f"{e['id']}{'-signs' if signs else ''}.md"
        if f.exists():
            continue
        lines = [f"{i['eref']} {i['text']}" for b in v.get("books", []) for i in b.get("items", [])][
            :900 if e["id"] in PHRASE_COMMON else VERSES]     # a common word read whole, to Revelation, not Genesis only
        task = (SIGN_TASK if signs else TASK).format(name=f"\"{e['name']}\"", verses="\n".join(lines))
        r = dj.call(delegate, task, 3, f"object {'signs' if signs else 'uses'} {e['id']}")
        if r.get("refused") or r.get("stopped") or not r.get("answer"):
            print(e["id"], "STOPPED:", r.get("refused") or r.get("stopped") or "empty")
            return
        spent += r["cost"]
        f.write_text(f"# {'What the text says ' + e['name'] + ' stands for' if signs else 'What the text says was done with ' + e['name']} (`{e['id']}`)\n\n"
                     f"{len(lines)} of {total} verses read; DeepSeek V4.1 Flash, blind, ${r['cost']:.4f}. Candidates, "
                     f"not yet checked by Claude; nothing in the graph changed.\n\n" + r["answer"].strip() + "\n",
                     encoding="utf-8")
        print(f"{e['id']}: {len(lines)} verses, ${r['cost']:.4f}")
    print(f"done: {min(MAX, len(objs))} objects of {len(objs)} with {MIN}+ verses; ${spent:.4f}")




# THE MAC'S TRIAGE (Doug, 2026-11-01: "do we need an Ollama audit on all the object cards that did not make the
# first cut. Stones should be obvious."). The hand-picked list missed stones; every other object card is read on the
# Mac (gemma4:26b, free) with one narrow question, and only what it flags goes to DeepSeek's full passes. A common
# word is sampled evenly across the canon, so the scenes past Genesis are seen.
#
#     python tools/meaning/object_uses.py mac-triage   -> out/grunt/jobs/10-object-triage.jsonl (+ .key)
#     python tools/grunt/grunt.py push out/grunt/jobs/10-object-triage.jsonl
TRIAGE = """You read Bible verses (the Berean Standard Bible) that name an object. Question: is this object
SIGNIFICANT in the text: does a verse tell of someone doing something with it in a scene that matters (Moses strikes
the rock with his staff; Joshua sets up twelve stones from the Jordan), or say it stands for something (a sign, a
memorial, a picture of something else), or tell of it doing what no ordinary object could?

Answer with ONE line of JSON:
{"significant": true or false, "scenes": [{"ref": "...", "what": "a few plain words"}], "signs": [{"ref": "...",
"what": "what the verse says it stands for or did"}]}
At most 5 scenes and 3 signs, the strongest. Only what the verses shown say. If the object is only mentioned (a list,
a measure, a figure of speech about something else), answer {"significant": false, "scenes": [], "signs": []}."""


def mac_triage():
    import random
    done = {p.stem.replace("-signs", "") for p in OUT.glob("*.md")}
    ents = [json.loads(l) for p in sorted((ROOT / "ontology" / "entities").glob("*.jsonl"))
            for l in open(p, encoding="utf-8") if l.strip()]
    jobs = ROOT / "out" / "grunt" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    rows, key = [], []
    for e in ents:
        if e.get("type") != "object" or e["id"] in done:
            continue
        try:
            v = get(f"/api/entity-verses?id={e['id']}")
        except Exception:
            v = {}
        lines = [f"{i['eref']} {i['text']}" for b in v.get("books", []) for i in b.get("items", [])]
        if not lines:
            word = e["name"].split()[-1]
            lines = berean(r"\b" + __import__("re").escape(word) + r"\b") if len(word) > 3 else []
        if not lines:
            continue
        if len(lines) > 60:                       # an even sample across the canon, not the first 60
            step = len(lines) / 60
            lines = [lines[int(i * step)] for i in range(60)]
        k = e["id"]
        rows.append({"key": k, "messages": [{"role": "system", "content": TRIAGE},
                                            {"role": "user", "content": f"OBJECT: {e['name']}\nVERSES:\n" + "\n".join(lines)}]})
        key.append({"key": k, "name": e["name"], "n": len(lines)})
    with open(jobs / "10-object-triage.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "qwen3.8:27b", "options": {"temperature": 0, "num_ctx": 8192},
                                     "pass": "object_triage"}}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(jobs / "10-object-triage.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for k in key:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(f"{len(rows)} objects for the Mac -> {jobs / '10-object-triage.jsonl'}")


if __name__ == "__main__":
    mac_triage() if "mac-triage" in sys.argv[1:] else main()
