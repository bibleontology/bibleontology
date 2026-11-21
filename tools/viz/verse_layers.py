"""VERSES HAND-SELECTED BY THE SITE MAKER, EACH DRAWN IN LAYERS (plan A.56; Doug, 2026-11-15: "Show the verse in
original language where each word shows phonic ... and English as is a word link and show the Berean and show the
diagram"; "create a selector on the verse diagram page").

One page, one section per verse, a selector between them. Each section:
  1. the original language, each word with its sound and English under it and a link to its card (the words, sounds,
     glosses and card keys are the site's own verse card, /api/verse-card, read from a running local server);
  2. the Berean, each clause underlined in its part's color;
  3. the diagram of the verse's nesting and dependencies, drawn by hand from the verse's grammar; tapping a part lights
     its words in both layers above;
  4. the verse in the graph: the cards it names, the editors' pointers, what the graph sets beside it.

The diagrams take no position on what readers debate; where the grammar itself is debated (Eph 2:8's "this") the
note says so. Approved verse by verse (2026-11-15) and served at /visual/verses as one of Explore's views; a copy
stays in docs/review/mockups/ for review.

    python tools/viz/verse_layers.py      (a local server on :8002)  -> app2/static/visual/verses.html and the review copy
"""
import html
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = "http://localhost:8002"
SITE = "https://bibleontology.org"
OUT = ROOT / "docs" / "review" / "mockups" / "verse-layers.html"
SERVED = ROOT / "app2" / "static" / "visual" / "verses.html"
TITLE = "Verses hand-selected by the site maker, drawn in layers"
DESC = ("Five verses hand-selected by the site maker, each in three layers: the Greek or Hebrew word by word, with its "
        "sound, its English and a link to its word card; the Berean; and a diagram of how the verse is built, whose "
        "parts light their words above. John 3:16, Ephesians 2:8-9, Romans 12:2, John 15:5 and Isaiah 52:7.")
GK = '"Gentium Plus","Palatino Linotype",Palatino,"Noto Serif","Times New Roman",serif'
HE = '"SBL Hebrew","Ezra SIL","Noto Serif Hebrew","Times New Roman",serif'   # the site's own Hebrew stack
COLOR = {"basis": "var(--basis)", "action": "var(--action)", "cond": "var(--cond)", "not": "var(--mute)",
         "life": "var(--life)"}


def verse_words(ref):
    with urllib.request.urlopen(f"{LOCAL}/api/verse-card?ref={ref}", timeout=120) as r:
        d = json.load(r)
    # a transliteration that holds Hebrew letters is a fault in the source (Isa 52:7's אלהיך): shown blank, not wrong
    heb = lambda s: any("֐" <= ch <= "׿" for ch in s or "")  # noqa: E731
    return [{"t": w["t"], "x": "" if heb(w.get("x")) else (w.get("x") or ""), "g": w.get("g") or "",
             "card": w.get("card"), "lemma": w.get("lemma")} for w in d["words"]]


def gk(text, size=14, italic=True, fill="var(--mute)"):
    font = HE if any("֐" <= ch <= "׿" for ch in text) else GK
    italic = italic and font == GK                       # Hebrew is never set in italic
    # single quotes inside the style attribute: GK's double quotes ended the attribute and the font fell back (the
    # first render: detached accents in the diagram boxes)
    return (f'<tspan style="font-family:{font.replace(chr(34), chr(39))};font-size:{size}px;{"font-style:italic;" if italic else ""}'
            f'fill:{fill}">{html.escape(text)}</tspan>')


def box(x, y, w, h, kind, label, english, greek, dashed=False, struck=False, path=None):
    col = COLOR[kind]
    shape = (f'<path d="{path}" fill="none" stroke="{col}" stroke-width="2"/>' if path else
             f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="{col}" stroke-width="2"'
             f'{" stroke-dasharray=\"6 5\"" if dashed else ""}/>')
    cx = x + w / 2
    eng = (f'<text x="{cx}" y="{y + 48}" text-anchor="middle" style="font:20px Georgia;fill:'
           f'{"var(--mute)" if struck else "var(--ink)"}{";text-decoration:line-through" if struck else ""}">'
           f'{html.escape(english)}</text>')
    return (f'<g class="node" data-c="{{G}}">{shape}'
            f'<text x="{cx}" y="{y + 22}" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.12em;'
            f'fill:{col}">{label}</text>{eng}'
            f'<text x="{cx}" y="{y + 68}" text-anchor="middle">{gk(greek)}</text></g>')


def node(group, *a, **k):
    return box(*a, **k).replace("{G}", group)


ARROW = ('<defs><marker id="ar-{id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="var(--mute)" stroke-width="1.6"/></marker></defs>')


