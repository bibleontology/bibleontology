"""Word pairs a reader of the English would miss (Doug, 2026-11-11, of the ἱερόν/ναός comparison: "is what you did with
the Temple word comparison a one time thing or is it something you do with other word pairs as well?" then "Yes, find
pairs").

ontology/word-partners.json holds pairs approved by hand; it had one, ἱερόν and ναός ("The Berean prints both as
'temple'; Abbott-Smith distinguishes them"). Candidates by rule: two content words of one language, each in 15 verses
or more, whose commonest English rendering is the same. Left out: names, the small words, an Aramaic word and the
Hebrew it corresponds to (one word in two languages, not two words), and the words for God and the Lord (divine
persons are Doug's by hand). One narrow question goes to the Mac per pair: do the lexicons tell them apart in a way a
reader of the English would miss? Nothing is written by this pass; Claude reads every "distinct", Doug approves what
goes into the table.

    python tools/meaning/word_pairs.py build   -> out/orchestra-intake/25-word-pairs/
"""
import collections
import itertools
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))

NAME = "25-word-pairs"
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261111
MIN_VERSES = 15
DIVINE_GLOSS = {"god", "lord", "gods", "lord's"}

BRIEF = """You compare two words of the Bible's original language that an English translation (the Berean Standard
Bible) renders the same way. You get each word's lexicon entry and two verses where it stands. Say whether the
lexicons distinguish them in a way a reader of the English would miss.

Answer with ONE line of JSON:
{"id": "...", "verdict": "...", "difference": "...", "why": "..."}

verdict:
- "distinct": the lexicons give the two words different senses or uses that a careful reader would want to know
  (one is the whole temple precinct, the other the sanctuary building).
- "same": the lexicons treat them as near-synonyms with no difference worth a reader's notice.
- "not_comparable": they share an English word only by accident (one is a verb "to keep", the other means "to draw
  near"), or one is a grammatical form of the other.
- "unclear": you cannot tell from what is given.

difference: for "distinct" only, one plain sentence saying how the lexicons distinguish them, in the lexicons' own
terms (no theology, no claim beyond the entries). Otherwise "".
why: one short reason.

Worked examples (not from the items):
- ἱερόν "temple" (the whole temple precinct, courts included) and ναός "temple" (the sanctuary building itself) ->
  distinct: "ἱερόν is the whole temple precinct with its courts; ναός is the sanctuary building itself."
- λαός "people" and ὄχλος "crowd" both rendered "people" in places -> distinct if the entries say so.
- φυλάσσω "to keep" (guard) and τηρέω "to keep" (watch over, observe) -> distinct only if the entries mark it.
"""


def build():
    import server as S
    from object_identity import verses
    text = verses()
    d = S.load()
    vo = S._verses_of(d)
    lemmas = d.get("lemmas") or {}

    def content(k):
        pos = ((d["lex"].get(k) or {}).get("pos") or "")
        return re.match(r"([HG]:)?[NVA]", pos) and not pos.startswith("N:N")      # H:V, G:N-F, A:A

    groups = collections.defaultdict(list)
    for k, p in d["profiles"].items():
        n = len(vo.get(k, ()))
        if n < MIN_VERSES or k in S._FUNCTION_WORDS or S.name_kind(d, k) or not content(k):
            continue
        gl = re.sub(r"^to ", "", (p.get("gloss") or "").lower()).strip()
        if not gl or len(gl.split()) > 2 or gl in DIVINE_GLOSS:
            continue
        groups[(k[0], gl)].append(k)
    items = []
    for (lang, gl), ks in groups.items():
        ks = sorted(ks, key=lambda k: -len(vo.get(k, ())))[:4]
        for a, b in itertools.combinations(ks, 2):
            da, db = (d["lex"].get(a) or {}).get("definition") or "", (d["lex"].get(b) or {}).get("definition") or ""
            # an Aramaic word and the Hebrew it corresponds to: one word in two languages
            if re.search(r"\(Aramaic\)|corresponding to", da + db) and \
                    re.sub(r"[^א-ת]", "", lemmas.get(a) or "") == re.sub(r"[^א-ת]", "", lemmas.get(b) or ""):
                continue
            if lemmas.get(a) and lemmas.get(a) == lemmas.get(b):
                continue

            def side(k, defn):
                vs = sorted(vo.get(k, ()))[:2]
                quotes = [f"{S.to_english(r) if hasattr(S, 'to_english') else r}: {text.get(r) or ''}"[:220] for r in vs]
                return (f"{lemmas.get(k) or k} ({k.upper()}, {len(vo.get(k, ()))} verses). LEXICON: {defn[:600]}\n"
                        + "\n".join(quotes))
            items.append({"key": f"{a}|{b}", "id": f"w{len(items) + 1}", "pair": [a, b], "gloss": gl,
                          "claim": f'Both rendered "{gl}".', "verse": side(a, da) + "\n---\n" + side(b, db),
                          "context": []})
    random.Random(SEED).shuffle(items)
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "word_pairs"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 30, "flag": {"verdict_in": []},
            "deepseek": {"budget_usd": 0}, "allowed_fields": ["id", "claim", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} candidate pairs from {sum(1 for v in groups.values() if len(v) > 1)} shared renderings -> {out}")


def messages(it):
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"id: {it['id']}\n{it['claim']}\nWORD A: {it['verse']}"}]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    else:
        print(__doc__)
