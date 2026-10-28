"""Show question cards on the site: set "shown" true on the cards named (2026-10-26).

A question card is drafted, read and ruled on while hidden; it goes public only when the owner says so. This turns
that word into one command instead of sixteen hand edits, and rebuilds what is derived from the shown cards.

    python tools/questions_show.py all                 every card in ontology/questions/
    python tools/questions_show.py hell rapture ...    these cards
    python tools/questions_show.py --hide hell         back to hidden

Then: python tools/sitemap.py (the cards and the traditions' pages join the sitemap), commit, and preflight.
The cards are hand-formatted, so only the "shown" line is touched.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / "ontology" / "questions"


def main(args: list[str]) -> int:
    hide = "--hide" in args
    ids = [a for a in args if a != "--hide"]
    if not ids:
        print(__doc__)
        return 1
    cards = sorted(Q.glob("*.json")) if ids == ["all"] else [Q / f"{i}.json" for i in ids]
    missing = [c.stem for c in cards if not c.exists()]
    if missing:
        print("no such card:", ", ".join(missing))
        return 1
    want, was = ("false", "true") if hide else ("true", "false")
    changed = []
    for c in cards:
        text = c.read_text(encoding="utf-8")
        old, new = f'"shown": {was}', f'"shown": {want}'
        if old in text:
            text = text.replace(old, new, 1)
            json.loads(text)
            c.write_text(text, encoding="utf-8", newline="\n")
            changed.append(c.stem)
    print(f"{'hidden' if hide else 'shown'}: {', '.join(changed) or 'none (already so)'}")
    # the traditions' layer is built from the cards; its pages follow what is shown
    subprocess.run([sys.executable, str(ROOT / "tools" / "traditions" / "build.py")], check=True)
    print("next: python tools/sitemap.py, commit, then bash deploy/preflight.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
