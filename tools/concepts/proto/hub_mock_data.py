"""The data for the morning mockup of two concept hubs (love, righteousness).
Rows and counts come from the prototypes (love-who.json, hub-rows.json);
the example verses are ones read and confirmed by hand for the mockup. Every
quotation is the Berean's text for that verse, read from the data here."""
import json
from pathlib import Path

ROOT = Path(r"<local> Ontology")
HERE = Path(__file__).parent
V = {}
for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[f"{d['b']}.{d['c']}.{d['v']}"] = d["t"]
NAMES = {"Gen": "Genesis", "Lev": "Leviticus", "Deut": "Deuteronomy", "1Kgs": "1 Kings", "Ps": "Psalm",
         "Prov": "Proverbs", "Isa": "Isaiah", "Jer": "Jeremiah", "Amos": "Amos", "Hab": "Habakkuk",
         "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts", "Rom": "Romans",
         "1Cor": "1 Corinthians", "2Cor": "2 Corinthians", "Gal": "Galatians", "Eph": "Ephesians",
         "Phil": "Philippians", "Col": "Colossians", "1Thess": "1 Thessalonians", "2Tim": "2 Timothy",
         "Jas": "James", "1John": "1 John", "Mic": "Micah"}


def q(ref):
    b, c, v = ref.split(".")
    t = V[ref]
    return {"ref": f"{NAMES.get(b, b)} {c}:{v}", "id": ref, "text": t}


who = {r["row"]: r["n"] for r in json.loads((HERE / "love-who.json").read_text(encoding="utf-8"))}
rows = json.loads((HERE / "hub-rows.json").read_text(encoding="utf-8"))
nrow = lambda cid, name: next(r["n"] for r in rows[cid]["noun_rows"] if r["row"] == name)  # noqa: E731

