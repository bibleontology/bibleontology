"""THE SOUND OF A HEBREW WORD PART, IN MACULA'S OWN SCHEME (P-2026-11-15-6, 2026-11-15).

MACULA gives no `transliteration` to the parts of a word a suffix splits (לְמִינוֹ: לְ "lə", then מִינ and וֹ with
none), and tools/interlinear.py fell back to its Greek transliterator, which on Hebrew keeps the bare consonants:
48,624 of 304,655 Hebrew words (16%) showed Hebrew letters as their sound, in 18,315 of 23,213 verses. This fills
exactly those parts, at the interlinear's load (app2/server.py), and nothing MACULA transliterated itself.

The rules were read off MACULA's own 372,548 transliterated parts and benched against them: 97.6% exact overall,
97.1% on parts that follow another part of their word (the kind it leaves blank). Most of the rest is MACULA
disagreeing with itself (šāmaʿətā and šāmaʿtā for one pattern).

Rules read off MACULA's own transliterations (bench: every part MACULA does transliterate):
  - begadkefat letters soften without a dagesh (ḇ ḡ ḏ ḵ p̄ ṯ); a dagesh after a sounded vowel doubles the letter,
    including across a prefix of the same word (haš-šāmayim -> "ššāmayim" for the part after the article);
  - shewa: written (ə) under a part's first letter, after a long vowel or a meteg, and before a letter that has no
    vowel of its own; dropped after a short vowel before a pointed letter, and at the end of a word;
  - a vowel letter (yod after hireq or tsere, he after qamets or segol at the end, vav with holem) is written
    contracted (î, ê, â, ô) unless the stress accent sits on that syllable, where MACULA writes vowel and letter (iy);
  - patah under a final guttural is furtive (ᵃʿ) unless the accent sits on the guttural.

    python -X utf8 app2/hebrew_sound.py bench    -> agreement with MACULA, and the commonest misses
"""
import collections
import gzip
import json
import re
import sys
import unicodedata

CONS = {"א": "ʾ", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "w", "ז": "z", "ח": "ḥ", "ט": "ṭ", "י": "y",
        "כ": "k", "ך": "k", "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "ʿ", "פ": "p",
        "ף": "p", "צ": "ṣ", "ץ": "ṣ", "ק": "q", "ר": "r", "ש": "š", "ת": "t"}
SPIRANT = {"b": "ḇ", "g": "ḡ", "d": "ḏ", "k": "ḵ", "p": "p̄", "t": "ṯ"}
SHEWA, HPATAH, HSEGOL, HQAMETS = "ְ", "ֲ", "ֱ", "ֳ"
HIREQ, TSERE, SEGOL, PATAH, QAMETS, HOLEM, HOLEM_HASER, QUBUTS = ("ִ", "ֵ", "ֶ", "ַ", "ָ",
                                                                 "ֹ", "ֺ", "ֻ")
DAGESH, METEG, SHIN_DOT, SIN_DOT, QAMATS_Q = "ּ", "ֽ", "ׁ", "ׂ", "ׇ"
VOWEL = {PATAH: "a", QAMETS: "ā", QAMATS_Q: "o", SEGOL: "e", TSERE: "ē", HIREQ: "i", HOLEM: "ō", HOLEM_HASER: "ō",
         QUBUTS: "u", HPATAH: "ă", HSEGOL: "ĕ", HQAMETS: "ŏ"}
OFFSYLLABLE = set("֚֭֮֙֒֩֠")   # pre- and postpositive accents
LONG = {"ā", "ē", "ō", "î", "ê", "â", "ô", "û"}
CONTRACT = {("i", "y"): "î", ("ē", "y"): "ê", ("e", "y"): "ê", ("ā", "h"): "â"}   # segol-he stays "eh"