def eph_svg():
    """Ephesians 2:8-9: grace and the gift of God as the source, faith as the channel, being saved as the state that
    stands, "not from yourselves" and "not by works" struck, and the purpose under it all."""
    a = ARROW.replace("{id}", "eph")
    m = 'marker-end="url(#ar-eph)"'
    parts = [
        '<text x="210" y="26" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.14em;fill:var(--mute)">WHERE IT COMES FROM</text>',
        '<text x="790" y="26" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.14em;fill:var(--mute)">NOT FROM HERE</text>',
        node("grace", 60, 40, 300, 80, "basis", "THE SOURCE", "by grace", "τῇ γὰρ χάριτί"),
        node("notyou", 640, 40, 300, 80, "not", "AND THIS · NOT", "from yourselves", "καὶ τοῦτο οὐκ ἐξ ὑμῶν",
             dashed=True, struck=True),
        # grace through faith to being saved
        f'<path d="M210 122 C210 180 300 190 340 214" fill="none" stroke="var(--cond)" stroke-width="2.4" {m}/>',
        node("faith", 150, 160, 190, 46, "cond", "", "", "").replace(
            'rx="10"', 'rx="23"'),
        node("saved", 350, 220, 300, 84, "action", "THE STATE · DONE, AND IT STANDS", "you have been saved",
             "ἐστε σεσῳσμένοι"),
        node("gift", 60, 380, 300, 84, "basis", "IT IS", "the gift of God", "Θεοῦ τὸ δῶρον"),
        f'<path d="M210 378 C210 330 300 300 346 284" fill="none" stroke="var(--basis)" stroke-width="2" stroke-dasharray="5 4" {m}/>',
        node("notworks", 640, 380, 300, 84, "not", "NOT", "by works", "οὐκ ἐξ ἔργων", dashed=True, struck=True),
        # the struck paths stop short of being saved
        '<path d="M790 122 C790 190 720 230 690 248" fill="none" stroke="var(--mute)" stroke-width="1.6" stroke-dasharray="5 5"/>',
        '<line x1="672" y1="236" x2="700" y2="262" stroke="var(--mute)" stroke-width="3"/><line x1="700" y1="236" x2="672" y2="262" stroke="var(--mute)" stroke-width="3"/>',
        '<path d="M790 378 C790 330 720 300 690 290" fill="none" stroke="var(--mute)" stroke-width="1.6" stroke-dasharray="5 5"/>',
        '<line x1="672" y1="278" x2="700" y2="304" stroke="var(--mute)" stroke-width="3"/><line x1="700" y1="278" x2="672" y2="304" stroke="var(--mute)" stroke-width="3"/>',
        f'<line x1="500" y1="306" x2="500" y2="500" stroke="var(--mute)" stroke-width="1.6" {m}/>',
        f'<text x="514" y="488" style="font:13px system-ui;fill:var(--mute)">{gk("ἵνα", 14, False, "var(--ink)")} so that: what it is for</text>',
        node("boast", 350, 504, 300, 84, "life", "THE PURPOSE", "no one can boast", "ἵνα μή τις καυχήσηται"),
    ]
    svg = "".join(parts)
    # the faith pill carries its own two lines (the generic box puts a label row first)
    svg = svg.replace('<g class="node" data-c="faith"><rect x="150" y="160" width="190" height="46" rx="23" fill="none" '
                      'stroke="var(--cond)" stroke-width="2"/>'
                      '<text x="245.0" y="182" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.12em;'
                      'fill:var(--cond)"></text><text x="245.0" y="208" text-anchor="middle" style="font:20px Georgia;'
                      'fill:var(--ink)"></text><text x="245.0" y="228" text-anchor="middle">'
                      f'{gk("")}</text></g>',
                      '<g class="node" data-c="faith"><rect x="150" y="160" width="190" height="46" rx="23" fill="var(--bg)" '
                      'stroke="var(--cond)" stroke-width="2"/>'
                      '<text x="245" y="181" text-anchor="middle" style="font:17px Georgia;fill:var(--ink)">through faith</text>'
                      f'<text x="245" y="199" text-anchor="middle">{gk("διὰ πίστεως", 13)}</text></g>')
    return f'<svg viewBox="0 0 1000 600" role="img" aria-label="The logic of Ephesians 2:8-9">{a}{svg}</svg>'


def _arrow(x1, y1, x2, y2, mid, color="var(--mute)", w=1.6, dash=""):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"'
            f'{" stroke-dasharray=" + chr(34) + dash + chr(34) if dash else ""} marker-end="url(#ar-{mid})"/>')


