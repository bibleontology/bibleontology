"""Stamp every clause of the corpus with Flash: plan 6.13, step 2.

2026-09-28/29: run DeepSeek Flash clause stamping on the whole corpus; Pro is
not needed at all, only a second Flash pass at the clause level that assigns a
strength to every clause that is matched; in pass 2 those assertions are
presented as they are, with the graph sections; the Flash run was started the
day the budget was added.

Per BSB section, two Flash calls (blind, no thinking), exactly the pilot's
design (pilot of 2026-09-28; out/pin-pilot/):

    pass 1   which of the section's 14 September stamps (theme and ref lanes)
             hold, at which clauses, or are general or wrong — with a
             confidence under the scoring rule (3/2/1 right, -10/-3/0 wrong)
    pass 2b  each pass-1 assertion AS MADE, beside the graph's clauses with
             their roles and links, plus the anchored concepts of the
             section's words: every clause that carries each, high / medium /
             low. The Son is shown resolved (out/son-titles.jsonl) — step 3's
             ready part, so Flash reads "the Son (Jesus, the Son of God)".

Parallel and careful (decided 2026-09-29): starts at 4 workers, adds one per
20 clean calls up to 8; halves on a timeout, an HTTP error, or the rolling
median call time doubling past its baseline; a call times out at 120 s;
failed sections go back in the queue twice; stops on 5 failures in a row or
more than 20% of the last 50; stops itself at BUDGET dollars spent; resumes —
a section with both answers on disk is skipped.

    python tools/stamp_corpus.py [--limit N] [--budget 18]
        -> out/clause-stamping/p1/<section>.json, p2b/<section>.json
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "clause-stamping"
sys.path.insert(0, str(ROOT / "src"))
from bibleont import delegate  # noqa: E402

OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov "
        "Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark "
        "Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet "
        "2Pet 1John 2John 3John Jude Rev").split()
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA "
        "JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO "
        "GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
MAC = ("Gen Exo Lev Num Deu Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est Job Psa Pro Ecc Sng Isa "
       "Jer Lam Ezk Dan Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal Mat Mrk Luk Jhn Act Rom 1Co 2Co "
       "Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev").split()
CODE, TOMAC = dict(zip(OSIS, USFM)), dict(zip(OSIS, MAC))
STAMPS_PER_CALL = 25       # pass 1: Pro capped on 27; Flash is kept well under its 8k answer
TAGS_PER_CALL = 45         # pass 2b: assertions + concepts per call
TIMEOUT = 120
NON_CONCEPTS = {"all", "thing", "kind", "matter", "go", "see", "hear", "hearing", "speak", "speaking",
                "words", "day", "days", "man", "men", "people", "hand", "face", "young", "travels",
                "troops", "ground", "completely", "countenance", "walk", "request", "answer",
                "answering", "answers", "produce", "wish", "desire"}
ROLE = {"s": "doer", "v": "action", "o": "acted on", "o2": "second object", "io": "to/for",
        "pp": "where/with", "p": "is"}
LINK = {"as": "compared with", "purpose": "so that", "because": "because", "therefore": "therefore",
        "result": "so that (result)", "contrast": "but", "condition": "if", "that": "that",
        "within": "contains", "then": "then", "and": "and"}

SCORING = ("Your answers are scored: you get 3 points for every correct high answer, 2 for every correct "
           "medium answer and 1 for every correct low answer; you lose 10 points for every high answer "
           "that is wrong and 3 points for every medium answer that is wrong, and nothing for a low "
           "answer that is wrong.")
P1_HEAD = """Below is one section of the Bible (Berean Standard Bible, public domain), the same section broken into numbered clauses (a word-by-word English gloss of the Hebrew or Greek, in the original's word order; a clause may sit inside another, shown as "in <id>"), and a list of STAMPS an earlier reader gave the section as a whole: ideas, roles and kinds of event it speaks of, each with the verse that reader cited.

Your task: for EACH stamp, say which clauses of this section specifically speak to it — the clauses a reader would point at to show the stamp is true here. Rules:
- Use clause ids exactly as given. List only clauses that themselves carry the idea; not every clause of the verse the reader cited, and not clauses merely near it.
- A stamp that describes the section's general drift but no clause in particular gets an empty list and "general": true.
- A stamp you think is wrong for this section gets an empty list and "wrong": true, with a short reason.
- Give the words (from the Berean text) that the clauses rest on.
- Give a confidence for each pin: high (the clauses plainly say it), medium (a reader would likely agree), or low (you are unsure which clauses, or whether the stamp belongs here at all). """ + SCORING + """
The stamps are plain ideas written with underscores ("sacrifice_ev" is a sacrifice as an event); no file needs to be consulted and none is supplied.

Return ONLY this JSON:
{"section": "<start ref>", "pins": [{"stamp": "<id>", "clauses": ["<clause id>", ...], "words": "<Berean words>", "general": false, "wrong": false, "reason": "", "confidence": "<high|medium|low>"}]}
"""
P2_HEAD = """Below is one section of the Bible (Berean Standard Bible, public domain) and its GRAPH: the section's clauses, each with the roles the grammar gives it (doer, action, acted on, where/with ...) and its links to other clauses (so that, because, compared with, contains ...). A clause may sit inside another.

An earlier reading of this section made ASSERTIONS: each says that the section speaks of an idea, with the words it rested on and how confident that reading was. They are shown exactly as made. There are also CONCEPTS whose words occur in the section.

Your task: for EACH assertion and EACH concept, list EVERY clause of the graph that carries it, each with a strength:
  high   - the clause plainly says it
  medium - a reader would likely agree it says it (for example through a figure or an image)
  low    - there is any chance at all that it speaks to it; some readers would see it, others not
About the tags: they are plain ideas to be read in this text — not entries in any file, list or ontology. No file needs to be consulted and none is supplied; answer from the text and your understanding of it. A concept means what its name ordinarily means in English. A stamp's name is its idea written with underscores ("sacrifice_ev" is a sacrifice as an event; "humiliation_to_vindication" is one brought low and then raised up).
Rules:
- Use clause ids exactly as given. Pin the smallest clause that says it by itself; add the containing clause only if the idea needs the whole sentence. Use the roles: an idea about who acts belongs on the clause where that one is the doer.
- The earlier reading may be wrong or may have placed an idea in the wrong verse: if no clause carries an assertion, give it an empty list.
- A concept whose word occurs in a clause is not automatically carried: the word must mean that concept there.
- """ + SCORING + """

Return ONLY this JSON:
{"section": "<start ref>", "tags": [{"tag": "<tag>", "kind": "<stamp|concept>", "clauses": [{"id": "<clause id>", "strength": "<high|medium|low>"}]}]}
"""


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def answer_of(text):
    m = re.search(r'\{\s*"section"', text or "")
    if not m:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[m.start():])[0]
    except ValueError:
        return None


def load():
    """Sections (BSB headings), their verses and text, stamps, clauses with
    roles, links and concepts, and the resolved Son."""
    secs, text = {}, {}
    for osis in OSIS:
        f = next((ROOT / "data" / "raw" / "usfm" / "engbsb").glob(f"*{CODE[osis]}engbsb.usfm"))
        ch, cur, pend, vcur = 0, None, False, None
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
                continue
            if line.startswith("\\s1"):
                pend = True
                continue
            if re.match(r"\\(s\d?|r|d|mt\d?|h|toc\d?|id|ms\d?|mr)\b", line):
                continue
            t = re.sub(r"\\f .*?\\f\*", "", line)
            t = re.sub(r"\\w ([^|]*)\|[^\\]*\\w\*", r"\1", t)
            for piece in re.split(r"(\\v \d+)", t):
                m = re.match(r"\\v (\d+)", piece)
                if m:
                    v = f"{osis}.{ch}.{m.group(1)}"
                    if pend or cur is None:
                        cur, pend = v, False
                        secs[cur] = []
                    secs[cur].append(v)
                    vcur = v
                    text[v] = ""
                    continue
                if vcur:
                    text[vcur] += " " + re.sub(r"\\\S+\*?", "", piece).strip()
    text = {k: re.sub(r"\s+", " ", v).strip() for k, v in text.items()}
    stamps = collections.defaultdict(list)
    for f in (OUT).glob("stamps-*-deepseek-*.jsonl"):
        lane = f.stem.rsplit("-", 1)[1]
        if lane not in ("theme", "ref"):
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                stamps[r["ref"]].append((r.get("category"), r["id"], r.get("cites")))
    # clauses and words of every verse
    need = {TOMAC[v.split(".")[0]] + "." + v.split(".", 1)[1] for vs in secs.values() for v in vs}
    nodes, clauses = {}, collections.defaultdict(list)
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        v = n["id"].split("#")[0]
        if v in need:
            nodes[n["id"]] = n
            if n.get("clause"):
                clauses[v].append(n)
    roles, links = collections.defaultdict(list), collections.defaultdict(list)
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        a = e["src"]
        if a.split("#")[0] not in need:
            continue
        if e["type"] in ROLE and "#ct" in a:
            roles[a.replace("#ct", "#cl")].append((ROLE[e["type"]], e["dst"]))
        elif e["type"] in LINK and "#cl" in a and "#cl" in e["dst"]:
            links[a].append((LINK[e["type"]], e["dst"]))
    son = {}
    for line in (OUT / "son-titles.jsonl").read_text(encoding="utf-8").splitlines()[1:]:
        r = json.loads(line)
        son[r["occurrence"]] = r
    anch, cname = collections.defaultdict(set), {}
    for r in rows(OUT / "concept-anchors.jsonl.gz"):
        if r["kind"] != "word":
            continue
        cname[r["id"]] = r["name"]
        for p in r["parts"]:
            for k, _n, s in p["anchors"]:
                if s >= 0.15:
                    anch[k].add(r["id"])
    return secs, text, stamps, nodes, clauses, roles, links, son, anch, cname


def build(data, sec):
    """The section's text block, clause list (pass 1), graph block and
    concepts (pass 2b)."""
    secs, text, stamps, nodes, clauses, roles, links, son, anch, cname = data
    vs = secs[sec]
    stext = "\n".join(f"{v.replace('.', ' ', 1).replace('.', ':')}  {text.get(v, '')}" for v in vs)
    cl1, cl2, concepts = [], [], set()

    def filler(w):
        n = nodes.get(w, {})
        t = n.get("text") or n.get("lemma") or ""
        if w in son:
            t += " (Jesus, the Son of God)" if son[w].get("title") == "the_son_of_god" else \
                 " (Jesus, the Son of Man)" if son[w].get("title") == "the_son_of_man" else " (Jesus)"
        return t
    for v in vs:
        mv = TOMAC[v.split(".")[0]] + "." + v.split(".", 1)[1]
        for n in sorted(clauses.get(mv, []), key=lambda n: n.get("order", 0)):
            cid = n["id"]
            nest = f"  (in {n['nested_in'].split('#')[1]})" if n.get("nested_in") else ""
            cl1.append(f"{cid}  {n.get('text') or ''}{nest}")
            r = " · ".join(f"{k}: {filler(w)}" for k, w in roles.get(cid, []) if filler(w))
            lk = "; ".join(f"{k} {d}" for k, d in links.get(cid, []))
            nest2 = f"  (inside {n['nested_in']})" if n.get("nested_in") else ""
            cl2.append(f"{cid}  \"{n.get('text') or ''}\"{nest2}" + (f"\n    roles: {r}" if r else "")
                       + (f"\n    links: {lk}" if lk else ""))
            for wi in n.get("w") or []:
                w = nodes.get(f"{mv}#w{wi}") or {}
                d = "".join(ch for ch in (w.get("strong") or "") if ch.isdigit())
                if d:
                    concepts |= anch.get(("g" if w.get("lang") == "greek" else "h") + str(int(d)), set())
    names = sorted({cname[c] for c in concepts} - NON_CONCEPTS)
    return {"text": f"{sec} ({vs[0]} to {vs[-1]})\n{stext}", "cl1": cl1, "cl2": cl2,
            "stamps": stamps.get(sec, []), "concepts": names}


class Pace:
    """Workers in flight, adapted to how DeepSeek answers."""

    def __init__(self, start=4, top=8):
        self.n, self.top, self.ok = start, top, 0
        self.times = collections.deque(maxlen=30)
        self.base = None
        self.recent = collections.deque(maxlen=50)
        self.fail_run = 0
        self.lock = threading.Lock()

    def done(self, secs, ok):
        with self.lock:
            self.recent.append(ok)
            if ok:
                self.fail_run = 0
                self.times.append(secs)
                if self.base is None and len(self.times) >= 10:
                    self.base = statistics.median(self.times)
                self.ok += 1
                slow = self.base and len(self.times) >= 10 and statistics.median(self.times) > 2 * self.base
                if slow:
                    self.cut("median call time doubled")
                elif self.ok % 20 == 0 and self.n < self.top:
                    self.n += 1
                    print(f"  pace: up to {self.n} workers", flush=True)
            else:
                self.fail_run += 1
                self.cut("a failed call")

    def cut(self, why):
        new = max(1, self.n // 2)
        if new != self.n:
            self.n = new
            print(f"  pace: down to {self.n} workers ({why}); pausing 60s", flush=True)
            time.sleep(60)

    def broken(self):
        bad = sum(1 for x in self.recent if not x)
        return self.fail_run >= 5 or (len(self.recent) >= 50 and bad / len(self.recent) > 0.2)


def call(task, label):
    t0 = time.time()
    r = delegate.run(task, 1, label=label, blind=True, timeout=TIMEOUT, check_balance=False)
    return r, time.time() - t0


def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)] or [[]]


def do_section(data, sec, pace, spent):
    """Pass 1 then pass 2b for one section; True when both are on disk."""
    b = build(data, sec)
    p1f, p2f = DEST / "p1" / f"{sec}.json", DEST / "p2b" / f"{sec}.json"
    cost = 0.0
    if not p1f.exists():
        pins = []
        for part in chunks(b["stamps"], STAMPS_PER_CALL):
            if not part:
                break
            task = (P1_HEAD + f"\nTHE SECTION: {b['text']}\n\nTHE CLAUSES\n" + "\n".join(b["cl1"])
                    + "\n\nTHE STAMPS\n" + "\n".join(f"{i} ({c}; cited {ci})" for c, i, ci in part) + "\n")
            r, secs = call(task, f"stamp-p1-{sec}")
            cost += r.get("cost") or 0
            a = answer_of(r.get("answer"))
            # only DeepSeek's own trouble (a stop: HTTP error, timeout) or
            # slowness moves the pace; an unreadable answer is just retried
            pace.done(secs, not r.get("stopped"))
            if a is None:
                spent.add(cost)
                return False
            # only the stamps offered: Flash invented "creation_ev_manner"
            # for Gen 1 in the trial
            offered = {i for _c, i, _ci in part}
            pins += [p for p in a.get("pins", [])
                     if str(p.get("stamp", "")).split(" (")[0] in offered]
        p1f.write_text(json.dumps({"section": sec, "pins": pins, "cost": cost}, ensure_ascii=False),
                       encoding="utf-8")
    p1 = json.loads(p1f.read_text(encoding="utf-8"))
    if not p2f.exists():
        asserts = []
        for p in p1["pins"]:
            if p.get("wrong"):
                continue
            # a clause may come back as {"id": ...} rather than its id (1 Sam
            # 28:1 in the corpus run raised on it)
            ids = [c.get("id", "") if isinstance(c, dict) else str(c) for c in p.get("clauses", [])]
            vs = sorted({c.split("#")[0] for c in ids if c})
            st = str(p.get("stamp", "")).split(" (")[0]
            asserts.append(f'{st}: "{p.get("words", "")}" — found in {", ".join(vs) or "the section as a whole"}; '
                           f'confidence {p.get("confidence", "?")}')
        items = [("a", x) for x in asserts] + [("c", c) for c in b["concepts"]]
        tags, c2 = [], 0.0
        for part in chunks(items, TAGS_PER_CALL):
            if not part:
                break
            task = (P2_HEAD + f"\nTHE SECTION: {b['text']}\n\nTHE GRAPH\n" + "\n".join(b["cl2"])
                    + "\n\nTHE ASSERTIONS\n" + "\n".join(x for k, x in part if k == "a")
                    + "\n\nTHE CONCEPTS\n" + "\n".join(f"concept: {x}" for k, x in part if k == "c") + "\n")
            r, secs = call(task, f"stamp-p2b-{sec}")
            c2 += r.get("cost") or 0
            a = answer_of(r.get("answer"))
            pace.done(secs, not r.get("stopped"))
            if a is None:
                spent.add(cost + c2)
                return False
            tags += a.get("tags", [])
        cost += c2
        p2f.write_text(json.dumps({"section": sec, "tags": tags, "cost": c2}, ensure_ascii=False),
                       encoding="utf-8")
    spent.add(cost)
    return True


class Spent:
    def __init__(self):
        self.v, self.lock = 0.0, threading.Lock()

    def add(self, x):
        with self.lock:
            self.v += x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only this many sections (a trial)")
    ap.add_argument("--budget", type=float, default=18.0)
    a = ap.parse_args()
    (DEST / "p1").mkdir(parents=True, exist_ok=True)
    (DEST / "p2b").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    data = load()
    secs = data[0]
    todo = [s for s in secs if data[2].get(s) and
            not ((DEST / "p1" / f"{s}.json").exists() and (DEST / "p2b" / f"{s}.json").exists())]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(secs):,} sections; {len(todo):,} to stamp (loaded in {time.time() - t0:.0f}s)", flush=True)
    pace, spent = Pace(), Spent()
    tries = collections.Counter()
    queue = collections.deque(todo)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        running = {}
        while queue or running:
            while queue and len(running) < pace.n and spent.v < a.budget and not pace.broken():
                s = queue.popleft()
                running[ex.submit(do_section, data, s, pace, spent)] = s
            if not running:
                break
            fin, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for f in fin:
                s = running.pop(f)
                ok = False
                try:
                    ok = f.result()
                except Exception as exc:                          # noqa: BLE001
                    print(f"  {s}: error {type(exc).__name__}: {exc}", flush=True)
                if ok:
                    done += 1
                    if done % 25 == 0:
                        el = time.time() - t0
                        print(f"  {done:,}/{len(todo):,} sections · ${spent.v:.2f} · {el / 60:.0f} min · "
                              f"{pace.n} workers", flush=True)
                else:
                    tries[s] += 1
                    if tries[s] <= 2:
                        queue.append(s)
                    else:
                        print(f"  {s}: gave up after 3 tries", flush=True)
            if spent.v >= a.budget:
                print(f"STOP: budget ${a.budget:.2f} reached", flush=True)
                queue.clear()
            if pace.broken():
                print("STOP: circuit breaker (5 failures in a row or >20% of the last 50)", flush=True)
                queue.clear()
    print(f"done: {done:,} sections, ${spent.v:.2f}, {(time.time() - t0) / 60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
