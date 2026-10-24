"""Audit a Copilot thread's ten "speech templates" against what the graph holds.

2026-09-30, on the thread (ontology/themes/speech-templates-copilot.md): it
might all map on themes or concepts already held, and the proposal was to
audit it. No template becomes a node. Each maps to
layers the graph already has (speech acts, messages, story patterns, major
themes); every verse a template's trace cites is checked against those
layers. A miss is a candidate gap in a layer, to be read and fixed by a
general rule -- not by adding the verse.

A whole chapter or book cited ("Gen 15", "Isa 40–55", "James") is too broad
to test a layer by and is counted apart, as the images audit did.

    python tools/themes/templates_audit.py
        -> out/templates-audit.json
        -> docs/review/TEMPLATES-AUDIT.md
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
from event_nodes import verses  # noqa: E402

SRC = ROOT / "ontology" / "themes" / "speech-templates-copilot.md"
BOOK = {"James": "Jas", "Song": "Song"}
# each template -> the layers it maps to (the proposal's table, 2026-09-30)
MAP = {
    1: {"acts": ["naming"], "story": ["word_order"], "themes": ["creation", "prophetic_word"]},
    2: {"acts": ["promise", "oath"], "msg_groups": ["promise"], "msgs": ["i_will_bless_you"],
        "story": ["promise"], "themes": ["covenant", "new_creation"]},
    3: {"acts": ["command", "warning"], "msg_groups": ["ethical"], "themes": ["law_wisdom"]},
    4: {"acts": ["confession_of_faith", "testimony"]},
    5: {"acts": ["blessing", "benediction"]},
    6: {"acts": ["summons"], "msgs": ["come_to_me", "i_will_give_you_rest",
                                     "the_spirit_and_the_bride_say_come"],
        "msg_groups": ["wisdom"]},
    7: {"acts": ["commissioning"], "story": ["call"], "msgs": ["go", "make_disciples_of_all_nations"],
        "themes": ["blessing_commission"]},
    8: {"acts": ["lament", "complaint"], "story": ["evil_to_good", "death_life"],
        "themes": ["sin_exile_death", "mercy_restoration"]},
    9: {"msg_groups": ["ethical"], "themes": ["law_wisdom", "wisdom_literature"]},
    10: {"msg_groups": ["last_things"], "themes": ["new_creation", "apocalyptic"],
         "story": ["death_life"]},
}


def parse():
    """The ten numbered templates and their cited references."""
    text = SRC.read_text(encoding="utf-8")
    block = text.split("**Ten templates")[1].split("Copilot also offered")[0]
    out = {}
    for m in re.finditer(r"(?ms)^\s*(\d+)\. ([^—]+?) — (.+?)(?=^\s*\d+\. |\Z)", block):
        out[int(m.group(1))] = (m.group(2).strip(), " ".join(m.group(3).split()))
    return out


def refs(s):
    """'Gen 12:2–3; 15; 26:24; Exod 3:12' -> ([verse ids], [broad refs])."""
    vs, broad, book = [], [], None
    for part in [p.strip().rstrip(".") for p in s.split(";")]:
        for piece in [x.strip() for x in part.split(",")]:
            m = re.fullmatch(r"((?:[1-3] )?[A-Z][a-z]+)?\s*(\d+)?(?::(\d+)(?:–(\d+))?)?(?:–(\d+))?", piece)
            if not m or not piece:
                continue
            if m.group(1):
                book = BOOK.get(m.group(1), m.group(1).replace(" ", ""))
            ch, v1, v2 = m.group(2), m.group(3), m.group(4)
            if not ch or not v1:
                broad.append(f"{book} {ch or ''}".strip() + (f"–{m.group(5)}" if m.group(5) else ""))
                continue
            vs += verses({"book": book, "start": [int(ch), int(v1)],
                          "end": [int(ch), int(v2 or v1)]})
    return vs, broad


def main():
    import messages
    story, _roles, themes, _events, _recurs, _tn = messages.layers()
    sa = json.loads((OUT / "speech-act-view.json").read_text(encoding="utf-8"))["acts"]
    mv = json.loads((OUT / "message-view.json").read_text(encoding="utf-8"))
    acts = {k.removeprefix("sact_"): {i["v"] for i in a["instances"]} for k, a in sa.items()}
    msgs = {k.removeprefix("msg_"): {i["v"] for i in m["instances"]} for k, m in mv["messages"].items()}
    groups = {g: set().union(*(msgs[m.removeprefix("msg_")] for m in v["messages"]))
              for g, v in mv["groups"].items()}
    fam = collections.defaultdict(set)
    for (f, *_rest), vs in story.items():
        fam[f] |= vs
    th = collections.defaultdict(set)
    for (tid, _t), vs in themes.items():
        th[tid] |= vs
    layer = {"acts": acts, "msgs": msgs, "msg_groups": groups, "story": fam, "themes": th}
    name = {"acts": lambda k: "speech act " + sa["sact_" + k]["name"],
            "msgs": lambda k: "message " + mv["messages"]["msg_" + k]["name"],
            "msg_groups": lambda k: "message group " + mv["groups"][k]["name"],
            "story": lambda k: "story pattern " + k, "themes": lambda k: "theme " + k}

    def where(v, only=None):
        hits = []
        for kind, d in layer.items():
            for k, vs in d.items():
                if (only is None or k in only.get(kind, [])) and v in vs:
                    hits.append(name[kind](k))
        return hits
    import gzip
    bsb = {}
    for ln in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r:
            bsb[r["ref"]] = r["text"]
    from event_nodes import TO_MACULA

    def shown(v):
        b, c, n = v.split(".")
        return bsb.get(f"{TO_MACULA.get(b, b)}.{c}.{n}", "")
    res, lines, tot = {}, [], collections.Counter()
    for n, (tname, s) in parse().items():
        vs, broad = refs(s)
        rows = []
        for v in vs:
            mapped = where(v, MAP[n])
            other = [] if mapped else where(v)
            rows.append({"v": v, "mapped": mapped, "elsewhere": other, "text": shown(v)})
            tot["held in its layer" if mapped else "held elsewhere" if other else "not held"] += 1
        tot["broad (not tested)"] += len(broad)
        res[n] = {"name": tname, "rows": rows, "broad": broad}
        held = sum(1 for r in rows if r["mapped"])
        lines += [f"## {n}. {tname}", "",
                  f"Maps to: {', '.join(name[k](x) for k, xs in MAP[n].items() for x in xs)}. "
                  f"Verses cited: {len(rows)}; held in those layers: {held}. Too broad to test: "
                  f"{', '.join(broad) or 'none'}.", ""]
        for r in rows:
            if not r["mapped"]:
                lines.append(f"- **{r['v']}** — "
                             f"{'held as ' + '; '.join(r['elsewhere'][:3]) if r['elsewhere'] else 'not held'}"
                             f" — {r['text'][:110]}")
        lines.append("")
    head = ["# The Copilot speech templates, audited against the graph", "",
            "Made by `tools/themes/templates_audit.py` from "
            "ontology/themes/speech-templates-copilot.md. No template is a node; each maps "
            "to layers the graph already has, and every verse its trace cites is checked "
            "against them. Below each template: the cited verses NOT in the layers it maps "
            "to -- candidate gaps, to be read, not added.", "",
            "| | verses |", "|---|---|"] + [f"| {k} | {v} |" for k, v in tot.items()] + [""]
    (ROOT / "docs" / "review" / "TEMPLATES-AUDIT.md").write_text("\n".join(head + lines) + "\n",
                                                                encoding="utf-8")
    (OUT / "templates-audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    print(dict(tot))


if __name__ == "__main__":
    main()
