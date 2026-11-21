"""Every sitemap page, built with the code about to be pushed, for Caddy to serve while the app restarts (plan A.49,
step 2; 2026-11-12).

Each push restarts the app, and for about two minutes Caddy could only answer "back in a moment" (503): crawlers among
the 133 requests of one push. This builds every page the sitemap lists, through the server's own request handler in
process, so each file is byte for byte what the live server would send: no second copy of the routing to drift.

    python tools/build_pages.py --sample 200          time 200 pages, write nothing
    python tools/build_pages.py                       build all, in parallel, beside preflight
    python tools/build_pages.py --workers 6           fewer processes (each loads the graph, about 2 GB)
    python tools/build_pages.py --with-unlisted       the sitemap's pages and every verse and word page beyond it

Writes out/pages/:
  site/<path>.html        one file per page ("/" is site/index.html; "/e/david" is site/e/david.html)
  assets/app-<hash>.js    the app's shell, this version's (step 1)
  assets/app-<hash>.css
  manifest.json           {path: sha256 of the page} for every page built, and the shell's two names
  changed.json            the paths whose page differs from the last upload's manifest (uploaded.json)
  report.json             counts, failures (a sitemap page not answered 200), seconds

The upload (step 3) sends changed pages and every version's shell; uploaded.json is the manifest as last uploaded.
Run beside preflight: it reads only the working tree and writes only out/pages/.
"""
import argparse
import hashlib
import io
import json
import multiprocessing as mp
import os
import re
import sys
import time
from email.message import Message
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "pages"
WWW = ROOT / "deploy" / "www"
SITE = "https://bibleontology.org"


def sitemap_paths():
    """Every page path the sitemaps list, in order, without the site's address."""
    paths = []
    for f in sorted(WWW.glob("sitemap-*.xml")):
        for loc in re.findall(r"<loc>([^<]+)</loc>", f.read_text(encoding="utf-8")):
            if loc.startswith(SITE):
                paths.append(loc[len(SITE):] or "/")
    return list(dict.fromkeys(paths))


# the file names and the policy <meta> are the live app's own (app2/page_copies.py), so a built copy and a copy the
# app refreshes as it serves are the same file, named the same way
sys.path.insert(0, str(ROOT / "app2"))
from page_copies import file_for, with_policy  # noqa: E402,F401


_S = None


def _server():
    global _S
    if _S is None:
        sys.path.insert(0, str(ROOT / "app2"))
        import server as S  # noqa: E402
        S.DEV = False                                   # the public site's behaviour, whatever argv says
        S.load()
        _S = S
    return _S


def render(path):
    """(status, body bytes, content type) as the server's own handler answers GET <path> for a crawler."""
    S = _server()
    h = S.Handler.__new__(S.Handler)
    h.path, h.command, h.request_version = path, "GET", "HTTP/1.1"
    h.client_address = ("127.0.0.1", 0)
    msg = Message()
    for k, v in (("Host", "bibleontology.org"), ("User-Agent", "BibleOntology-build/1.0"),
                 ("Accept", "text/html"), ("X-Forwarded-Proto", "https")):
        msg[k] = v
    h.headers = msg
    got = {}

    def send(code, body, ctype, headers=None):
        got.update(code=code, body=body, ctype=ctype)
        h._status = code

    h._send = send
    h._gate = lambda u: True                            # the build sees the public site, no invite involved
    h._status = 0
    # where a real request enters: do_GET answers /mcp, /privacy, /terms and /ns/* itself, before _get (the first
    # full build, 2026-11-12, called _get and got those ten pages as 404s)
    h.do_GET()
    return got.get("code"), got.get("body") or b"", got.get("ctype") or ""


