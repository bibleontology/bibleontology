"""LOCAL MODEL BENCH: can a model on the Mac mini read verses as well as a Sonnet reader? (2026-10-24)

The test set is the image audit's 58 images (plan 8.2h): 3,088 verses, each read by a first Sonnet reader
and a blind second one, with a third settling where they split (tier2-final.json). The local model gets the
tie-break reader's brief, one verse at a time with the verse before and after, and is scored the way the
Sonnet readers were: by the card each answer would place the verse on.

  - vs the first reader: the like-for-like number. The blind Sonnet reader agrees with it at the rate printed
    as the baseline, so the local model is a usable second reader if it comes close.
  - vs the settled reading: the Sonnet readers helped make it, so their rate is flattered and the local
    model's is not; read it as a floor.
  - missed figures: the settled reading puts the verse on the image card and the model does not.

Ollama runs on the Mac, listening only there; reach it by tunnel first:
    ssh -N -L 11434:localhost:11434 macmini

    python tools/meaning/local_reader_bench.py run MODEL [--n 400] [--think] [--narrow]
    python tools/meaning/local_reader_bench.py score [FILE ...]

Not tools/local_bench.py, which is the 2026-09-02 bench of the extraction contract on a CPU laptop.
      -> out/meaning/local-bench/<model>.jsonl (resumable), summary printed
"""
import collections
import glob
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from derive import BOOK  # noqa: E402

CAND = ROOT / "out" / "meaning" / "image-audit" / "candidates"
OUT = ROOT / "out" / "meaning" / "local-bench"
URL = "http://localhost:11434/api/chat"
SENSES = ["figure_keyed", "figure", "both", "literal", "readers_differ", "other_sense", "unclear"]
PLACE = {"literal": "literal", "figure": "figure", "figure_keyed": "figure", "both": "both"}

BRIEF = """You are a blind reader in an audit of a Bible knowledge graph's image cards. You are given one verse \
(with the verse before and after for context) and the image card it may belong to ("name": the figure the card \
is about). The question: how is the card's word used in THIS verse?
- figure_keyed: used as a figure AND the text itself says what it stands for
- figure: a figure (metaphor, simile, parable, personification) with no stated key
- both: the literal thing and a figure in the same verse
- literal: the thing itself
- readers_differ: Christian traditions genuinely read it differently; choose none
- other_sense: the word means something else here, or the verse does not use it
- unclear
Answer with ONLY a JSON object, nothing before or after it: {"sense": "<one of the senses above>", \
"reason": "<one line quoting the verse>"}"""

# The narrow pass (Doug, 2026-10-24: "limiting responsibilities of any pass and giving great instructions for the
# pass"). One question, three answers, criteria, and worked pairs taken from settled verses outside the test sample
# (the shuffled first 400 are never used as examples). Keys and readers_differ are left to a later pass.
NARROW = """You are reading one Bible verse for an audit. The card names a thing (its "name"). Answer ONE question: \
is that thing used AS ITSELF in this verse?

- "itself": the real thing is meant: a real body part, a real mountain or river, a real person's father, a real \
shepherd with real sheep. Poetry, prophecy or a solemn setting do not change this if the real thing is meant.
- "figure": the word is used for something else. Signs of this:
  1. a comparison: "like", "as", "is a", "became a" with the thing as the picture;
  2. the thing does what it cannot really do: mountains hear, wisdom is embraced, a land vomits;
  3. a person or group called by the word who is not literally that: a ruler as "a father to Jerusalem", kings as \
"shepherds", the people as "sheep";
  4. a body part standing for the whole person or their state: "my bones are in agony" means "I am in agony".
- "absent": the word is not in the verse, or it means something unrelated (a title, a different sense).

Worked examples (card name -> answer):
- bones, "how the bones are formed in a mother's womb" (Ecc 11:5) -> itself: real bones in a real womb.
- bones, "heal me, O LORD, for my bones are in agony" (Ps 6:2) -> figure: the bones stand for the whole sufferer.
- mountain, "as you drank on My holy mountain" (Obad 1:16) -> itself: Zion, a real place.
- mountain, "Hear, O mountains, the LORD's indictment" (Mic 6:2) -> figure: mountains addressed as witnesses.
- father, "this was what their father said to them" (Gen 49:28) -> itself: Jacob, their real father.
- father, "he will be a father to the dwellers of Jerusalem" (Isa 22:21) -> figure: an official, not their father.
- shepherd, "The men are shepherds; they raise livestock" (Gen 46:32) -> itself: their real occupation.
- shepherd, "Listen to the wailing of the shepherds, for their glory is in ruins" (Zech 11:3) -> figure: rulers.
- masters, "the Son of Man is Lord even of the Sabbath" (Mark 2:28) -> absent: "Lord" is a title here, not a master.

Answer with ONLY a JSON object, nothing before or after it: {"answer": "itself" | "figure" | "absent", \
"reason": "<one line quoting the verse>"}"""
NARROW_PLACE = {"itself": "literal", "figure": "figure", "absent": "neither"}