def _xmark(x, y):
    return (f'<line x1="{x - 14}" y1="{y - 13}" x2="{x + 14}" y2="{y + 13}" stroke="var(--mute)" stroke-width="3"/>'
            f'<line x1="{x + 14}" y1="{y - 13}" x2="{x - 14}" y2="{y + 13}" stroke="var(--mute)" stroke-width="3"/>')


def rom_svg():
    """Romans 12:2: two ways to be shaped, the one refused (conformed to this age) and the one commanded (transformed),
    its means (the renewing of the mind), its result (to test and approve), and what is found (God's will: good,
    pleasing, perfect)."""
    a = ARROW.replace("{id}", "rom")
    will = ('<g class="node" data-c="will"><rect x="440" y="404" width="540" height="140" rx="10" fill="none" '
            'stroke="var(--life)" stroke-width="2.6"/>'
            '<text x="710" y="428" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.12em;fill:var(--life)">WHAT IS</text>'
            '<text x="710" y="458" text-anchor="middle" style="font:21px Georgia;fill:var(--ink)">the will of God</text>'
            f'<text x="710" y="478" text-anchor="middle">{gk("τί τὸ θέλημα τοῦ Θεοῦ")}</text>'
            + "".join(f'<rect x="{x}" y="490" width="150" height="44" rx="22" fill="none" stroke="var(--life)" stroke-width="1.4"/>'
                      f'<text x="{x + 75}" y="509" text-anchor="middle" style="font:16px Georgia;fill:var(--ink)">{e}</text>'
                      f'<text x="{x + 75}" y="526" text-anchor="middle">{gk(g, 12)}</text>'
                      for x, e, g in ((465, "good", "τὸ ἀγαθὸν"), (635, "pleasing", "εὐάρεστον"), (805, "perfect", "τέλειον")))
            + '</g>')
    parts = [
        '<text x="500" y="22" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.14em;fill:var(--mute)">TWO WAYS TO BE SHAPED</text>',
        node("conf", 40, 40, 380, 84, "not", "NOT · μή", "conformed to this age", "μὴ συσχηματίζεσθε τῷ αἰῶνι τούτῳ",
             dashed=True, struck=True),
        node("trans", 540, 40, 400, 84, "action", "BUT · ἀλλά", "be transformed", "ἀλλὰ μεταμορφοῦσθε"),
        '<path d="M230 126 C230 200 230 230 230 262" fill="none" stroke="var(--mute)" stroke-width="1.6" stroke-dasharray="5 5"/>',
        _xmark(230, 280),
        _arrow(740, 126, 740, 162, "rom"),
        node("renew", 540, 166, 400, 84, "cond", "BY · THE MEANS", "the renewing of your mind", "τῇ ἀνακαινώσει τοῦ νοός"),
        _arrow(740, 252, 740, 288, "rom"),
        node("test", 540, 292, 400, 84, "basis", "SO THAT · εἰς τό", "you can test and approve", "εἰς τὸ δοκιμάζειν ὑμᾶς"),
        _arrow(740, 378, 740, 400, "rom"),
        will,
    ]
    return f'<svg viewBox="0 0 1000 560" role="img" aria-label="The logic of Romans 12:2">{a}{"".join(parts)}</svg>'


