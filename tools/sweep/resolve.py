"""THE RESOLUTION PASS (proposal P-2026-10-16-3; 2026-10-16: unresolved is much better
than wrong, so prepare another sweep with really large passages and really
specific instructions as to where resolution is needed, and if the context is
large enough, Sonnet could be justified to get this right).

The first pass left a third of its pronouns and unstated subjects open, most
of them inside speeches whose speaker and audience are named chapters back
(Mark 54%, John 44%, against Genesis 20%). This pass asks about those and
nothing else:

  context    the whole chapter and the one before it, in the Berean
  cast       everyone named in the book so far (proper names, deduplicated by
             the original's word), every candidate of these two chapters, the
             divine persons wherever the book names them, and the narrator
  questions  each open slot (its word, morphology, clause and the first
             pass's own note) and each speech missing its speaker or addressee

It fills blanks only. The first pass's decisions are never changed here.

    python tools/sweep/resolve.py run <run name> <Book.chapter> ...   (Sonnet, one call per chapter)
    python tools/sweep/resolve.py run <run name> done                 (every chapter the first pass has finished)
    python tools/sweep/resolve.py merge <run name>                    -> per-verse answers with the blanks filled
"""
import collections
import concurrent.futures as cf
import gzip
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402
import headless as H  # noqa: E402

FIRST = ROOT / "out" / "sweep" / "runs" / "sweep-1"
MODEL = "claude-sonnet-5-5"
DIVINE = {"יהוה", "אֱלֹהִים", "אֲדֹנָי", "θεός", "Ἰησοῦς", "κύριος", "Χριστός", "πνεῦμα"}

TASK = """You are finishing the reading of one chapter of the Bible. A first pass has already settled most of its
pronouns, unstated subjects and speeches. It left the ones below open, usually because the person was named
too far back for it to see. You have the whole chapter, the chapter before it, and the book's cast.

For each question, choose who is meant from the CAST, by id, or answer "none".

Rules:
- UNRESOLVED IS BETTER THAN WRONG. The owner's rule: a blank costs little and a wrong answer costs a great deal.
  Answer only where the text makes it plain. If two readings are open, answer "none" and say so in `why`.
- The original's morphology must agree (given in `morph`): a plural is a group, or several people; a feminine is not a man.
- A first or second person ("I", "you", "we") inside a speech is the speaker or the hearer of THAT speech. Work out
  whose speech it is from the text: it may have begun in the chapter before, or earlier still (Jesus speaking
  from John 13:31 to 16:33; Moses' sermons in Deuteronomy; the LORD speaking to Moses for Israel in Leviticus).
- Where "they", "we" or "us" is several people or groups together, give their ids as a list: ["id1", "id2"]. A list may
  mix people and groups (Moses, Aaron and the people of Israel).
- A GENERIC ENTITY for someone the text plainly describes but does not offer by name (the owner's ruling): the
  harvesters, the four men carrying a paralytic, a crowd, a messenger. Give it as {"new": "<a short description in
  the text's own words>", "first": "<the verse that first describes them>"}. Use the SAME description, word for word,
  every time the same people are meant in this chapter, so they become one entity; never mint one for a named person
  or for anyone in the cast. A generic entity can also stand in a list.
- Choose only ids from the CAST. The cast includes the ordinary nouns of these two chapters (the harvesters, the crowd,
  the disciples), each with the verse it is in; prefer the mention nearest the question. If the right person or group
  is not in it, answer "none" and name them in `why`.
- When you answer "none", say which kind of none in "none_is":
  "no referent"  the word refers to no one (an impersonal "it was", a "where?", an indefinite "someone");
  "not plain"    the text leaves it open between readings;
  "not in cast"  the referent is plain but not offered.
- If a choice is God, the LORD, the Father, Jesus or the Holy Spirit, set "divine": true. Still make the choice.
- For a speech missing its speaker or addressee, give the id (or a generic entity, or a list), or null where the
  text does not say.

Answer with ONLY this JSON object:
{"chapter": "<as given>",
 "answers": [{"q": "<q id>", "choice": "<cast id>" | ["<id or generic>", ...] | {"new": "...", "first": "..."} | "none",
              "none_is": "<only with none>",
              "confidence": "high|medium|low", "divine": false, "why": "<a dozen words: the evidence>"}],
 "turns": [{"q": "<t id>", "sender": "<cast id>" | null, "addressee": "<cast id>" | null,
            "confidence": "high|medium|low", "divine": false, "why": "<a dozen words>"}]}
Answer every question once.

"""


def chapter_refs(book):
    out = collections.defaultdict(set)
    for line in gzip.open(C.OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line).get("ref") or ""
        if r.startswith(book + "."):
            _b, c, v = r.split(".")
            out[int(c)].add(int(v))
    return {c: [f"{book}.{c}.{v}" for v in sorted(vs)] for c, vs in out.items()}


