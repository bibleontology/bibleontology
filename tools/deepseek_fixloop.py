"""One verse, audited by DeepSeek, each fault returned with a generic rule.

2026-09-26: DeepSeek is given one verse at a time and is responsible for
identifying what is wrong and creating a generic fix algorithm that uses the
original language first or a translation fallback. And, earlier the same day,
after a 60-verse sweep overshot: wait until everything known is fixed, audit a
verse, fix while auditing another verse in the background, repeat; when few
issues are found, start batching 2, then 3, then 4 verses in an audit.

DeepSeek never sees the Python, so a rule comes back as a SPECIFICATION over
features it can see: the Hebrew words (lemma, Strong's, part of speech), the
clauses (form, force, links, position) and — only as a marked fallback — the
BSB's English with the Berean editors' Strong's tags. Claude checks each
fault against the text, implements the rule, samples 16 of its hits across
the corpus for a blind judging run twice, and the site's owner decides before it is
built (delegate skill). A rule that could only fire on the verse shown is a
one-off and is rejected.

    python tools/deepseek_fixloop.py              # the next verse in the order
    python tools/deepseek_fixloop.py Jdg.9.15     # a named verse
    python tools/deepseek_fixloop.py --n 2        # two verses (as findings thin)

Every answer is appended to docs/FIXLOOP.md the moment it returns.
"""
import argparse
import collections
import datetime as dt
import gzip
import json
import random
import re
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import deepseek_audit as A                                # noqa: E402
import structure as S                                     # noqa: E402
from bibleont import delegate as D                        # noqa: E402

LOG = ROOT / "docs" / "FIXLOOP.md"
SHARD = [0, 1]
SEED = 20260927
# verses whose findings were already worked: the passages vetted by hand, and
# the first audit's sample (docs/AUDIT-OT-2026-09-26.md)
DONE_BEFORE = ROOT / "docs" / "AUDIT-OT-2026-09-26.md"


