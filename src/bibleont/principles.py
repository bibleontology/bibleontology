"""`docs/PRINCIPLES.md`, parsed, so the same text can be shown in three places.

2026-09-01, on Deuteronomy 6:9: that verse says to put the law everywhere,
which is what is done with the principles -- prominent on the about page, in
the caches, and so on.

Three surfaces need them and they need different amounts of them:

    the file            all of it -- statement, evidence, falsifier
    the About view      title and statement, with a link to the file
    the worker prefix   the marked subset, and nothing else

The obvious way to do that is to write the short forms out twice. **That is
the mistake this module exists to avoid**, and the project has already paid for
it once: a corrected alias written straight to the merged output was reverted
by the next merge, because a pipeline rebuilds its output and discards anything
authored there. Copies of a principle behave the same way -- the file gets
edited, the copies do not, and nothing reports it, because a stale copy is
consistent with itself.

So the file is the source and both other surfaces are rendered from it. The
cost is this parser and one test; the return is that a principle cannot be
true in one place and stale in another.

## What the format has to guarantee

Only three things, all of which the file already does naturally:

    ### <n>. <title>          a principle starts here
    <first paragraph>         the statement, if there is one
    `Carried by the worker.`  it goes in the extraction prompt

Everything else in a principle -- the evidence, the falsifier, an AMENDED
block -- is for a person reading the file, and is not rendered anywhere else.

`## <n>. <name>` opens a section. A principle keeps its section, which is why
the numbers run through the file rather than restarting: the list grows in the
middle, and a new rule about grouping is filed with the other rules about
grouping rather than appended at the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .paths import ROOT

PATH = ROOT / "docs" / "PRINCIPLES.md"

_SECTION = re.compile(r"^## ([IVX]+)\. (.+)$")
_PRINCIPLE = re.compile(r"^### (\d+)\. (.+)$")
_MARK = "`Carried by the worker.`"

# A paragraph that is annotation rather than statement. The file writes these
# in a fixed form -- *Evidence.* and *Falsifier.* -- and an amendment is a
# blockquote. None of them is the rule; they are why it is believed.
#
# `---` is in the list because it is a section rule and the first thing after
# the last principle of a section. Without it, "Antithesis is invisible to
# every measure here" was rendered with the statement "---": the principle
# says the whole rule in its title, its only paragraphs are evidence and a
# falsifier, and the scan ran off the end of it into the page furniture.
_ASIDE = re.compile(r"^\s*(>|\*(Evidence|Falsifier)|\||-{3,}$)")


@dataclass
class Principle:
    number: int
    title: str
    section: str            # "III"
    section_title: str      # "Language"
    statement: str          # first ordinary paragraph, or "" -- see below
    worker: bool = False
    body: list[str] = field(default_factory=list)

    @property
    def short(self) -> str:
        """Title plus statement, for a place with room for two lines.

        A statement is genuinely optional and its absence is not a defect:
        "Nothing leaves the graph silently" and "Always split" say the whole
        rule in the heading, and a sentence restating them would be padding.
        """
        return f"{self.title}. {self.statement}" if self.statement else self.title


def _paragraphs(lines: list[str]) -> list[str]:
    out, cur = [], []
    for line in lines:
        if line.strip():
            cur.append(line.strip())
        elif cur:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


@lru_cache(maxsize=1)
def load() -> list[Principle]:
    text = PATH.read_text(encoding="utf-8")
    section = section_title = ""
    items: list[Principle] = []
    for line in text.splitlines():
        if m := _SECTION.match(line):
            section, section_title = m.group(1), m.group(2)
            continue
        if m := _PRINCIPLE.match(line):
            items.append(Principle(number=int(m.group(1)), title=m.group(2),
                                   section=section, section_title=section_title,
                                   statement=""))
            continue
        if items:
            items[-1].body.append(line)

    for p in items:
        p.worker = any(ln.strip() == _MARK for ln in p.body)
        for para in _paragraphs([ln for ln in p.body if ln.strip() != _MARK]):
            if not _ASIDE.match(para):
                p.statement = para
                break
    return items


def worker() -> list[Principle]:
    """The subset an extraction worker can act on inside one window."""
    return [p for p in load() if p.worker]


def head(width: int = 76) -> str:
    """The block that opens every worker prompt.

    Deliberately short and deliberately first. The rules below it in the
    prompt carry the worked examples, which is where the teaching happens --
    this is the index, so that a rule the worker is about to break has been
    named on the way in.
    """
    import textwrap

    out = [
        "THE PRINCIPLES THIS GRAPH IS BUILT ON",
        "",
        "Read these first. Everything after them is one of these worked out in",
        "detail, with the cases where it was got wrong.",
        "",
    ]
    items = worker()
    pad = " " * (len(str(len(items))) + 2)          # hangs under the text, not the number
    for i, p in enumerate(items, 1):
        body = f"{i}. {p.title}."
        if p.statement:
            body += f" {p.statement}"
        out += textwrap.wrap(body, width=width, subsequent_indent=pad)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--head" in argv:
        print(head())
        return 0
    sec = ""
    for p in load():
        if p.section != sec:
            sec = p.section
            print(f"\n{p.section}. {p.section_title.upper()}")
        mark = "W" if p.worker else " "
        print(f"  {mark} {p.number:>2}. {p.title}")
    n = len(worker())
    print(f"\n{len(load())} principles, {n} carried by the worker (W)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
