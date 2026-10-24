"""THE SWEEP'S ANSWER PER VERSE: Haiku where its two blind runs agreed,
Sonnet where they did not (plan 1.34).

    python tools/sweep/combine.py <haiku a> <sonnet dir> <out dir>

A verse with no disagreement and nothing left undecided takes run A as it
stands. An escalated verse takes Sonnet's whole answer, which was asked to
decide the disputed points and answer the rest of the verse as well.
"""
import json
import shutil
import sys
from pathlib import Path


def main():
    a, s, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    esc = json.loads((a / "escalate.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    n_s = n_h = missing = 0
    for p in sorted(a.glob("*.json")):
        if p.name.startswith(("score", "escalate", "_")):
            continue
        ref = p.stem
        if ref in esc:
            sp = s / p.name
            if sp.exists():
                shutil.copy(sp, out / p.name)
                n_s += 1
            else:
                missing += 1
        else:
            shutil.copy(p, out / p.name)
            n_h += 1
    print(f"{n_h} verses from Haiku (agreed), {n_s} from Sonnet (escalated), {missing} escalations missing -> {out}")


if __name__ == "__main__":
    main()
