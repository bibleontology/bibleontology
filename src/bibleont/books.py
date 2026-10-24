"""Canonical book identifiers and name normalization.

Book ids follow the common OSIS-style abbreviations so that references are
short, stable, and recognizable ("Gen 5:3", "1Sam 16:13").
"""

from __future__ import annotations

# (source name in KJV.json, book id, display name, testament, canonical order)
BOOKS: list[tuple[str, str, str, str]] = [
    ("Genesis", "Gen", "Genesis", "OT"),
    ("Exodus", "Exod", "Exodus", "OT"),
    ("Leviticus", "Lev", "Leviticus", "OT"),
    ("Numbers", "Num", "Numbers", "OT"),
    ("Deuteronomy", "Deut", "Deuteronomy", "OT"),
    ("Joshua", "Josh", "Joshua", "OT"),
    ("Judges", "Judg", "Judges", "OT"),
    ("Ruth", "Ruth", "Ruth", "OT"),
    ("I Samuel", "1Sam", "1 Samuel", "OT"),
    ("II Samuel", "2Sam", "2 Samuel", "OT"),
    ("I Kings", "1Kgs", "1 Kings", "OT"),
    ("II Kings", "2Kgs", "2 Kings", "OT"),
    ("I Chronicles", "1Chr", "1 Chronicles", "OT"),
    ("II Chronicles", "2Chr", "2 Chronicles", "OT"),
    ("Ezra", "Ezra", "Ezra", "OT"),
    ("Nehemiah", "Neh", "Nehemiah", "OT"),
    ("Esther", "Esth", "Esther", "OT"),
    ("Job", "Job", "Job", "OT"),
    ("Psalms", "Ps", "Psalms", "OT"),
    ("Proverbs", "Prov", "Proverbs", "OT"),
    ("Ecclesiastes", "Eccl", "Ecclesiastes", "OT"),
    ("Song of Solomon", "Song", "Song of Solomon", "OT"),
    ("Isaiah", "Isa", "Isaiah", "OT"),
    ("Jeremiah", "Jer", "Jeremiah", "OT"),
    ("Lamentations", "Lam", "Lamentations", "OT"),
    ("Ezekiel", "Ezek", "Ezekiel", "OT"),
    ("Daniel", "Dan", "Daniel", "OT"),
    ("Hosea", "Hos", "Hosea", "OT"),
    ("Joel", "Joel", "Joel", "OT"),
    ("Amos", "Amos", "Amos", "OT"),
    ("Obadiah", "Obad", "Obadiah", "OT"),
    ("Jonah", "Jonah", "Jonah", "OT"),
    ("Micah", "Mic", "Micah", "OT"),
    ("Nahum", "Nah", "Nahum", "OT"),
    ("Habakkuk", "Hab", "Habakkuk", "OT"),
    ("Zephaniah", "Zeph", "Zephaniah", "OT"),
    ("Haggai", "Hag", "Haggai", "OT"),
    ("Zechariah", "Zech", "Zechariah", "OT"),
    ("Malachi", "Mal", "Malachi", "OT"),
    ("Matthew", "Matt", "Matthew", "NT"),
    ("Mark", "Mark", "Mark", "NT"),
    ("Luke", "Luke", "Luke", "NT"),
    ("John", "John", "John", "NT"),
    ("Acts", "Acts", "Acts", "NT"),
    ("Romans", "Rom", "Romans", "NT"),
    ("I Corinthians", "1Cor", "1 Corinthians", "NT"),
    ("II Corinthians", "2Cor", "2 Corinthians", "NT"),
    ("Galatians", "Gal", "Galatians", "NT"),
    ("Ephesians", "Eph", "Ephesians", "NT"),
    ("Philippians", "Phil", "Philippians", "NT"),
    ("Colossians", "Col", "Colossians", "NT"),
    ("I Thessalonians", "1Thess", "1 Thessalonians", "NT"),
    ("II Thessalonians", "2Thess", "2 Thessalonians", "NT"),
    ("I Timothy", "1Tim", "1 Timothy", "NT"),
    ("II Timothy", "2Tim", "2 Timothy", "NT"),
    ("Titus", "Titus", "Titus", "NT"),
    ("Philemon", "Phlm", "Philemon", "NT"),
    ("Hebrews", "Heb", "Hebrews", "NT"),
    ("James", "Jas", "James", "NT"),
    ("I Peter", "1Pet", "1 Peter", "NT"),
    ("II Peter", "2Pet", "2 Peter", "NT"),
    ("I John", "1John", "1 John", "NT"),
    ("II John", "2John", "2 John", "NT"),
    ("III John", "3John", "3 John", "NT"),
    ("Jude", "Jude", "Jude", "NT"),
    ("Revelation of John", "Rev", "Revelation", "NT"),
]

SOURCE_NAME_TO_ID = {src: bid for src, bid, _, _ in BOOKS}
BOOK_IDS = [bid for _, bid, _, _ in BOOKS]
BOOK_ORDER = {bid: i + 1 for i, bid in enumerate(BOOK_IDS)}
BOOK_TITLE = {bid: title for _, bid, title, _ in BOOKS}
BOOK_TESTAMENT = {bid: t for _, bid, _, t in BOOKS}

