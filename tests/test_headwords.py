"""A word card is headed by its own Strong's number's word (2026-10-27).

G2411 (the temple) was headed ἱερός, the adjective, because MACULA files it and
G2413 (sacred) under one lemma; G689 (Aram) was headed ἀδμίν, the first lemma
met, from one stray use; H1886 (Dothan) was headed by the suffix ה. Found by a
reader comparing the card with the lexicon. tools/audit_headwords.py counts
every disagreement between MACULA's lemmas and STEP's headwords; this holds the
rule that settles which one leads (server.headwords()):

  - known answers: G2411 ἱερόν (MACULA's ἱερός beside it, with G2413); G611
    ἀποκρίνομαι (Strong's ἀποκρίνω beside it, the deponent kept); G689 Ἀράμ;
    G5179 τύπος; H1886 Dothan
  - no two Greek cards share a headword, unless STEP heads them alike too
  - planted: a shared lemma, and a stray first lemma, must each be resolved

Reads MACULA through tools/structure.py; no server. Run: python tests/test_headwords.py"""
import collections
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app2"))
import audit_headwords as A  # noqa: E402
import server  # noqa: E402

N = lambda s: unicodedata.normalize("NFC", s or "")  # noqa: E731
# STEP's headwords come from its files or from data/raw/stepbible/lexicon.json (tools/fetch_lexicon.py builds it on
# the live server); without them the committed extract has 135 entries, the rule has nothing to lead with, and the
# cards keep MACULA's lemma (the public copy, where data/raw/ never travels)
if len(A.step_headwords()) < 10_000:
    print("headwords: skipped, STEP's lexicon is not on this machine (python tools/fetch_lexicon.py)")
    sys.exit(0)
fails = []
rows = {r["key"]: r for r in A.audit()}

KNOWN = {"g2411": ("ἱερόν", "ἱερός"), "g611": ("ἀποκρίνομαι", "ἀποκρίνω"), "g689": ("Ἀράμ", None),
         "g5179": ("τύπος", None), "h1886": ("דֹּתָן", None)}
for k, (lead, also) in KNOWN.items():
    r = rows.get(k)
    if not r:
        fails.append(f"{k}: not in the text")
        continue
    if N(r["card_leads"]) != N(lead):
        fails.append(f"{k}: headed {r['card_leads']}, expected {lead}")
    if also and N(r["card_also"]) != N(also):
        fails.append(f"{k}: lists {r['card_also']}, expected {also}")

leads = collections.defaultdict(list)
for k, r in rows.items():
    if k[0] == "g":
        leads[N(r["card_leads"])].append(k)
shared = {l: ks for l, ks in leads.items() if len(ks) > 1}
# where STEP itself heads the numbers alike (G680 "a Form of" G681, both ἅπτω),
# neither source tells them apart: listed, not failed
alike = {l: ks for l, ks in shared.items() if len({N(rows[k]["step"]) for k in ks}) == 1}
for l, ks in sorted(shared.items()):
    if l not in alike:
        fails.append(f"Greek cards sharing a headword: {l} {', '.join(sorted(ks))}")

# planted: g1 and g2 share MACULA's lemma, and STEP tells them apart; g3's first lemma is a stray
h = server.headwords({"g1": "ἱερός", "g2": "ἱερός", "g3": "τύπος"},
                     {"g1": "ἱερός", "g2": "ἱερός", "g3": "τυπικώς"},
                     {"g1": {"word": "ἱερόν"}, "g2": {"word": "ἱερός"}, "g3": {"word": "τύπος"}})
if (h.get("g1") or {}).get("lemma") != "ἱερόν":
    fails.append("planted: a shared lemma was not resolved to STEP's form")
if (h.get("g3") or {}).get("lemma") != "τύπος":
    fails.append("planted: a stray first lemma was not replaced by the commonest")

for f in fails:
    print("FAIL", f)
g = [r for r in rows.values() if r["key"][0] == "g"]
print(f"headwords: {len(KNOWN)} known answers, {len(g):,} Greek cards, "
      f"{sum(len(ks) for ks in alike.values())} sharing a headword STEP shares too "
      f"({'; '.join(l + ' ' + ', '.join(sorted(ks)) for l, ks in sorted(alike.items()))}), "
      f"{sum(1 for r in rows.values() if r['card_leads'] != r['was'])} headwords corrected; "
      f"planted faults caught: 2 of 2; {len(fails)} failures")
sys.exit(1 if fails else 0)
