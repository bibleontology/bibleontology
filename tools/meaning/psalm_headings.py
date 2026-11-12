"""The Psalter's headings as described claims (plan 8.1g, step 3's first pass; 2026-11-03).

A psalm's heading ("A Psalm of David, when he fled from his son Absalom") is a described claim about the psalm, never
the psalm's own statement: its attribution, its kind, its occasion and its musical directions. The Berean folds each
heading into the psalm's first verse. This pass turns each heading into claims a person could check against that verse,
for the orchestrator's first unattended run: the Mac reads every claim, then DeepSeek reads them blind, twice, off-peak
(Doug, 2026-11-03: "make sure that the Mac has a productive window between 11-1"). Nothing is written to the graph.

    python tools/meaning/psalm_headings.py build   -> out/orchestra-intake/16-psalm-headings/ (copied to the Mac)
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import verse_reread as vr  # noqa: E402

NAME = "16-psalm-headings"
OUT = ROOT / "out" / "orchestra-intake" / NAME
AUTHORS = ["David", "Asaph", "Solomon", "Moses", "the sons of Korah", "Heman the Ezrahite", "Ethan the Ezrahite"]
KINDS = ["Psalm", "Song", "Maskil", "Miktam", "Prayer", "Shiggaion", "song of ascents", "Song of Ascents"]
DIRECTIONS = [r"For the choirmaster", r"With stringed instruments", r"With the flutes", r"To the tune of [^.]+",
              r"According to [^.]+", r"On the [A-Z][^.]+", r"For the dedication of [^.]+", r"To bring remembrance",
              r"For the Sabbath day", r"For giving grateful praise", r"A petition"]
HEADING_START = re.compile(r"^(A |An |For |Of |To |When |With |According |On |Concerning |Upon |Set )")
DIVINE = re.compile(r"\b(LORD|God|Lord)\b")


def heading_of(text):
    """The leading sentences of a psalm's first verse that are its heading, not its speech."""
    parts = re.split(r"(?<=[.])\s+", text.strip())
    head = []
    for p in parts:
        if HEADING_START.match(p) and len(" ".join(head + [p])) < 400:
            head.append(p)
        else:
            break
    return " ".join(head)


def claims_for(c, head):
    out = []
    for a in AUTHORS:
        if re.search(r"\b[Oo]f " + re.escape(a) + r"\b", head):     # "A Psalm of David" and "Of David." (Ps 145)
            out.append(("author", f"Psalm {c}'s heading attributes it to {a}"))
    for k in KINDS:
        if re.search(r"\b" + re.escape(k) + r"\b", head):
            out.append(("kind", f"Psalm {c}'s heading calls it a {k.lower()}"))
            break
    for d in DIRECTIONS:
        m = re.search(d, head)
        if m:
            out.append(("direction", f"Psalm {c}'s heading gives a direction: {m.group(0).lower()}"))
    m = re.search(r"\b([Ww]hen [^.]+)\.", head)
    if m:
        out.append(("occasion", f"Psalm {c}'s heading gives its occasion: {m.group(1)[0].lower() + m.group(1)[1:]}"))
    return out


def build():
    verses = {}
    for l in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("b") == "Ps" and r.get("v") == 1:
            verses[r["c"]] = r["t"]
    items, mac_only = [], 0
    for c in sorted(verses):
        head = heading_of(verses[c])
        if not head:
            continue
        for kind, claim in claims_for(c, head):
            it = {"key": f"ps{c}-{kind}-{len(items)}", "id": f"h{len(items) + 1}", "claim": claim, "ref": f"Ps {c}:1",
                  "verse": verses[c], "context": [], "kind": kind}
            if DIVINE.search(claim):
                it["mac_only"] = True                     # never to DeepSeek: it names the LORD or God
                mac_only += 1
            items.append(it)
    rnd = random.Random(20261103)
    authored = [i for i in items if i["kind"] == "author"]
    plants = []
    for n, it in enumerate(rnd.sample(authored, min(12, len(authored)))):
        other = rnd.choice([a for a in AUTHORS if a not in it["claim"]])
        plants.append({"id": f"p{n + 1}", "claim": re.sub(r"to [^,.]+$", "to " + other, it["claim"]), "ref": it["ref"],
                       "verse": it["verse"], "context": [], "expect": "not_said"})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": vr.OPTIONS, "pass": "psalm_headings"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": vr.messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 10,
            # every claim the Mac reads goes to DeepSeek, not only its flags: a small, whole pass, read three times
            "flag": {"verdict_in": ["stated", "implied", "partly", "not_said", "unclear"]},
            "deepseek": {"runs": 2, "batch": 36, "brief": "brief.md", "planted": "planted.jsonl", "budget_usd": 0.15},
            "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (OUT / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (OUT / "brief.md").write_text(vr.SLOT_BRIEF + "\n", encoding="utf-8")   # the claims fill a slot: who wrote it
    with open(OUT / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            if not it.get("mac_only"):
                f.write(json.dumps({k: it[k] for k in ("key", "id", "claim", "ref", "verse", "context")}, ensure_ascii=False) + "\n")
    with open(OUT / "planted.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in plants:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    kinds = {}
    for it in items:
        kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
    print(f"{NAME}: {len(items)} claims from {len([c for c in verses if heading_of(verses[c])])} headings {kinds}; "
          f"{mac_only} kept from DeepSeek; {len(plants)} plants")


if __name__ == "__main__":
    {"build": build}[sys.argv[1]]()
