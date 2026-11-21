"""One brief per five pairs: is the second record the same thing as the first, recorded twice?"""
import json, sys
from pathlib import Path
pairs = json.load(open(sys.argv[1], encoding="utf-8"))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
HEAD = """You are judging pairs of records from a graph of the Bible. Each pair is two concept cards led by the same Hebrew or
Greek word, with the same or nearly the same English name (often one is the plural of the other). The question for each
pair is narrow: is the second record ONE THING RECORDED TWICE with the first -- the same idea, the word used in the
same sense, so that one card would lose nothing -- or are they two different things that only look alike?

Rules:
- Read the verses. Same sense means the word does the same job in both records' verses (for example "servant" of a
  household in both), not merely the same dictionary word.
- A record built from a single verse can still be the same thing as a larger one, if that verse uses the word in a
  sense the larger one already holds.
- Different senses mean DIFFERENT, even with one Hebrew or Greek word: for example an action against a thing, a group
  of people against a quality they have, a literal sense against a figurative one.
- When the evidence does not settle it, say UNSURE. Doubt keeps two cards.

Return ONLY a JSON array, one object per pair: {"pair": n, "verdict": "same" | "different" | "unsure", "why": "one or two
sentences quoting the verses that decide it"}.
"""
for b in range(0, len(pairs), 5):
    parts = []
    for n, p in enumerate(pairs[b:b + 5], start=b + 1):
        def show(r):
            vs = "\n".join(f"      {v['ref']}: {v['text']}" for v in r["verses"])
            rl = "; ".join(f"{x['type']} {'->' if x['dir'] == 'out' else '<-'} {x['other']} {' '.join(x['refs'])}" for x in r["relations"])
            return (f"    name: {r['name']}" + (f" (also: {', '.join(r['aka'])})" if r['aka'] else "") +
                    f"\n    description: {r['desc']}\n    verses:\n{vs}\n    relations ({r['n_relations']}): {rl or 'none'}")
        parts.append(f"PAIR {n} (word {p['word']})\n  FIRST (kept):\n{show(p['keep'])}\n  SECOND (would be merged in):\n{show(p['merge'])}")
    (out / f"batch-{b // 5:02d}.txt").write_text(HEAD + "\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
print((len(pairs) + 4) // 5, "briefs")
