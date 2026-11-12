"""Does the Berean's marked English translate this word here? (audit round 1, MISLEADING 4; 2026-11-07)

The scholar's audit found "How the Berean renders it" carrying alignment artifacts: ὁ "died" (41) and "t" (45), δέ
"the Baptist", υἱός "of disobedience" and "son asks", יְהוָה "by fire" (30). Each row of that list is a run of the
Berean's words the alignment tied to the original word. This pass asks one narrow question of each row, at the first
verse it occurs in: is the marked English this word's translation in this verse?

    stated    the marked words translate this word (small words such as "the", "of", "to" may come with it)
    partly    they hold this word's English and also another word's ("son asks": "asks" is another verb)
    not_said  they translate another word of the verse, not this one
    unclear   cannot tell

The Mac reads every row; DeepSeek reads the rows it does not call stated. Nothing is changed by the pass: its verdicts
are the measure the alignment fix is judged by (before and after), and the candidates Claude reads. All inputs are
released texts: the Berean (CC0), MACULA's glosses, Strong's and Abbott-Smith (public domain).

    python tools/meaning/renderings_check.py build [WORDS]   -> out/orchestra-intake/21-renderings-check/
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))

NAME = "21-renderings-check"
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261107
PER_WORD = 12        # rows read per word, in the card's own order
WORDS = 3000         # the most used words first: the cards readers open

BRIEF = """You check an English Bible's word alignment. A word of the Hebrew or Greek original is shown with its
dictionary meaning, and a verse of the Berean Standard Bible with some words marked «like this». The marked words are
what an alignment says translates that original word in this verse. Say whether that is right.

Answer each with ONE line of JSON:
{"id": "...", "verdict": "...", "words": "...", "why": "..."}

verdict:
- "stated": the marked words translate this original word here. Small words that English needs around it ("the",
  "of", "to", "a", "will") may be marked with it. An unusual but fair translation counts ("house" for a family).
- "partly": the marked words hold this word's English AND another word's ("son asks", where "asks" is the verb).
- "not_said": the marked words translate a different word of the verse, not this one ("died" marked for the
  article "the"; "by fire" marked for the name of the LORD).
- "unclear": you cannot tell.

words: the marked words that belong to ANOTHER word, copied exactly ("" if none).
why: one short reason.

Worked examples (not from the items):
- WORD ὁ "the" (the article). VERSE: "For the death He «died», He died to sin once for all" -> not_said: "died" is
  the verb ἀπέθανεν.