def clusters(text):
    """[consonant, marks, accented] for the pointed text; maqaf kept as its own cluster."""
    out = []
    for ch in text:
        if ch in CONS:
            out.append([ch, [], False, False])
        elif ch == "־":
            out.append(["-", [], False, False])
        elif not out and unicodedata.combining(ch) and "ְ" <= ch <= "ׇ":
            out.append(["", [ch], False, False])          # a part that starts with its vowel (a suffix: ָא, ֔וֹ)
        elif out and "֑" <= ch <= "֯":
            out[-1][3] = True                              # any accent
            if ch not in OFFSYLLABLE:
                out[-1][2] = True                          # an accent on the stressed syllable
        elif out and unicodedata.combining(ch) and "ְ" <= ch <= "ׇ":
            out[-1][1].append(ch)
            if ch == METEG:
                out[-1][2] = True                          # meteg and silluq mark the syllable too
    return out


def translit_hebrew(text, prev_vowel=False, after_part=False, followed=False):
    """The sound of one MACULA word part. `prev_vowel`: the part before it in the same word ends in a vowel;
    `after_part`: there is such a part (a suffix's וֹ after a consonant is "ô": lə-mîn-ô); `followed`: another part
    of the same word comes after it, so its last letter takes that part's vowel (זַרְע + וֹ is zarʿô, not zarəʿ)."""
    cl = clusters(text)
    if "".join(c[0] for c in cl) == "יהוה":
        if SHEWA not in cl[0][1]:
            return "yhw" + "".join(VOWEL[m] for m in cl[2][1] if m in VOWEL) + "h"
        return "yəhwāh" if cl[2][2] else "yhwh"
    res = []
    skip = set()
    for i, (c, marks, acc, acc_any) in enumerate(cl):
        if i in skip:
            continue
        if c == "":
            res.append("".join(VOWEL[m] for m in marks if m in VOWEL))
            prev_vowel = True
            continue
        if c == "-":
            res.append("-")
            prev_vowel = False
            continue
        ms = set(marks)
        nxt = cl[i + 1] if i + 1 < len(cl) and cl[i + 1][0] != "-" else None
        last = nxt is None
        # vav as a vowel: shureq and holem-vav
        if c == "ו" and DAGESH in ms and not (ms & set(VOWEL)) and SHEWA not in ms and (i == 0 or not prev_vowel):
            res.append("û")
            prev_vowel = True
            continue
        if c == "ו" and HOLEM in ms and not (ms - {HOLEM, METEG}) & set(VOWEL) and (i > 0 or after_part)                 and not prev_vowel:
            res.append("ô")
            prev_vowel = True
            continue
        base = "ś" if (c == "ש" and SIN_DOT in ms) else CONS[c]
        if c == "ה" and DAGESH in ms and last:
            base = "ẖ"                                     # the mappiq: a final he that is sounded (ʿāśāẖ)
        if base in SPIRANT:
            # doubled inside a part after a vowel (ʾattāh, dibbēr), never at a part's start (bayiṯ after the article)
            cons = (base + base if prev_vowel and i > 0 else base) if DAGESH in ms else SPIRANT[base]
        else:
            cons = base + base if (DAGESH in ms and (prev_vowel or i == 0) and c not in "הא") else base
        if PATAH in ms and last and c in "חעה" and i > 0 and not acc_any:
            res.append("ᵃ" + cons)
            prev_vowel = False
            continue
        v = "".join(VOWEL[m] for m in marks if m in VOWEL)
        # qamets hatuf: a closed, unstressed syllable before a maqaf (כָּל־ kol)
        if v == "ā" and not acc and nxt and not nxt[1] and i + 2 < len(cl) and cl[i + 2][0] == "-":
            v = "o"
        # a vowel letter after the vowel: contracted unless the accent is on this syllable
        if v and nxt and not nxt[1] and not acc:
            letter = CONS.get(nxt[0])
            key = (v, letter)
            final_he = letter == "h" and i + 1 == len(cl) - 1
            he_marked = final_he and nxt[3]                 # a postpositive accent on the he: šānāh, bəhēmāh
            if key in CONTRACT and (letter == "y" or (final_he and not he_marked)):
                res.append(cons + CONTRACT[key])
                skip.add(i + 1)
                prev_vowel = True
                continue
        if SHEWA in ms and not v:
            if i == 0 and len(cl) == 1:
                v = "" if (c == "כ" and DAGESH not in ms) else "ə"   # a prefix part: bə, wə, lə; but ḵ
            elif last:
                v = "ə" if (c == "ך" and acc_any) else ""  # silent (ḥōšeḵ), but written under an accented final kaf (ḥănôḵə)
            else:
                pv = "".join(res).rstrip("ʾ")[-1:]               # a quiescent aleph hides nothing: yōʾmərû
                prev_long = (pv in LONG) or (i > 0 and METEG in cl[i - 1][1])
                after = cl[i + 2] if i + 2 < len(cl) else None
                vav_vowel = bool(after and after[0] == "ו" and (DAGESH in after[1] or HOLEM in after[1])
                                 and not set(after[1]) & (set(VOWEL) - {HOLEM}))
                nxt_pointed = (bool(set(nxt[1]) & (set(VOWEL) | {SHEWA, HOLEM})) or (nxt[0] == "ו" and DAGESH in nxt[1])
                               or vav_vowel                       # šimʿû: the vowel is the vav after
                               or (followed and i + 1 == len(cl) - 1))     # zarʿô: the vowel is in the next part
                before_ti = (nxt[0] == "ת" and DAGESH in nxt[1] and HIREQ in nxt[1] and after is not None
                             and after[0] == "י" and i + 2 == len(cl) - 1)        # the perfect's -tî: šāmaʿətî
                by_yod = c == "י"                                 # layəlâ
                silent = (i > 0 and not prev_long and nxt_pointed and DAGESH not in ms and not before_ti
                          and not by_yod)
                v = "" if silent else "ə"
        res.append(cons + v)
        prev_vowel = bool(v) and v != "ə"
    return "".join(res)


