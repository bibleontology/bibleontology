"""Personal preview links, for a beta that is shared rather than published.

The graph goes on the open web before it is finished, to a handful of people
who were asked whether they wanted it. That is a different thing from
publishing, and the difference is worth building rather than assuming: a
stranger who finds the URL should get a closed door, and the people invited
should never see one.

## Why an invitation and not a registration

A registration is self-service, so anyone who finds the address can complete
it, which gates nothing unless every signup is also approved by hand. It
obliges the site to hold identity data, which is exactly what `feedback` was
designed to avoid holding. And it drags in passwords or mailed links, meaning
credential storage and mail infrastructure, for a beta with five readers.

An invitation is a line in a file. No form, no password, no address, and
revoking someone is deleting the line.

## What this is and is not

**It is not security against someone who wants in.** A token in a link can be
forwarded, screenshotted, or read out of a browser's history, and a forwarded
link works. It stops crawlers, search indexing and the passer-by, which is the
whole of the actual threat model here, and it should never be described as
more than that.

**It is not a login.** Nobody is authenticated; a token says only that whoever
holds it was given it. That is enough to decide whether to serve the page and
enough to label a note, and it is deliberately not enough to authorise
anything else.

## How it behaves

The link carries the token once. On the first visit it is exchanged for a
cookie and the reader is redirected to the clean address, so the token stops
riding in the address bar, in browser history, and in any referrer the page
later sends. The cookie is long-lived because friction is the thing this is
supposed to avoid: opening the original text message again is the recovery
path, and it should almost never be needed.

The same token works on every device the reader owns. It identifies a person,
not a browser -- she reads on a phone and then opens the graph on a laptop
with the same link, which is what makes the phone-and-desktop split usable.

## Off by default

No invite file means no gate, so a local checkout runs open the way it always
has. The gate exists when there is a list to check against, which is also the
only state in which anyone could be locked out by it.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .paths import ROOT

# Beside the feedback store and outside the repository, for the same reason:
# an invite list in git history is a secret in git history, and history is
# forever. `feedback/` is already gitignored here; this never lands in the
# tree at all.
DEFAULT_DIR = ROOT.parent / "Bible Ontology Feedback"

COOKIE = "bo_preview"


def store_dir() -> Path:
    return Path(os.environ.get("BIBLEONT_INVITES")
                or os.environ.get("BIBLEONT_FEEDBACK")
                or DEFAULT_DIR)


def invites_path(path: Path | None = None) -> Path:
    return path or store_dir() / "invites.jsonl"


@dataclass
class Invite:
    token: str
    label: str
    issued: str
    revoked: bool = False
    note: str = ""

    def as_dict(self) -> dict:
        return {"token": self.token, "label": self.label,
                "issued": self.issued, "revoked": self.revoked,
                "note": self.note}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path | None = None) -> list[Invite]:
    path = invites_path(path)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        out.append(Invite(token=row["token"], label=row.get("label", ""),
                          issued=row.get("issued", ""),
                          revoked=bool(row.get("revoked")),
                          note=row.get("note", "")))
    return out


def enabled(path: Path | None = None) -> bool:
    """Whether a gate exists at all. No file means an open site.

    Keyed on the file existing rather than on it holding anyone, and the
    difference matters in one direction only: revoking every invite must
    close the site, not open it. A gate that swings wide when the guest list
    empties is worse than no gate, because it fails open at exactly the moment
    someone has decided nobody should be let in.

    The cost is a way to lock yourself out -- a file with no active invite
    refuses everyone, including whoever wrote it. That is the correct
    behaviour and a bad surprise, so `invites list` says so plainly, and the
    way back is to mint one or move the file aside. Deleting the file is what
    makes a checkout open again; that is the switch.
    """
    return invites_path(path).is_file()


def check(token: str, path: Path | None = None) -> Invite | None:
    """The invite a token belongs to, or None.

    Compared with `compare_digest` rather than `==`. The timing signal from a
    plain comparison is small and awkward to exploit over a network, and
    writing the careful version costs nothing, so there is no reason to be the
    person who left the easy one in.
    """
    # compare_digest raises on a non-ASCII str, so "?k=%C3%A9" dropped the
    # connection and left a traceback in the journal (security review,
    # 2026-10-01); a token is never anything but URL-safe ASCII
    if not token or not token.isascii():
        return None
    for inv in load(path):
        if inv.revoked:
            continue
        if hmac.compare_digest(inv.token, token):
            return inv
    return None


def mint(label: str, note: str = "", path: Path | None = None) -> Invite:
    """Issue a new personal link."""
    path = invites_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    inv = Invite(token=secrets.token_urlsafe(24), label=label.strip(),
                 issued=_now(), note=note)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(inv.as_dict(), sort_keys=True) + "\n")
    return inv


def revoke(label_or_token: str, path: Path | None = None) -> int:
    """Retire every invite matching a label or a token. Returns how many."""
    path = invites_path(path)
    rows = load(path)
    hit = 0
    for inv in rows:
        if not inv.revoked and label_or_token in (inv.label, inv.token):
            inv.revoked = True
            hit += 1
    if hit:
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for inv in rows:
                f.write(json.dumps(inv.as_dict(), sort_keys=True) + "\n")
    return hit


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="mint a personal link")
    a.add_argument("label", help="who it is for, shown to them on arrival")
    a.add_argument("--note", default="", help="a reminder to yourself")
    a.add_argument("--base", default="https://bibleontology.org",
                   help="site address, for printing the link")

    sub.add_parser("list", help="show every invite")

    r = sub.add_parser("revoke", help="retire an invite by label or token")
    r.add_argument("label_or_token")

    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if args.cmd == "add":
        inv = mint(args.label, args.note)
        print(f"{inv.label}:\n  {args.base}/?k={inv.token}")
        print(f"\nwritten to {invites_path()}")
        print("Send it as a personal link. It works on every device they own,\n"
              "and opening it again is how they get back in if they clear\n"
              "their cookies.")
        return 0

    if args.cmd == "revoke":
        n = revoke(args.label_or_token)
        print(f"retired {n} invite(s)")
        return 0 if n else 1

    rows = load()
    if not rows:
        print(f"no invites at {invites_path()}")
        print("The site is OPEN: with no list there is nothing to check.")
        return 0
    for inv in rows:
        state = "revoked" if inv.revoked else "active "
        print(f"  {state}  {inv.label:20}{inv.issued:22}{inv.note}")
    print(f"\n{invites_path()}")
    if not any(not inv.revoked for inv in rows):
        print("\nNOBODY CAN GET IN, INCLUDING YOU. The file exists, so the "
              "gate is on;\nevery invite in it is revoked, so nothing opens "
              "it. Mint one, or move\nthe file aside to run open again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