def john15_svg():
    """John 15:5, the words first (Doug, 2026-11-15: "make it a little more subtle like the mountain and realistic -
    but the words are the key"). Who is who, as a pair; the one who remains (both ways) is the one who bears much
    fruit; and ὅτι gives the reason: apart from Me, nothing. The vine is a small sketch beside the title, a detail."""
    a = ARROW.replace("{id}", "jn")
    leaf = ('<path d="M0 0 C-7 -2 -15 -6 -15 -14 C-11 -13 -10 -18 -12 -22 C-6 -20 -3 -24 0 -30 C3 -24 6 -20 12 -22 '
            'C10 -18 11 -13 15 -14 C15 -6 7 -2 0 0Z" fill="none" stroke="var(--mute)" stroke-width="1.3" '
            'transform="{t}"/>')
    vine = [
        '<g opacity=".75">',
        # the old stock, the cane, a tendril
        '<path d="M58 124 C66 100 52 82 70 62 C86 44 112 46 132 30" fill="none" stroke="var(--mute)" stroke-width="3.2" '
        'stroke-linecap="round"/>',
        '<path d="M70 62 C92 66 118 74 146 70" fill="none" stroke="var(--mute)" stroke-width="2" stroke-linecap="round"/>',
        '<path d="M118 40 c9 -7 16 2 9 7 c-6 4 -10 -3 -5 -5" fill="none" stroke="var(--mute)" stroke-width="1"/>',
        leaf.replace("{t}", "translate(146 70) rotate(100)"),
        leaf.replace("{t}", "translate(132 30) rotate(60) scale(.85)"),
        leaf.replace("{t}", "translate(62 92) rotate(-80) scale(.8)"),
        # a cluster hanging from the cane
        '<path d="M100 70 L100 80" stroke="var(--mute)" stroke-width="1.2"/>',
        "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="var(--rule)" stroke="var(--mute)" stroke-width=".8"/>'
                for x, y in ((92, 86), (102, 85), (112, 87), (97, 95), (107, 95), (102, 104), (97, 104))),
        '</g>',
    ]
    faint = lambda x1, y1, x2, y2: (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="var(--rule)" '  # noqa: E731
                                    f'stroke-width="1.4"/>')
    parts = vine + [
        node("vine", 230, 18, 340, 84, "basis", "THE VINE", "I am the vine", "ἐγώ εἰμι ἡ ἄμπελος"),
        node("branches", 610, 18, 340, 84, "action", "YOU · ὑμεῖς", "are the branches", "ὑμεῖς τὰ κλήματα"),
        faint(400, 102, 300, 162), faint(780, 102, 380, 162),
        node("remain", 90, 164, 440, 92, "cond", "THE ONE WHO REMAINS · BOTH WAYS", "in Me, and I in him",
             "ὁ μένων ἐν ἐμοὶ κἀγὼ ἐν αὐτῷ"),
        _arrow(532, 210, 594, 210, "jn"),
        node("fruit", 600, 164, 350, 92, "life", "THIS ONE · οὗτος · BEARS", "much fruit", "φέρει καρπὸν πολύν"),
        '<path d="M500 330 L500 290 C500 274 400 274 310 258" fill="none" stroke="var(--mute)" stroke-width="1.4" '
        'stroke-dasharray="4 5" marker-end="url(#ar-jn)"/>',
        '<text x="512" y="300" style="font:italic 13px Georgia;fill:var(--mute)">the reason</text>',
        node("apart", 250, 334, 500, 92, "not", "FOR · ὅτι · APART FROM ME", "you can do nothing",
             "χωρὶς ἐμοῦ οὐ δύνασθε ποιεῖν οὐδέν", dashed=True),
    ]
    return f'<svg viewBox="0 0 1000 440" role="img" aria-label="The logic of John 15:5">{a}{"".join(parts)}</svg>'


def isa_svg():
    """Isaiah 52:7: one messenger, and a set of five things said of him, all singular participles of the same one
    (brings good news, proclaims peace, brings good tidings, proclaims salvation, says to Zion). The fifth carries
    the message itself, "Your God reigns!". Doug, 2026-11-15: the characteristics belong together as a set; the
    mountain is a detail, not the focus, so it is kept small."""
    a = ARROW.replace("{id}", "isa")

    def member(grp, x, y, eng, heb, w=280):
        return (f'<g class="node" data-c="{grp}"><rect x="{x}" y="{y}" width="{w}" height="74" rx="10" fill="var(--bg)" '
                f'stroke="var(--action)" stroke-width="2"/><text x="{x + w / 2}" y="{y + 31}" text-anchor="middle" '
                f'style="font:19px Georgia;fill:var(--ink)">{eng}</text><text x="{x + w / 2}" y="{y + 58}" '
                f'text-anchor="middle">{gk(heb, 17)}</text></g>')

    parts = [
        # the mountain, small: where the feet are, not what the verse is about
        '<path d="M70 104 L112 50 L130 68 L156 34 L206 104" fill="none" stroke="var(--rule)" stroke-width="2"/>',
        '<ellipse cx="151" cy="24" rx="4" ry="7" fill="var(--basis)" transform="rotate(-16 151 24)"/>'
        '<ellipse cx="162" cy="21" rx="4" ry="7" fill="var(--basis)" transform="rotate(14 162 21)"/>',
        node("beauty", 260, 14, 480, 92, "basis", "HOW BEAUTIFUL ON THE MOUNTAINS", "are the feet", "מַה־נָּאווּ עַל־הֶהָרִים רַגְלֵי"),
        '<line x1="500" y1="106" x2="500" y2="140" stroke="var(--basis)" stroke-width="1.6"/>',
        # the set: everything said of the one whose feet they are
        '<rect x="30" y="140" width="940" height="244" rx="18" fill="var(--action)" fill-opacity=".05" '
        'stroke="var(--action)" stroke-width="1.4"/>',
        '<text x="500" y="166" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.12em;fill:var(--action)">'
        'OF THE ONE WHO · FIVE THINGS SAID OF ONE MESSENGER</text>',
        member("news", 60, 186, "brings good news", "מְבַשֵּׂר"),
        member("peace", 360, 186, "proclaims peace", "מַשְׁמִיעַ שָׁלוֹם"),
        member("good", 660, 186, "brings good tidings", "מְבַשֵּׂר טוֹב"),
        member("salv", 210, 290, "proclaims salvation", "מַשְׁמִיעַ יְשׁוּעָה"),
        member("say", 510, 290, "says to Zion", "אֹמֵר לְצִיּוֹן"),
        # what he says, coming out of the set
        _arrow(650, 366, 650, 404, "isa", "var(--life)", 2.2),
        '<g class="node" data-c="reigns"><rect x="490" y="408" width="320" height="92" rx="12" fill="none" '
        'stroke="var(--life)" stroke-width="2.8"/><text x="650" y="430" text-anchor="middle" '
        'style="font:600 11px system-ui;letter-spacing:.12em;fill:var(--life)">THE MESSAGE</text>'
        '<text x="650" y="460" text-anchor="middle" style="font:22px Georgia;fill:var(--ink)">\u201cYour God reigns!\u201d</text>'
        f'<text x="650" y="486" text-anchor="middle">{gk("מָלַךְ אֱלֹהָיִךְ", 17)}</text></g>',
    ]
    return f'<svg viewBox="0 0 1000 512" role="img" aria-label="Isaiah 52:7: one messenger and what is said of him">{a}{"".join(parts)}</svg>'


