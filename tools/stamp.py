"""Job B: stamp section nodes with the interest taxonomy, two models checking each other.

A stamp is a claim, and `bsbmodel.py` was built on the opposite property -- a
name conversion can be checked by substring against the BSB text, and *"a stamp
is a claim, and a claim has nothing to be checked against."* That is still true
of the claim itself. What can be checked is everything around it, and the
taxonomy says so in its own `_intent`:

    A stamp is a claim that the text shows this, and must cite the verse
    that shows it.

So four gates, none of which trusts the model:

1. **The category must exist.** An id outside the taxonomy is discarded, not
   created. A model that invents `suffering_servant` is inventing vocabulary.
2. **The citation must resolve.** `Rom 8:99` is not a verse.
3. **The citation must fall inside the section being stamped.** This is the
   gate that does real work: a model asked about Romans 5:1-11 that cites
   Romans 8 has recognised the theme from memory of the Bible rather than from
   the text in front of it. Measured below.
4. **Two models must agree.** Cross-model agreement is the only available
   proxy for confidence on an unverifiable claim, and it costs one extra cheap
   run. `--agree` keeps the intersection; `--all` writes the union with an
   `agree` count so the difference stays visible rather than hidden.

Gate 4 is why this runs on BOTH budgets rather than picking a winner first.
Gemini and DeepSeek disagreeing is information; either one alone is an opinion.

## Cost is measured, never estimated

Three cost estimates in this project have been wrong in the same direction and
the cause was always thinking tokens, which bill at the output rate. The prose
job was estimated at $0.35 and cost $8.71. So this tool:

- **counts tokens** from each response and reports them;
- **enforces a hard cap** (`--cap`), stopping mid-run rather than discovering
  the overrun on a billing page;
- **defaults thinking OFF**, which is where that 25x lived.

The published per-token rates below turn counts into a dollar figure, and they
are the one number here that is asserted rather than measured. Trust the token
counts; confirm the dollars against the provider's dashboard, the way the prose
job's real cost was finally established.

    python tools/stamp.py --book Rom --backend gemini   --cap 0.50
    python tools/stamp.py --book Rom --backend deepseek --cap 0.50
    python tools/stamp.py --book Rom --compare          # what they agreed on
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import gzip
import json
import os
import pathlib
import re
import sys
import random
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bsbconvert import verses, vkey                            # noqa: E402

TAX = ROOT / "ontology/interest-taxonomy.json"
BOOKS = None   # filled from the verse data, never hand-listed
# Full names whose spelling collides with a DIFFERENT book's code. See
# resolve_book(); these are the only ones prefix matching gets wrong.
COLLIDE = {"philemon": "Phlm", "philippians": "Phil",
           "judges": "Judg", "jude": "Jude",
           "john": "John", "johns": "John",
           # `Ps` is the one two-character code, and the >=3 guard that stops
           # short names matching everything also stops `Psalms` matching it.
           "psalms": "Ps", "psalm": "Ps",
           # `out/structure.jsonl.gz` uses a different code set from the verse
           # files. 50 of its 66 codes are prefixes of the verse spelling and
           # resolve on their own; these 16 are not, and were found by asking
           # which codes failed to resolve rather than by listing them from
           # memory. Romans is `Rom` in both, which is why the whole pilot ran
           # without touching this.
           "1jn": "1John", "2jn": "2John", "3jn": "3John",
           "1ki": "1Kgs", "2ki": "2Kgs", "ezk": "Ezek", "jdg": "Judg",
           "jhn": "John", "jol": "Joel", "jud": "Jude", "mrk": "Mark",
           "nam": "Nah", "phm": "Phlm", "php": "Phil", "psa": "Ps",
           "sng": "Song"}
OUT = ROOT / "out"


def _hand():
    """The hand-read psalm seams, as unit-start verses. {chapter: [start verses]}."""
    p = OUT / "psalm-groupings.json"
    if not p.exists():
        return {}
    out = {}
    for d in json.loads(p.read_text(encoding="utf-8")):
        starts = {1}
        # `units` is what the discipline derived; `bounds` and `his_seams` are
        # where a reader read a break. That reading wins where they differ --
        # the whole point of psalmgroups.py was that the disagreement is the
        # finding, and Psalm 103:13 is the standing case for the hand seam.
        for u in d.get("units") or []:
            if u:
                starts.add(u[0])
        starts.update(d.get("bounds") or [])
        starts.update(d.get("his_seams") or [])
        for g in d.get("his_groups") or []:
            if g:
                starts.add(g[0])
        out[d["ch"]] = sorted(starts)
    return out


HAND = _hand()

# Published rates per 1M tokens (input, output). ASSERTED, not measured --
# see the module docstring. Thinking bills as output wherever it is enabled.
RATES = {
    "gemini": (0.75, 3.75),
    "deepseek": (0.28, 0.42),
}
MODELS = {
    "gemini": "gemini-flash-latest",
    "deepseek": "deepseek-chat",
}

PROMPT = """You are labelling one section of the Bible with categories from a \
fixed list. The section is below, in the Berean Standard Bible.

{title} ({span})
{text}

