"""Each theme's public address, made once from its shown name (plan 7.6d).

2026-10-08: transition the theme urls to more standard forms while it is early,
and do the URL change first. The addresses were /theme/<id>: underscores, and ids older than the
names (/theme/law_wisdom for "The Law", /theme/prophetic_word for "Prophets
and Prophecy"). Now /themes/<slug>, lowercase and hyphenated, made from the
name the site shows; every theme's table at /themes/<slug>/side-by-side.

The slugs are written to ontology/themes/theme-addresses.json and then kept:
a theme already listed is never re-slugged, so renaming a theme does not
silently move its address (a moved address needs its own redirect). A theme
not yet listed gets a slug from its name when this runs.

    python tools/themes/theme_addresses.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ontology" / "themes" / "theme-addresses.json"
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402


def slug(name):
    s = re.sub(r"\s*\(.*?\)\s*", " ", name)          # "(Poetic Theology)" off
    s = s.replace("&", " and ").replace("/", " ")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def main():
    tm = S._theme_map()
    names = S._theme_homes().get("names") or {}
    have = json.loads(OUT.read_text(encoding="utf-8"))["addresses"] if OUT.exists() else {}
    for t in tm["themes"]:
        if t["id"] in have:
            continue
        shown = (names.get(t["id"]) or {}).get("name") or S._title(t["title"])
        have[t["id"]] = slug(shown)
    seen = {}
    for tid, s in have.items():
        assert s not in seen, f"two themes at /themes/{s}: {seen[s]} and {tid}"
        seen[s] = tid
    OUT.write_text(json.dumps({
        "_about": "Each theme's public address, /themes/<slug>, made once from its shown name by "
                  "tools/themes/theme_addresses.py and never re-made (plan 7.6d, 2026-10-08). The old "
                  "/theme/<id> addresses answer 301 to these. Changing a slug moves a public address: "
                  "keep the old one redirecting.",
        "addresses": have}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for tid, s in have.items():
        print(f"  /theme/{tid:20} -> /themes/{s}")


if __name__ == "__main__":
    main()
