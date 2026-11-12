"""Word-card audit by a DeepSeek scholar, thinking on (A.48; Doug, 2026-11-07: "squeeze as much value as I can from
DeepSeek over the weekend … leverage think mode where it can compensate for the lower model").

Each word is one task: the card's PUBLIC data, fetched from the live site (/api/sense), cut to what a reader sees,
with the brief audit rounds 1 and 2 used. Blind (no tools, no files): it reads only what is sent, and what is sent
is already published. Divine-name words are left out (no divine-person rows to DeepSeek).

    python tools/word_audit_deepseek.py run [N] [--one KEY]
        -> docs/review/word-audit/round3-deepseek-<date>.jsonl (every answer) and .md (the findings)
"""
import datetime as dt
import json
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SITE = "http://localhost:8022" if "--local" in sys.argv else "https://bibleontology.org"   # --local: the build in hand
DONE = set("""G1161 G1344 G1510 G1511 G2036 G2076 G2258 G2316 G2424 G3004 G3056 G3588 G40 G4102 G4151 G5207 G5547 H1 H136
H160 H1768 H1961 H2572 H2617 H3068 H3069 H3091 H3478 H426 H559 H565 H6235 H705 H7307 H7657 H776 H7965 H7970 H8346
G25 G26 G225 G1096 G1427 G1722 G2222 G2532 G3187 G3739 G4396 G5101 H113 H259 H430 H1121 H1285 H1732 H3045 H3820
H4428 H4430 H7225 H8034""".split())
DIVINE = {"G2316", "G2962", "G2424", "G5547", "G4151", "G3962", "H3068", "H3069", "H3050", "H136", "H113", "H430",
          "H410", "H433", "H426", "H7706", "H5945", "H6635"}

BRIEF = """You are a scholar who reads r/Koine: a Koine Greek teacher equally at home in Biblical Hebrew and Aramaic.
You audit one word card of a free Bible-study site that wants to be a credible first-choice research tool for people
without Logos or Accordance. Below is everything the card shows a reader, as data. Check, from your own knowledge:
- the headword (accents, breathings, vowel points) and that the transliteration is of the headword;
- the gloss and the short sense;
- whether the use count is plausible for this Strong's number;
- that the lexicon entry and its pull-quote are this word's, and the quote a whole, sensible clause;
- that each UBS sense belongs to this word (judge by its gloss, domain and cited verses);
- the "Berean prints" renderings (each should be a translation of THIS word, not a neighbor's);
- the Septuagint rows (Hebrew words) and "what the text does with it" (does it read as English? is it true?).
ALREADY KNOWN, not to be reported: renderings that carry a neighboring word's English, or miss the commonest
rendering of a function word (a redesign is underway); Hebrew transliterations in STEP's dotted style; the Hebrew
lexicon being Strong's own dictionary.
BY DESIGN, not faults: Greek cards have no Septuagint rows (those are given on Hebrew cards only); UBS's senses are
the UBS dictionary's own analysis (a phrase sense such as "Son of Man" is theirs to make), so report a UBS sense only
when it belongs to a DIFFERENT Strong's number; a dagesh lene in an initial begadkefat letter is correct pointing.
Each finding names the question it answers ("question": "headword|translit|gloss|count|entry|quote|ubs|renderings|
septuagint|rows") and how sure you are ("sure": "certain|likely").
Answer with ONE JSON object and nothing else:
{"key": "...", "verdict": "right|polish|misleading|wrong",
 "findings": [{"level": "WRONG|MISLEADING|POLISH", "what": "what the card shows", "should": "what it should show",
               "evidence": "your reason"}],
 "right": "one sentence on what held up"}
WRONG is reserved for a factual error a scholar would correct: a wrong headword, count, entry, sense or translation.
Report only what you are confident of; say nothing rather than guess."""


def fetch(key):
    out = subprocess.run(["curl", "-s", f"{SITE}/api/sense?key={key.lower()}"], capture_output=True, timeout=120)
    try:
        return json.loads(out.stdout.decode("utf-8"))
    except ValueError:              # the site restarting ("back in a moment") or a refusal: not a card
        return {"found": False}