love = {
 "name": "Love", "kind": "Concept",
 "intro": ["“But the greatest of these is love” (1 Corinthians 13:13): the text ranking its own terms. "
           "And of God himself, “God is love” (1 John 4:8).",
           "Older English translations say “charity” through 1 Corinthians 13 and “love” elsewhere, for the "
           "same Greek word, ἀγάπη."],
 "words": [["אָהֵב", "ʾāhēḇ", "to love", "Hebrew", 215], ["אַהֲבָה", "ʾahăḇāh", "love", "Hebrew", 34],
           ["ἀγαπάω", "agapaō", "to love", "Greek", 143], ["ἀγάπη", "agapē", "love", "Greek", 116],
           ["φιλέω", "phileō", "to love", "Greek", 21], ["ἀγαπητός", "agapētos", "beloved", "Greek", 61]],
 "themes": [["The Law", "You shall love the LORD your God"], ["The Law", "Love your neighbor as yourself"],
            ["Spirit", "The fruit of the Spirit is love"], ["Church", "Love one another"]],
 "own_words": [q(r) for r in ("1Cor.13.13", "1John.4.8", "John.3.16", "Deut.6.5", "Lev.19.18",
                              "John.13.34", "Matt.5.44", "Rom.5.8")],
 "sections": [
  {"form": "As a verb", "title": "Who loves whom",
   "note": "From the Hebrew and Greek grammar: who loves (the subject) and what is loved (the object). "
           "Counts are verses; each row opens all of them.",
   "rows": [
    ["The LORD loves", who["The LORD loves"], ["Deut.7.13", "Isa.43.4", "John.3.16", "John.3.35"]],
    ["Jesus loves", who["Jesus loves"], ["Mark.10.21", "John.11.5", "John.13.1", "John.15.9"]],
    ["Love the LORD your God", who["Love the LORD your God"], ["Deut.6.5", "Ps.97.10", "Matt.22.37", "1John.4.10"]],
    ["Love your neighbor", who["Love your neighbor"], ["Lev.19.18", "Matt.22.39", "Rom.13.9"]],
    ["Love one another", who["Love one another"], ["John.13.34", "John.15.12", "Rom.13.8", "1John.4.11"]],
    ["Love your enemies", who["Love your enemies"], ["Matt.5.44", "Luke.6.27", "Luke.6.35"]],
    ["Husbands and wives", who["Husbands and wives"], ["Eph.5.25", "Eph.5.28", "Col.3.19"]],
    ["Love the law, wisdom and what is right", who["Love the law, wisdom and what is right"],
     ["Ps.119.47", "Ps.119.97", "Ps.45.7"]],
    ["What the text warns against loving", who["What the text warns against loving"],
     ["John.3.19", "1John.2.15", "Luke.20.46"]],
   ]},
  {"form": "As a noun", "title": "What the text says love is",
   "rows": [["Said of love", None, ["1Cor.13.4", "1Cor.13.8", "1John.4.16", "1John.4.18", "Rom.13.10", "Col.3.14"]]]},
  {"form": "As a noun", "title": "Whose love",
   "note": "The text's own phrase, kept as written: where readers part on whether “the love of God” is God's "
           "love or love for God, the page does not choose.",
   "rows": [["The love of God", nrow("love", "The love of God"), ["Rom.5.5", "Rom.8.39", "1John.3.1", "1John.4.9"]],
            ["The love of Christ", nrow("love", "The love of Christ"), ["2Cor.5.14", "Eph.3.19", "Rom.8.35"]],
            ["Faith, hope and love", nrow("love", "Faith, hope and love"), ["1Cor.13.13", "1Thess.5.8", "Col.1.4"]]]},
  {"form": "As an adjective", "title": "Called “beloved”",
   "rows": [["Beloved", 61, ["Matt.3.17", "Rom.1.7", "1John.4.7"]]]},
 ],
 "gather": ["love of God toward man", "Love is patient", "love your neighbor as yourself",
            "Love one another (Church)", "love (a second record, once “charity”)"],
}
righteousness = {
 "name": "Righteousness", "kind": "Concept",
 "intro": ["‘with the breastplate of righteousness arrayed’ (Eph 6:14).",
           "The Bible mostly speaks of it as something reckoned rather than achieved: ‘Abram believed the LORD, and "
           "it was credited to him as righteousness.’ (Gen 15:6), a verse three New Testament writers return to. "
           "Whether that reckoning is a change in standing or in the person is among the oldest disputes about these "
           "texts, and the verses settle nothing."],
 "intro_flag": "The card's present introduction, unchanged. Flagged: the rows below count “do righteousness” 48 times "
               "and “justice and righteousness” 63, so “mostly reckoned rather than achieved” says more than the "
               "text does; for the nine readers.",
 "words": [["צְדָקָה", "ṣĕdāqāh", "righteousness", "Hebrew", 157], ["צֶדֶק", "ṣedeq", "righteousness", "Hebrew", 119],
           ["צַדִּיק", "ṣaddîq", "righteous", "Hebrew", 206], ["δικαιοσύνη", "dikaiosynē", "righteousness", "Greek", 91],
           ["δίκαιος", "dikaios", "righteous, just", "Greek", 79], ["δικαιόω", "dikaioō", "to justify", "Greek", 39]],
 "themes": [["Kingdom", "Righteousness and justice"], ["Wisdom Literature", "A throne is established through righteousness"],
            ["Deliverance / Salvation", "Justified"], ["The Law", "The law and the promise"]],
 "own_words": [q(r) for r in ("Gen.15.6", "Ps.89.14", "Amos.5.24", "Matt.5.6", "Matt.6.33", "Rom.1.17",
                              "2Cor.5.21", "Isa.64.6")],
 "sections": [
  {"form": "As a noun", "title": "What righteousness stands beside",
   "note": "From the Hebrew and Greek phrases: the words that stand with it. The noun leads here, as the text "
           "uses it most.",
   "rows": [
    ["Justice and righteousness", nrow("righteousness", "Justice and righteousness"), ["1Kgs.10.9", "Ps.89.14", "Isa.9.7", "Amos.5.24"]],
    ["Do righteousness", nrow("righteousness", "Do righteousness"), ["Gen.18.19", "Ps.106.3", "1John.3.7"]],
    ["The righteousness of the LORD, of God", nrow("righteousness", "The righteousness of the LORD, of God"),
     ["Ps.36.6", "Rom.1.17", "Rom.3.21", "Rom.3.22"]],
    ["Righteousness and faith", nrow("righteousness", "Righteousness by faith"), ["Gen.15.6", "Rom.4.13", "Phil.3.9"]],
    ["Seek, pursue, hunger for it", nrow("righteousness", "Seek, pursue, hunger for righteousness"),
     ["Deut.16.20", "Isa.51.1", "Matt.5.6", "Matt.6.33"], {"Deut.16.20": "The Hebrew is צֶדֶק, righteousness, twice: “righteousness, righteousness you shall pursue”; the Berean renders it “justice”."}],
   ]},
  {"form": "As an adjective", "title": "Who is called righteous",
   "rows": [["Called righteous", rows["righteousness"]["adj"]["n"],
             ["Gen.6.9", "Matt.1.19", "Luke.1.6", "Acts.10.22", "1John.2.1", "Hab.2.4"]],
            ["None is righteous", None, ["Rom.3.10", "Isa.64.6"]]]},
  {"form": "As a verb", "title": "Justified",
   "note": "Set side by side as the text has them; where Christian traditions part on how one is justified, "
           "the page takes no side.",
   "rows": [["By faith, by works", 38, ["Rom.3.28", "Jas.2.24", "Gal.2.16", "Rom.5.1", "Luke.18.14", "Matt.12.37"]]]},
 ],
 "gather": ["righteous", "the righteous (two records, one once “the just”)", "justification"],
}