DRAW = {"eph": eph_svg, "rom": rom_svg, "jn15": john15_svg, "isa": isa_svg}

VERSES = [
    {"id": "john316", "ref": "John 3:16", "refs": ["John.3.16"],
     "groups": [["basis"] * 7 + ["action"] * 6 + ["cond"] * 6 + ["not"] * 2 + ["life"] * 4],
     "colors": {"basis": "basis", "action": "action", "cond": "cond", "not": "not", "life": "life"},
     "conn": [{1, 7, 13, 19, 21}],
     "bsb": [("For God so loved the world", "basis"), ("that He gave His one and only Son,", "action"),
             ("that everyone who believes in Him", "cond"), ("shall not perish", "not"), ("but have eternal life.", "life")],
     "svg": None,
     "note": "Drawn from the verse's own grammar in the Greek: γάρ (for) gives the basis, ὥστε (so that) what the love "
             "did, ἵνα (in order that) what the gift is for, and μὴ … ἀλλά (not … but) the effect. The diagram shows "
             "how the sentence is built. It takes no position on questions readers debate.",
     "ties": [("Who and what it names", [("God", "/e/god"), ("Jesus (the Son)", "/e/jesus"), ("the Father", "/e/the_father"),
                                         ("eternal life", "/e/eternal_life"), ("faith", "/e/faith"),
                                         ("the saying: God so loved the world", "/e/god_so_loved_the_world")]),
              ("The Berean editors point this section to", [("Genesis 22:1–10: Abraham offers his only son", "/p/Gen.22.2"),
                                                            ("Romans 5:6–11: God shows His love", "/p/Rom.5.8")]),
              ("Says the same, as a reader judged the pair", [("John 3:36", "/p/John.3.36"), ("5:24", "/p/John.5.24"),
                                                              ("6:40", "/p/John.6.40"), ("6:47", "/p/John.6.47"),
                                                              ("20:31", "/p/John.20.31")])],
     "nav": "/graph/god_so_loved_the_world"},
    {"id": "eph28", "ref": "Ephesians 2:8–9", "refs": ["Eph.2.8", "Eph.2.9"],
     "groups": [["grace"] * 3 + ["saved"] * 2 + ["faith"] * 2 + ["notyou"] * 5 + ["gift"] * 3,
                ["notworks"] * 3 + ["boast"] * 4],
     "colors": {"grace": "basis", "gift": "basis", "saved": "action", "faith": "cond", "notyou": "not",
                "notworks": "not", "boast": "life"},
     "conn": [{1, 5, 7, 9}, {0, 3}],
     "bsb": [("For it is by grace", "grace"), ("you have been saved", "saved"), ("through faith,", "faith"),
             ("and this not from yourselves;", "notyou"), ("it is the gift of God,", "gift"), ("not by works,", "notworks"),
             ("so that no one can boast.", "boast")],
     "svg": "eph",
     "note": "Drawn from the Greek's own grammar: γάρ (for), διά (through), καὶ τοῦτο οὐκ (and this not), οὐκ ἐξ "
             "(not from), ἵνα (so that). σεσῳσμένοι is a perfect: saved, and it stands. “This” (τοῦτο) is neuter, while "
             "grace and faith are feminine, so readers differ on whether it points to faith, to grace, or to the whole of "
             "being saved. The diagram shows how the sentence is built and takes no side.",
     "ties": [("Who and what it names", [("Paul, whose words these are", "/e/paul"), ("grace", "/e/grace"),
                                         ("faith", "/e/faith"), ("salvation", "/e/salvation"), ("works", "/e/works"),
                                         ("the saying: by grace you have been saved", "/e/by_grace_you_have_been_saved")]),
              ("What the graph sets beside it", [("Ephesians 2:10, the next verse: created in Christ Jesus to do good works",
                                                  "/p/Eph.2.10"),
                                                 ("James 2:24: a man is justified by his deeds", "/p/Jas.2.24"),
                                                 ("The question readers debate: faith and works", "/questions/faith-and-works")]),
              ("The Berean editors point this section to", [("Colossians 2:6–23", "/p/Col.2.6")])],
     "nav": "/graph/by_grace_you_have_been_saved"},
    {"id": "rom122", "ref": "Romans 12:2", "refs": ["Rom.12.2"],
     "groups": [["conf"] * 6 + ["trans"] * 2 + ["renew"] * 4 + ["test"] * 4 + ["will"] * 11],
     "colors": {"conf": "not", "trans": "action", "renew": "cond", "test": "basis", "will": "life"},
     "conn": [{1, 6, 12}],
     "bsb": [("Do not be conformed to this world,", "conf"), ("but be transformed", "trans"),
             ("by the renewing of your mind.", "renew"), ("Then you will be able to test and approve", "test"),
             ("what is the good, pleasing, and perfect will of God.", "will")],
     "svg": "rom",
     "note": "Drawn from the Greek's own grammar: μή … ἀλλά (not … but) sets the two ways against each other; τῇ "
             "ἀνακαινώσει (by the renewing) gives the means; εἰς τό with the infinitive gives what follows, to test and "
             "approve. αἰών is “age” (the Berean: “world”). μεταμορφοῦσθε is the verb used of the "
             "transfiguration (Matthew 17:2). The diagram shows how the sentence is built and takes no side.",
     "ties": [("Who and what it names", [("Paul, whose words these are", "/e/paul"), ("the mind", "/e/mind"),
                                         ("renewal", "/e/renewal"), ("worship", "/e/worship"),
                                         ("the saying: be transformed by the renewing of your mind",
                                          "/e/be_not_conformed_but_transformed")]),
              ("What the graph sets beside it", [("a new creation", "/e/new_creature"),
                                                 ("the word: μεταμορφόω, transformed", "/word/G3339")]),
              ("The Berean editors point this section to", [("1 Corinthians 3:16–23", "/p/1Cor.3.16"),
                                                            ("1 Corinthians 6:18–20", "/p/1Cor.6.19")])],
     "nav": "/graph/be_not_conformed_but_transformed"},
    {"id": "jn155", "ref": "John 15:5", "refs": ["John.15.5"],
     "groups": [["vine"] * 4 + ["branches"] * 3 + ["remain"] * 7 + ["fruit"] * 4 + ["apart"] * 7],
     "colors": {"vine": "basis", "branches": "action", "remain": "cond", "fruit": "life", "apart": "not"},
     "conn": [{11, 18}],
     "bsb": [("I am the vine", "vine"), ("and you are the branches.", "branches"),
             ("The one who remains in Me, and I in him,", "remain"), ("will bear much fruit.", "fruit"),
             ("For apart from Me you can do nothing.", "apart")],
     "svg": "jn15",
     "note": "Drawn from the verse's own grammar. Two statements of who is who: I am the vine, you are the "
             "branches. Then ὁ μένων … οὗτος: the one who remains is the one who bears much fruit, and remaining runs "
             "both ways, “in Me, and I in him.” ὅτι (for) gives the reason: χωρὶς ἐμοῦ, apart from Me, "
             "nothing. The diagram adds nothing the verse does not say.",
     "ties": [("Who and what it names", [("the true vine", "/e/the_true_vine"), ("the image: vine", "/e/image_vine"),
                                         ("bearing fruit", "/e/bearing_fruit"),
                                         ("the saying: the one who remains in Me", "/e/abide_in_me")]),
              ("Where it is told", [("the Vine and the Branches discourse", "/e/event_vine_and_branches_discourse"),
                                    ("the Last Supper", "/e/event_last_supper")]),
              ("The Berean editors point this section to", [("Isaiah 27:1–13, the song of the vineyard", "/p/Isa.27.2")])],
     "nav": "/graph/abide_in_me"},
    {"id": "isa527", "ref": "Isaiah 52:7", "refs": ["Isa.52.7"], "lang": "he",
     "groups": [["beauty"] * 5 + ["news"] + ["peace"] * 2 + ["good"] * 2 + ["salv"] * 2 + ["say"] * 2 + ["reigns"] * 2],
     "colors": {"beauty": "basis", "news": "action", "peace": "action", "good": "action", "salv": "action", "say": "action",
                "reigns": "life"},
     "conn": [set()],
     "bsb": [("How beautiful on the mountains are the feet", "beauty"), ("of those who bring good news,", "news"),
             ("who proclaim peace,", "peace"), ("who bring good tidings,", "good"), ("who proclaim salvation,", "salv"),
             ("who say to Zion,", "say"), ("“Your God reigns!”", "reigns")],
     "svg": "isa",
     "note": "Drawn as one messenger and the set of things said of him. In the Hebrew all five are singular "
             "participles of the same one: brings good news (מְבַשֵּׂר), proclaims (מַשְׁמִיעַ), says (אֹמֵר); the Berean "
             "reads “those who.” The fifth carries the message itself, “Your God reigns” "
             "(מָלַךְ אֱלֹהָיִךְ). Paul quotes the verse in Romans 10:15.",
     "ties": [("Who and what it names", [("Zion", "/e/zion"), ("peace", "/e/peace"), ("salvation", "/e/salvation"),
                                         ("the word: בָּשַׂר, to bring good news", "/word/H1319"),
                                         ("the saying: how beautiful are the feet", "/e/how_beautiful_are_the_feet")]),
              ("The Berean editors point this to", [("Romans 10:15, where Paul quotes it", "/p/Rom.10.15")]),
              ("What the graph sets beside it", [("Acts 13:32: we proclaim to you the good news", "/p/Acts.13.32")])],
     "nav": "/graph/how_beautiful_are_the_feet"},
]
COMING = []