# Aliases people (and models) actually type. Keys are lowercased with all
# spaces and periods stripped.
_EXTRA_ALIASES = {
    "gen": "Gen", "ge": "Gen", "gn": "Gen",
    "ex": "Exod", "exo": "Exod", "exod": "Exod",
    "lev": "Lev", "lv": "Lev",
    "num": "Num", "nu": "Num", "nm": "Num",
    "deut": "Deut", "dt": "Deut", "deu": "Deut",
    "josh": "Josh", "jos": "Josh",
    "judg": "Judg", "jdg": "Judg", "jg": "Judg",
    "rth": "Ruth", "ru": "Ruth",
    "1sa": "1Sam", "1sam": "1Sam", "1samuel": "1Sam", "isamuel": "1Sam", "isam": "1Sam",
    "2sa": "2Sam", "2sam": "2Sam", "2samuel": "2Sam", "iisamuel": "2Sam", "iisam": "2Sam",
    "1ki": "1Kgs", "1kgs": "1Kgs", "1kings": "1Kgs", "ikings": "1Kgs",
    "2ki": "2Kgs", "2kgs": "2Kgs", "2kings": "2Kgs", "iikings": "2Kgs",
    "1ch": "1Chr", "1chr": "1Chr", "1chron": "1Chr", "1chronicles": "1Chr", "ichronicles": "1Chr",
    "2ch": "2Chr", "2chr": "2Chr", "2chron": "2Chr", "2chronicles": "2Chr", "iichronicles": "2Chr",
    "ezr": "Ezra",
    "neh": "Neh", "ne": "Neh",
    "est": "Esth", "esth": "Esth", "esther": "Esth",
    "jb": "Job",
    "ps": "Ps", "psa": "Ps", "psalm": "Ps", "psalms": "Ps", "pss": "Ps",
    "pr": "Prov", "prov": "Prov", "prv": "Prov",
    "ec": "Eccl", "eccl": "Eccl", "eccles": "Eccl", "qoh": "Eccl",
    "so": "Song", "sos": "Song", "song": "Song", "songofsongs": "Song", "canticles": "Song",
    "isa": "Isa", "is": "Isa",
    "jer": "Jer", "je": "Jer",
    "lam": "Lam", "la": "Lam",
    "ezek": "Ezek", "eze": "Ezek", "ezk": "Ezek",
    "dan": "Dan", "dn": "Dan",
    "hos": "Hos", "ho": "Hos",
    "jl": "Joel",
    "am": "Amos",
    "obad": "Obad", "ob": "Obad",
    "jon": "Jonah", "jnh": "Jonah",
    "mic": "Mic", "mi": "Mic",
    "nah": "Nah", "na": "Nah",
    "hab": "Hab",
    "zeph": "Zeph", "zep": "Zeph",
    "hag": "Hag", "hg": "Hag",
    "zech": "Zech", "zec": "Zech",
    "mal": "Mal",
    "mt": "Matt", "matt": "Matt", "mat": "Matt",
    "mk": "Mark", "mr": "Mark",
    "lk": "Luke", "luk": "Luke",
    "jn": "John", "joh": "John",
    "ac": "Acts", "act": "Acts",
    "rom": "Rom", "ro": "Rom",
    "1co": "1Cor", "1cor": "1Cor", "1corinthians": "1Cor", "icorinthians": "1Cor",
    "2co": "2Cor", "2cor": "2Cor", "2corinthians": "2Cor", "iicorinthians": "2Cor",
    "gal": "Gal", "ga": "Gal",
    "eph": "Eph",
    "phil": "Phil", "php": "Phil", "philippians": "Phil",
    "col": "Col",
    "1th": "1Thess", "1thess": "1Thess", "1thes": "1Thess", "1thessalonians": "1Thess",
    "2th": "2Thess", "2thess": "2Thess", "2thes": "2Thess", "2thessalonians": "2Thess",
    "1ti": "1Tim", "1tim": "1Tim", "1timothy": "1Tim",
    "2ti": "2Tim", "2tim": "2Tim", "2timothy": "2Tim",
    "tit": "Titus", "ti": "Titus",
    "phlm": "Phlm", "phm": "Phlm", "philem": "Phlm", "philemon": "Phlm",
    "heb": "Heb",
    "jas": "Jas", "jam": "Jas", "james": "Jas",
    "1pe": "1Pet", "1pet": "1Pet", "1peter": "1Pet", "ipeter": "1Pet",
    "2pe": "2Pet", "2pet": "2Pet", "2peter": "2Pet", "iipeter": "2Pet",
    "1jn": "1John", "1joh": "1John", "1john": "1John", "ijohn": "1John",
    "2jn": "2John", "2joh": "2John", "2john": "2John", "iijohn": "2John",
    "3jn": "3John", "3joh": "3John", "3john": "3John", "iiijohn": "3John",
    "jud": "Jude", "jde": "Jude",
    "rev": "Rev", "re": "Rev", "apoc": "Rev", "apocalypse": "Rev",
    "revelationofjohn": "Rev", "revelations": "Rev",
}


def _key(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "").replace("_", "")


_ALIASES: dict[str, str] = {}
for _src, _bid, _title, _t in BOOKS:
    _ALIASES[_key(_src)] = _bid
    _ALIASES[_key(_bid)] = _bid
    _ALIASES[_key(_title)] = _bid
_ALIASES.update(_EXTRA_ALIASES)


def resolve_book(name: str) -> str | None:
    """Return the canonical book id for a book name/abbreviation, or None."""
    return _ALIASES.get(_key(name))