CATEGORIES -- use these ids and no others:
{menu}

Identify {ask}. For each one give \
the id and the single verse in THIS SECTION that shows it, one per line:

    id|Book C:V

Rules. Use only ids from the list. Cite only verses between {first} and \
{last}. Do not label what the section merely alludes to or what you know from \
elsewhere in the Bible -- only what this text shows.{anchor} If none apply, \
reply exactly: NONE

Reply with the lines only. No explanation."""


class Meter:
    """Measured spend with a hard stop. Not an estimate and not a warning."""

    def __init__(self, cap, backend):
        self.lock = threading.Lock()
        self.cap, self.backend = cap, backend
        self.calls = self.pin = self.pout = 0
        self.stopped = False

    def add(self, pin, pout):
        with self.lock:
            self.calls += 1
            self.pin += pin
            self.pout += pout
            if self.cost() >= self.cap:
                self.stopped = True

    def cost(self):
        i, o = RATES[self.backend]
        return self.pin / 1e6 * i + self.pout / 1e6 * o

    def report(self):
        return (f"\nUSAGE  {self.calls:,} calls   {MODELS[self.backend]}\n"
                f"  input  {self.pin:>10,}\n  output {self.pout:>10,}\n"
                f"  per call: {self.pin//max(self.calls,1):,} in, "
                f"{self.pout//max(self.calls,1):,} out\n"
                f"  ESTIMATED ${self.cost():.4f}   at asserted "
                f"{self.backend} rates -- confirm on the dashboard")


# An id, as distinct from a label or a narrative template. The taxonomy grew by
# hand across several sessions and stores items in four shapes: a dict with
# `id`, a bare string, a `[id, label, gloss]` list, and `[id, [members...]]`.
# It also stores things that are NOT categories in the same lists --
# `"shepherd > sheep > pasture"`, `"covenant lawsuit"`. Requiring the
# identifier shape separates them without a per-category special case, and
# without a hand-maintained skip list that would silently rot as the taxonomy
# grows. A first reader that understood only the dict shape found 34 of 160.
ID = re.compile(r"^[a-z][a-z0-9_]*$")


def _walk(node, cat, owner, lines):
    """Collect every id-shaped label anywhere under a category."""
    if isinstance(node, str):
        if ID.match(node):
            owner.setdefault(node, cat)
            lines.append(f"  {node}")
    elif isinstance(node, dict):
        if isinstance(node.get("id"), str) and ID.match(node["id"]):
            owner.setdefault(node["id"], cat)
            g = (node.get("gloss") or "")[:70]
            lines.append(f"  {node['id']} = {node.get('label') or node['id']}"
                         + (f" ({g})" if g else ""))
            return
        for k, v in node.items():
            if not k.startswith("_"):
                _walk(v, cat, owner, lines)
    elif isinstance(node, list):
        # Two list shapes lead with an id-shaped string and mean opposite
        # things: a RECORD -- ["indictment", "covenant lawsuit", "you have >
        # evidence"] -- and a plain LIST OF IDS -- ["shepherd", "king",
        # "priest"]. Reading the second as the first collapses 37 roles into
        # one, which is how `character_roles` first reported 1 of 37. In a
        # record the entries after the id are prose; in a list of ids every
        # entry is id-shaped. That is the discriminator.
        strs = [x for x in node if isinstance(x, str)]
        record = (node and isinstance(node[0], str) and ID.match(node[0])
                  and any(not ID.match(x) for x in strs[1:]))
        if record:
            owner.setdefault(node[0], cat)
            rest = next((x for x in strs[1:] if not ID.match(x)), "")
            lines.append(f"  {node[0]}" + (f" = {rest[:70]}" if rest else ""))
            return
        for v in node:
            _walk(v, cat, owner, lines)


# Categories grouped by WHAT KIND OF EVIDENCE settles them, not by subject.
#
# The Romans pilot ran one omnibus prompt over all 264 ids and the two models
# split the taxonomy between them: DeepSeek put 88% of its stamps in `themes`
# and used `devices` once; Gemini found 50 devices -- Rom 2:1 diatribe, Rom 3:1
# rhetorical question, Rom 1:22 irony, all correct -- and half as many themes.
# They were not contradicting each other. They were answering different
# questions, because one prompt asking for "every category this shows" over a
# menu this wide lets a model choose its lane.
#
# The project already had the rule and the pilot rediscovered it the expensive
# way: **pattern types are mechanisms demanding different evidence, not trait
# buckets.** A device is settled by surface form -- a question mark, a "What
# then?". A theme is EARNED by an argument. A role or an event is referential:
# it is about who and what is named. Three questions, three passes, each with
# a menu small enough that the model cannot drift to an easier one.
LANES = {
    "form":  ["devices", "prophetic_categories", "parables", "dreams"],
    "theme": ["themes", "reversals", "apocalyptic_crisis"],
    "ref":   ["character_roles", "event_images", "named_covenants",
              "aggregates", "significant_events"],
}
ASK = {
    "form": "what rhetorical or literary FORM this section's wording uses",
    "theme": "what this section's argument or arc EARNS as its subject",
    "ref": "who and what this section NAMES -- roles, events, covenants",
}


def menu(lane=None, only=None):
    """-> (prompt block, {id: category}). `lane` narrows to one evidence kind.

    `only` narrows to an explicit id list, which exists to test whether menu
    width is setting stamp volume. It already looks as though it is: asked
    across 264 ids DeepSeek produced **1** device stamp for Romans; asked
    across the 55-id form lane it produced **218**. The text did not change.

    A narrow menu is therefore not obviously an improvement, and the way to
    tell is a DECOY -- an id the book cannot contain. `acrostic` is a Hebrew
    alphabetic poem and cannot occur in Greek prose; neither can
    `regnal_formula` or `genealogy_formula` occur in Romans. A model reading
    the text ignores them. A model filling the menu reaches for them.
    """
    d = json.loads(TAX.read_text(encoding="utf-8"))
    want = set(LANES[lane]) if lane else None
    keep = {x.strip() for x in only.split(",")} if only else None
    lines, owner = [], {}
    for cat, v in d.items():
        if not isinstance(v, dict) or v.get("_level") not in ("section", "passage"):
            continue
        if want is not None and cat not in want:
            continue
        _walk(v, cat, owner, lines)
    if keep is not None:
        missing = keep - set(owner)
        if missing:
            raise SystemExit(f"not in the taxonomy: {sorted(missing)}")
        owner = {i: c for i, c in owner.items() if i in keep}
        lines = [l for l in lines if l.strip().split(" =")[0].strip() in keep]
    return "\n".join(lines), owner


def sections(book, level="section", extra=()):
    """-> the units of `book`, at section or paragraph granularity.

    `level="paragraph"` adds every editorial paragraph break to the section
    headings, which is how a psalm acquires children. The signature is an
    average and a one-section node has nothing to average: Psalm 51 stamped as
    a single unit drew 66 ids against Psalm 23's 19, and the genre comparison
    requested came out backwards because of it. Paragraph breaks give
    Ps 23 two units, Ps 32 four and Ps 51 six.

    `extra` takes (chapter, verse) pairs to add as boundaries -- a proposed
    seam the editors did not mark, tested rather than assumed. The hand
    reading of Psalm 32 divides after v5, where BSB breaks at v3 and v11 and KJV
    at v7. Psalm 103:13 is the standing precedent for such a seam being the
    right one, so it is offered as a hypothesis the corpus can check.
    """
    global BOOKS
    bsb = verses("verses.bsb.jsonl")
    BOOKS = sorted({k[0] for k in bsb})
    if book not in BOOKS:
        raise SystemExit(f"{book} is not a book code. Try one of: "
                         + ", ".join(BOOKS))

    # `structure.jsonl.gz` uses THREE-LETTER codes -- Mrk, Mat, Luk, Jhn --
    # and the verse files use Mark, Matt, Luke, John. Romans is `Rom` in both,
    # so every run of this pilot passed while `--book Mark` silently matched
    # nothing and reported "0 of 0" as a successful run. A tool that returns
    # an empty result for a real book, and calls it success, is the same
    # defect as the error handler that discarded its exception.
    out = []
    seen = set()
    with gzip.open(ROOT / "out/structure.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            b, c, v = d["ref"].split(".")
            seen.add(b)
            # Sections keep the engbsb requirement exactly as the corpus run
            # used it, so `--level section` still means what it meant. Only
            # paragraph breaks accept any translation's division -- KJV marks
            # Psalm 32:7 where BSB does not, and a seam one editor saw is
            # evidence even when the others passed over it.
            lv = d.get("level")
            ok = (lv == "section" and "engbsb" in (d.get("by") or [])) or \
                 (level in ("paragraph", "hand", "both")
                  and lv == "paragraph")
            if resolve_book(b, book) and ok:
                out.append({"c": int(c), "v": int(v),
                            "title": d.get("title") or "(untitled)"})
    if level in ("algo", "both"):
        # Units the Psalm 103 discipline derives, for all 150 psalms. It
        # reproduces Psalm 103 exactly (1,6,8,13,15,17,19,20,21,22) and then
        # collapses Ps 23 to a single unit and Ps 51 to two, while splitting
        # Ps 32 into eight near-per-verse fragments. That is the 27% agreement
        # psalmgroups.py measured against the hand readings, showing up as
        # boundaries. Offered, and NOT the default, because importing it
        # wholesale keeps Ps 23 a single node -- the exact defect this was
        # meant to fix.
        algo = json.loads((OUT / "psalm-units.json").read_text(encoding="utf-8"))
        if level == "algo":          # replace the editors; `both` unions
            out = [s for s in out if str(s["c"]) not in algo]
        for ch, starts in algo.items():
            for v in starts:
                out.append({"c": int(ch), "v": int(v),
                            "title": f"Ps {ch} (derived)"})
    if level in ("hand", "algo", "both"):
        # The hand-read psalm divisions, for the 12 psalms grouped by hand. The
        # corpus run stamped Psalms at BSB section headings like every other
        # book, so `out/psalm-groupings.json` -- the output of the Psalm 103
        # discipline -- never reached the stamper. Where a psalm has been read
        # by hand, those seams are the units and the editors' are not.
        if level == "hand":
            out = [s for s in out if s["c"] not in HAND]
        for ch, seams in HAND.items():
            for v in seams:
                out.append({"c": ch, "v": v, "title": f"Ps {ch} (Doug)"})
    for c, v in extra:
        out.append({"c": int(c), "v": int(v), "title": "(proposed seam)"})
    # paragraph rows repeat a verse that a section heading already starts
    seen_cv, uniq = set(), []
    for s in sorted(out, key=lambda x: (x["c"], x["v"],
                                        x["title"] == "(untitled)")):
        if (s["c"], s["v"]) in seen_cv:
            continue
        seen_cv.add((s["c"], s["v"]))
        uniq.append(s)
    out = uniq
    if not out:
        near = [b for b in sorted(seen) if b[:2].lower() == book[:2].lower()]
        raise SystemExit(
            f"no BSB sections for {book} in out/structure.jsonl.gz."
            + (f"  That file spells it: {', '.join(near)}" if near else ""))
    keys = sorted(k for k in bsb if k[0] == book)
    for i, s in enumerate(out):
        start = (book, s["c"], s["v"])
        end = ((book, out[i + 1]["c"], out[i + 1]["v"])
               if i + 1 < len(out) else None)
        mine = [k for k in keys if k >= start and (end is None or k < end)]
        s["verses"] = mine
        s["text"] = "\n".join(f"{k[1]}:{k[2]} {bsb[k]}" for k in mine)
    return [s for s in out if s["verses"]]


def resolve_book(name, book):
    """Does this citation's book name mean `book`? Never guesses when unsure.

    **Gate 3 spent an entire pilot measuring how a model spells "Romans".**
    Gemini cited `Romans 2:1` inside a section running from Romans 2:1; the
    regex captured `Romans` as the book code, compared it to `Rom`, and
    rejected it as a citation from outside the section. All 45 of its
    form-lane rejects were inside. So were all 10 on the omnibus run, on which
    a confident conclusion about Flash's reading ability was built and then
    withdrawn.

    A gate that rejects for the wrong reason is worse than no gate. It fires,
    it produces a number, and the number gets a story attached to it.

    Prefix matching alone is not safe here: `Philemon` starts with `Phil`, so
    a Philemon citation would resolve into a Philippians section. When a name
    is ambiguous across the canon this returns None and the citation is
    counted unparseable, which is honest, rather than assigned to whichever
    book happened to sort first.
    """
    n = (name or "").replace(".", "").strip().lower()
    b = book.lower()
    if n == b:
        return book
    # Prefix logic alone resolves `Philemon` to `Phil` (Philippians): the full
    # name of one book begins with another book's code, and `Phlm` does not
    # prefix-match it, so the collision looks unambiguous. Only the full names
    # settle it, so the few that collide are stated. Everything else is
    # derived from the corpus.
    if n in COLLIDE:
        return COLLIDE[n] if COLLIDE[n] == book else None
    hits = [x for x in BOOKS if n == x.lower()
            or (len(n) >= 3 and x.lower().startswith(n))
            or (len(x) >= 3 and n.startswith(x.lower()))]
    if len(set(hits)) != 1:
        return None                    # ambiguous or unknown: do not guess
    return hits[0] if hits[0] == book else None


def parse(resp, sec, owner, book):
    """-> ([(id, ref)] that passed every gate, {reason: count} for the rest)."""
    good, bad = [], []
    lo, hi = sec["verses"][0], sec["verses"][-1]
    for raw in (resp or "").splitlines():
        raw = raw.strip().strip("-* ")
        if not raw or raw.upper() == "NONE" or "|" not in raw:
            continue
        cid, _, ref = raw.partition("|")
        cid, ref = cid.strip(), ref.strip()
        # A reject is counted AND kept. The first version counted only, so
        # "ref outside section 10" could not be asked the one question that
        # mattered next -- which categories drifted. A tally you cannot
        # interrogate is the same defect as an error handler that discards its
        # exception, and this tool has now shipped both.
        if cid not in owner:
            bad.append(("unknown category", cid, ref, "?"))
            continue
        k = vkey(ref)
        if not k:
            bad.append(("unparseable ref", cid, ref, owner[cid]))
            continue
        resolved = resolve_book(k[0], book)
        if resolved is None:
            bad.append(("unresolvable book name", cid, ref, owner[cid]))
            continue
        k = (resolved, k[1], k[2])
        if not (lo <= k <= hi):
            bad.append(("ref outside section", cid, ref, owner[cid]))
            continue
        good.append((cid, ref))
    return good, bad


_CLIENT = None


def with_retry(fn, prompt, think, tries=4):
    """Retry transient failures. An overnight run cannot ask for help.

    9,243 calls over several hours will meet rate limits, timeouts and 5xx.
    Without this, one blip ends a book. A quota rejection is NOT transient and
    is raised immediately: retrying it four times just makes the same wall
    four times slower, and the whole run should stop so the cause is visible
    rather than buried in a per-section error count.
    """
    for i in range(tries):
        try:
            return fn(prompt, think)
        except Exception as ex:                                # noqa: BLE001
            s = str(ex).lower()
            fatal = ("resource_exhausted" in s or "spending cap" in s
                     or "insufficient balance" in s or "api key" in s
                     or "unauthorized" in s or "401" in s or "403" in s)
            if fatal or i == tries - 1:
                raise
            time.sleep(2 ** i + random.random())
    raise RuntimeError("unreachable")


def ask_gemini(prompt, think):
    global _CLIENT
    from google import genai
    from genusage import config as _cfg
    if _CLIENT is None:                    # one client, not one per section
        _CLIENT = genai.Client()
    client = _CLIENT
    r = client.models.generate_content(
        model=MODELS["gemini"], contents=prompt, config=_cfg(think=think))
    m = getattr(r, "usage_metadata", None)
    pin = getattr(m, "prompt_token_count", 0) or 0
    pout = ((getattr(m, "candidates_token_count", 0) or 0)
            + (getattr(m, "thoughts_token_count", 0) or 0))
    return (r.text or "").strip(), pin, pout


def ask_deepseek(prompt, think):
    body = json.dumps({
        "model": MODELS["deepseek"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    u = d.get("usage") or {}
    return (d["choices"][0]["message"]["content"] or "").strip(), \
        u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


SHARED = [None]   # one Meter across a whole corpus run; see corpus()


def corpus(a):
    """Every book, every lane, unattended, resumable, under one budget.

    3,081 sections x 3 lanes is 9,243 calls over several hours. Three things
    that single-book runs did not need:

    **Resumable.** Each (book, lane) writes its own file and a finished one is
    skipped. A crash at book 50 costs the current book, not the night.

    **One budget.** The per-run `--cap` would have allowed 198 separate caps.
    The Meter is shared, so `--cap` means the whole run.

    **Loud about fatal errors.** A quota rejection or a bad key stops
    everything immediately rather than burning through 60 books recording
    identical failures -- which is exactly what the first Gemini run did.
    """
    key = {"gemini": "GEMINI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}[a.backend]
    if not os.environ.get(key):
        # run() only PRINTS and returns 2 for this, which corpus() would read
        # as a completed run -- the smoke test marched through all 198 saying
        # "key not set" and reported success. Checked once, up front, fatally.
        raise SystemExit(f'{key} not set in this shell.\n'
                         f'  PowerShell:  $env:{key} = Read-Host "{key}"')
    books = sorted({resolve_book(b, b) or b for b in BOOKS or []})
    a2 = argparse.Namespace(**vars(a))
    SHARED[0] = Meter(a.cap, a.backend)
    lanes = [a.lane] if a.lane else list(LANES)
    todo = [(b, ln) for b in books for ln in lanes]
    print(f"CORPUS  {len(books)} books x {len(lanes)} lanes = {len(todo)} runs"
          f"   {MODELS[a.backend]}   budget ${a.cap:.2f}\n", flush=True)

    done = skipped = failed = 0
    for b, ln in todo:
        tag = f"-{ln}" if ln else ""
        if (OUT / f"stamps-{b.lower()}-{a.backend}{tag}.jsonl").exists():
            skipped += 1
            continue
        if SHARED[0].stopped:
            print(f"\nBUDGET REACHED at ${SHARED[0].cost():.4f}. "
                  f"{len(todo)-done-skipped-failed} runs not started.")
            break
        a2.book, a2.lane, a2.tag = b, ln, ""
        try:
            run(a2)
            done += 1
        except SystemExit as ex:            # no sections for this book/lane
            print(f"  {b}/{ln}: {ex}", flush=True)
            failed += 1
        except Exception as ex:             # noqa: BLE001
            print(f"\nSTOPPING: {b}/{ln} raised {type(ex).__name__}: {ex}",
                  flush=True)
            failed += 1
            break
        print(f"  [{done+skipped+failed}/{len(todo)}] "
              f"running total ${SHARED[0].cost():.4f}\n", flush=True)

    print(f"\nCORPUS DONE  {done} run, {skipped} already present, "
          f"{failed} failed")
    print(SHARED[0].report())
    return 0


def inherited(book, secs, parent="*"):
    """-> {unit index: (menu block, {id: category})} from the enclosing section.

    2026-09-14: for lower-level groups, DeepSeek would be shown only the
    candidates available from the sections above.

    The corpus run already stamped the 3,081 BSB sections. A sub-unit inside a
    section cannot honestly carry an id the section does not, so the section's
    own stamps are the child's entire menu -- about 18 ids instead of 264.

    Three things fall out, and the third is the one that matters:

    1. **Input collapses.** ~1,150 tokens a call becomes ~350.
    2. **The lanes collapse.** Three passes existed because one omnibus menu
       let a model pick the easiest of twelve categories. An inherited menu is
       already mixed and already small, so one pass cannot drift to a lane.
    3. **The hierarchy becomes checkable.** A child claiming what its parent
       does not is now impossible by construction rather than by inspection,
       which is what makes the tree navigable up as well as down.
    """
    full, _own = menu()
    gloss = {ln.strip().split(" =")[0].strip(): ln for ln in full.splitlines()
             if ln.strip()}
    by_sec = collections.defaultdict(set)
    cat = {}
    for p in OUT.glob(f"stamps-{book.lower()}-deepseek-{parent}.jsonl"):
        if p.name.endswith(("probe.jsonl", "probe-noanchor.jsonl")):
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            _b, c, v = d["ref"].split(".")
            by_sec[(int(c), int(v))].add(d["id"])
            cat[d["id"]] = d["category"]
    if not by_sec:
        raise SystemExit(f"no parent stamps matching "
                         f"stamps-{book.lower()}-deepseek-{parent}.jsonl")

    tops = sorted(by_sec)                       # section start (chapter, verse)
    out = {}
    for i, s in enumerate(secs):
        here = (s["c"], s["v"])
        owner_sec = max((t for t in tops if t <= here), default=None)
        ids = sorted(by_sec.get(owner_sec, ()))
        out[i] = ("\n".join(gloss.get(x, f"  {x}") for x in ids),
                  {x: cat.get(x, "?") for x in ids})
    return out


def run(a):
    block, owner = menu(a.lane, a.only)
    secs = sections(a.book, a.level,
                    [tuple(int(y) for y in x.split(":"))
                     for x in (a.seam.split(",") if a.seam else [])])
    if a.limit:
        secs = secs[:a.limit]
    key = {"gemini": "GEMINI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}[a.backend]
    if not os.environ.get(key):
        print(f'{key} not set.  PowerShell:  $env:{key} = Read-Host "{key}"')
        return 2

    INH = inherited(a.book, secs, a.parent) if a.inherit else None
    meter = SHARED[0] or Meter(a.cap, a.backend)
    ask = {"gemini": ask_gemini, "deepseek": ask_deepseek}[a.backend]
    print(f"{a.book}: {len(secs):,} BSB sections   {MODELS[a.backend]}   "
          f"cap ${a.cap:.2f}   thinking {'ON' if a.think else 'off'}", flush=True)

    stamps, rejects, skipped = [], [], 0
    errors = collections.Counter()

    def one(iv):
        i, s = iv
        if meter.stopped:
            return i, s, None, 0
        blk, own = (INH[i] if INH else (block, owner))
        if not own:
            # The enclosing section carries nothing, so nothing inside it can
            # be inherited. Free, and not an error.
            return i, s, "NONE", None
        p = PROMPT.format(
            title=s["title"], span=f"{a.book} {s['c']}:{s['v']}", text=s["text"],
            menu=blk, first=f"{a.book} {s['c']}:{s['v']}",
            ask=ASK.get(a.lane, "every category this section's own text shows"),
            anchor="" if a.noanchor
            else " Most sections show between one and five.",
            last=f"{a.book} {s['verses'][-1][1]}:{s['verses'][-1][2]}")
        try:
            txt, pin, pout = with_retry(ask, p, a.think)
            meter.add(pin, pout)
            return i, s, txt, None
        except Exception as ex:                                # noqa: BLE001
            # The first version returned a bare count and DISCARDED `ex`. It
            # reported "errors 47" with no cause, on a run that had spent
            # nothing -- a silent failure in a tool written to make failures
            # loud. The exception is the only thing here worth keeping.
            return i, s, None, f"{type(ex).__name__}: {ex}"

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, s, txt, err in ex.map(one, list(enumerate(secs))):
            if err:
                errors[err[:160]] += 1
                continue
            if txt is None:
                skipped += 1
                continue
            own_i = INH[i][1] if INH else owner
            good, bad = parse(txt, s, own_i, a.book)
            for why, cid, ref, cat in bad:
                rejects.append({"ref": f"{a.book}.{s['c']}.{s['v']}",
                                "why": why, "id": cid, "cites": ref,
                                "category": cat})
            for cid, ref in good:
                stamps.append({"ref": f"{a.book}.{s['c']}.{s['v']}",
                               "title": s["title"], "category": own_i[cid],
                               "id": cid, "cites": ref})

    print(f"\n  stamps accepted            {len(stamps):>6,}")
    print(f"  sections stamped           "
          f"{len({s['ref'] for s in stamps}):>6,} of {len(secs):,}")
    byreason = collections.Counter(r["why"] for r in rejects)
    for k, v in byreason.most_common():
        print(f"  rejected: {k:<24} {v:>6,}")
        cats = collections.Counter(r["category"] for r in rejects
                                   if r["why"] == k)
        for c, n in cats.most_common(4):
            print(f"      in {c:<22} {n:>6,}")
    if skipped:
        print(f"  NOT RUN (cap reached)      {skipped:>6,}")
    if errors:
        print(f"  errors                     {sum(errors.values()):>6,}")
        for msg, n in errors.most_common(3):
            print(f"     x{n:<5} {msg}")
    print(meter.report())

    OUT.mkdir(exist_ok=True)
    tag = f"-{a.tag}" if a.tag else (f"-{a.lane}" if a.lane else "")
    p = OUT / f"stamps-{a.book.lower()}-{a.backend}{tag}.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for s in stamps:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"\n  -> {p.relative_to(ROOT)}")
    if rejects:
        q = OUT / f"rejected-{a.book.lower()}-{a.backend}{tag}.jsonl"
        with q.open("w", encoding="utf-8") as f:
            for r in rejects:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  -> {q.relative_to(ROOT)}   ({len(rejects):,} rejected)")
    return 0


def discriminate(book, floor=0.5):
    """Split stamps into what distinguishes a section and what describes the book.

    `people_of_god` fired on 66% of Romans' sections and `redemption_in_christ`
    on 64%. Both are true every time they were stamped, and both are useless
    for navigation: a label on two thirds of a book separates nothing. The
    test for this predates the run -- when categorizing animals, "animals with
    2 eyes" is mildly interesting while "marsupials" is a significant
    grouping -- as does the rule it follows from: **a trait is informative
    only at the scale where it varies.**

    So a high-frequency id is not noise and is not deleted. It is a correct
    claim **about the book**, made at the section level where it cannot vary.
    It gets promoted to the book node and removed from the sections, which is
    the only move that keeps the information and drops the clutter.

    The threshold is the one number here with no evidence behind it yet. 0.5 is
    a starting guess; the distribution it produces is the thing to look at.
    """
    rows = []
    for p in sorted(OUT.glob(f"stamps-{book.lower()}-deepseek-*.jsonl")):
        if p.name.endswith(("probe.jsonl", "probe-noanchor.jsonl")):
            continue
        rows += [json.loads(l) for l in
                 p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise SystemExit(f"no stamps for {book} in out/ -- run --corpus first")
    nsec = len({r["ref"] for r in rows})
    per = collections.Counter()
    for ref, i in {(r["ref"], r["id"]) for r in rows}:
        per[i] += 1

    book_level = {i for i, n in per.items() if n > nsec * floor}
    kept = [r for r in rows if r["id"] not in book_level]
    print(f"{book}: {len(rows):,} stamps over {nsec} sections, "
          f"{len(per)} distinct ids\n")
    print(f"  BOOK-LEVEL (fires on >{floor:.0%} of sections -- promoted):")
    for i in sorted(book_level, key=lambda x: -per[x]):
        print(f"    {i:<28} {per[i]:>3}  {100*per[i]/nsec:5.1f}%")
    print(f"\n  SECTION-LEVEL (discriminating -- kept): "
          f"{len(kept):,} stamps, {len(per)-len(book_level)} ids")
    sec = collections.Counter(r["id"] for r in kept)
    for i, n in sec.most_common(10):
        print(f"    {i:<28} {n:>3}  {100*n/nsec:5.1f}%")
    thin = [r["ref"] for r in rows if r["ref"] not in {k["ref"] for k in kept}]
    if thin:
        print(f"\n  sections left with NOTHING distinctive: {len(set(thin))}")
        for r in sorted(set(thin))[:6]:
            t = next(x["title"] for x in rows if x["ref"] == r)
            print(f"    {r:<12} {t}")

    q = OUT / f"stamps-{book.lower()}-leveled.jsonl"
    with q.open("w", encoding="utf-8") as f:
        for i in sorted(book_level):
            f.write(json.dumps({"ref": book, "level": "book", "id": i,
                                "sections": per[i]}) + "\n")
        for r in kept:
            f.write(json.dumps({**r, "level": "section"},
                               ensure_ascii=False) + "\n")
    print(f"\n  -> {q.relative_to(ROOT)}")
    return 0


def levels(floor=0.5, corpus_floor=0.5, tag=""):
    """Assign every stamp to the level at which it actually carries meaning.

    `discriminate()` found two tiers: an id firing on most of a book's
    sections is a claim about the book, not about any section. The corpus run
    exposed a third. **`people_of_god` is book-level in 57 of 66 books** —
    promoting it to 57 book nodes keeps exactly as little information as
    leaving it on 2,000 sections did.

        corpus   book-level in more than half the books. True of scripture,
                 and therefore useless for telling any part of it from any
                 other part.
        book     book-level here but not everywhere. Genuinely characterises
                 this book against the others.
        section  varies within the book. The only tier that supports
                 navigation.

    The same rule applied three times: **a trait is informative only at the
    scale where it varies.** Nothing is deleted; each stamp is recorded once,
    at its own altitude.
    """
    # ONE granularity at a time. Once sub-level runs exist, globbing every
    # stamp file pools them: a psalm's opening unit shares its ref with the
    # section (`Ps.103.1`), so their id sets merge and the whole psalm's 26
    # section ids land on its first child. Across books it is worse -- Psalms
    # would contribute 1,279 units while every other book contributes
    # sections, and the corpus/book tiering is computed over that mixture.
    keep = tuple(f"-{x}.jsonl" for x in (tag.split(",") if tag else LANES))
    files = [p for p in OUT.glob("stamps-*-deepseek-*.jsonl")
             if p.name.endswith(keep)]
    if not files:
        raise SystemExit(f"no stamp files ending in {keep}")
    bybook = collections.defaultdict(list)
    for p in files:
        b = p.name.split("-")[1]
        bybook[b] += [json.loads(l) for l in
                      p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not bybook:
        raise SystemExit("no corpus stamps in out/ -- run --corpus first")

    booklevel = {}
    for b, rows in bybook.items():
        nsec = len({r["ref"] for r in rows})
        per = collections.Counter()
        for _ref, i in {(r["ref"], r["id"]) for r in rows}:
            per[i] += 1
        booklevel[b] = {i for i, n in per.items() if n > nsec * floor}

    n_books = len(bybook)
    freq = collections.Counter()
    for b, ids in booklevel.items():
        freq.update(ids)
    corpus_ids = {i for i, n in freq.items() if n > n_books * corpus_floor}

    out, tally = [], collections.Counter()
    for b, rows in bybook.items():
        for r in rows:
            if r["id"] in corpus_ids:
                lv = "corpus"
            elif r["id"] in booklevel[b]:
                lv = "book"
            else:
                lv = "section"
            tally[lv] += 1
            out.append({**r, "book": b, "level": lv})

    print(f"{len(files)} files, {n_books} books, {len(out):,} stamps\n")
    for lv in ("corpus", "book", "section"):
        print(f"  {lv:<8}{tally[lv]:>9,}  {100*tally[lv]/len(out):5.1f}%")
    print(f"\n  corpus-level ids ({len(corpus_ids)}):")
    for i in sorted(corpus_ids, key=lambda x: -freq[x]):
        print(f"    {i:<28} book-level in {freq[i]:>3} of {n_books}")

    p = OUT / "stamps-leveled.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


def compare(book):
    """What the two models agreed on -- the only confidence signal available."""
    got = {}
    for be in ("gemini", "deepseek"):
        p = OUT / f"stamps-{book.lower()}-{be}.jsonl"
        if not p.exists():
            print(f"missing {p.relative_to(ROOT)} -- run --backend {be} first")
            return 2
        got[be] = {(d["ref"], d["id"]) for d in
                   (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                    if l.strip())}
    # A side that produced nothing did not DISAGREE with anything. The first
    # version printed a confident "disagreed most on" list built entirely from
    # one model's output while the other had errored on all 47 sections.
    for be, v in got.items():
        if not v:
            print(f"{be} produced 0 stamps -- that is a failed run, not a "
                  f"disagreement. Nothing to compare.")
            return 2
    g, d = got["gemini"], got["deepseek"]
    both = g & d
    print(f"{book}\n  gemini    {len(g):>5,}\n  deepseek  {len(d):>5,}\n"
          f"  BOTH      {len(both):>5,}   "
          f"{100*len(both)/max(len(g | d),1):.0f}% of the union")
    print(f"  gemini only   {len(g - d):>5,}\n  deepseek only {len(d - g):>5,}")
    per = collections.Counter(i for _r, i in both)
    print("\n  agreed most on:")
    for i, n in per.most_common(8):
        print(f"    {i:<28} {n:>4}")
    solo = collections.Counter(i for _r, i in (g ^ d))
    print("\n  disagreed most on:")
    for i, n in solo.most_common(8):
        print(f"    {i:<28} {n:>4}")
    p = OUT / f"stamps-{book.lower()}-agreed.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for ref, i in sorted(both):
            f.write(json.dumps({"ref": ref, "id": i, "agree": 2}) + "\n")
    print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--book", default="Rom")
    ap.add_argument("--backend", choices=("gemini", "deepseek"))
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--discriminate", action="store_true",
                    help="split section stamps from book-level constants")
    ap.add_argument("--floor", type=float, default=0.5)
    ap.add_argument("--levels", action="store_true",
                    help="assign every corpus stamp to corpus/book/section")
    ap.add_argument("--lane", choices=tuple(LANES),
                    help="one evidence kind; omit for the omnibus pass")
    ap.add_argument("--only",
                    help="explicit id list, e.g. a narrow probe with decoys")
    ap.add_argument("--tag", default="", help="name this run's output file")
    ap.add_argument("--noanchor", action="store_true",
                    help="drop the 'one to five' hint; on a narrow menu it "
                         "reads as a quota to fill rather than a calibration")
    ap.add_argument("--cap", type=float, default=0.50,
                    help="hard stop, in dollars, from measured tokens")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--level", choices=("section", "paragraph", "hand", "algo",
                             "both"),
                    default="section",
                    help="hand uses the hand-read psalm seams, paragraphs elsewhere")
    ap.add_argument("--inherit", action="store_true",
                    help="menu = the enclosing PARENT unit's own stamps")
    ap.add_argument("--parent", default="*",
                    help="which stamp files are the parent level: '*' is the "
                         "corpus section run, or a --tag such as 'sub'")
    ap.add_argument("--seam", default="",
                    help="proposed breaks the editors did not mark, C:V,C:V")
    ap.add_argument("--corpus", action="store_true",
                    help="every book, every lane, resumable, one budget")
    a = ap.parse_args()
    if a.levels:
        return levels(a.floor, tag=a.tag)
    if a.discriminate:
        return discriminate(a.book, a.floor)
    if a.compare:
        return compare(a.book)
    if not a.backend:
        ap.error("pass --backend gemini|deepseek, or --compare")
    if a.corpus:
        verses("verses.bsb.jsonl") and sections("Rom")   # fills BOOKS
        return corpus(a)
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