def section(v, first):
    words = [verse_words(r) for r in v["refs"]]
    flat = []
    for k, ws in enumerate(words):
        for i, w in enumerate(ws):
            flat.append(dict(w, c=v["groups"][k][i] if i < len(v["groups"][k]) else "", conn=i in v["conn"][k],
                             verse=v["refs"][k] if len(v["refs"]) > 1 and i == 0 else None))
    svg = (open(Path(__file__).resolve().parents[0] / "_john316.svg", encoding="utf-8").read() if v["svg"] is None
           else DRAW[v["svg"]]())
    bsb = " ".join(f'<span data-c="{c}">{html.escape(t)}</span>' for t, c in v["bsb"])
    ties = "".join(f'<div><h4>{html.escape(h)}</h4><p>' + " · ".join(f'<a href="{u}">{html.escape(n)}</a>' for n, u in links)
                   + "</p></div>" for h, links in v["ties"])
    return (f'<section class="verse" id="{v["id"]}"{"" if first else " hidden"} data-colors=\'{json.dumps(v["colors"])}\'>'
            f'<h1>{html.escape(v["ref"])}</h1><p class="sub">Tap a part of the diagram to light its words in the {"Hebrew" if v.get("lang") == "he" else "Greek"} and '
            f'the Berean.</p>'
            f'<div class="layer"><div class="lh">The {"Hebrew" if v.get("lang") == "he" else "Greek"} · each word opens its '
            f'card</div><div class="words{" he" if v.get("lang") == "he" else ""}"{" dir=rtl" if v.get("lang") == "he" else ""} '
            f'data-words=\'{html.escape(json.dumps(flat, ensure_ascii=False), quote=True)}\'></div></div>'
            f'<div class="layer"><div class="lh">The Berean Standard Bible</div><p class="bsb">{bsb}</p></div>'
            f'<div class="layer"><div class="lh">What the verse says, as it is built</div>{svg}'
            f'<p class="note">{html.escape(v["note"])}</p></div>'
            f'<div class="layer"><div class="lh">In the graph</div><div class="tie">{ties}</div>'
            f'<a class="nav" href="{v["nav"]}">Show in Navigator</a></div></section>')