SCHEMA = {"type": "object", "properties": {"sense": {"type": "string", "enum": SENSES},
                                           "reason": {"type": "string"}}, "required": ["sense", "reason"]}


def place(sense):
    return PLACE.get(sense, "neither")


def load():
    final = json.loads((CAND / "tier2-final.json").read_text(encoding="utf-8"))
    three = {(img, x[0] if isinstance(x, list) else x) for img, p in final["per"].items() for x in p.get("three") or []}
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    pos = {k: i for i, k in enumerate(order)}
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    items = []
    for f in sorted(glob.glob(str(CAND / "*.pack.json"))):
        pack = json.loads(Path(f).read_text(encoding="utf-8"))
        img = pack["image"]
        name = json.loads((CAND / f"{img}.json").read_text(encoding="utf-8")).get("name") or img
        blind = {v["ref"]: v["sense"] for v in json.loads(
            (CAND / f"{img}.blind.json").read_text(encoding="utf-8")).get("verses", [])}
        for v in pack["verses"]:
            key = f"{img}|{v['ref']}"
            if key not in final["final"] or (img, v["ref"]) in three:
                continue
            k = moved.get(v["ref"], v["ref"])
            i = pos.get(k)
            items.append({"key": key, "image": img, "name": name, "ref": v["ref"],
                          "before": text[order[i - 1]] if i else None, "text": v.get("text") or text.get(k),
                          "after": text[order[i + 1]] if i is not None and i + 1 < len(order) else None,
                          "first": v["sense"], "blind": blind.get(v["ref"]), "settled": final["final"][key]})
    return items


