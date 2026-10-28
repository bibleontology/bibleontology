"""Every word card's headword against its Strong's number, deterministically (2026-10-27).

A word card is keyed by Strong's number and was headed by the first MACULA
lemma seen under that number. MACULA files several Strong's numbers under one
dictionary form: G2411 (the temple, 71 uses) and G2413 (sacred, 3) are both
lemma ἱερός, so the temple's card was headed by the adjective while its own
Strong's entry, and STEP's, is the noun ἱερόν. Found by a reader comparing the
card with the lexicon (2026-10-27), not by any check.

For every Strong's number the text uses, this compares:

  macula   the lemma(s) MACULA gives its uses, with counts
  step     STEP's headword for the number (TBESG / TBESH, the Strong's form)

and sorts each number into one of:

  same            identical once Unicode-normalized
  marks           the letters agree; accents, breathings or vowel points differ
  ending          Greek: the same stem, a different ending (ἱερός / ἱερόν) --
                  usually a different part of speech filed under one lemma
  form            the letters differ otherwise
  no_step         STEP has no single headword for the number
  several         MACULA gives the number's uses more than one lemma

No model and no judgment: what it reports is a count of disagreements between
two published sources, for a reader or editor to decide. The card leads with
STEP's headword where the two differ (the number's own form) and lists
MACULA's beside it.

Writes out/audit/headwords.json (every number) and prints the totals.
Run: python tools/audit_headwords.py [--show KIND] [--limit N]"""
import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