def main():
    css = (Path(__file__).resolve().parents[0] / "_layers.css").read_text(encoding="utf-8")
    chips = "".join(f'<button class="chip{" on" if i == 0 else ""}" data-v="{v["id"]}">{html.escape(v["ref"])}</button>'
                    for i, v in enumerate(VERSES)) + "".join(
        f'<span class="chip off" title="drawn next">{html.escape(c)}</span>' for c in COMING)
    body = "".join(section(v, i == 0) for i, v in enumerate(VERSES))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE} · Bible Ontology</title>
<meta name="description" content="{html.escape(DESC)}">
<link rel="canonical" href="{SITE}/visual/verses">
<meta property="og:type" content="article"><meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{html.escape(DESC)}"><meta property="og:url" content="{SITE}/visual/verses">
<meta property="og:site_name" content="Bible Ontology"><meta name="twitter:card" content="summary">
<style>{css}
button.chip{{font:13px system-ui,sans-serif;background:none;cursor:pointer}} .chip.off{{opacity:.5}}
.w .vn{{font:600 10px system-ui;color:var(--mute)}} .tie p{{line-height:1.7}}
.words.he .gk{{font-family:{HE};font-size:27px}} .words.he .tr{{direction:ltr}}
</style></head><body><div class="wrap">
<div class="kicker"><a class="home" href="/">Bible Ontology</a> · <a class="home" href="/#explore">Explore</a> · verses hand-selected by the site maker</div>
<div class="chips">{chips}</div>{body}
<p class="note foot">The words, their sounds and their English: MACULA Greek and Hebrew (© Biblica, CC BY 4.0). The
verse in English: the Berean Standard Bible. The links: the Bible Ontology graph, each word to its word card. The diagrams
are drawn by hand from each verse's grammar, a reader's drawing; the note under each says what it rests on and what it
leaves open.<span class="home-line"> <a class="home" href="/#explore">More views, and the whole graph, in Explore →</a></span></p></div>
<script>
const COL = {{basis:'var(--basis)', action:'var(--action)', cond:'var(--cond)', not:'var(--mute)', life:'var(--life)'}};
document.querySelectorAll('section.verse').forEach(sec => {{
  const colors = JSON.parse(sec.dataset.colors), g = sec.querySelector('.words');
  JSON.parse(g.dataset.words).forEach(w => {{
    if (w.verse) {{ const v = document.createElement('span'); v.className = 'w vn'; v.textContent = 'v' + w.verse.split('.').pop(); g.appendChild(v); }}
    const a = document.createElement(w.card ? 'a' : 'span'); a.className = 'w' + (w.conn ? ' conn' : ''); a.dataset.c = w.c;
    a.style.borderColor = COL[colors[w.c]] || 'transparent';
    if (w.card) {{ a.href = '/word/' + w.card; a.title = (w.lemma || '') + ' · ' + w.card; }}
    a.innerHTML = `<span class="gk" lang="${{g.classList.contains('he') ? 'he' : 'grc'}}">${{w.t}}</span><span class="tr">${{w.x}}</span><span class="gl">${{w.g === '-' ? 'the' : w.g}}</span>`;
    g.appendChild(a); }});
  sec.querySelectorAll('.bsb [data-c]').forEach(s => s.style.borderColor = COL[colors[s.dataset.c]]);
  let held = null;
  const light = c => sec.querySelectorAll('[data-c]').forEach(el => {{ const on = c && el.dataset.c === c;
    if (el.classList.contains('node')) el.classList.toggle('dim', !!c && !on); else el.classList.toggle('lit', on); }});
  sec.querySelectorAll('.node').forEach(n => {{
    n.addEventListener('mouseenter', () => {{ if (!held) light(n.dataset.c); }});
    n.addEventListener('mouseleave', () => {{ if (!held) light(null); }});
    n.addEventListener('click', () => {{ held = held === n.dataset.c ? null : n.dataset.c; light(held); }}); }});
}});
document.querySelectorAll('button.chip').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('button.chip').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('section.verse').forEach(s => s.hidden = s.id !== b.dataset.v);
  history.replaceState(null, '', '#' + b.dataset.v); }}));
// a verse by its own address (#eph28), so each can be linked and shared
const want = location.hash.slice(1), wb = want && document.querySelector('button.chip[data-v="' + want + '"]');
if (wb) wb.click();
/* INSIDE THE APP (a card in a frame), every link opens there, in place: a card, a chapter, a word card, the Navigator;
   the way home is plain text, as on the other views */
if (window.parent !== window) {{
  document.querySelectorAll('a.home').forEach(a => a.replaceWith(a.textContent));
  const hl = document.querySelector('.home-line'); if (hl) hl.remove();
  document.addEventListener('click', e => {{
    const a = e.target.closest('a'); if (!a) return;
    const m = (a.getAttribute('href') || '').match(/^[/](e|p|word|graph)[/]([^?#]+)/); if (!m) return;
    e.preventDefault();
    const k = decodeURIComponent(m[2]);
    parent.postMessage(m[1] === 'e' ? {{ent: k}} : m[1] === 'p' ? {{go: m[2]}} : m[1] === 'word' ? {{word: k}} : {{graph: k}}, location.origin);
  }});
}}
</script></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    SERVED.write_text(page, encoding="utf-8", newline="\n")
    print("->", OUT, "and", SERVED)


if __name__ == "__main__":
    main()