def build(book, ch, chapters, bsb, ctxs=None):
    """The prompt for one chapter, and what it asks (to merge by). `ctxs`, the
    whole book's contexts built once, spares a rebuild per chapter (Genesis 50
    would otherwise read the clause files for all fifty chapters)."""
    upto = [r for c in sorted(chapters) if c <= ch for r in chapters[c]]
    here = chapters.get(ch, [])
    prev = chapters.get(ch - 1, [])
    ctxs = ctxs or C.build(upto)
    cast, by_lemma = {}, {}
    for r in upto:
        for c in ctxs[r]["candidates"]:
            near = r in here or r in prev
            if c.get("proper") or near or (c.get("lemma") in DIVINE):
                # A VERSE'S OWN NOUNS ARE NAMED WITH THE VERSE. Their ids ("w14")
                # are unique only within it; gathered across a chapter they
                # overwrote each other, and the pilot's judge could not find the
                # harvesters, the crowd, the disciples or the angel of the LORD
                # that the text names (2026-10-16).
                cid = c["id"] if "#" in c["id"] else f"{r}#{c['id']}"
                key = c.get("lemma") or cid
                # names and the divine words once each, at their latest mention
                # (the Genesis 22 cast listed God 130 times, once per mention)
                if (c.get("proper") or c.get("lemma") in DIVINE) and not near and key in by_lemma:
                    cast.pop(by_lemma[key], None)          # keep the latest mention of a name
                cast[cid] = {**{k: c[k] for k in ("text", "lemma", "morph", "where", "members", "voice") if c.get(k)}, "id": cid}
                by_lemma[key] = cid
    cast["narrator"] = {"id": "narrator", "text": "the narrator: the book's own voice (and the 'we' of a narrator's company)"}
    questions, turnq, asked = [], [], {}
    for r in here:
        p = FIRST / f"{r}.json"
        if not p.exists():
            continue
        ans = json.loads(p.read_text(encoding="utf-8"))
        ctx = ctxs[r]
        gl = {c["id"]: c["gloss"] for c in ctx["clauses"]}
        made = {x.get("slot"): x for x in ans.get("referents") or []}
        for s in ctx["slots"]:
            x = made.get(s["id"]) or {}
            if x.get("rhetorical") or x.get("choice") not in (None, "none", "cant_tell"):
                continue
            q = f"q{len(questions) + 1}"
            # an unstated subject is named for its clause ("cl3s"); a pronoun is
            # placed by the word it hangs on ("in")
            clause = next((g for cid, g in gl.items() if s["id"] == cid + "s"), "")
            note = next((f"{c.get('what')}: {c.get('why')}" for c in ans.get("cant_tell") or []
                         if s["id"] in json.dumps(c, ensure_ascii=False)), x.get("why") or "")
            questions.append({"q": q, "verse": r, "word": s.get("text"), "in": s.get("in_text"), "morph": s.get("morph"),
                              "clause": clause or None, "first_pass": note or None})
            asked[q] = (r, s["id"])
        for g in ans.get("groups") or []:
            if g.get("kind") != "turn" or g.get("action") not in ("add", "change", "keep"):
                continue
            roles = {m.get("role"): m.get("node") for m in g.get("members") or []}
            missing = [k for k in ("sender", "addressee") if k not in roles]
            if not missing:
                continue
            q = f"t{len(turnq) + 1}"
            turnq.append({"q": q, "verse": r, "said_in": gl.get((roles.get("frame") or "").split("#")[-1]),
                          "missing": missing, "has": {k: roles[k] for k in ("sender", "addressee") if k in roles}})
            asked[q] = (r, g.get("id"))
    if not questions and not turnq:
        return None, asked
    text = lambda refs: [{"verse": bsb(r)[0], "ref": r, "text": bsb(r)[1]} for r in refs]  # noqa: E731
    name = f"{book}.{ch}"
    body = TASK + json.dumps({"chapter": name, "cast": list(cast.values()), "chapter_before": text(prev),
                              "text": text(here), "questions": questions, "turn_questions": turnq},
                             ensure_ascii=False, separators=(",", ":")) + "\n"
    return body, asked


LOCK = threading.Lock()