def bsb_tagged():
    """ref -> the BSB verse with each tagged span marked [H####]."""
    t = {}
    for l in gzip.open(ROOT / "out/bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if not (r.get("ref") and r.get("text")):
            continue
        s, out, at = r["text"], [], 0
        for a, b, tag in sorted(r.get("spans") or []):
            out += [s[at:a], s[a:b], f"[{tag.upper()}]"]
            at = b
        t[r["ref"]] = "".join(out + [s[at:]])
    return t


def words():
    h = {}
    for l in gzip.open(ROOT / "out/interlinear.jsonl.gz", "rt",
                       encoding="utf-8"):
        r = json.loads(l)
        if r.get("ref"):
            h[r["ref"]] = r["words"]
    return h


def done():
    refs = set()
    for f in (LOG, DONE_BEFORE):
        if f.exists():
            refs |= set(re.findall(r"\b[1-3]?[A-Z][a-z]{1,2}\.\d+\.\d+\b",
                                   f.read_text(encoding="utf-8")))
    return refs


def order(bsb):
    """A seeded walk through the genres in turn, verses of 2+ clauses."""
    rng = random.Random(SEED)
    pools = []
    for g, books in A.GENRES.items():
        bs = books.split()
        pool = [r for r in bsb if r.split(".")[0] in bs
                and not r.startswith(A.VETTED)]
        rng.shuffle(pool)
        pools.append((g, pool))
    i = 0
    while any(p for _, p in pools):
        g, p = pools[i % len(pools)]
        if p:
            yield g, p.pop(0)
        i += 1


def pick(bsb, n, named):
    if named:
        g = next((g for g, bs in A.GENRES.items()
                  if named.split(".")[0] in bs.split()), "?")
        b, c, v = named.split(".")
        return [(g, named, S.verse(b, int(c), int(v)))]
    seen, out = done(), []
    for g, r in order(bsb):
        if r in seen:
            continue
        b, c, v = r.split(".")
        try:
            d = S.verse(b, int(c), int(v))
        except Exception:                             # noqa: BLE001
            continue
        if len(d.get("clauses") or []) < 2:
            continue
        out.append((g, r, d))
        if len(out) >= n:
            break
    return out


FUNCTION_POS = {"particle", "conjunction", "preposition", "pronoun",
                "adverb"}


def features(nodes_by_ref, edges_by_ref, heb, ref):
    """What a verse is MADE of, for telling verses apart: its clause forms,
    patterns and links, its groups, its roles and function words. Two verses
    that share little here are unlikely to share a fix."""
    f = set()
    for n in nodes_by_ref.get(ref, []):
        if n.get("clause"):
            f.add("mood:" + str(n.get("verb_mood")))
            f.add("pattern:" + str(n.get("rule")))
            f.add("force:" + str(n.get("upper_force")))
        if n.get("kind"):
            f.add("group:" + n["kind"])
    for e in edges_by_ref.get(ref, []):
        if e.get("clause_link"):
            f.add("link:" + e["type"])
        elif e.get("clause_role"):
            f.add("role:" + e["type"] + (":" + e["prep"] if e.get("prep")
                                         else ""))
        if e.get("type") == "refers_to":
            f.add("refers_to")
    for w in heb.get(ref, []):
        if w.get("p") in FUNCTION_POS:
            f.add("fw:" + str(w.get("l")))
    return f


def diverse(bsb, heb, k, pool_size=400):
    """2026-09-26: be prepared with verses that are highly unlikely
    to share the same solution. Farthest-first: each pick is the candidate
    whose features overlap LEAST (Jaccard) with every verse already audited
    or vetted, and with the picks before it; a genre not yet picked breaks
    ties."""
    sys.path.insert(0, str(FIX.parent))
    from fixrules import harness as H
    nodes, edges = H.load_graph()
    nb, eb = collections.defaultdict(list), collections.defaultdict(list)
    for n in nodes:
        nb[n.get("ref")].append(n)
    for e in edges:
        eb[e.get("ref")].append(e)
    seen = done() | {r for r in json.load(
        open(ROOT / "tests" / "verses.json", encoding="utf-8"))
        if not r.startswith("_")}
    ref_set = [features(nb, eb, heb, r) for r in seen if r in nb]
    cands = []
    for g, r in order(bsb):
        if r in seen or r not in nb:
            continue
        if sum(1 for n in nb[r] if n.get("clause")) < 2:
            continue
        cands.append((g, r, features(nb, eb, heb, r)))
        if len(cands) >= pool_size:
            break

    def jac(a, b):
        return len(a & b) / len(a | b) if a | b else 1.0
    picks, genres = [], set()
    for _ in range(k):
        best = min(cands, key=lambda c: (
            max((jac(c[2], x) for x in ref_set), default=0),
            c[0] in genres, c[1]))
        cands.remove(best)
        near = max((jac(best[2], x) for x in ref_set), default=0)
        picks.append((best[0], best[1], round(near, 2)))
        ref_set.append(best[2])
        genres.add(best[0])
    return picks


def item(n, g, r, d, bsb, heb):
    b, c, v = r.split(".")
    prev, nxt = f"{b}.{c}.{int(v) - 1}", f"{b}.{c}.{int(v) + 1}"
    mref = d.get("ref") or r
    ws = heb.get(mref) or []
    parts = [f"### {n}. {b} {c}:{v} ({g})",
             f"Before (BSB): {bsb.get(prev, '—')}",
             f"VERSE (BSB, tagged): {bsb.get(r, '')}",
             f"After (BSB): {bsb.get(nxt, '—')}",
             "Hebrew words (position. word · lemma · Strong's · part of "
             "speech · usual gloss):"]
    parts += [f"  {i + 1}. {w.get('t')} · {w.get('l')} · H{w.get('s')} · "
              f"{w.get('p')} · {w.get('g')}" for i, w in enumerate(ws)]
    parts.append("Built structure:")
    for cl in d["clauses"]:
        parts.append(f"  clause {cl['id'].split('#')[1]}: {cl['text']}  "
                     f"[{cl.get('force')}; {cl.get('mood') or 'no verb'}]")
        for t in A.triples(cl.get("diagram", ""))[:30]:
            parts.append(f"      {t}")
    return "\n".join(parts)


FIX = ROOT / "tools" / "fixrules"


def framework_pack():
    """The fixed part of the brief — the same bytes every call, so DeepSeek's
    prefix cache holds it (the framework goes in the cache along with
    some good examples that have worked)."""
    parts = ["===== tools/fixrules/framework.py =====\n"
             + (FIX / "framework.py").read_text(encoding="utf-8")]
    for p in sorted((FIX / "examples").glob("*.py")):
        parts.append(f"===== tools/fixrules/examples/{p.name} (WORKED "
                     f"EXAMPLE: built, measured, reproduced by the framework) "
                     f"=====\n" + p.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


# TWO CALLS, NOT ONE. 2026-09-26: asking for the audit AND working code in
# one call spent all 32,000 output tokens reasoning, twice on the same verse
# (2Sa 17:14; $0.068 prose, $0.073 with the framework), and returned nothing
# usable. A 5-verse audit with no rules had fitted (26-29k). So the audit
# names the faults, and each fault gets its own rule call.
AUDIT = """You are auditing a structure graph of the Hebrew Bible, ONE verse. The purpose of the graph is to show what a passage is SAYING: who acts, what is claimed, how the clauses relate.

How to read the structure: each clause is a node with its force and its verb's form. Roles (subject s, object o, predicate p, verb v, prepositional phrase pp, qualifier) hang off each clause's content. Clauses are linked (and, because, if, then, purpose, content, within ...) and grouped (speech turns with a frame and parts, commands with their effects, acts of one agent ...). "is · inferred" marks a resolution a rule supplied, and BSB marks one taken from the English.

===== the ontology: the kinds the graph may use =====
{onto}

Read the verse in its context (the verses before and after are given) and judge the built structure against the Hebrew. Pick AT MOST TWO faults, the ones that most distort what the verse says. For each, state a GENERAL condition that would find the same fault in other verses. The condition must be over form, role, link, order, a function word or agreement, never over this verse's nouns, verbs or names. Keep your deliberation short.

RETURN exactly:
VERDICT: RIGHT | MINOR | WRONG
FAULT 1: <node or link> — <what is wrong> — <what the graph should hold>
  GENERAL: <the condition that finds it elsewhere>
  ALGORITHM: <in plain numbered steps over the graph: how to find every case, and what to change; no code>
  BASIS: original | translation (<why the Hebrew cannot decide>)
  GAP: none | <the kind the ontology lacks>
FAULT 2: ... (same form, or omit)
OTHER FAULTS: <one line each, or none>

THE VERSE
{items}
"""

CLUSTER = """Below are the faults found in a structure graph of the Hebrew Bible: an audit of about 60 verses chosen to be dissimilar, plus the owner's own readings of passages. Each fault names a verse, what is wrong, a general condition, and an algorithm. Group them into RECURRING PATTERNS so the most common problems can be attacked first.

===== the ontology: the kinds the graph may use =====
{onto}

RETURN, in Markdown:
1. PATTERNS, ranked by how many distinct verses report them. For each:
   - NAME (short snake_case) and one sentence stating the pattern.
   - VERSES: every reference that reports it.
   - CONDITION: the merged general condition, over form, role, link, order, function words or agreement. Never over particular content words.
   - DETECTOR: the features a detector would test, stated precisely enough to code, over the graph as the faults describe it.
   - KIND: the existing kind the fix would use, or GAP and the new kind.
   - Whether the OWNER's readings belong to it (they are authoritative).
2. BLENDED SOLUTIONS: single mechanisms that would answer SEVERAL patterns at once (e.g. one decision about a function word that fixes three patterns). For each, the patterns it covers and why one mechanism serves them all.
3. DISAGREEMENTS: faults that contradict each other or the owner's readings. Say which to trust and why.
4. SINGLETONS: faults that fit no pattern, listed in one line each.
Keep your deliberation short: the grouping is what matters.

THE FAULTS
{faults}
"""

DETECT = """Write ONE DETECTOR for a structure graph of the Hebrew Bible: a Python plug-in for the framework below. Write ONLY detect(); fix() yields nothing and validate() returns []. The detector's hits will be COUNTED over the whole corpus and a sample judged, so precision matters more than recall.

You have NO tools and no files: everything you need is in this message. Answer directly with the module.

{framework}

===== the ontology =====
{onto}

THE PATTERN TO DETECT:
{pattern}

REQUIREMENTS
- Test general features only: roles, clause form and force, links, order, part of speech, the lemma of a FUNCTION word, agreement. Never a content word.
- Read the framework's docstring for the exact field names and edge directions. For example, clause links run clause -> clause, roles run from the content node, and a verb node's person is `person` while a clause's is `verb_person`. Rules written earlier failed on exactly these.
- Each finding: {{"at": <node id>, "why": <one line a reader can check against the verse>}}.
- Keep your deliberation short.

RETURN the module:
```python
# tools/fixrules/rules/<name>.py
...
```
"""


def all_faults():
    """Every recorded fault, trimmed: the finding batch, the audits, and
    the owner's readings (marked as the owner's)."""
    t = LOG.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^## (\S+) — (find|audit|generalize) — .*?\n(.*?)"
                         r"(?=^## |\Z)", t, re.M | re.S):
        ref, kind, body = m.groups()
        body = re.sub(r"\n\s*\n", "\n", body)
        body = re.sub(r"(?s)VERIFY:.*", "", body)
        body = body.replace("**Claude's review:** pending", "").strip()
        who = "OWNER'S READINGS, generalized" if kind == "generalize" else \
            "audit"
        out.append(f"### {ref} ({who})\n{body[:3500]}")
    for m in re.finditer(r"^## (Doug's .*?)\n(.*?)(?=^## |\Z)", t,
                         re.M | re.S):
        out.append(f"### {m.group(1)} (OWNER)\n{m.group(2).strip()[:3000]}")
    return "\n\n".join(out)


GENERALIZE = """The owner of a structure graph of the Hebrew Bible has read a verse and stated how its structure should be. Your job is to find the GENERAL pattern behind each reading, so that it can be applied wherever else it occurs. Write NO code.

How to read the structure: each clause is a node with its force and its verb's form. Roles (subject s, object o, predicate p, verb v, prepositional phrase pp, qualifier) hang off each clause's content. Clauses are linked (and, because, if, then, purpose, content, within ...) and grouped.

===== the ontology: the kinds the graph may use =====
{onto}

THE OWNER'S READINGS (take them as correct; do not argue them):
{readings}

For EACH reading:
- GENERAL: the condition, over form, role, link, order, a function word or agreement, that finds the same situation in other verses. Never over this verse's nouns, verbs or names.
- ALGORITHM: plain numbered steps over the graph: how to find every case, and what to change.
- KIND: the existing kind to use, or GAP and the kind the ontology lacks.
- ALSO: up to 5 other verses (Hebrew Bible) where you are confident the same pattern occurs, each with a few words saying why.
- MISFIRES: the likeliest wrong case, and a guard against it.
Keep your deliberation short.

THE VERSE
{items}
"""


RULE = """Write ONE rule for a structure graph of the Hebrew Bible: a Python plug-in for the framework below, with a detect, a fix and a validate pass. Two worked examples follow the framework. Both are rules that were built, measured and reproduced by it, so follow their pattern.

You have NO tools and no files: everything you need is in this message. Do not try to read, list or run anything. Answer directly with the module.

{framework}

===== the ontology: the kinds a rule may use =====
{onto}

THE FAULT, found in {ref}:
{fault}

THE VERSE WHERE IT WAS FOUND (its built structure is shown; your rule must fix it here AND wherever the same fault occurs):
{items}

REQUIREMENTS
- ORIGINAL LANGUAGE FIRST (BASIS = "original"): roles, clause form and force, links, order, part of speech, the lemma of a FUNCTION word, agreement. BASIS = "translation" only where the Hebrew cannot decide; it reads v.bsb() and never removes or overrides.
- NO ONE-OFFS: never test for a content word (noun, verb, name). A rule that could only fire in this verse is rejected unread.
- detect() is measured ALONE on a corpus sample before fix() ever runs: make it precise.
- validate() states what must be true AFTER the fix, in graph terms, not a replay of the fix.
- Use only edge types that exist (see the framework). If the fault needs a new kind, return GAP and the kind instead of code.
- Keep your deliberation short: the code is what matters.

RETURN: ALSO FIRES: <up to 3 refs you are confident of>; MISFIRES WHEN: <the likeliest wrong case>; then the module:
```python
# tools/fixrules/rules/<name>.py
...
```
"""


REFINE = """You wrote the rule below for a structure graph of the Hebrew Bible. It was run over the whole corpus, and a sample of what it did was judged against the text. Revise the rule so that it keeps the successes and stops the failures. Do not special-case the failing verses. Find the GENERAL feature that separates them from the successes. If no such feature exists, say so and narrow detect() instead.

{framework}

===== your rule =====
```python
{code}
```

===== results: {summary} =====
{results}

RETURN: one sentence on what separates the failures, then the revised module:
```python
# tools/fixrules/rules/<name>.py
...
```
"""


JUDGE = """Below are places in the Hebrew Bible where a rule for a structure graph fired. The rule's claim is stated once. For EACH place, read the verse and its context and judge whether the claim is true THERE.

THE RULE'S CLAIM: {test}

Answer one line per place, exactly: "N | RIGHT or WRONG | a few words why". Judge only the claim, not anything else about the verse. Keep your deliberation short.

{items}
"""


def judge(rule_path, n=16):
    """Sample the rule's DETECTIONS (before any fix), have them judged blind,
    twice; write a results file that --refine sends back. Where the two runs
    differ, the item is UNSETTLED, never counted either way."""
    sys.path.insert(0, str(FIX.parent))
    from fixrules import framework as F, harness as H
    rule_path = Path(rule_path)
    m = F.load([rule_path.stem], folder=rule_path.parent)[0]
    nodes, edges = H.load_graph()
    bsb, wds = H.load_text()
    r = F.run([m], nodes, edges, bsb=bsb, words=wds, detect_only=True)[m.NAME]
    det = r["detected"]
    if not det:
        print(f"{m.NAME}: detects nothing")
        return
    shown = bsb_tagged()
    sample = random.Random(SEED).sample(det, min(n, len(det)))
    items = []
    for i, (ref, f) in enumerate(sample, 1):
        b, c, v = ref.split(".")
        items.append(f"### {i}. {b} {c}:{v}\n"
                     f"Before: {shown.get(f'{b}.{c}.{int(v) - 1}', '—')}\n"
                     f"VERSE: {shown.get(ref, '')}\n"
                     f"After: {shown.get(f'{b}.{c}.{int(v) + 1}', '—')}\n"
                     f"Where it fired: {f.get('why')}")
    task = JUDGE.format(test=m.TEST, items="\n\n".join(items))
    runs = []
    for k in (1, 2):
        res = D.run(task, level=2, label=f"judge-{m.NAME}-{k}", blind=True)
        ans = res.get("answer") or ""
        runs.append({int(x.group(1)): (x.group(2), x.group(3).strip())
                     for x in re.finditer(r"^\s*(\d+)\s*\|\s*(RIGHT|WRONG)"
                                          r"\s*\|\s*(.*)$", ans, re.M)})
        print(f"judge run {k}: ${res.get('cost')}, {len(runs[-1])} verdicts",
              flush=True)
        if not runs[-1]:
            print("BREAKER: no verdicts — stopping", flush=True)
            return
    out, tally = [], collections.Counter()
    for i, (ref, f) in enumerate(sample, 1):
        a_, b_ = runs[0].get(i, ("?", "")), runs[1].get(i, ("?", ""))
        verdict = a_[0] if a_[0] == b_[0] else "UNSETTLED"
        tally[verdict] += 1
        out.append(f"- {ref} | {verdict} | fired: {f.get('why')} | "
                   f"why: {a_[1]}" + (f" / {b_[1]}" if a_[0] != b_[0] else ""))
    p = FIX / "proposed" / f"{m.NAME}.results.md"
    p.write_text(f"# {m.NAME}: {len(det)} detections; a sample of "
                 f"{len(sample)} judged blind, twice\n\n"
                 f"{tally['RIGHT']} RIGHT, {tally['WRONG']} WRONG, "
                 f"{tally['UNSETTLED']} UNSETTLED (the runs differ)\n\n"
                 + "\n".join(out) + "\n", encoding="utf-8")
    print(f"{m.NAME}: {len(det)} detected; {dict(tally)} -> "
          f"{p.relative_to(ROOT)}")


def save_rules(ans, refs, folder="proposed"):
    """Each ```python block of the answer, as a proposed rule file (never
    enabled: tools/fixrules/rules/ is for rules the owner has approved)."""
    out = []
    for code in re.findall(r"```python\n(.*?)```", ans, re.S):
        m = re.search(r'^NAME\s*=\s*["\'](\w+)["\']', code, re.M)
        if not m:
            continue
        p = FIX / folder / f"{m.group(1)}.py"
        p.parent.mkdir(exist_ok=True)
        p.write_text(f"# PROPOSED by DeepSeek from {refs} — not enabled\n"
                     + code, encoding="utf-8")
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", nargs="?")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--queue", type=int, default=0,
                    help="print the next N verses, farthest-first, and stop")
    ap.add_argument("--refine", nargs=2, metavar=("RULE.py", "RESULTS.md"),
                    help="send a rule back with its judged sample")
    ap.add_argument("--fault", help="a stated fault: skip the audit, "
                                    "write its rule")
    ap.add_argument("--reuse", action="store_true",
                    help="take the verse's recorded audit; only write rules")
    ap.add_argument("--judge", metavar="RULE.py",
                    help="judge a sample of the rule's detections, blind x2")
    ap.add_argument("--find", type=int, default=0,
                    help="audit the next N dissimilar verses, no code")
    ap.add_argument("--budget", type=float, default=3.0)
    ap.add_argument("--generalize", nargs=2, metavar=("REF", "READINGS"),
                    help="Doug's readings of a verse -> general pattern, "
                         "algorithm, other verses; no code")
    ap.add_argument("--shard", default="0/1", help="worker k/n of a wide run")
    ap.add_argument("--cluster", action="store_true",
                    help="group every recorded fault into ranked patterns")
    ap.add_argument("--cluster-continue", action="store_true")
    ap.add_argument("--detect", nargs=2, metavar=("NAME", "PATTERN"),
                    help="a detector (detect() only) for one pattern")
    a = ap.parse_args()
    SHARD[:] = [int(x) for x in a.shard.split("/")]
    if a.cluster:
        # 2026-09-26: focus on attacking the most common issues first
        # and also look for blended solutions that meet multiple objectives
        faults = all_faults()
        print(f"{len(faults):,} chars of faults", flush=True)
        ans, ok = send(CLUSTER.format(onto=A.ontology_summary(),
                                      faults=faults),
                       "cluster-faults", "all faults", "cluster",
                       effort="high")
        (ROOT / "docs" / "FIXLOOP-PATTERNS.md").write_text(
            "# Recurring patterns in the recorded faults (DeepSeek, "
            f"{dt.date.today().isoformat()})\n\nA proposal until Claude has "
            "measured each detector over the corpus.\n\n" + ans,
            encoding="utf-8")
        return
    if a.cluster_continue:
        # the first cluster answer stopped at the output cap (26 Sep: 27,665
        # reasoning + 4,335 answer = 32,000) mid-pattern 9
        doc = ROOT / "docs" / "FIXLOOP-PATTERNS.md"
        so_far = doc.read_text(encoding="utf-8")
        task = CLUSTER.format(onto=A.ontology_summary(),
                              faults=all_faults()) + (
            "\n\nYOUR ANSWER SO FAR stopped mid-way (output limit). Do NOT "
            "repeat it. Continue from where it stops: finish the pattern it "
            "was writing, give the remaining PATTERNS, then sections 2 "
            "(BLENDED SOLUTIONS), 3 (DISAGREEMENTS) and 4 (SINGLETONS). Be "
            "concise: verse lists and conditions, no preamble.\n\n"
            "===== YOUR ANSWER SO FAR =====\n" + so_far)
        ans, ok = send(task, "cluster-continue", "all faults",
                       "cluster (continued)", effort="high")
        doc.write_text(so_far + "\n\n<!-- continued in a second call -->\n\n"
                       + ans, encoding="utf-8")
        return
    if a.detect:
        name, pattern = a.detect
        ans, ok = send(DETECT.format(framework=framework_pack(),
                                     onto=A.ontology_summary(),
                                     pattern=pattern),
                       f"detect-{name}", name, "detector", effort="high")
        for p in save_rules(ans, f"detector {name}", "detectors"):
            print(f"detector: {p.relative_to(ROOT)}", flush=True)
        return
    if a.generalize:
        # 2026-09-26: queue up the coding suggestions, but the search can be
        # delegated to DeepSeek.
        r, readings = a.generalize
        bsb, heb = bsb_tagged(), words()
        b, c, v = r.split(".")
        g = next((g for g, bs in A.GENRES.items() if b in bs.split()), "?")
        send(GENERALIZE.format(onto=A.ontology_summary(), readings=readings,
                               items=item(1, g, r, S.verse(b, int(c), int(v)),
                                          bsb, heb)),
             f"generalize-{r}", r, "generalize")
        return
    if a.find:
        find(a.find, a.budget)
        return
    if a.judge:
        judge(a.judge)
        return
    bsb, heb = bsb_tagged(), words()
    if a.queue:
        for g, r, near in diverse(bsb, heb, a.queue):
            print(f"{r:12} {g:9} nearest overlap {near}  {bsb.get(r, '')[:90]}")
        return
    if a.refine:
        # 2026-09-26: a results file with the set of successes and failures
        # can go back to deepseek to refine its algorithm
        code = Path(a.refine[0]).read_text(encoding="utf-8")
        results = Path(a.refine[1]).read_text(encoding="utf-8")
        right = len(re.findall(r"\bRIGHT\b", results))
        wrong = len(re.findall(r"\bWRONG\b", results))
        refs = f"refine {Path(a.refine[0]).stem}"
        task = REFINE.format(framework=framework_pack(), code=code,
                             results=results,
                             summary=f"{right} right, {wrong} wrong")
    else:
        if a.ref or a.n > 1:
            picked = pick(bsb, a.n, a.ref)
        else:
            g, r, _ = diverse(bsb, heb, 1)[0]
            b, c, v = r.split(".")
            picked = [(g, r, S.verse(b, int(c), int(v)))]
        items = "\n\n".join(item(i + 1, g, r, d, bsb, heb)
                            for i, (g, r, d) in enumerate(picked))
        refs = ", ".join(r for _, r, _ in picked)
        onto = A.ontology_summary()
        prior = re.findall(rf"^## {re.escape(refs)} — audit — .*?\n(.*?)"
                           rf"(?=^---$|\Z)",
                           LOG.read_text(encoding="utf-8") if LOG.exists()
                           else "", re.M | re.S)
        if a.fault:
            # a fault stated by hand, sent straight to a rule call
            ans = f"FAULT 1: {a.fault}\n  GAP: none\n"
        elif a.reuse and prior:
            ans = prior[-1]                  # the recorded audit, not re-paid
        else:
            ans, ok = send(AUDIT.format(onto=onto, items=items),
                           f"fixloop-audit-{refs}", refs, "audit")
            if not ok:
                return
        faults = re.findall(r"^FAULT \d+:.*?(?=^FAULT \d+:|^OTHER FAULTS:|\Z)",
                            ans, re.M | re.S)
        for i, fault in enumerate(faults[:2], 1):
            if re.search(r"^\s*GAP:[ \t]*(?!none\b)\S", fault, re.M | re.I):
                print(f"fault {i} is a GAP — no rule asked", flush=True)
                continue
            ans_r, ok = send(RULE.format(framework=framework_pack(),
                                         onto=onto, ref=refs,
                                         fault=fault.strip(), items=items),
                             f"fixloop-rule-{refs}-{i}", refs, f"rule {i}",
                             effort="high")
            saved = save_rules(ans_r, refs)
            for p in saved:
                print(f"proposed rule: {p.relative_to(ROOT)}", flush=True)
            if not saved and not re.search(r"^\s*GAP\b", ans_r, re.M):
                # 26 Sep: blind rule calls answered with imitation tool calls
                # — non-empty, so the empty-answer breaker passed them
                print("BREAKER: no rule module in the answer — stopping",
                      flush=True)
                return
            if not ok:
                return
        return
    ans, ok = send(task, f"fixloop-{refs}", refs, "refine", effort="high")
    for p in save_rules(ans, refs):
        print(f"proposed rule: {p.relative_to(ROOT)}", flush=True)


