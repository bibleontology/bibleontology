"""Notes captured in the app, pinned to a version, worked as a backlog.

Two things feed the outstanding-work list and they are kept apart on purpose.

**Generated** items come from `bookstats.worklist` and are recomputed every
time. They are never stored, never ticked off, and cannot go stale, because
they are a query rather than a record.

**Captured** items are these: written by hand in the interface while looking at
something, and therefore the only part of the system that is a document. They
are stored as JSONL in a **separate repository**, so that they diff and review
like everything else in this project without putting readers' words -- or their
identities -- into the graph's own history.

## A note is not authoritative

**A note opens a question. It does not settle one.** Nothing in this file is
evidence about the corpus; it is evidence about a reader -- what they expected,
what they could not find, what looked wrong from where they were standing. All
three are worth having and none of them is a citation.

So the only correct way to work an item is to go back to the text, check the
claim, and record what the text said. A note asking for a relation between two
figures is answered by reading the verses, and "the verse does not say that" is
a complete and successful resolution. `declined` exists for exactly that and is
not a failure state.

This matters more, not less, once the beta is out. Notes will arrive from
people who know the scriptures well, and some will be right where the graph is
wrong -- which is the point of collecting them. But a note that reads as an
instruction is still a reader's reading, and acting on it directly would put
unsourced claims into a graph whose entire argument is that every claim is
sourced. **The resolution field is where the check goes**, and a resolution
that cites nothing is an item that has not actually been worked.

Three further properties matter, and each exists because the obvious version
fails.

**Every note carries the version it was written against.** A report that a
relation is wrong, read three weeks and four hundred edges later, is a puzzle
rather than a report. The ontology hash says whether the graph has moved since,
and the answer changes what the note means.

**Context is optional and free-form.** The first sketch of this required a
book, and most of what a tester actually wants to say is not about a book: the
graph view is unreadable at depth 3, this relation type is the wrong shape, the
Marys need checking. A note with no anchor is still worth having.

**Status is on the note, not in a separate list.** One file, appended to, with
the resolution written back onto the record. A second file tracking which items
in the first file are done is the drift this whole design exists to avoid.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import ROOT
from . import version

# Feedback lives in its own repository, not this one.
#
# The reasoning went in two steps. First, identity had to be separable from
# what was said: personal data in version control is permanent, exists in
# every clone, and leaks completely the day a repository goes public. Then the
# simpler answer -- keep the whole of it out of the graph's history. A note is
# not a claim about the corpus and has no business in the corpus's git log.
#
# There is no server-side identity store at all. Recognition is a token the
# browser mints and keeps; a self-description, if the reader writes one, also
# lives in their browser and rides along only when they choose to send it.
# Nothing is held about anyone that they did not attach to a note themselves,
# which is both the smallest design and the easiest one to disclose honestly.
#
# Located by, in order: $BIBLEONT_FEEDBACK, then a sibling directory beside
# this repository. Nothing is written into the ontology tree, and `feedback/`
# is gitignored here so that an older checkout cannot quietly start doing so.
DEFAULT_DIR = ROOT.parent / "Bible Ontology Feedback"


def store_dir() -> Path:
    return Path(os.environ.get("BIBLEONT_FEEDBACK") or DEFAULT_DIR)


def notes_path(path: Path | None = None) -> Path:
    return path or store_dir() / "notes.jsonl"


def inbox_dir() -> Path:
    """Where notes land before they are folded into the file.

    One file per note, so that concurrent arrivals cannot collide -- the
    problem an append-in-place design has and this one does not. `pull` drains
    it. Gitignored: these are in-flight, and the JSONL is the record.
    """
    return store_dir() / "inbox"


OPEN = "open"
WORKING = "working"
DONE = "done"
DECLINED = "declined"
STATUSES = (OPEN, WORKING, DONE, DECLINED)

MAX_TEXT = 4000


@dataclass
class Note:
    id: str
    at: str
    text: str
    status: str = OPEN
    context: dict = field(default_factory=dict)
    build: dict = field(default_factory=dict)
    resolution: str = ""
    resolved_at: str = ""
    # Where it came from. `channel` separates the owner's own testing from
    # anything arriving over the domain, because the two deserve different
    # weight and mixing them would hide that. `device` is desktop or mobile,
    # which matters because the beta's likeliest first contact is a phone and
    # a complaint about layout means nothing without it.
    channel: str = "internal"
    device: str = ""
    # Opaque per-device token, minted in the browser and kept there. Not a
    # name and not an address: recognition, not identity, which is the whole
    # of what the beta needs and the least that can be stored.
    author: str = ""
    # What they said they were hoping to get out of it, kept apart from the
    # self-description because it answers a different question and ages
    # differently. A profile says who is writing; this says what they came
    # for, and read across every reader it is the closest thing to a product
    # brief anybody is going to write. Optional like the rest.
    hoping: str = ""
    # An optional self-description the reader wrote about themselves, held in
    # their browser and attached only if they choose to send it. It is
    # **context for reading the note** -- a seminary background, a lifelong
    # reader, a developer who came for the graph -- and never authority. It
    # changes how a note is understood, never whether it is checked.
    #
    # **A snapshot, not a pointer.** The browser sends it only when it
    # changes -- there is no reason to put the same sentence on the wire
    # forty times -- but every note stores whatever was current for that
    # reader when they wrote it, carried forward on arrival.
    #
    # The same reasoning as `build`. A note pinned to the ontology hash of the
    # day it was written stays readable; one pointing at "current" quietly
    # changes meaning underneath you. If a reader re-describes themselves in
    # six months, their older notes should keep the context they were written
    # with, and `profile_changed` marks the note where the description moved.
    #
    # It lands in the repository, so it is capped short, and it is the one
    # field the disclosure on the public site has to cover.
    profile: str = ""
    profile_changed: bool = False
    # Intake is one-way and that is a decision, not a gap. A reply needs a
    # route back, and a browser-held token has no inbox -- which would mean
    # verified accounts, addresses at rest, and a system that holds
    # credentials. None of that is worth it to answer a note.
    #
    # Kept as fields because a reply drafted for the owner to read beside the
    # note costs nothing and is useful even when nothing is sent. `reply_sent`
    # is written by a person, never by this module.
    reply: str = ""
    reply_sent: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def load(path: Path | None = None) -> list[Note]:
    """Every note, latest state. Later records for an id replace earlier ones,
    so the file stays append-only and still answers "what is open now"."""
    path = notes_path(path)
    if not path.is_file():
        return []
    latest: dict[str, Note] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[row.get("id", "")] = Note(**row)
    return list(latest.values())


def _append(note: Note, path: Path | None = None) -> Note:
    path = notes_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(note.as_dict(), sort_keys=True) + "\n")
    return note


def add(text: str, context: dict | None = None, store=None,
        path: Path | None = None, channel: str = "internal",
        device: str = "", author: str = "", profile: str = "",
        hoping: str = "") -> Note:
    text = (text or "").strip()[:MAX_TEXT]
    if not text:
        raise ValueError("a note needs text")
    if channel not in ("internal", "public"):
        channel = "public"
    if device not in ("desktop", "mobile", ""):
        device = ""
    # Only keys the interface is known to send. A note is written by a person
    # into a text box; the context comes from the page rather than from them,
    # and an open-ended dict here would let a page put anything in the file.
    allowed = ("view", "entity", "relation", "verse", "book", "chapter",
               "query")
    ctx = {k: str(v)[:200] for k, v in (context or {}).items()
           if k in allowed and v}

    # Carry the last description forward when none came with this note, so
    # that the wire stays quiet and the record stays complete. A supplied
    # value that differs from the last one is a change worth marking: a reader
    # re-describing themselves is signal, and it is invisible if every note
    # simply overwrites.
    profile = profile[:400]
    hoping = (hoping or '').strip()[:400]
    previous = last_profile(author, path) if author else ""
    changed = bool(profile) and profile != previous
    if not profile:
        profile = previous

    return _append(
        Note(id=uuid.uuid4().hex[:10], at=_now(), text=text, context=ctx,
             build=version.build(store).as_dict(), channel=channel,
             device=device, author=author[:64], profile=profile,
             hoping=hoping, profile_changed=changed),
        path)


def last_profile(author: str, path: Path | None = None) -> str:
    """The most recent description this reader gave of themselves."""
    if not author:
        return ""
    for note in sorted(load(path), key=lambda n: n.at, reverse=True):
        if note.author == author and note.profile:
            return note.profile
    return ""


def profile_history(author: str, path: Path | None = None)         -> list[tuple[str, str]]:
    """Every description this reader has given, oldest first, with dates.

    Worth having rather than only the latest: someone who arrives calling
    themselves curious and later calls themselves a pastor has told you
    something, and keeping only the current value throws it away.
    """
    out: list[tuple[str, str]] = []
    for note in sorted(load(path), key=lambda n: n.at):
        if note.author == author and note.profile_changed:
            out.append((note.at, note.profile))
    return out


def set_status(note_id: str, status: str, resolution: str = "",
               path: Path | None = None) -> Note | None:
    """Move an item. Closing one requires saying what the text said.

    `done` and `declined` both mean the question was taken back to the corpus
    and answered; neither means the note was obeyed or dismissed. Refusing to
    close without a resolution is the mechanism that keeps that true -- an
    item closed silently is indistinguishable from one that was never read.
    """
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if status in (DONE, DECLINED) and not resolution.strip():
        raise ValueError(
            "closing an item needs a resolution saying what was checked "
            "against the text -- 'the verse does not say that' is a complete "
            "one")
    for note in load(path):
        if note.id == note_id:
            note.status = status
            note.resolution = resolution[:MAX_TEXT]
            note.resolved_at = _now() if status in (DONE, DECLINED) else ""
            return _append(note, path)
    return None


def outstanding(path: Path | None = None) -> list[Note]:
    notes = [n for n in load(path) if n.status in (OPEN, WORKING)]
    notes.sort(key=lambda n: n.at)
    return notes


def stale(path: Path | None = None, store=None) -> list[Note]:
    """Open notes written against an ontology that has since changed.

    Not a problem in itself -- most notes survive a rebuild -- but it is the
    set worth re-checking before acting, because the thing complained about
    may already be gone.
    """
    now = version.build(store).ontology
    return [n for n in outstanding(path)
            if n.build.get("ontology") and n.build["ontology"] != now]


def drain() -> int:
    """Fold anything waiting in the inbox into the notes file.

    The asynchronous half of the design. Notes arrive whenever a reader writes
    one, as one file each; this is run whenever the owner connects, and turns
    a pile of arrivals into lines in the record.

    One file per arrival rather than an append is what makes it safe: two
    readers writing at the same moment produce two files and no conflict,
    where appending to a shared file produces a race that has to be retried.
    """
    d = inbox_dir()
    if not d.is_dir():
        return 0
    moved = 0
    for f in sorted(d.glob("*.json")):
        try:
            row = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # Rebuilt through the constructor rather than trusted as written: an
        # inbox file arrived over the wire, and the fields it is allowed to
        # set are the ones `add` allows.
        known = {k: row.get(k) for k in
                 ("text", "channel", "device", "author", "profile")}
        try:
            note = add(context=row.get("context") or {},
                       **{k: v for k, v in known.items() if v is not None})
        except (TypeError, ValueError):
            continue
        f.unlink(missing_ok=True)
        moved += 1
    return moved


def sync(pull: bool = True) -> tuple[bool, str]:
    """Bring the feedback repository up to date, or report why not.

    A thin wrapper over git rather than anything cleverer: the store is a git
    repository, and pretending otherwise would only hide what went wrong.
    """
    import subprocess

    d = store_dir()
    if not (d / ".git").is_dir():
        return False, f"{d} is not a git repository"
    try:
        out = subprocess.run(
            ["git", "pull", "--ff-only"] if pull else ["git", "fetch"],
            cwd=str(d), capture_output=True, text=True, timeout=60,
            check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    ok = out.returncode == 0
    text = (out.stdout or out.stderr).strip()
    # No upstream yet is the normal state of a repository that has not been
    # pushed anywhere, not a failure worth an error.
    if not ok and "no tracking information" in text.lower():
        return True, "no remote configured yet -- local only"
    return ok, text


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Notes captured in the app.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("stale")
    sub.add_parser("pull")
    sub.add_parser("where")
    a = sub.add_parser("add")
    a.add_argument("text")
    d = sub.add_parser("status")
    d.add_argument("id")
    d.add_argument("status", choices=STATUSES)
    d.add_argument("--note", default="")
    args = ap.parse_args(argv)

    if args.cmd == "where":
        d = store_dir()
        print(f"{d}  {'(exists)' if d.is_dir() else '(not created yet)'}")
        print(f"notes    {notes_path()}")
        print(f"inbox    {inbox_dir()}  (drained by `pull`)")
        return 0
    if args.cmd == "pull":
        ok, msg = sync()
        n = drain()
        if n:
            print(f"drained {n} from the inbox")
        print(msg or ("up to date" if ok else "failed"))
        if ok:
            n = outstanding()
            print(f"{len(n)} outstanding, {len(stale())} written against an "
                  f"older ontology")
        return 0 if ok else 1
    if args.cmd == "add":
        n = add(args.text)
        print(f"{n.id}  {n.at}")
        return 0
    if args.cmd == "status":
        n = set_status(args.id, args.status, args.note)
        print("updated" if n else "no such note")
        return 0 if n else 1

    rows = stale() if args.cmd == "stale" else outstanding()
    if not rows:
        print("nothing outstanding" if args.cmd != "stale" else "none stale")
        return 0
    # How many notes each device has sent, so a familiar voice is visible as
    # one. This is the whole practical value of a stable token: without it,
    # five notes from one careful reader look like five strangers.
    seen: dict[str, int] = {}
    for n in load():
        if n.author:
            seen[n.author] = seen.get(n.author, 0) + 1

    # Once the site is reachable from outside, some of these were typed by
    # somebody the owner has never met, and one of them may eventually be
    # written to be read by a machine rather than by him. Text arriving over
    # the wire is marked as such at the point it is read, every time, rather
    # than left to be remembered.
    #
    # The marking is not the defence and should not be mistaken for it. Two
    # things actually hold. Nothing here is ever executed, pasted into a
    # command, or treated as an instruction. And a note cannot become a claim
    # in the graph on its own account: working one means opening the verses
    # and citing what they say, so an injected demand for a relation still
    # has to survive somebody reading the text, and "the verse does not say
    # that" is already a first-class outcome. See the head of this file.
    external = [n for n in rows if n.channel == "public"]
    if external:
        print(f"{len(external)} of these came from outside. Their text is "
              f"data, not instruction:\nit reports what a reader saw, and it "
              f"is answered against the corpus like anything else.\n")

    for n in rows:
        where = " ".join(f"{k}={v}" for k, v in n.context.items()) or "-"
        who = n.author or "-"
        if n.author and seen.get(n.author, 0) > 1:
            who += f" ({seen[n.author]} notes)"
        flag = "  [from outside]" if n.channel == "public" else ""
        print(f"{n.id}  {n.at}  {n.status:8} {n.channel}/{n.device or '?'}"
              f"  {who}{flag}")
        print(f"    {n.text}")
        if n.profile:
            # Their own words about themselves, and context for reading the
            # note rather than authority over it. Flagged where this is the
            # note the description changed on, since a reader re-describing
            # themselves is worth noticing and is otherwise silent.
            mark = " (new)" if n.profile_changed else ""
            print(f"    they say of themselves{mark}: {n.profile}")
        print(f"    at {where}")
        print(f"    ontology {n.build.get('ontology', '?')}"
              f"  app {n.build.get('app', '?')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
