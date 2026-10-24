"""A DeepSeek audit of the Hebrew structure graph over a diverse OT sample.

2026-09-26, after Psalm 23: an audit of the OT by DeepSeek, picking verses
pseudo-randomly but making sure they are not read out of context, finding
diversity and categorizing them according to whether the graph looks right,
with a complete report and specifically lists of what it sees as gaps in the
ontology and verses to review in order of opportunity, and recommendations to
fix for the verses it recommends evaluating. Budget: no more than $0.50.

Stratified by genre, seeded, verses with two clauses or more, the passages
already vetted left out. Each verse goes with the verse before and after
(context), its Hebrew, and its built structure as compact triples. The
ontology goes as ids, labels and definitions only — its proof fields name
known-wrong cases and would be an answer key. Batches run blind (no tools);
a last call writes the report from the batch findings.

    python tools/deepseek_audit.py            # writes docs/AUDIT-OT-<date>.md
"""
import datetime as dt
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import structure as S                                     # noqa: E402
from bibleont import delegate as D                        # noqa: E402

GENRES = {
    "narrative": "Gen Exo Num Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est",
    "law": "Lev Deu",
    "poetry": "Psa Sng Lam Job",
    "wisdom": "Pro Ecc",
    "prophecy": "Isa Jer Ezk Dan Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag "
                "Zec Mal",
}
VETTED = ("Exo.7.", "Exo.8.", "Psa.23.", "Psa.107.1", "Psa.119.105")
PER_GENRE, BATCH, BUDGET = 6, 5, 0.42      # batches; the report has its own
# SPENT BEFORE: the first run, batches of 20 at max thinking, came back EMPTY
# — each used all 32,000 output tokens reasoning (ledger: completion 31,999 =
# reasoning 31,999) and wrote nothing: $0.234 for no answer, three times over,
# because nothing stopped it after the first. That spend counts against
# the $0.50 budget, and — governing must be smart and circuit breakers must
# kick in early — the run now STOPS at the first batch that
# answers nothing or whose reasoning reaches the output cap.
PRIOR = 0.234
SEED = 20260926