def _work(args):
    paths, out_dir = args
    out_dir = Path(out_dir)
    done, fails, t0 = {}, [], time.time()
    for p in paths:
        try:
            code, body, ctype = render(p)
        except Exception as e:                          # noqa: BLE001 -- reported, never fatal to the build
            fails.append([p, f"error: {type(e).__name__}: {e}"[:200]])
            continue
        if code != 200 or not ctype.startswith("text/html"):
            fails.append([p, f"{code} {ctype}"])
            continue
        # the page's content-security policy travels inside it, since Caddy serving the copy cannot know it: the
        # server's own policy for this page, as a <meta>, without frame-ancestors (a <meta> cannot carry it; Caddy's
        # copy is never framed anyway). The one byte-for-byte difference from what the app sends.
        body = with_policy(body, _server().csp_for(body))
        f = out_dir / "site" / file_for(p)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, f)
        # the fingerprint ignores the shell's file names (/app-<hash>.js, .css): every page names them, so a new shell
        # made every page look changed (2026-11-15: 42,065 of 42,065), hiding which pages' content really changed
        done[p] = hashlib.sha256(re.sub(rb"/app-[0-9a-f]{12}\.(js|css)", rb"/app-SHELL.\1", body)).hexdigest()
    return done, fails, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="time this many pages, spread over the sitemap; write nothing")
    ap.add_argument("--workers", type=int, default=max(1, min(10, (os.cpu_count() or 4) - 2)))
    ap.add_argument("--paths", nargs="+", help="build only these pages, merged into the last build's manifest")
    # P-2026-11-15-2: the verse and word pages the sitemap leaves out keep copies too; this builds them beside the
    # sitemap's, so the manifest holds both and nothing listed is marked removed
    ap.add_argument("--with-unlisted", action="store_true", help="also every verse and word page beyond the sitemap")
    a = ap.parse_args()
    if a.paths:
        return build_some(a.paths)
    paths = sitemap_paths()
    if a.with_unlisted:
        listed = set(paths)
        paths += sorted(p for p in _server().every_page_paths(_server()._data) if p not in listed)
    t0 = time.time()
    if a.sample:
        step = max(1, len(paths) // a.sample)
        pick = paths[::step][:a.sample]
        _server()
        t_load = time.time() - t0
        times, sizes, bad = [], [], []
        for p in pick:
            t = time.time()
            code, body, _ = render(p)
            times.append(time.time() - t)
            sizes.append(len(body))
            if code != 200:
                bad.append((p, code))
        times.sort()
        print(f"{len(paths):,} pages listed; load {t_load:.0f}s; {len(pick)} sampled: median {times[len(times)//2]*1000:.0f} ms, "
              f"p95 {times[int(len(times)*.95)]*1000:.0f} ms, mean {sum(times)/len(times)*1000:.0f} ms; "
              f"mean size {sum(sizes)//len(sizes):,} B; not 200: {bad[:5]}")
        est = sum(times) / len(times) * len(paths)
        print(f"one process for all: about {est/60:.0f} min; with {a.workers} workers: about {est/a.workers/60 + t_load/60:.0f} min")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    chunks = [paths[i::a.workers] for i in range(a.workers)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(a.workers) as pool:
        results = pool.map(_work, [(c, str(OUT)) for c in chunks])
    manifest, fails = {}, []
    for done, f, _sec in results:
        manifest.update(done)
        fails.extend(f)
    # the shell, this version's, beside every version's (the upload keeps them all on the server)
    S = _server()
    sh = S.app_shell()
    (OUT / "assets").mkdir(exist_ok=True)
    for kind in ("js", "css"):
        name = f"app-{sh[kind + '_hash']}.{kind}"
        (OUT / "assets" / name).write_bytes(sh[kind])
    shell = {"js": f"app-{sh['js_hash']}.js", "css": f"app-{sh['css_hash']}.css"}
    prev = {}
    if (OUT / "uploaded.json").exists():
        prev = json.loads((OUT / "uploaded.json").read_text(encoding="utf-8")).get("pages", {})
    changed = sorted(p for p, h in manifest.items() if prev.get(p) != h)
    removed = sorted(set(prev) - set(manifest))
    (OUT / "manifest.json").write_text(json.dumps({"pages": manifest, "shell": shell}, indent=0), encoding="utf-8")
    (OUT / "changed.json").write_text(json.dumps({"changed": changed, "removed": removed}, indent=0), encoding="utf-8")
    rep = {"listed": len(paths), "built": len(manifest), "failed": len(fails), "failures": fails[:50],
           "changed": len(changed), "removed": len(removed), "seconds": round(time.time() - t0),
           "workers": a.workers, "shell": shell}
    (OUT / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(f"pages: {len(manifest):,} of {len(paths):,} built, {len(fails)} failed, {len(changed):,} changed since the "
          f"last upload, {len(removed)} removed; {rep['seconds']} s with {a.workers} workers -> {OUT}")
    sys.exit(1 if fails and len(fails) > len(paths) // 100 else 0)


def build_some(paths):
    """Build a few pages in this process and merge them into out/pages/manifest.json and changed.json (a failed page
    from the full build, rebuilt after a fix, without the 18 minutes again)."""
    done, fails, sec = _work((paths, str(OUT)))
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    man["pages"].update(done)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=0), encoding="utf-8")
    prev = {}
    if (OUT / "uploaded.json").exists():
        prev = json.loads((OUT / "uploaded.json").read_text(encoding="utf-8")).get("pages", {})
    ch = json.loads((OUT / "changed.json").read_text(encoding="utf-8"))
    ch["changed"] = sorted(p for p, h in man["pages"].items() if prev.get(p) != h)
    (OUT / "changed.json").write_text(json.dumps(ch, indent=0), encoding="utf-8")
    print(f"built {len(done)} of {len(paths)} in {sec:.0f} s; failed: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
