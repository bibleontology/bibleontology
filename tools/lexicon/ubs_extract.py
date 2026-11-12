"""Extract the UBS Hebrew and Greek dictionaries into one record per Strong's number.

    python -X utf8 tools/lexicon/ubs_extract.py hebrew|greek IN.json OUT.jsonl [version]

The acceptance test is tests/test_ubs_extract.py. Python 3.9, standard library only.
"""
import json
import re
import sys

BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam",
    "1Kgs", "2Kgs", "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov",
    "Eccl", "Song", "Isa", "Jer", "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos",
    "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal",
    "Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph",
    "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas",
    "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev",
]

LANG_LETTERS = {"hebrew": "h", "greek": "g"}

_DIGITS = re.compile(r"[0-9]+")


def lang_letter(lang):
    lang = (lang or "").strip().lower()
    return LANG_LETTERS.get(lang, lang[:1])


def ref_of(code):
    """"00100202400012" -> "Gen.2.24"; None for a malformed code or a book outside 1-66."""
    if not isinstance(code, str):
        return None
    code = code.strip()
    if len(code) != 14 or not code.isascii() or not code.isdigit():
        return None
    book = int(code[0:3])
    if not 1 <= book <= 66:
        return None
    return "%s.%d.%d" % (BOOKS[book - 1], int(code[3:6]), int(code[6:9]))


def keys_of(entry, lang):
    """"H0001"/"A0004" -> ["h1", "h4"], "G0026" -> ["g26"], bare "2062" -> ["h2062"], sorted, deduplicated."""
    letter = lang_letter(lang)
    keys = set()
    for raw in entry.get("StrongCodes") or []:
        if not isinstance(raw, str):
            continue
        code = raw.strip()
        if not code:
            continue
        if code[0].isalpha():
            code = code[1:]
        match = _DIGITS.match(code)
        if match:
            keys.add(letter + str(int(match.group(0))))
    return sorted(keys)


def _domains(meaning):
    out = []
    for domain in meaning.get("LEXDomains") or []:
        if isinstance(domain, dict):
            out.append({"code": domain.get("DomainCode"), "label": domain.get("Domain")})
    return out


def _refs(meaning):
    out = []
    for raw in meaning.get("LEXReferences") or []:
        ref = ref_of(raw)
        if ref is not None:
            out.append(ref)
    return out


def _senses(meaning, domains, refs):
    out = []
    for sense in meaning.get("LEXSenses") or []:
        if not isinstance(sense, dict):
            continue
        if sense.get("LanguageCode") != "en":
            continue
        if sense.get("AIGenerated") or sense.get("HumanCheckRecommended"):
            continue
        glosses = sense.get("Glosses")
        out.append({
            "domains": [dict(d) for d in domains],
            "short": sense.get("DefinitionShort", ""),
            "long": sense.get("DefinitionLong", ""),
            "glosses": list(glosses) if isinstance(glosses, list) else [],
            "refs": list(refs),
        })
    return out


def extract(entries, lang, version):
    """Turn a UBS dictionary into key -> {"key", "lemma", "source", "version", "senses"}."""
    result = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        keys = keys_of(entry, lang)
        if not keys:
            continue
        senses = []
        for base in entry.get("BaseForms") or []:
            if not isinstance(base, dict):
                continue
            for meaning in base.get("LEXMeanings") or []:
                if not isinstance(meaning, dict):
                    continue
                senses.extend(_senses(meaning, _domains(meaning), _refs(meaning)))
        for key in keys:
            record = result.get(key)
            if record is None:
                record = {"key": key, "lemma": entry.get("Lemma", ""), "source": "ubs-" + lang,
                          "version": version, "senses": []}
                result[key] = record
            record["senses"].extend(senses)
    return result


def domain_index(extracted):
    """Domain code -> {"label", "words": sorted keys whose kept senses carry it}."""
    index = {}
    for key in sorted(extracted):
        for sense in extracted[key].get("senses") or []:
            for domain in sense.get("domains") or []:
                code = domain.get("code")
                if code is None:
                    continue
                record = index.setdefault(code, {"label": domain.get("label"), "words": []})
                if key not in record["words"]:
                    record["words"].append(key)
    for record in index.values():
        record["words"].sort()
    return index


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) < 3:
        sys.stderr.write("usage: ubs_extract.py hebrew|greek IN.json OUT.jsonl [version]\n")
        return 2
    lang, in_path, out_path = argv[0], argv[1], argv[2]
    version = argv[3] if len(argv) > 3 else ""
    with open(in_path, encoding="utf-8") as handle:
        entries = json.load(handle)
    extracted = extract(entries, lang, version)
    # newline="\n": the server rebuilds this file and checks it against a pinned hash, so its bytes must not depend on
    # the platform (on Windows the default wrote CRLF, and the hash pinned there never matched on Linux, 2026-11-05)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        for key in sorted(extracted):
            handle.write(json.dumps(extracted[key], ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