def find(n, budget):
    """THE FINDING BATCH. 2026-09-26, after the first evening of
    rule-writing: DeepSeek is not a good coder, so the focus moves to problem
    finding and searching in the Hebrew corpus with high level algorithmic
    suggestion, giving a decent size batch for a few more dollars, to be coded
    later when tokens are less of a concern. ($3.)
    One dissimilar verse per call; faults with a general condition and an
    algorithm in prose; no code. Stops at the first empty or capped answer,
    at the budget, and before peak hours."""
    bsb, heb = bsb_tagged(), words()
    onto = A.ontology_summary()
    spent = 0.0
    # GOING WIDE (3-4 workers wide with DeepSeek):
    # one queue, computed once and written down; worker k of n takes every
    # n-th verse of it, so no verse is audited twice.
    qf = ROOT / "out" / "find-queue.json"
    if SHARD[0] == 0 and not qf.exists():
        qf.write_text(json.dumps(diverse(bsb, heb, n)), encoding="utf-8")
    while not qf.exists():
        time.sleep(5)
    queue = json.loads(qf.read_text(encoding="utf-8"))
    for g, r, near in queue[SHARD[0]::SHARD[1]]:
        if r in done():
            continue
        if D.spend.is_peak(dt.datetime.now(dt.timezone.utc)):
            print("peak hours — stopping (resume off-peak)", flush=True)
            return
        b, c, v = r.split(".")
        items = item(1, g, r, S.verse(b, int(c), int(v)), bsb, heb)
        before = len(LOG.read_text(encoding="utf-8")) if LOG.exists() else 0
        ans, ok = send(AUDIT.format(onto=onto, items=items),
                       f"find-{r}", r, "find")
        spent += _last_cost()
        print(f"  {r} ({g}, overlap {near}) — spent ${spent:.3f}", flush=True)
        if not ok or not re.search(r"^VERDICT:", ans, re.M):
            # an answer without a verdict is blank however long it is
            # (blank results must not slip through)
            print("BREAKER — stopping the batch (no verdict)", flush=True)
            return
        if spent >= budget:
            print(f"budget ${budget} reached", flush=True)
            return
    print("queue done", flush=True)