DOORS = {
 "The LORD loves": ["God"], "Jesus loves": ["Jesus"], "Love the LORD your God": ["God", "the greatest commandment"],
 "Love your neighbor": ["neighbor", "the second commandment"], "Love one another": ["one another", "the new commandment"],
 "Love your enemies": ["enemies"], "Husbands and wives": ["marriage"], "Love the law, wisdom and what is right": ["the law", "wisdom"],
 "What the text warns against loving": ["the world", "money"], "Said of love": ["1 Corinthians 13"],
 "The love of God": ["God"], "The love of Christ": ["Christ"], "Faith, hope and love": ["faith", "hope"], "Beloved": ["the beloved Son"],
 "Justice and righteousness": ["justice"], "Do righteousness": ["obedience"], "The righteousness of the LORD, of God": ["God"],
 "Righteousness and faith": ["faith", "Abraham"], "Seek, pursue, hunger for it": ["the kingdom of God"],
 "Called righteous": ["the righteous"], "None is righteous": ["sin"], "By faith, by works": ["justification", "faith", "works"],
}
LEADS = {"love": ["God", "the commandments", "your neighbor", "one another", "enemies", "faith", "hope",
                  "the fruit of the Spirit", "Christ", "marriage"],
         "righteousness": ["God", "justice", "faith", "the law", "Abraham", "the kingdom of God", "the throne",
                           "justification", "the righteous", "sin"]}
for hub in (love, righteousness):
    for s in hub["sections"]:
        s["rows"] = [{"label": r[0], "doors": DOORS.get(r[0], []), "n": r[1], "eg": [dict(q(x), find=(r[3] if len(r) > 3 else {}).get(x)) for x in r[2]]} for r in s["rows"]]
love["leads"] = LEADS["love"]; righteousness["leads"] = LEADS["righteousness"]
data = {"love": love, "righteousness": righteousness}
(HERE / "hub-mock.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("ok", sum(len(r["eg"]) for h in data.values() for s in h["sections"] for r in s["rows"]), "quotations")