def ask(model, it, think, narrow=False):
    msg = {k: it[k] for k in ("name", "ref", "before", "text", "after")}
    # Ollama 0.40 refuses "format" for some models ("structured output is unavailable"), so the brief asks for
    # JSON and the reply is parsed; one that does not parse is a failure, which is part of what is measured.
    body = {"model": model, "stream": False, "think": think,
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [{"role": "system", "content": NARROW if narrow else BRIEF},
                         {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    raw = d["message"]["content"]
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        ans = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        ans = {}
    if narrow:
        # small models leave quotes unescaped inside the reason; the answer itself is still readable
        a = ans.get("answer") or (re.search(r'"answer"\s*:\s*"(itself|figure|absent)"', raw) or [None, None])[1]
        ans["sense"] = {"itself": "literal", "figure": "figure", "absent": "other_sense"}.get(a)
    if ans.get("sense") not in SENSES:
        return {"error": "unparsed: " + raw[:200], "secs": round(time.time() - t, 2)}
    return {"sense": ans.get("sense"), "reason": ans.get("reason"), "secs": round(time.time() - t, 2),
            "in_tok": d.get("prompt_eval_count"), "out_tok": d.get("eval_count"),
            "gen_secs": round((d.get("eval_duration") or 0) / 1e9, 2)}


def run(model, n, think, narrow=False):
    items = load()
    random.Random(1).shuffle(items)
    items = items[:n]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / (f"{model.replace(':', '_').replace('/', '_')}{'_think' if think else ''}"
                  f"{'_narrow' if narrow else ''}.jsonl")
    done = set()
    if path.exists():
        done = {json.loads(l)["key"] for l in open(path, encoding="utf-8") if l.strip()}
    with open(path, "a", encoding="utf-8") as f:
        for i, it in enumerate(items):
            if it["key"] in done:
                continue
            try:
                r = ask(model, it, think, narrow)
            except Exception as e:  # a failed call is recorded, never counted as an answer
                r = {"error": str(e)[:200]}
            f.write(json.dumps({"key": it["key"], **r}, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(items)}", flush=True)
    print(f"done: {path}")


def score(paths):
    items = {it["key"]: it for it in load()}
    base = list(items.values())
    print(f"baseline over all {len(base)} settled verses (Sonnet readers):")
    print(f"  blind vs first   {sum(place(i['blind']) == place(i['first']) for i in base) / len(base):.1%}")
    print(f"  blind vs settled {sum(place(i['blind']) == i['settled'] for i in base) / len(base):.1%}")
    for p in paths:
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        for r in rows:  # rows written before the narrow parse read past unescaped quotes
            m = re.search(r'"answer"\s*:\s*"(itself|figure|absent)"', r.get("error", ""))
            if m:
                r.update(sense={"itself": "literal", "figure": "figure", "absent": "other_sense"}[m[1]],
                         out_tok=None, gen_secs=0)
        ok = [r for r in rows if "sense" in r and r["sense"] in SENSES]
        sub = [items[r["key"]] for r in ok]
        lp = {r["key"]: place(r["sense"]) for r in ok}
        if "_narrow" in Path(p).stem:  # the narrow pass cannot say "both"; either half of it counts as right
            lp = {k: items[k]["settled"] if items[k]["settled"] == "both" and v in ("literal", "figure") else v
                  for k, v in lp.items()}
        n = len(ok)
        if not n:
            print(f"\n{Path(p).stem}: no answers ({len(rows)} rows)")
            continue
        figs = [i for i in sub if i["settled"] in ("figure", "both")]
        missed = [i for i in figs if lp[i["key"]] not in ("figure", "both")]
        secs = sum(r["secs"] for r in ok)
        print(f"\n{Path(p).stem}: {n} answered, {len(rows) - n} failed")
        print(f"  vs first reader  {sum(lp[i['key']] == place(i['first']) for i in sub) / n:.1%}"
              f"   (blind Sonnet on the same verses: {sum(place(i['blind']) == place(i['first']) for i in sub) / n:.1%})")
        print(f"  vs settled       {sum(lp[i['key']] == i['settled'] for i in sub) / n:.1%}"
              f"   (blind Sonnet on the same verses: {sum(place(i['blind']) == i['settled'] for i in sub) / n:.1%})")
        print(f"  missed figures   {len(missed)} of {len(figs)}"
              f"   (blind Sonnet: {sum(place(i['blind']) not in ('figure', 'both') for i in figs)})")
        print(f"  speed            {n / secs * 60:.1f} verses/min, {secs / n:.1f} s each, "
              f"{sum(r['out_tok'] or 0 for r in ok) / max(sum(r['gen_secs'] for r in ok), 1e-9):.1f} tok/s generating")
        conf = collections.Counter((i["settled"], lp[i["key"]]) for i in sub if lp[i["key"]] != i["settled"])
        print("  misplaced (settled -> model): " + ", ".join(f"{a}->{b} {c}" for (a, b), c in conf.most_common(6)))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 400
        run(sys.argv[2], n, "--think" in sys.argv, "--narrow" in sys.argv)
    elif cmd == "score":
        score(sys.argv[2:] or sorted(glob.glob(str(OUT / "*.jsonl"))))