def one(out, b, ch, chapters, bsb, ctxs):
    dst = out / f"R-{b}.{ch}.json"
    if dst.exists() or (out / "STOP").exists():
        return
    body, asked = build(b, ch, chapters, bsb, ctxs)
    if body is None:
        return
    for attempt in range(2):
        t0 = time.time()
        res, err = H.call(body, MODEL)
        blob = json.dumps(res or {}) + (err or "")
        if (res is None or res.get("is_error")) and "limit" in blob.lower():
            log(out, f"{b}.{ch}: usage limit; waiting 10 minutes")
            time.sleep(600)
            continue
        ans = H.parse(res) if res and not res.get("is_error") else None
        if ans is not None and not (ans.get("answers") or ans.get("turns")):
            ans = None                  # parsed, but answers nothing: unusable, not done
        u = (res or {}).get("usage") or {}
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        with LOCK, open(out / "_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"chapter": f"{b}.{ch}", "questions": len(asked), "tokens": toks, "usage": u,
                                "seconds": round(time.time() - t0), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
        if ans:
            dst.write_text(json.dumps({"asked": asked, "answer": ans}, ensure_ascii=False, indent=1), encoding="utf-8")
            n_ok = sum(1 for a in ans.get("answers") or [] if a.get("choice") not in (None, "none"))
            log(out, f"{b}.{ch}: {len(asked)} questions, {n_ok} resolved, {toks:,} tokens, {time.time() - t0:.0f}s")
            return
        (out / f"bad-{b}.{ch}.txt").write_text(json.dumps(res or err, ensure_ascii=False)[:20000], encoding="utf-8")
        log(out, f"{b}.{ch}: unusable answer (attempt {attempt + 1})")


def log(out, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with LOCK, open(out / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(name, chapters_asked, workers=6):
    """The chapters named ("Rut.2"), or with "done" every chapter the first
    pass has finished, in canonical order, `workers` at a time (2026-10-16: the resolution pass now, alongside the first)."""
    out = ROOT / "out" / "sweep" / "runs" / name
    out.mkdir(parents=True, exist_ok=True)
    bsb = C._bsb()
    books = collections.defaultdict(list)
    if chapters_asked == ["done"]:
        for b in CANON:
            for ch, refs in sorted(chapter_refs(b).items()):
                if all((FIRST / f"{r}.json").exists() for r in refs) and not (out / f"R-{b}.{ch}.json").exists():
                    books[b].append(ch)
    else:
        for bc in chapters_asked:
            b, c = bc.split(".")
            books[b].append(int(c))
    log(out, f"start: {sum(map(len, books.values()))} chapters in {len(books)} books, {workers} at a time, {MODEL}")
    futs = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for b, chs in books.items():
            chapters = chapter_refs(b)
            ctxs = C.build([r for c in sorted(chapters) if c <= max(chs) for r in chapters[c]])
            for ch in chs:
                while sum(not f.done() for f in futs) > 3 * workers:
                    time.sleep(3)
                futs.append(ex.submit(one, out, b, ch, chapters, bsb, ctxs))
        for f in futs:
            f.result()
    log(out, "end")


CANON = ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa", "1Ki", "2Ki", "1Ch", "2Ch", "Ezr",
         "Neh", "Est", "Job", "Psa", "Pro", "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo",
         "Oba", "Jon", "Mic", "Nam", "Hab", "Zep", "Hag", "Zec", "Mal", "Mat", "Mrk", "Luk", "Jhn", "Act", "Rom",
         "1Co", "2Co", "Gal", "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas", "1Pe",
         "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"]


def mint(chapter, x, generics):
    """A generic entity's id: one per description per chapter. 2026-10-16: for the
    harvesters and the bearers the cast could not offer, generic entities are
    created."""
    if isinstance(x, list):
        return [mint(chapter, y, generics) for y in x]
    if isinstance(x, dict) and x.get("new"):
        slug = re.sub(r"[^a-z0-9]+", "-", x["new"].lower()).strip("-")[:60]
        gid = f"{chapter}#generic:{slug}"
        generics.setdefault(gid, {"id": gid, "label": x["new"], "first": x.get("first"), "kind": "generic",
                                  "made_by": "resolution pass"})
        return gid
    return x


def merge(name):
    """Per-verse answers: the first pass's, with only its blanks filled."""
    src = ROOT / "out" / "sweep" / "runs" / name
    dst = src / "merged"
    dst.mkdir(exist_ok=True)
    filled = collections.defaultdict(dict)
    turns = collections.defaultdict(dict)
    generics = {}
    for p in src.glob("R-*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        chapter = p.stem[2:]
        for a in d["answer"].get("answers") or []:
            if a.get("q") in d["asked"] and a.get("choice") not in (None, "none"):
                r, slot = d["asked"][a["q"]]
                filled[r][slot] = {**a, "choice": mint(chapter, a["choice"], generics)}
        for t in d["answer"].get("turns") or []:
            if t.get("q") in d["asked"]:
                r, gid = d["asked"][t["q"]]
                turns[r][gid] = {**t, **{k: mint(chapter, t.get(k), generics) for k in ("sender", "addressee")}}
    (src / "generics.json").write_text(json.dumps(list(generics.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    n = 0
    for r in set(filled) | set(turns):
        ans = json.loads((FIRST / f"{r}.json").read_text(encoding="utf-8"))
        for x in ans.get("referents") or []:
            a = filled[r].get(x.get("slot"))
            if a and x.get("choice") in (None, "none", "cant_tell") and not x.get("rhetorical"):
                x.update({"choice": a["choice"], "confidence": a.get("confidence"), "divine": a.get("divine", False),
                          "why": a.get("why"), "resolved_by": "resolution pass"})
                n += 1
        for g in ans.get("groups") or []:
            t = turns[r].get(g.get("id"))
            if t:
                roles = {m.get("role") for m in g.get("members") or []}
                for k in ("sender", "addressee"):
                    if k not in roles and t.get(k):
                        g.setdefault("members", []).append({"role": k, "node": t[k], "resolved_by": "resolution pass"})
                        n += 1
        (dst / f"{r}.json").write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n} blanks filled in {len(set(filled) | set(turns))} verses -> {dst}")


if __name__ == "__main__":
    H.stay_awake()
    if sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3:], int(os.environ.get("RESOLVE_WORKERS", "6")))
    else:
        merge(sys.argv[2])