def card(c):
    face = c.get("face") or {}
    pr = face.get("printed") or {}
    ubs = c.get("ubs") or {}
    return {
        "key": c.get("key"), "lemma": c.get("lemma"), "translit": c.get("translit"), "lang": c.get("lang"),
        "pos": c.get("pos"), "gloss": c.get("gloss"), "short": c.get("short"), "uses": c.get("observations"),
        "counted_under": c.get("counted_under"), "headword_note": c.get("lemma_also"),
        "lexicon_entry": (c.get("definition") or "")[:1500], "lexicon_credit": c.get("definition_credit"),
        "pull_quote": (face.get("lexicon") or {}).get("quote"),
        "berean_prints": [(r["text"], r["n"]) for r in (pr.get("rows") or [])[:12]],
        "no_separate_word": pr.get("none"),
        "ubs_senses": [{"gloss": s.get("gloss") or s.get("short"), "definition": s.get("short") or s.get("def"),
                        "domain": s.get("domain"), "verses": (s.get("refs") or [])[:4]}
                       for s in (ubs.get("senses") or [])[:8]],
        "ubs_filed_under": ubs.get("filed_under"),
        "septuagint": [x.get("word") for x in c.get("lxx") or []],
        "what_the_text_does": [f"{f.get('says')} {f.get('with')} ({f.get('count')})" for f in (c.get("features") or [])[:12]
                               if f.get("kind") != "lxx"],
    }


def pick(n, seed=20261108):
    import gzip
    uses = {}
    for line in gzip.open(ROOT / "out" / "interlinear.jsonl.gz", "rt", encoding="utf-8") \
            if (ROOT / "out" / "interlinear.jsonl.gz").exists() else []:
        for w in json.loads(line).get("words", []):
            s = re.sub(r"[^0-9]", "", w.get("s") or "").lstrip("0")
            if s:
                uses[s] = uses.get(s, 0) + 1
    rnd = random.Random(seed)
    greek = [f"G{k}" for k in range(1, 5625)]
    hebrew = [f"H{k}" for k in range(1, 8675)]
    pool = [k for k in greek + hebrew if k not in DONE and k not in DIVINE]
    rnd.shuffle(pool)
    common = [k for k in pool if uses.get(k[1:], 0) >= 30]
    rare = [k for k in pool if 3 <= uses.get(k[1:], 0) < 30]
    g = [k for k in common if k[0] == "G"][: n // 3] + [k for k in rare if k[0] == "G"][: n // 6]
    h = [k for k in common if k[0] == "H"][: n // 3] + [k for k in rare if k[0] == "H"][: n - n // 3 - n // 3 - n // 6]
    return g + h


def one(key):
    from bibleont import delegate as D
    c = fetch(key)
    if not c.get("found"):
        return {"key": key, "error": "no card"}
    task = BRIEF + "\n\nTHE CARD (as data, from " + f"{SITE}/word/{key}):\n" + json.dumps(card(c), ensure_ascii=False)
    r = D.run(task, level=3, label=f"word-audit-r3 {key}", blind=True, think=True, effort="high", timeout=900)   # with room to finish: 64,000 output tokens
    text = r.get("answer") or r.get("text") or r.get("content") or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        ans = json.loads(m.group(0)) if m else None
    except ValueError:
        ans = None
    return {"key": key, "answer": ans, "raw": None if ans else text[:2000], "cost": r.get("cost") or r.get("cost_usd"),
            "refused": r.get("refused")}


def main():
    args = sys.argv[1:]
    if not args or args[0] != "run":
        print(__doc__)
        return
    keys = [k.strip().upper() for k in args[args.index("--keys") + 1].split(",")] if "--keys" in args else         [args[args.index("--one") + 1]] if "--one" in args else pick(int(args[1]) if len(args) > 1 and args[1].isdigit() else 30,
                                                                   int(args[args.index("--seed") + 1]) if "--seed" in args else 20261108)
    # no divine-name word goes to DeepSeek, however the list was given (a hand list included H430 on 2026-11-09; the
    # run was stopped before it was sent)
    keys = [k for k in keys if k.upper() not in DIVINE]
    day = dt.date.today().isoformat()
    out = ROOT / "docs" / "review" / "word-audit" / f"round3-deepseek-{day}.jsonl"
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, keys))
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wrong = [r for r in rows if (r.get("answer") or {}).get("verdict") == "wrong"]
    print(f"{len(rows)} words; {len(wrong)} wrong: {[r['key'] for r in wrong]}; "
          f"cost ${sum(float(r.get('cost') or 0) for r in rows):.3f}; refused {[r['key'] for r in rows if r.get('refused')]}")


if __name__ == "__main__":
    main()