def norm(x):
    return unicodedata.normalize("NFC", (x or "").strip().rstrip(":"))


def bench(n_show=30):
    heb = re.compile("[֐-׿]")
    tot = ok = 0
    tot2 = ok2 = 0
    miss = collections.Counter()
    ex = collections.defaultdict(list)
    for line in gzip.open("out/interlinear.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        ws = d.get("words", [])
        for j, w in enumerate(ws):
            t, x = w.get("t") or "", norm(w.get("x"))
            if not heb.search(t) or not x or heb.search(x):
                continue
            prev = ws[j - 1] if j else None
            pv = bool(prev and prev.get("w") == w.get("w") and re.search(r"[aeiouāēīōūăĕŏâêîôûə]$", norm(prev.get("x"))))
            tot += 1
            y = norm(translit_hebrew(t, pv))
            later = bool(prev and prev.get("w") == w.get("w"))
            tot2 += later
            if y == x:
                ok += 1
                ok2 += later
            else:
                # the first place they differ, as a pattern
                k = next((n for n in range(min(len(x), len(y))) if x[n] != y[n]), min(len(x), len(y)))
                pat = (x[max(0, k - 1):k + 2], y[max(0, k - 1):k + 2])
                miss[pat] += 1
                if len(ex[pat]) < 2:
                    ex[pat].append((d["ref"], t, x, y))
    print(f"{ok:,} of {tot:,} exact ({ok / tot:.1%}); parts after another part of their word: "
          f"{ok2:,} of {tot2:,} ({ok2 / tot2:.1%})")
    for pat, n in miss.most_common(n_show):
        print(f"{n:6,}  macula {pat[0]!r:10} ours {pat[1]!r:10}", *ex[pat][0])


if __name__ == "__main__":
    if sys.argv[1:] == ["bench"]:
        bench()
    else:
        for a in sys.argv[1:]:
            print(a, translit_hebrew(a))
