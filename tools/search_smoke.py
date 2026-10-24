"""Search smoke sweep (plan A.24, P-89 approved 2026-10-02).

On 2026-10-02 "heaven", "seed", "vine", "waters", "flood" and "Judah" all
answered 400 for most of a day: a shadowed variable inside search, which
the server then reported as the reader's mistake. No suite ran search.

This loads the app in-process and puts a fixed sample through the search
route exactly as a request would go (answer(): the route, the JSON, the
credit scrub): the commonest words of the Berean, a seeded sample of card
names, the six words that broke, and the inputs a bug hunter types. Any
exception, or an answer that is not JSON with a results list, fails.

    python tools/search_smoke.py            # exit 1 on any failure
"""
import collections
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.argv = [sys.argv[0]]                      # the server reads its own flags
import server as S  # noqa: E402

WORDS = 300          # commonest Berean words
NAMES = 300          # card names, seeded sample
BROKE = ["heaven", "seed", "vine", "waters", "flood", "Judah"]
HUNTER = ["", "   ", "asdfghjk", "12345", "@@@###", "Rah", "Mosez", "<script>alert(1)</script>",
          "' OR 1=1 --", "🙏", "אברהם", "Ἀβραάμ", "Zoë", "Gen 99:99", "John 3:99", "Rev 23",
          "Genesis 1:1-3", "Gen1:1", "mat 5:3", "1 Jn 4:8", "%", "\\", "a\u0000b", "x" * 900]


def sample():
    c = collections.Counter()
    for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if "t" in d:
            c.update(w.lower() for w in re.findall(r"[A-Za-z]+", d["t"]))
    names = sorted({json.loads(l)["name"] for l in
                    (ROOT / "ontology" / "entities" / "entities.jsonl").open(encoding="utf-8")})
    rng = random.Random(20261002)
    return list(dict.fromkeys(BROKE + HUNTER + [w for w, _ in c.most_common(WORDS)]
                              + rng.sample(names, min(NAMES, len(names)))))


def main():
    t0 = time.time()
    S.load()
    loaded = time.time() - t0
    qs, bad = sample(), []
    for q in qs:
        try:
            body = json.loads(S.answer("/api/search", urlencode({"q": q})))
            if not isinstance(body.get("results"), list):
                bad.append((q, "no results list"))
        except Exception as e:                      # noqa: BLE001 -- the point is to catch all
            bad.append((q, f"{type(e).__name__}: {e}"[:120]))
    took = time.time() - t0 - loaded
    print(f"{len(qs)} searches in {took:.0f}s (load {loaded:.0f}s); {len(bad)} failed")
    for q, why in bad[:20]:
        print(f"  {q[:40]!r}: {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