FINALS = str.maketrans({"ς": "σ", "ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
# MACULA's lemmas for a pronoun suffix or a particle written as part of another
# word: a letter code carrying one of these is a morpheme, not a sub-entry


def _set(*ws):
    return {letters(w) for w in ws}


def letters(s):
    """The letters alone: marks, punctuation and spaces gone, finals made medial."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] == "L")
    return s.lower().translate(FINALS)


FUNCTION = _set("הוּא", "הִיא", "הֵם", "הֵמָּה", "ה", "הּ", "וְ", "כְּ", "לְ", "בְּ", "מִן", "שֶׁ", "שֶׁל", "נ", "א",
                "אֲנִי", "אַתָּה", "אַנְתָּה")


def kind(macula, step, lang):
    if not step:
        return "no_step"
    a, b = unicodedata.normalize("NFC", macula), unicodedata.normalize("NFC", step)
    if a == b:
        return "same"
    la, lb = letters(a), letters(b)
    if la == lb:
        return "marks"
    if lang == "g" and len(la) > 3 and len(lb) > 3:
        n = 0
        while n < min(len(la), len(lb)) and la[n] == lb[n]:
            n += 1
        if n >= min(len(la), len(lb)) - 2:
            return "ending"
    return "form"


def step_headwords():
    """{key: (headword, transliteration)} as the server builds its lexicon:
    STEP's own files first, then the built lexicon, the first source to hold a
    number winning; a number STEP holds only as letter variants takes the
    headword they share, else none."""
    from bibleont import lemma as L
    sources = []
    try:
        sources.append(L.tbes_entries())
    except OSError:
        pass
    for cand in (ROOT / "data" / "raw" / "stepbible" / "lexicon.json", ROOT / "ontology" / "lexicon.json"):
        if cand.exists():
            sources.append(json.loads(cand.read_text(encoding="utf-8")))
    out = {}
    for raw in sources:
        if not raw:
            continue
        for code, v in list(raw.items()) + list(L.variant_entries(raw).items()):
            if not isinstance(v, list) or len(v) < 4:
                continue
            k = code[0].lower() + re.sub(r"^0+", "", code[1:])
            out.setdefault(k, (v[0], v[1]))
        break
    return out


def audit():
    import structure as S
    sys.path.insert(0, str(ROOT / "app2"))
    import server
    tally = collections.defaultdict(collections.Counter)
    codes = collections.defaultdict(collections.Counter)      # key -> raw code -> uses
    code_lemma = {}
    own_n = collections.defaultdict(collections.Counter)      # key -> lemma -> uses without a letter code
    first = {}
    for lang, strong, _ref, _text, lemma in S.words():
        s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", strong or ""))
        if s and lemma:
            key = (lang or "")[:1] + s
            tally[key][lemma] += 1
            first.setdefault(key, lemma)
            codes[key][strong] += 1
            code_lemma.setdefault((key, strong), lemma)
            if not strong[-1:].isalpha():
                own_n[key][lemma] += 1
    step = step_headwords()
    # the card's lead, by the server's own rule: the commonest lemma, the
    # number's own uses (no letter code) first
    common = {key: (own_n.get(key) or c).most_common(1)[0][0] for key, c in tally.items()}
    heads = server.headwords(common, first, {k: {"word": w, "translit": t} for k, (w, t) in step.items()})
    rows = []
    for key, c in tally.items():
        lang = key[0]
        was = first[key]                 # what the card showed before: the first lemma met
        h = heads.get(key) or {}
        leads = h.get("lemma") or was
        head, translit = step.get(key, ("", ""))
        k = kind(leads, head, lang)      # what still differs from STEP, after the rule
        # HEBREW MORPHEMES UNDER A WORD'S NUMBER: MACULA codes a pronoun suffix or
        # a particle as a number and a letter (2050c "his", 2967a "my"); the card
        # key drops the letter, so they land on an unrelated word's card. Counted
        # as the uses of letter codes whose lemma's letters are not the headword's.
        merged = {code: n for code, n in codes[key].items()
                  if lang == "h" and re.search(r"[a-z]$", code) and head
                  and letters(code_lemma[(key, code)]) not in {letters(x) for x in re.split(r"[,=]", head)}}
        rows.append({"key": key, "uses": sum(c.values()), "kind": k,
                     "step": head, "step_translit": translit,
                     "macula": dict(c.most_common()), "several": len(c) > 1,
                     "was": was, "card_leads": leads,
                     "card_also": (h.get("also") or {}).get("form"),
                     "merged": {code: [code_lemma[(key, code)], n,
                                       "suffix or particle" if letters(code_lemma[(key, code)]) in FUNCTION
                                       else "sub-entry"] for code, n in merged.items()}})
    rows.sort(key=lambda r: (r["key"][0], -r["uses"]))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="list one kind: same, marks, ending, form, no_step, several, changed, merged")
    ap.add_argument("--lang", choices=["g", "h"])
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)
    rows = audit()
    out = ROOT / "out" / "audit" / "headwords.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for lang, name in (("g", "Greek"), ("h", "Hebrew and Aramaic")):
        rs = [r for r in rows if r["key"][0] == lang]
        by = collections.Counter(r["kind"] for r in rs)
        uses = collections.Counter()
        for r in rs:
            uses[r["kind"]] += r["uses"]
        sev = [r for r in rs if r["several"]]
        print(f"{name}: {len(rs):,} numbers, {sum(r['uses'] for r in rs):,} uses")
        for k in ("same", "marks", "ending", "form", "no_step"):
            print(f"  {k:8} {by[k]:6,} numbers {uses[k]:8,} uses")
        print(f"  several MACULA lemmas under one number: {len(sev):,}")
        changed = [r for r in rs if r["card_leads"] != r["was"]]
        listed = [r for r in rs if r["card_also"]]
        print(f"  the card's headword changed: {len(changed):,}; the other form listed beside it: {len(listed):,}")
        for what in ("suffix or particle", "sub-entry"):
            mg = [r for r in rs if any(x[2] == what for x in r["merged"].values())]
            if mg:
                print(f"  {what} under another word's number: {len(mg):,} numbers, "
                      f"{sum(x[1] for r in mg for x in r['merged'].values() if x[2] == what):,} uses")
    if a.show:
        pick = [r for r in rows if (r["several"] if a.show == "several"
                                    else bool(r["merged"]) if a.show == "merged"
                                    else r["card_leads"] != r["was"] if a.show == "changed"
                                    else r["kind"] == a.show)
                and (not a.lang or r["key"][0] == a.lang)]
        if a.show == "merged":
            pick.sort(key=lambda r: -sum(x[1] for x in r["merged"].values()))
        for r in pick[:a.limit]:
            m = ", ".join(f"{l} {n}" for l, n in r["macula"].items())
            extra = ("  merged " + ", ".join(f"{c} {x[0]} {x[1]}" for c, x in r["merged"].items())) if r["merged"] else ""
            print(f"{r['key']:7} {r['uses']:6}  STEP {r['step'] or '-':14} ({r['step_translit']})  MACULA {m}"
                  f"  card {r['card_leads']}{' / ' + r['card_also'] if r['card_also'] else ''}{extra}")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