def _last_cost():
    try:
        with open(ROOT / ".delegate" / "ledger.jsonl", encoding="utf-8") as f:
            return float(json.loads(f.readlines()[-1]).get("cost") or 0)
    except (OSError, ValueError, IndexError):
        return 0.0


def send(task, label, refs, what, effort="max"):
    """One call, recorded the moment it returns; False = a breaker tripped
    (an empty answer, or reasoning at the cap) and nothing more is spent."""
    print(f"sending {refs} ({what}, effort {effort})", flush=True)
    res = D.run(task, level=3, label=label, blind=True, effort=effort)
    ans = (res.get("answer") or "").strip()
    tok = res.get("tokens") or {}
    capped = tok.get("reasoning", 0) >= 0.95 * D.MAX_TOKENS[D.PRO]
    if not ans:
        # an empty answer is a FAILURE, not a finding
        ans = ("EMPTY — " + str(res.get("refused") or res.get("stop") or
               f"no answer; reasoning {tok.get('reasoning')} tokens"))
    if not LOG.exists():
        LOG.write_text(
            "# The fix loop — one verse at a time, each fault with its rule\n\n"
            "Doug, 2026-09-26: DeepSeek audits one verse and returns a "
            "generic rule per fault, original language first, a translation "
            "fallback second. Written by DeepSeek-V4-Pro; every fault and "
            "rule is a PROPOSAL until Claude has checked it against the text "
            "and measured the rule on a corpus sample, and Doug has said "
            "yes.\n", encoding="utf-8")
    with open(LOG, "a", encoding="utf-8") as f:           # recorded at once
        f.write(f"\n---\n\n## {refs} — {what} — "
                f"{dt.date.today().isoformat()} "
                f"(${res.get('cost')}, {res.get('result_file')})\n\n"
                f"**Claude's review:** pending\n\n{ans}\n")
    print(f"{what}: ${res.get('cost')}  reasoning {tok.get('reasoning')} / "
          f"completion {tok.get('completion')}"
          + ("  BREAKER: reasoning at cap" if capped else ""), flush=True)
    return ans, bool(res.get("answer")) and not capped


if __name__ == "__main__":
    main()
