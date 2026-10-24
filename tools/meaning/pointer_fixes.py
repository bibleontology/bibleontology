"""CORRECTIONS FOR THE POINTERS THE PANEL OBJECTED TO (2026-10-19), as
CANDIDATES. The panel of eleven found 154 words the sweep had pointed to God or
Jesus that point to someone else (Deut 15:2's "he" is the creditor). Those links
are wrong wherever they are used; the fix belongs in the sweep (plan 2.18: a
fault found high is fixed at the lowest layer that could have known it). Two
judges each name the true referent; where they agree, the correction waits for
the mark on docs/review/divine-ends-2026-10-19.html (decision 2). Nothing
is written to the sweep layer here.

    python tools/meaning/pointer_fixes.py   -> out/meaning/divine-panel/corrections.jsonl
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "meaning" / "divine-panel"
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402
import headless as H  # noqa: E402

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
TASK = """Each item is one word in a Bible verse (a pronoun, or a verb's unstated subject). An automated link said it
refers to God or Jesus; careful readers objected (their reasons are given). Read the verses (Berean text) and say what
the word actually refers to:
  "referent"   the words in the text that name it, as they appear ("the creditor", "the man in the open field",
               "anyone who wants to be first", "the Father", "Stephen"); or "God"/"Jesus" if the objection is wrong
  "ref"        the verse where those words stand
  "confidence" high | medium | low
Unresolved is better than wrong: if it is truly unclear, give referent "unclear".

Answer with ONLY this JSON object:
{"items": [{"id": "<item id>", "referent": "...", "ref": "...", "confidence": "high|medium|low", "why": "a dozen words"}]}

"""


def norm(s):
    return re.sub(r"^(the|a|an)\s+", "", re.sub(r"[^a-z ]", "", (s or "").lower()).strip())


def main():
    rows = [json.loads(x) for x in (OUT / "verdicts.jsonl").read_text(encoding="utf-8").splitlines()]
    obj = [r for r in rows if r["verdict"] == "objected"]
    bsb = C._bsb()
    res = {}
    for model in ("sonnet", "haiku"):
        res[model] = {}
        for i in range(0, len(obj), 20):
            b = obj[i:i + 20]
            its = []
            for r in b:
                refs = sorted({c["ref"] for c in r["chain"] if c["ref"]})
                lo = refs[0].rsplit(".", 1)
                ctx = [f"{lo[0]}.{int(lo[1]) - k}" for k in (2, 1) if int(lo[1]) - k > 0] + refs
                its.append({"id": r["id"], "texts": {x: bsb(x)[1] for x in ctx if bsb(x)[1]},
                            "word": r["chain"][0]["text"] or "(unstated subject)", "verse": r["ref"],
                            "linked_to": {"god": "God", "jesus": "Jesus"}.get(r["person"]),
                            "objections": sorted({o.get("why") for o in (r["pass1"] or []) + (r["pass2"] or [])})[:4]})
            out, err = H.call(TASK + json.dumps({"items": its}, ensure_ascii=False, separators=(",", ":")) + "\n",
                              MODELS[model])
            for a in (H.parse(out) or {}).get("items") or []:
                res[model][a.get("id")] = a
    lines, agree = [], 0
    for r in obj:
        s, h = res["sonnet"].get(r["id"]) or {}, res["haiku"].get(r["id"]) or {}
        same = bool(s) and bool(h) and norm(s.get("referent")) == norm(h.get("referent")) \
            and norm(s.get("referent")) not in ("unclear", "")
        agree += same
        lines.append({"id": r["id"], "ref": r["ref"], "word": r["chain"][0]["text"], "was": r["person"],
                      "sonnet": s, "haiku": h, "agree": same})
    (OUT / "corrections.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines),
                                           encoding="utf-8")
    print(f"{len(obj)} objected; both judges name the same referent in {agree}")
    for x in lines[:12]:
        print(x["ref"], x["word"], "->", (x["sonnet"] or {}).get("referent"), "/", (x["haiku"] or {}).get("referent"),
              "AGREE" if x["agree"] else "")


if __name__ == "__main__":
    main()
