"""One probe per writing style, run unattended, for inspection in the morning.

2026-09-02, overnight: a run with some diversity, to check in the morning that
all bases are covered.

**Breadth, not depth, and the reason is what is actually unmeasured.** The
pipeline has one mode -- `mode_of` returns "concept" for every book in the
canon, by decision, since the lemma layer removed the reason for a separate
narrative mode. So the open question is not whether it can finish a book. It
is whether one prompt handles a genealogy, an acrostic, a divine speech out of
a whirlwind, a legal argument with rhetorical questions, an antithetical
proverb and an apocalyptic vision. A night spent finishing Genesis would
answer none of that.

Each probe is one or two chapters with its own ceiling, so a book that goes
wrong costs its own budget and nothing else. They run in sequence because the
farm takes a per-book lock; a failure is logged and the next book starts.

## Why these, specifically

    Gen 1-3     foundational narrative, and the only windows with a
                like-for-like predecessor to diff against
    Gen 5       genealogy. A distinct structure, the source of most `father_of`
                edges, and the passage whose dangling `part_of` orphaned 42
                passages from every climb
    Mark 1      gospel, and the Greek half of the lemma layer
    Isa 53      prophecy, and the OT passage the NT quotes most -- the future
                anchor for Hebrew-to-Greek mapping
    Eccl 3      wisdom as a list, where the unit is the pair and not the verse
    Ps 1,23     lyric poetry -- short units, heavy imagery
    Ps 119      the acrostic. 22 stanzas of exactly eight verses, which is the
                case the windowing code exists to not cut
    Job 38      God answering out of the whirlwind. One utterance, and the
                graph previously held 42 separate nodes of it
    Prov 10     antithetical parallelism, which is also the free source of
                contrast anchors the similarity layer needs
    Rom 3       Paul's argument -- transitions, and rhetorical questions that
                must not be read as assertions
    Rev 1       apocalyptic vision, the furthest thing from narrative
    Obad        a whole minor prophet in one chapter, start to finish

Exodus is deliberately absent: it is stopped at 16/118 windows pending the
plague-typing ruling, and starting it unattended would spend the budget on
windows that are about to be re-run under a new rule.

    python tools/overnight.py --reset    # re-run these chapters under the
                                         # current rules (what you want
                                         # after a prompt change)
    python tools/overnight.py            # resume, skipping finished windows
    python tools/overnight.py --dry      # print the plan, change nothing
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (book, chapters or None for all, worker ceiling, supervisor ceiling)
PLAN = [
    ("Gen",   "5",     0.30, 0.10),
    ("Mark",  "1",     0.40, 0.12),
    ("Ps",    "1,23",  0.30, 0.10),
    ("Ps",    "119",   1.20, 0.15),
    ("Job",   "38",    0.35, 0.10),
    ("Prov",  "10",    0.30, 0.10),
    ("Rom",   "3",     0.40, 0.12),
    ("Isa",   "53",    0.30, 0.10),
    ("Eccl",  "3",     0.30, 0.10),
    ("Rev",   "1",     0.35, 0.10),
    ("Obad",  None,    0.30, 0.10),
]

LOG = ROOT / "out" / "overnight.log"


def balance() -> float:
    p = ROOT / "ontology" / "proposals" / ".farm" / ".balance.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("usd", 0.0)
    except Exception:                                            # noqa: BLE001
        return 0.0


def reset(book: str, chapters: str | None) -> str:
    """Clear only the windows this probe will re-run, and keep the rest.

    The farm is incremental: it skips windows it has already done, which is
    correct for resuming and wrong for a rebase. The first overnight run lost
    eight of its ten probes to exactly this -- the books had been extracted in
    English weeks earlier, so each reported "0 windows to do" and produced
    nothing.

    **Chapter-aware, because the probe is.** Job has 107 finished windows and
    $2.00 behind them; clearing the book to re-run chapter 38 would throw all
    of it away and the state file is the only record of what was spent where.
    So only the named chapters are dropped. A probe with no chapters given
    (Obadiah, one chapter) clears the book.

    The prior state is archived beside the file either way, once per day.
    """
    p = ROOT / "ontology" / "proposals" / ".farm" / f"{book.lower()}.json"
    if not p.exists():
        return "no prior state -- runs fresh"
    d = json.loads(p.read_text(encoding="utf-8"))
    done = d.get("done", {})
    if not done:
        return "already empty"
    keep = p.with_suffix(f".json.pre-original-{time.strftime('%Y%m%d')}")
    if not keep.exists():
        keep.write_text(json.dumps(d, indent=1), encoding="utf-8")

    if chapters:
        want = {int(x) for x in chapters.split(",")}
        # Window keys look like "Gen 1:13-24"; the chapter is what precedes
        # the colon in the first reference.
        drop = [k for k in done
                if k.rsplit(" ", 1)[-1].split(":")[0].isdigit()
                and int(k.rsplit(" ", 1)[-1].split(":")[0]) in want]
    else:
        drop = list(done)
    for k in drop:
        done.pop(k, None)
    d["done"] = done
    p.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return (f"cleared {len(drop)} window(s), kept {len(done)}"
            + (f", archive -> {keep.name}" if drop else ""))


def main() -> int:
    dry = "--dry" in sys.argv
    total = sum(w for _, _, w, _ in PLAN)
    have = balance()
    print(f"{len(PLAN)} probes, worker ceilings total ${total:.2f}, "
          f"last known DeepSeek balance ${have:.2f}")
    if total > have:
        print(f"  ceilings exceed the balance by ${total - have:.2f}; the farm "
              f"stops per book at its own ceiling, so the run simply ends "
              f"early rather than failing")
    for book, chs, w, o in PLAN:
        where = f"{book} {chs}" if chs else f"{book} (whole)"
        print(f"  {where:16} worker ${w:.2f}  supervisor ${o:.2f}")
    if "--reset" in sys.argv and not dry:
        print("\nclearing only the windows these probes re-run:")
        for book, chs, _, _ in PLAN:
            where = f"{book} {chs}" if chs else book
            print(f"  {where:16}{reset(book, chs)}")
    elif "--reset" in sys.argv:
        print("\n--dry given, so nothing is cleared. --reset would clear the "
              "windows for the chapters above and keep every other window.")
    elif not dry:
        stale = [b for b in dict.fromkeys(b for b, _, _, _ in PLAN)
                 if (ROOT / "ontology" / "proposals" / ".farm"
                     / f"{b.lower()}.json").exists()]
        if stale:
            print(f"\nNOTE: {len(stale)} of these books already have farm "
                  f"state and will skip finished windows: {', '.join(stale)}")
            print("      pass --reset to re-run them under the current rules.")

    if dry:
        return 0

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n=== overnight {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} ===\n")
        for book, chs, w, o in PLAN:
            cmd = [sys.executable, "-m", "bibleont.farm", book,
                   f"--budget={w:.2f}", f"--opus-budget={o:.2f}"]
            if chs:
                cmd.append(f"--chapter={chs}")
            where = f"{book} {chs}" if chs else book
            print(f"\n--- {where} ---", flush=True)
            log.write(f"\n--- {where} ---\n")
            log.flush()
            try:
                p = subprocess.run(cmd, cwd=ROOT, text=True, timeout=7200,
                                   capture_output=True,
                                   env={**__import__("os").environ,
                                        "PYTHONIOENCODING": "utf-8"})
                # The return code is logged even on success, because its
                # absence is what made the first run unreadable: every probe
                # after Genesis died the moment the parent console closed,
                # producing zero bytes on both streams. Empty output and a
                # clean exit look identical unless the code is written down.
                out = (p.stdout or "") + (p.stderr or "")
                out += f"[exit {p.returncode}, {len(out)} bytes captured]\n"
                if p.returncode != 0 and not (p.stdout or p.stderr):
                    out += ("[died without output -- usually the console was "
                            "torn down under it. Run from a shell that "
                            "outlives the session.]\n")
            except subprocess.TimeoutExpired:
                out = "TIMEOUT after 2h\n"
            except Exception as exc:                             # noqa: BLE001
                out = f"FAILED to launch: {exc}\n"
            print(out[-1200:], flush=True)
            log.write(out)
            log.flush()

    print(f"\ndone. full log: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
