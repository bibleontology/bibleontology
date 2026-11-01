"""IndexNow in small groups (pilot task 1, 2026-10-31). Bing Webmaster Tools: "IndexNow is in batch mode ... URLs are
submitted individually or in smaller groups as changes occur". tools/indexnow.py gains --batch-size N and --pause S.
No network: key(), live_ok() and send() are replaced; the sent record is a scratch file removed afterwards.

    python -X utf8 tests/test_indexnow_stream.py
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("indexnow", ROOT / "tools" / "indexnow.py")
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)

fails = []
SCRATCH = ROOT / "out" / "_test_indexnow_sent.json"


def run(argv, statuses=None):
    """main() with argv; returns (batch sizes sent, sleeps, recorded addresses, exit code or None)."""
    calls, sleeps = [], []
    statuses = list(statuses or [])
    I.key = lambda: "k"
    I.live_ok = lambda k: (True, "test")
    I.send = lambda k, urls: (calls.append(len(urls)), statuses.pop(0) if statuses else 200)[1]
    I.time.sleep = lambda s: sleeps.append(s)
    I.SENT = SCRATCH
    if SCRATCH.exists():
        SCRATCH.unlink()
    sys.argv = ["indexnow.py"] + argv
    code = None
    try:
        I.main()
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    rec = json.loads(SCRATCH.read_text(encoding="utf-8")) if SCRATCH.exists() else {}
    return calls, sleeps, rec, code


URLS = ["https://%s/p/Gen.1.%d" % (I.HOST, n) for n in range(1, 251)]

try:
    calls, sleeps, rec, code = run(["--urls", *URLS, "--batch-size", "100", "--pause", "0"])
    if calls != [100, 100, 50]:
        fails.append("--batch-size 100 sends %s, not [100, 100, 50]" % calls)
    if len(rec) != 250:
        fails.append("--batch-size 100 records %d addresses, not 250" % len(rec))

    calls, sleeps, rec, code = run(["--urls", *URLS])
    if calls != [250]:
        fails.append("without --batch-size the whole list goes in one call (as before); got %s" % calls)
    if sleeps:
        fails.append("without --pause nothing sleeps; slept %s" % sleeps)

    calls, sleeps, rec, code = run(["--urls", *URLS, "--batch-size", "100", "--pause", "2"])
    if sleeps != [2, 2]:
        fails.append("--pause 2 sleeps between batches only (expected [2, 2]); got %s" % sleeps)

    calls, sleeps, rec, code = run(["--urls", *URLS, "--batch-size", "100"], statuses=[200, 429])
    if calls != [100, 100]:
        fails.append("a 429 on batch 2 stops there; sent %s" % calls)
    if len(rec) != 100 or code in (None, 0):
        fails.append("after a 429 only batch 1 is recorded and the exit is non-zero; recorded %d, exit %s"
                     % (len(rec), code))

    for bad in ("0", "-5"):
        calls, sleeps, rec, code = run(["--urls", *URLS, "--batch-size", bad])
        if code in (None, 0) or calls:
            fails.append("--batch-size %s must be refused before sending; exit %s, sent %s" % (bad, code, calls))

    calls, sleeps, rec, code = run(["--urls", *URLS, "--batch-size", "100", "--dry-run"])
    if calls:
        fails.append("--dry-run sends nothing; sent %s" % calls)
finally:
    if SCRATCH.exists():
        SCRATCH.unlink()

for f in fails:
    print("FAIL", f)
print("indexnow stream: %d checks, %d failures" % (7, len(fails)))
sys.exit(1 if fails else 0)
