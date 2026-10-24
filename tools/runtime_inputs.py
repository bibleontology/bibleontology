"""THE SERVER'S RUNTIME INPUTS, AS A NAMED SET (plan 8.3b; the committee of
2026-10-21, item 3: "the server's runtime inputs published as a named set,
after the KJV scan").

The public repository carries the built files the site reads, so a clone can
run the site without the private pipeline that made some of them. Which files
those are is measured, not listed by hand: this starts the server with an
audit hook on every file it opens, lets it load, asks it every API route and
the page routes, and writes each repository file it read to
deploy/runtime-inputs.txt. tools/export_public.py publishes that list (tracked
files only, and only after its scans), and the exported tree's own check
starts the server there, so a file this missed fails the cut rather than the
first person to clone it.

    python tools/runtime_inputs.py            (a few minutes: the server loads)
"""
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "deploy" / "runtime-inputs.txt"
PORT = 8791
opened: set[str] = set()


def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        try:
            p = Path(os.fsdecode(args[0])).resolve()
        except (OSError, ValueError):
            return
        if p.is_relative_to(ROOT):
            opened.add(p.relative_to(ROOT).as_posix())


def routes(server) -> list[str]:
    q = urllib.parse.urlencode({"ref": "Gen 1:1", "id": "david", "book": "Gen", "c": "1", "chapter": "1",
                                "q": "love", "lemma": "H157", "theme": "faith", "v": "1"})
    out = [f"{r}?{q}" for r in sorted(server.ROUTES)]
    out += ["/", "/healthz", "/llms.txt", "/e/david", "/e/love", "/word/H157", "/themes/", "/explore/",
            "/passage?ref=Ps%2023", "/ns/meaning", "/ns/structure", "/ns/relation", "/ns/claim", "/ns/shapes",
            "/ns/map", "/ns/alignment", "/Gen/1/1"]
    return out


def main():
    sys.path.insert(0, str(ROOT / "app2"))
    os.chdir(ROOT)
    scratch = ROOT / "out" / ".runtime-inputs-scratch"
    os.environ["BIBLEONT_FEEDBACK"] = str(scratch)     # never the real feedback folder
    sys.addaudithook(hook)
    sys.argv = ["server.py", "--port", str(PORT)]
    import server  # noqa: E402
    threading.Thread(target=server.main, daemon=True).start()
    for _ in range(900):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=5).read()
            break
        except OSError:
            time.sleep(1)
    else:
        sys.exit("the server never answered /healthz")
    bad = 0
    for r in routes(server):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}{r}", timeout=120).read()
        except urllib.error.HTTPError:
            bad += 1                         # a 400/404 still read what it reads
        except OSError as ex:
            print(f"  {r}: {ex}")
    time.sleep(10)                           # the background warm-ups
    # what the public copy never carries is left off the list too (the KJV
    # verse file, which the server reads only if present; the practitioner,
    # 2026-10-22: a listed file the copy lacks puzzles a reader)
    sys.path.insert(0, str(ROOT / "tools"))
    import export_public as E  # noqa: E402
    keep = sorted(f for f in opened
                  if not f.endswith((".py", ".pyc")) and "__pycache__" not in f
                  and not f.startswith(("out/.runtime-inputs-scratch", ".git/"))
                  and not E.matches(f, E.NEVER))
    LIST.write_text("# The repository files app2/server.py reads at run time, measured by\n"
                    "# tools/runtime_inputs.py. Do not edit by hand: re-run it.\n"
                    + "\n".join(keep) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(keep)} files the server read -> {LIST.relative_to(ROOT)} ({bad} routes answered 4xx)",
          flush=True)                        # os._exit skips the buffer's flush
    os._exit(0)


if __name__ == "__main__":
    main()