def bsb_text():
    t = {}
    for l in gzip.open(ROOT / "out/bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("ref") and r.get("text"):
            t[r["ref"]] = r["text"]
    return t


def hebrew():
    h = {}
    for l in gzip.open(ROOT / "out/interlinear.jsonl.gz", "rt",
                       encoding="utf-8"):
        r = json.loads(l)
        if r.get("ref"):
            h[r["ref"]] = " ".join(w.get("t", "") for w in r["words"])
    return h


def triples(mermaid):
    """Mermaid source -> readable 'A —label→ B' lines, styles and clicks out."""
    lab = {}
    for m in re.finditer(r'^\s*(\w+)[\[\(\{]+"?(.*?)"?[\]\)\}]+\s*$',
                         mermaid, re.M):
        lab[m.group(1)] = re.sub(r"<br/>", " · ",
                                 re.sub(r"</?[bi]>", "", m.group(2)))
    out = []
    for m in re.finditer(r'^\s*(\w+)\s*[-=.]+>?\|"(.*?)"\|\s*(\w+)', mermaid,
                         re.M):
        a, l_, b = m.groups()
        out.append(f"{lab.get(a, a)[:70]} —{l_}→ {lab.get(b, b)[:70]}")
    return out


def ontology_summary():
    k = json.load(open(ROOT / "ontology/kinds.json", encoding="utf-8"))
    lines = []
    for sec in ("classes", "relations"):
        for x in k.get(sec, []):
            if not isinstance(x, dict) or x.get("status") != "built":
                continue
            d = (x.get("definition") or "")[:260]
            lines.append(f"- {sec[:-1]} {x['id']} ({x.get('label', '')}): {d}")
    return "\n".join(lines)


def sample(bsb):
    rng = random.Random(SEED)
    picked = []
    for g, books in GENRES.items():
        bs = books.split()
        pool = [r for r in bsb if r.split(".")[0] in bs
                and not r.startswith(VETTED)]
        rng.shuffle(pool)
        n = 0
        for r in pool:
            b, c, v = r.split(".")
            try:
                d = S.verse(b, int(c), int(v))
            except Exception:                     # noqa: BLE001
                continue
            if len(d.get("clauses") or []) < 2:
                continue
            picked.append((g, r, d))
            n += 1
            if n >= PER_GENRE:
                break
    # interleave the genres, so a run that stops early is still diverse
    by = {}
    for x in picked:
        by.setdefault(x[0], []).append(x)
    mixed = []
    for i in range(PER_GENRE):
        mixed += [v[i] for v in by.values() if i < len(v)]
    return mixed


def item(n, g, r, d, bsb, heb):
    b, c, v = r.split(".")
    prev, nxt = f"{b}.{c}.{int(v) - 1}", f"{b}.{c}.{int(v) + 1}"
    mref = d.get("ref") or r
    parts = [f"### {n}. {b} {c}:{v} ({g})",
             f"Before: {bsb.get(prev, '—')}",
             f"VERSE (BSB): {bsb.get(r, '')}",
             f"After: {bsb.get(nxt, '—')}",
             f"Hebrew: {heb.get(mref, '')}"]
    for cl in d["clauses"]:
        parts.append(f"  clause {cl['id'].split('#')[1]}: {cl['text']}  "
                     f"[{cl.get('force')}; {cl.get('mood') or 'no verb'}]")
        for t in triples(cl.get("diagram", ""))[:22]:
            parts.append(f"      {t}")
    return "\n".join(parts)


BRIEF = """You are auditing a structure graph of the Hebrew Bible, verse by verse. The graph is built by rule from MACULA's syntax trees: each clause is a node with its force and its verb's form; roles (subject, object, predicate, prepositional phrases) hang off each clause's content; clauses are linked (because, if, and, then, purpose, content, even though, ...) and grouped (speech turns, commands with their effects, concessions, acts of one agent, a psalm as a writing ...). Pronouns are resolved only where the rules allow; "is · inferred" marks a resolution. The graph's purpose is to show what a passage is SAYING: who acts, what is claimed, how clauses relate.

Its ontology (the kinds it may use):
{onto}

For EACH verse below, read it IN CONTEXT (the verses before and after are given), then judge the built structure against the Hebrew:
- CATEGORY: RIGHT (the structure says what the verse says), MINOR (small faults — a missing role, a label, an unresolved pronoun that context resolves), or WRONG (a link or group misstates how the clauses relate, a role on the wrong word, a clause missing).
- FAULTS: each fault in one line, naming the node or link.
- GAP: if a fault is not a bug but something the ontology has no kind for, say what kind is missing.
- FIX: for MINOR and WRONG, a concrete recommendation — what the graph should hold instead, and where possible the rule that would produce it.

Return, per verse: "N. ref | CATEGORY | faults | gap (or none) | fix". Then a short list of the recurring faults you saw in this batch.

VERSES
{items}
"""

SYNTH = """Below are the batches of an audit of a Hebrew Bible structure graph (verses across narrative, law, poetry, wisdom and prophecy). Write the COMPLETE REPORT for the project owner, in Markdown:

1. Summary: counts of RIGHT / MINOR / WRONG overall and by genre, and a one-paragraph judgement of where the graph is strong and weak.
2. GAPS IN THE ONTOLOGY: a de-duplicated list of kinds the ontology lacks, each with the verses that showed it and why it matters for reading what the text says. Order by how much of the text it affects.
3. VERSES TO REVIEW, IN ORDER OF OPPORTUNITY: the verses whose review would teach the most, chosen so the list is DIVERSE — each addresses a different issue where possible. For each: the reference, the issue, why it is an opportunity (how many other verses it probably stands for), and the RECOMMENDED FIX (what the graph should hold, and the rule that would produce it).
4. RECURRING FAULTS: bugs (not gaps) seen more than once, with examples.
5. What looked RIGHT and should not be changed.

Be concrete and cite verses. Do not invent verses that are not in the batches. Keep your deliberation short: the written report is what matters.

BATCH FINDINGS
{batches}
"""


def main():
    """The rule: record as it goes so that nothing is lost; do not stop once in
    the synthesis report due to money, within reason; the report can have a
    reasonable but separate budget of its own. So every batch is
    appended to the document the moment it returns, and the report runs
    whatever the batches spent (its own budget is the delegate's daily cap)."""
    bsb, heb = bsb_text(), hebrew()
    picked = sample(bsb)
    onto = ontology_summary()
    day = dt.date.today().isoformat()
    doc = ROOT / "docs" / f"AUDIT-OT-{day}.md"
    head = (f"# OT structure audit by DeepSeek — {day}\n\n"
            f"Requested by Doug after Psalm 23. {len(picked)} verses, "
            f"stratified by genre (seed {SEED}), each read with the verse "
            f"before and after; the ontology sent without its proof fields; "
            f"batches run blind. Written by DeepSeek-V4-Pro; NOT yet reviewed "
            f"by Claude — every finding is a proposal until checked against "
            f"the text.\n\nVerses: "
            + ", ".join(f"{r} ({g})" for g, r, _ in picked) + "\n")
    doc.write_text(head + "\n(report pending — batch findings follow as "
                          "they arrive)\n", encoding="utf-8")
    spent, answers = PRIOR, []
    for i in range(0, len(picked), BATCH):
        chunk = picked[i:i + BATCH]
        items = "\n\n".join(item(i + j + 1, g, r, d, bsb, heb)
                            for j, (g, r, d) in enumerate(chunk))
        res = D.run(BRIEF.format(onto=onto, items=items), level=3,
                    label=f"ot-audit-{i // BATCH + 1}", blind=True)
        spent += float(res.get("cost") or 0)
        ans = (res.get("answer") or "").strip()
        tok = res.get("tokens") or {}
        capped = tok.get("reasoning", 0) >= 0.95 * D.MAX_TOKENS[D.PRO]
        broke = None
        if not ans:
            # an empty answer is a FAILURE, not a finding
            broke = ("EMPTY — " + str(res.get("refused") or res.get("stop") or
                     f"no answer; reasoning {tok.get('reasoning')} tokens"))
            ans = broke
        else:
            answers.append(ans)
        with open(doc, "a", encoding="utf-8") as f:     # recorded as it goes
            f.write(f"\n---\n\n## Batch {i // BATCH + 1} "
                    f"(${res.get('cost')}, {res.get('result_file')})\n\n{ans}\n")
        print(f"batch {i // BATCH + 1}: ${res.get('cost')}, total ${spent:.3f}",
              flush=True)
        # CIRCUIT BREAKERS, early: the first failure stops the spending
        if broke or capped:
            print(f"BREAKER: {'empty answer' if broke else 'reasoning at cap'}"
                  f" — stopping batches", flush=True)
            break
        if spent > BUDGET:
            print("batch budget reached; on to the report", flush=True)
            break
    if not answers:
        print("no batch answered; no report", flush=True)
        return
    res = D.run(SYNTH.format(batches="\n\n---\n\n".join(answers)),
                level=3, label="ot-audit-report", blind=True)
    spent += float(res.get("cost") or 0)
    synth = res.get("answer") or res.get("refused") or res.get("stop") or ""
    print(f"report: ${res.get('cost')}, total ${spent:.3f}", flush=True)
    body = doc.read_text(encoding="utf-8").split("\n(report pending", 1)
    doc.write_text(head + f"\nTotal cost ${spent:.3f}.\n\n---\n\n" + synth
                   + "\n\n---\n\n# Appendix: batch findings\n"
                   + (body[1].split("\n", 1)[1] if len(body) > 1 else ""),
                   encoding="utf-8")
    print(f"wrote {doc}  total ${spent:.3f}")


if __name__ == "__main__":
    main()