- WORD λόγος "word". VERSE: "In the beginning was «the Word»" -> stated.
- WORD οἶκος "house". VERSE: "you and «your household» will be saved" -> stated: household is a fair sense.
- WORD υἱός "son". VERSE: "Which of you, if his «son asks» for bread" -> partly, words "asks".
"""


def gloss_of(c):
    return (c.get("short") or c.get("gloss") or "").strip()


def definition_of(c):
    text = re.sub(r"\s+", " ", (c.get("definition") or c.get("def") or "")).strip()
    return text[:220] + ("…" if len(text) > 220 else "")


def build(words=WORDS):
    import server as S
    d = S.load()
    vo = S._verses_of(d)
    keys = sorted((k for k in vo if k[:1] in "gh" and k not in DIVINE), key=lambda k: -len(vo[k]))[:words]
    items, n = [], 0
    for key in keys:
        c = S.api_sense(d, {"key": [key]})
        lemma, gloss = c.get("lemma") or "", gloss_of(c)
        lang = "Hebrew" if key.startswith("h") else "Greek"
        alts = S._alts(d, key)
        known = S._known_runs(d, key, None, alts)
        pr = S.printed_of(d, key, vo[key])
        for row in pr["rows"][:PER_WORD]:
            ref = row["refs"][0]
            got, _u = S._printed_here(d, key, ref, alts, known)
            rec = (d.get("align") or {}).get(S.bsb_ref(d, ref)) or (d.get("align") or {}).get(ref) or {}
            text = rec.get("text") or ""
            hit = [(p, s, e) for p, s, e, _m, _g in (got or ()) if p.lower() == row["text"].lower()]
            if not (text and hit):
                continue
            p, s, e = hit[0]
            at = s + max(0, text[s:e].find(p))
            verse = text[:at] + "«" + p + "»" + text[at + len(p):]
            lw = "hebrew" if key.startswith("h") else "greek"
            here = [w for w in d["orig"].get(ref, ()) if S.sense_key(lw, w.get("s")) == key]
            others = [f"{(w.get('t') or '').strip()} \"{(w.get('g') or '').strip()}\"" for w in d["orig"].get(ref, ())
                      if S.sense_key(lw, w.get("s")) != key and (w.get("g") or "").strip()]
            n += 1
            items.append({"key": f"{key}:{row['text']}@{ref}", "id": f"r{n}", "word": key, "rendering": row["text"],
                          "n": row["n"], "ref": ref,
                          "claim": f"In {ref}, the marked words «{p}» translate the {lang} word {lemma} "
                                   f"(Strong's {key[:1].upper()}{key[1:]}, \"{gloss}\").",
                          "verse": verse,
                          "context": [f"WORD: {lemma} ({lang}, Strong's {key[:1].upper()}{key[1:]}) \"{gloss}\"; "
                                      f"here as {', '.join((w.get('t') or '').strip() for w in here)}. "
                                      f"Dictionary: {definition_of(c)}",
                                      "OTHER WORDS OF THE VERSE (original, gloss): " + "; ".join(others[:40])]})
    plants = [x for x in items if (x["word"], x["rendering"].lower()) in PLANTS]
    items = [x for x in items if x not in plants]
    random.Random(SEED).shuffle(items)
    plants += moved(items, 24 - len(plants))
    plants = [{"id": f"p{i}", "claim": x["claim"], "ref": x["ref"], "verse": x["verse"], "context": x["context"],
               "expect": "not_said"} for i, x in enumerate(plants, 1)]
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "renderings_check"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 20,
            "flag": {"verdict_in": ["partly", "not_said", "unclear"]},
            "deepseek": {"runs": 1, "batch": 36, "brief": "brief.md", "planted": "planted.jsonl", "budget_usd": 0.5},
            "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps({k: it[k] for k in ("key", "id", "word", "rendering", "n", "claim", "ref", "verse",
                                                   "context")}, ensure_ascii=False) + "\n")
    with open(out / "planted.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in plants:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{len(keys)} words, {len(items)} rows to read, {len(plants)} plants -> {out}")


# words that name a divine person or are mostly read of one: DeepSeek gets no divine-person rows, so Claude reads
# these cards itself
DIVINE = {"h3068", "h3069", "h3050", "h136", "h113", "h430", "h410", "h433", "h426", "h7706", "h5945", "g2316",
          "g2962", "g2424", "g5547", "g4151", "g3962", "g2316", "g5207"}

# the audit's own finds, read as plants (their answer is known)
PLANTS = {("g3588", "died"), ("g3588", "t"), ("g1161", "the baptist"), ("g5207", "of disobedience"),
          ("h3068", "by fire"), ("h3068", "your fathers"), ("h3069", "of horror"), ("h3069", "the lion"),
          ("h3069", "will eat"), ("g1161", "however, slander")}


def moved(items, k):
    """Plants made from real rows: the mark moved onto another word's English in the same verse ("rain" marked for
    בְּ), so a plant reads exactly as a row does and its answer is known (not_said)."""
    out = []
    for x in items:
        if len(out) >= k:
            break
        plain = x["verse"].replace("«", "").replace("»", "")
        mine = x["rendering"].lower()
        for g in re.findall(r'"([A-Za-z]{5,})"', x["context"][1]):
            if g.lower() in mine or mine in g.lower():
                continue
            m = re.search(rf"\b{re.escape(g)}\b", plain)
            if m:
                verse = plain[:m.start()] + "«" + g + "»" + plain[m.end():]
                claim = re.sub(r"«[^»]*»", f"«{g}»", x["claim"], count=1)
                out.append(dict(x, verse=verse, claim=claim))
                break
    return out


def messages(it):
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"id: {it['id']}\nCLAIM: {it['claim']}\n{it['context'][0]}\n"
                                        f"{it['context'][1]}\nVERSE ({it['ref']}): {it['verse']}"}]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build(int(sys.argv[2]) if len(sys.argv) > 2 else WORDS)
    else:
        print(__doc__)
