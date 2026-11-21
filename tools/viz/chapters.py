"""CHAPTERS HAND-SELECTED BY THE SITE MAKER, DRAWN WHOLE (plan A.57, P-2026-11-16-1; Doug, 2026-11-16: "a selected
chapter card similar to selected verses, but with the diagram only"). Psalm 23 first, as the shape test; Romans 8
after it.

The drawing holds A.56's lessons: parallel members are a set, a sequence only where the text orders it, the image
is a small sketch at the edge, and the words are the drawing. Each phrase carries its Hebrew (vowels kept, the
cantillation dropped for reading).

PSALM 23, what the drawing shows and why each mark is the text's own:
- **the address turns at v. 4:** vv. 1-3 speak of the LORD ("He makes me lie down"), vv. 4-5 speak to him ("for You
  are with me", אַתָּה), v. 6 of him again ("the house of the LORD"). The left edge marks it.
- **the image turns at v. 5:** shepherd through v. 4 (the rod and the staff are a shepherd's), host from v. 5 (a
  table, oil, a cup). The right edge marks it. The two turns do not coincide, and the drawing does not make them.
- **the divine name, first and last:** יְהוָה stands in v. 1 and in v. 6 and nowhere between; a thin line joins them.
- **v. 4's grammar:** "even though" (גַּם כִּי) concedes the valley; "I will fear no evil" is the main clause; "for"
  (כִּי) gives its reason, "You are with me".
- **v. 6's verb** is רָדַף, which the Berean renders "follow"; its sense is to pursue. Said as a gloss, no more.

    python tools/viz/chapters.py   -> app2/static/visual/chapters.html (served at /visual/chapters), and the
                                      mockup docs/review/mockups/chapters.html with chapters-ps23.png
"""
import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verse_layers import ARROW, HE, _arrow, node  # noqa: E402
from share_ideas import BROWSERS  # noqa: E402
from chapters_rom8 import rom8_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "review" / "mockups" / "chapters.html"
CSS = (Path(__file__).resolve().parent / "_layers.css").read_text(encoding="utf-8")


def plain(heb):
    """Hebrew with its vowels and without the cantillation: easier to read at diagram size (paseq dropped too)."""
    return re.sub(r"[֑-ֽ֯׀]", "", heb).replace("  ", " ").strip()


NAME = "יְהוָה"


def he(text, size=16, fill="var(--mute)"):
    # the divine name in the drawing's own color wherever it stands: v. 1 and v. 6, and nowhere between
    body = html.escape(plain(text)).replace(NAME, f'<tspan style="fill:var(--basis);font-weight:700">{NAME}</tspan>')
    return (f'<tspan style="font-family:{HE.replace(chr(34), chr(39))};font-size:{size}px;fill:{fill}">'
            f'{body}</tspan>')


def member(grp, x, y, w, eng, heb, col="var(--action)", h=74, eng2=None):
    """One member of a set: the English, a second line if it needs one, and the Hebrew under it."""
    lines = f'<text x="{x + w / 2}" y="{y + 29}" text-anchor="middle" style="font:18px Georgia;fill:var(--ink)">{html.escape(eng)}</text>'
    hy = y + 56
    if eng2:
        lines += (f'<text x="{x + w / 2}" y="{y + 50}" text-anchor="middle" style="font:italic 15px Georgia;'
                  f'fill:var(--ink)">{html.escape(eng2)}</text>')
        hy = y + 76
    return (f'<g class="node" data-c="{grp}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="var(--bg)" '
            f'stroke="{col}" stroke-width="2"/>{lines}<text x="{x + w / 2}" y="{hy}" text-anchor="middle">{he(heb)}</text></g>')


def head(x, y, text, col):
    return (f'<text x="{x}" y="{y}" text-anchor="middle" style="font:600 11px system-ui;letter-spacing:.12em;'
            f'fill:{col}">{text}</text>')


def ps23_svg():
    a = ARROW.replace("{id}", "ps")
    cx = 500
    # the shepherd's crook and the host's cup: small, at the right edge, each beside its half
    crook = ('<g opacity=".7"><path d="M948 150 L948 74 C948 52 976 52 976 72 C976 84 966 86 962 80" fill="none" '
             'stroke="var(--mute)" stroke-width="2.4" stroke-linecap="round"/></g>')
    cup = ('<g opacity=".7" transform="translate(30 92)"><path d="M934 676 L962 676 L958 700 C956 708 940 708 938 700 Z" '
           'fill="none" stroke="var(--mute)" stroke-width="1.8"/><path d="M948 708 L948 722 M938 724 L958 724" '
           'stroke="var(--mute)" stroke-width="1.8"/><path d="M936 674 C940 664 946 672 950 664 C954 672 958 664 962 672" '
           'fill="none" stroke="var(--life)" stroke-width="1.4"/></g>')

    def band(x, y1, y2, label, col, side):
        # a bracket down the edge, its label turned along it
        tick = 10 if side == "left" else -10
        ly = (y1 + y2) / 2
        return (f'<path d="M{x + tick} {y1} L{x} {y1} L{x} {y2} L{x + tick} {y2}" fill="none" stroke="{col}" stroke-width="1.6"/>'
                f'<text x="{x - 12 if side == "left" else x + 16}" y="{ly}" text-anchor="middle" transform="rotate(-90 '
                f'{x - 12 if side == "left" else x + 16} {ly})" style="font:600 11px system-ui;letter-spacing:.14em;'
                f'fill:{col}">{label}</text>')

    parts = [
        # THE EDGES: who is spoken to (left), which image (right)
        head(52, 14, "SPOKEN", "var(--mute)"),
        band(52, 22, 440, "ABOUT HIM · HE", "var(--mute)", "left"),
        band(52, 456, 900, "TO HIM · YOU · אַתָּה", "var(--action)", "left"),
        band(52, 916, 1022, "ABOUT HIM", "var(--mute)", "left"),
        head(948, 14, "IMAGE", "var(--mute)"),
        band(940, 168, 732, "THE SHEPHERD", "var(--basis)", "right"),
        band(940, 756, 1022, "THE HOST", "var(--basis)", "right"),
        crook, cup,
        # v. 1, THE CLAIM AND WHAT FOLLOWS FROM IT
        node("claim", 150, 22, 400, 92, "basis", "v. 1 · THE CLAIM", "The LORD is my shepherd", "x"),
        '<line x1="552" y1="68" x2="614" y2="68" stroke="var(--rule)" stroke-width="2"/>',
        node("want", 616, 22, 240, 92, "life", "AND · ITS SECOND LINE", "I shall not want", "x"),
        # vv. 2-3, THE SET: four things the shepherd does, all his, one purpose under them
        '<rect x="110" y="150" width="780" height="244" rx="18" fill="var(--action)" fill-opacity=".05" '
        'stroke="var(--action)" stroke-width="1.4"/>',
        head(cx, 174, "vv. 2–3 · WHAT HE DOES · FOUR THINGS, ONE SHEPHERD", "var(--action)"),
        member("lie", 140, 190, 350, "makes me lie down in green pastures", "בִּנְאוֹת דֶּשֶׁא יַרְבִּיצֵנִי"),
        member("lead", 510, 190, 350, "leads me beside quiet waters", "עַל־מֵי מְנֻחוֹת יְנַהֲלֵנִי"),
        member("soul", 140, 286, 350, "restores my soul", "נַפְשִׁי יְשׁוֹבֵב"),
        member("paths", 510, 286, 350, "guides me in paths of righteousness", "יַנְחֵנִי בְמַעְגְּלֵי־צֶדֶק"),
        _arrow(cx, 396, cx, 418, "ps"),
        f'<rect x="330" y="420" width="340" height="30" rx="15" fill="var(--bg)" stroke="var(--basis)" stroke-width="1.6"/>'
        f'<text x="{cx}" y="441" text-anchor="middle" style="font:16px Georgia;fill:var(--ink)">for the sake of His name '
        f'{he("לְמַעַן שְׁמוֹ", 15)}</text>',
        # v. 4, THE VALLEY: a concession, the main clause, and its reason, which turns to "You"
        '<path d="M110 476 C300 476 360 560 500 560 C640 560 700 476 890 476" fill="none" stroke="var(--rule)" '
        'stroke-width="10" stroke-linecap="round" opacity=".7"/>',
        head(cx, 474, "v. 4 · THROUGH THE VALLEY", "var(--mute)"),
        member("valley", 110, 490, 360, "even though I walk", "גַּם כִּי־אֵלֵךְ בְּגֵיא צַלְמָוֶת", "var(--mute)", 96,
               "through the valley of the shadow of death"),
        _arrow(472, 538, 536, 572, "ps", "var(--mute)", 1.4, "4 4"),
        node("fear", 540, 520, 320, 92, "action", "THE MAIN CLAUSE", "I will fear no evil", "x"),
        _arrow(700, 648, 700, 616, "ps", "var(--basis)", 2.2),
        f'<text x="712" y="636" style="font:italic 13px Georgia;fill:var(--mute)">for · {he("כִּי", 14)} · the reason</text>',
        node("with", 540, 650, 320, 92, "basis", "THE REASON · NOW SPOKEN TO HIM", "for You are with me", "x"),
        member("rod", 110, 618, 360, "Your rod and Your staff,", "שִׁבְטְךָ וּמִשְׁעַנְתֶּךָ הֵמָּה יְנַחֲמֻנִי",
               "var(--basis)", 96, "they comfort me"),
        # v. 5, THE HOST: three things done for him, a set
        '<rect x="110" y="756" width="780" height="?" rx="18"/>',
        # v. 6, WHERE IT ENDS
    ]
    # v. 5
    v5 = [
        '<rect x="110" y="756" width="780" height="140" rx="18" fill="var(--life)" fill-opacity=".05" '
        'stroke="var(--life)" stroke-width="1.4"/>',
        head(cx, 780, "v. 5 · WHAT YOU DO · THE TABLE SET", "var(--life)"),
        member("table", 130, 794, 300, "You prepare a table before me", "תַּעֲרֹךְ לְפָנַי שֻׁלְחָן נֶגֶד צֹרְרָי",
               "var(--life)", 94, "in the presence of my enemies"),
        member("oil", 444, 794, 230, "You anoint my head", "דִּשַּׁנְתָּ בַשֶּׁמֶן רֹאשִׁי", "var(--life)", 94, "with oil"),
        member("cup", 688, 794, 182, "my cup", "כּוֹסִי רְוָיָה", "var(--life)", 94, "overflows"),
    ]
    v6 = [
        _arrow(cx, 898, cx, 920, "ps"),
        head(cx, 916, "", "var(--mute)"),
        member("follow", 110, 924, 380, "goodness and mercy will follow me", "טוֹב וָחֶסֶד יִרְדְּפוּנִי כָּל־יְמֵי חַיָּי",
               "var(--basis)", 96, "all the days of my life"),
        _arrow(492, 972, 530, 972, "ps", "var(--life)", 2.2),
        node("dwell", 534, 924, 356, 96, "life", "v. 6 · WHERE IT ENDS", "I will dwell in the house of the LORD", "x"),
        f'<text x="300" y="1042" text-anchor="middle" style="font:italic 13px Georgia;fill:var(--mute)">"follow": the verb is '
        f'{he("רָדַף", 14)}, to pursue</text>',
    ]
    svg = "".join(p for p in parts if 'height="?"' not in p) + "".join(v5) + "".join(v6)
    # the Hebrew line of each node(): node() writes its third argument in the Greek style, so the plain-Hebrew line is
    # set here, by group, in the site's Hebrew face
    heb = {"claim": "יְהוָה רֹעִי", "want": "לֹא אֶחְסָר", "fear": "לֹא־אִירָא רָע", "with": "כִּי־אַתָּה עִמָּדִי",
           "dwell": "וְשַׁבְתִּי בְּבֵית־יְהוָה לְאֹרֶךְ יָמִים"}
    for g, h in heb.items():
        svg = re.sub(rf'(<g class="node" data-c="{g}">.*?<text [^>]*text-anchor="middle">)<tspan[^>]*>x</tspan>',
                     lambda m: m.group(1) + he(h, 17), svg, count=1, flags=re.S)
    svg += (f'<text x="712" y="1042" text-anchor="middle" style="font:italic 13px Georgia;fill:var(--mute)">'
            f'{he(NAME, 14)}, the LORD: named in v. 1 and here, and nowhere between</text>')
    return f'<svg viewBox="0 0 1000 1056" role="img" aria-label="Psalm 23 drawn whole">{a}{svg}</svg>'


# EVERY PART OPENS ITS CARD: the graph already holds a card for each saying and image the psalm is made of
LINKS = {"claim": "/e/the_lord_is_my_shepherd", "want": "/e/i_shall_not_want",
         "lie": "/e/he_makes_me_to_lie_down_in_green_pastures", "lead": "/e/he_leads_me_beside_the_still_waters",
         "soul": "/e/he_restores_my_soul", "paths": "/e/he_leads_me_in_the_paths_of_righteousness_for_his_names_sake",
         "valley": "/e/image_the_valley_of_the_shadow_of_death", "fear": "/e/i_will_fear_no_evil",
         "with": "/e/for_you_are_with_me", "rod": "/e/image_staff", "table": "/e/image_table", "oil": "/e/image_oil",
         "cup": "/e/my_cup_runs_over", "follow": "/p/Ps.23.6", "dwell": "/e/i_will_dwell_in_the_house_of_the_lord_for_ever"}
TIES = [
    ("The sayings, each a card", [
        ("The LORD is my shepherd", "/e/the_lord_is_my_shepherd"), ("I shall not want", "/e/i_shall_not_want"),
        ("He makes me lie down in green pastures", "/e/he_makes_me_to_lie_down_in_green_pastures"),
        ("He leads me beside quiet waters", "/e/he_leads_me_beside_the_still_waters"),
        ("He restores my soul", "/e/he_restores_my_soul"),
        ("He guides me in the paths of righteousness", "/e/he_leads_me_in_the_paths_of_righteousness_for_his_names_sake"),
        ("I will fear no evil", "/e/i_will_fear_no_evil"), ("for You are with me", "/e/for_you_are_with_me"),
        ("my cup overflows", "/e/my_cup_runs_over"),
        ("I will dwell in the house of the LORD forever", "/e/i_will_dwell_in_the_house_of_the_lord_for_ever")]),
    ("The images it draws on", [
        ("shepherd", "/e/image_shepherd"), ("green pastures", "/e/image_green_pastures"),
        ("quiet waters", "/e/image_still_waters"), ("path", "/e/image_path"),
        ("the valley of the shadow of death", "/e/image_the_valley_of_the_shadow_of_death"),
        ("rod and staff", "/e/image_staff"), ("table", "/e/image_table"), ("oil", "/e/image_oil"),
        ("cup", "/e/image_cup"), ("the house of the LORD", "/e/image_the_house_of_the_lord")]),
    ("Who it names", [("the LORD, likened to a shepherd", "/e/god"), ("David, by its heading", "/e/david"),
                      ("the heading: A Psalm of David", "/e/psalm_of_david")]),
    ("Its words, each a word card", [
        ("shepherd · רֹעִי", "/word/H7473"), ("want · חָסֵר", "/word/H2637"), ("quiet · מְנוּחָה", "/word/H4496"),
        ("restores · שׁוּב", "/word/H7725"), ("shadow of death · צַלְמָוֶת", "/word/H6757"),
        ("rod · שֵׁבֶט", "/word/H7626"), ("table · שֻׁלְחָן", "/word/H7979"), ("cup · כּוֹס", "/word/H3563"),
        ("goodness · טוֹב", "/word/H2896"), ("mercy · חֶסֶד", "/word/H2617"), ("follow, pursue · רָדַף", "/word/H7291"),
        ("the LORD · יְהוָה", "/word/H3068")]),
    ("The Berean editors point this psalm to", [
        ("Ezekiel 34:11–24", "/p/Ezek.34.11"), ("John 10:1–21", "/p/John.10.1"), ("Revelation 7:17", "/p/Rev.7.17")]),
]
NOTE = ("Drawn by hand from the psalm's grammar, a reader's drawing. The turns are the text's own: who is spoken to "
        "changes at v. 4 (“You”, אַתָּה), and the image at v. 5 (a table, oil, a cup). What the valley, the table and "
        "the enemies stand for, the psalm does not say, and the drawing adds nothing.")
TITLE = "Chapters hand-selected by the site maker, drawn whole"
DESC = ("Psalm 23 and Romans 8 drawn whole from the Hebrew and Greek: the shepherd who becomes the host, and Romans 8 "
        "from “no condemnation” to “nothing able to separate us”, each part opening its card in the Bible Ontology graph.")
SERVED = ROOT / "app2" / "static" / "visual" / "chapters.html"
SITE = "https://bibleontology.org"
FRAME_JS = """
/* INSIDE THE APP (a card in a frame), every link opens there, in place: a card, a chapter, a word card, the Navigator;
   the way home is plain text, as on the other views */
if (window.parent !== window) {
  document.querySelectorAll('a.home').forEach(a => a.replaceWith(a.textContent));
  const hl = document.querySelector('.home-line'); if (hl) hl.remove();
  document.addEventListener('click', e => {
    const a = e.target.closest('a'); if (!a) return;
    const m = (a.getAttribute('href') || '').match(/^[/](e|p|word|graph)[/]([^?#]+)/); if (!m) return;
    e.preventDefault();
    const k = decodeURIComponent(m[2]);
    parent.postMessage(m[1] === 'e' ? {ent: k} : m[1] === 'p' ? {go: m[2]} : m[1] === 'word' ? {word: k} : {graph: k}, location.origin);
  });
}
"""


def linked_svg():
    svg = ps23_svg()
    return re.sub(r'(<g class="node" data-c="(\w+)">.*?</g>)',
                  lambda m: f'<a href="{LINKS[m.group(2)]}">{m.group(1)}</a>' if m.group(2) in LINKS else m.group(1),
                  svg, flags=re.S)


ROM8_TIES = [
    ("The sayings, each a card", [
        ("no condemnation", "/e/no_condemnation"), ("the law of the Spirit of life", "/e/the_law_of_the_spirit_of_life"),
        ("the mind of the flesh is death", "/e/to_be_carnally_minded_is_death"), ("led by the Spirit", "/e/led_by_the_spirit"),
        ("the Spirit of adoption", "/e/the_spirit_of_adoption"),
        ("heirs of God and co-heirs with Christ", "/e/heirs_of_god_and_joint_heirs_with_christ"),
        ("our present sufferings", "/e/the_sufferings_of_this_present_time"),
        ("the whole creation has been groaning", "/e/the_whole_creation_groans"),
        ("hope that is seen is no hope at all", "/e/hope_that_is_seen_is_not_hope"),
        ("groans too deep for words", "/e/groanings_which_cannot_be_uttered"),
        ("God works all things together for the good", "/e/all_things_work_together"),
        ("those He predestined, He also called", "/e/those_he_predestined_he_also_called"),
        ("If God is for us, who can be against us", "/e/if_god_is_for_us_who_can_be_against_us"),
        ("He who did not spare His own Son", "/e/he_that_spared_not_his_own_son"),
        ("Who shall separate us from the love of Christ", "/e/who_shall_separate_us_from_the_love_of_christ"),
        ("we are considered as sheep to be slaughtered", "/e/we_are_accounted_as_sheep_for_the_slaughter"),
        ("more than conquerors", "/e/more_than_conquerors")]),
    ("Ideas it names", [("condemnation", "/e/condemnation"), ("adoption", "/e/adoption"), ("heirs", "/e/heirs"),
                        ("suffering", "/e/suffering"), ("glory", "/e/glory"), ("intercession", "/e/intercession")]),
    ("Its words, each a word card", [
        ("Spirit · πνεῦμα", "/word/G4151"), ("flesh · σάρξ", "/word/G4561"), ("condemnation · κατάκριμα", "/word/G2631"),
        ("adoption · υἱοθεσία", "/word/G5206"), ("groan · στενάζω", "/word/G4727"), ("love · ἀγάπη", "/word/G26")]),
]
ROM8_NOTE = ("Drawn by hand from the chapter's grammar, a reader's drawing, in the five sections the Berean editors "
             "mark. The counts are MACULA's. 8:29–30 is drawn as the text links it (“those He … these He also …”); "
             "what “foreknew” and “those” mean, readers differ, and the drawing takes no side.")
CHIPS_JS = """
/* two chapters, one shown: the chip, or the address (#rom8, #rom8-s3: a section of it) */
const showCh = (id, anchor) => {
  document.querySelectorAll('section.chapter').forEach(s => s.hidden = s.id !== id);
  document.querySelectorAll('button.chip').forEach(b => b.classList.toggle('on', b.dataset.v === id));
  const t = anchor && document.getElementById(anchor); if (t) t.scrollIntoView();
};
document.querySelectorAll('button.chip').forEach(b => b.addEventListener('click', () => {
  showCh(b.dataset.v); history.replaceState(null, '', '#' + b.dataset.v); }));
{ const h = location.hash.slice(1); if (/^rom8/.test(h)) showCh('rom8', h === 'rom8' ? null : h); }
"""


def ties_html(ties):
    return "".join(f'<div><h4>{html.escape(h)}</h4><p>' + " · ".join(
        f'<a href="{u}">{html.escape(n)}</a>' for n, u in links) + "</p></div>" for h, links in ties)


def page(for_site):
    ties = ties_html(TIES)
    meta = (f'<title>{TITLE} · Bible Ontology</title><meta name="description" content="{html.escape(DESC)}">'
            f'<link rel="canonical" href="{SITE}/visual/chapters"><meta property="og:type" content="article">'
            f'<meta property="og:title" content="Psalm 23 and Romans 8, drawn whole"><meta property="og:description" '
            f'content="{html.escape(DESC)}"><meta property="og:url" content="{SITE}/visual/chapters">'
            f'<meta property="og:site_name" content="Bible Ontology"><meta name="twitter:card" content="summary">'
            if for_site else "<title>Psalm 23, drawn whole (mockup)</title>")
    style = (CSS + "\nbody{margin:0;background:var(--bg);color:var(--ink)} .wrap{max-width:1000px;margin:0 auto;"
             "padding:24px 16px}\nh1{font:700 34px Georgia;margin:8px 0 4px} .s{font:17px/1.5 Georgia;color:var(--mute);"
             "margin:0 0 14px}\nsvg{width:100%;height:auto;display:block} svg a:hover .node rect{fill:color-mix(in srgb, "
             "var(--rule) 35%, var(--bg))}\n.tie p{line-height:1.8} .tie h4{margin:14px 0 2px}"
             "\nh2{font:700 22px Georgia;margin:26px 0 2px} button.chip{font:13px system-ui,sans-serif;background:none;"
             "cursor:pointer}"
             # A PHONE KEEPS THE DRAWING READABLE (Doug, 2026-11-17, on the pane at 330 px: "make the phone fix now"): at
             # phone width a 1000-unit drawing shrank its words to about 6 px; it now keeps 720 px and scrolls sideways
             # inside its own frame, the page around it still fitting the screen
             "\n.fig{overflow-x:auto;-webkit-overflow-scrolling:touch} .fig-hint{display:none;font:13px system-ui,"
             "sans-serif;color:var(--mute);margin:6px 0}\n@media (max-width:760px){.fig svg{min-width:720px} "
             ".fig-hint{display:block}}")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">' + meta + f'<style>{style}</style></head>'
            '<body><div class="wrap"><div class="kicker"><a class="home" href="/">Bible Ontology</a> · '
            '<a class="home" href="/#explore">Explore</a> · chapters hand-selected by the site maker, drawn whole</div>'
            '<div class="chips"><button class="chip on" data-v="ps23">Psalm 23</button>'
            '<button class="chip" data-v="rom8">Romans 8</button></div>'
            '<section class="chapter" id="ps23"><h1>Psalm 23 · The LORD Is My Shepherd</h1>'
            '<p class="s">Six verses, one voice. Spoken about the LORD, then to him, then about him again; the shepherd '
            'becomes the host; and the name that opens it closes it. Each part opens its card.</p>'
            + '<p class="fig-hint">Swipe sideways inside the drawing to see all of it.</p>' + '<div class="fig">' + linked_svg() + '</div>'
            + f'<p class="note">{html.escape(NOTE)}</p>'
            f'<div class="layer"><div class="lh">In the graph</div><div class="tie">{ties}</div>'
            '<p><a href="/p/Ps.23">Read Psalm 23 in the reader</a> · <a class="nav" href="/graph/the_lord_is_my_shepherd">'
            'Show in Navigator</a></p></div></section>'
            # ROMANS 8 (Doug, 2026-11-17: "Romans 8 looks great - the user will need to scroll but that is not a problem")
            '<section class="chapter" id="rom8" hidden>' + rom8_html()
            + f'<p class="note">{html.escape(ROM8_NOTE)}</p>'
            f'<div class="layer"><div class="lh">In the graph</div><div class="tie">{ties_html(ROM8_TIES)}</div>'
            '<p><a href="/p/Rom.8">Read Romans 8 in the reader</a> · <a class="nav" href="/graph/no_condemnation">'
            'Show in Navigator</a></p></div></section>'
            '<p class="note foot">The Hebrew and the Greek: MACULA Hebrew and Greek (© Biblica, CC BY 4.0), the Hebrew '
            'shown with its vowels and without the cantillation marks. The English: the Berean Standard Bible. The '
            "links: the Bible Ontology graph. The drawings are by hand, a reader's drawings; the note under each says "
            'what it rests on and what it leaves open.'
            '<span class="home-line"> <a class="home" href="/#explore">More views, and the whole graph, in Explore →</a>'
            '</span></p></div><script>' + CHIPS_JS + FRAME_JS + '</script></body></html>')


def main():
    OUT.write_text(page(False), encoding="utf-8")
    SERVED.write_text(page(True), encoding="utf-8", newline="\n")
    png = OUT.with_name("chapters-ps23.png")
    png.unlink(missing_ok=True)
    exe = next((b for b in BROWSERS if Path(b).exists()), None)
    for _ in range(3):
        with tempfile.TemporaryDirectory(prefix="chapters-", ignore_cleanup_errors=True) as prof:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            "--window-size=1040,1260", f"--user-data-dir={prof}", f"--screenshot={png}", OUT.as_uri()],
                           check=False, timeout=120, capture_output=True)
            for _ in range(20):
                if png.exists():
                    break
                time.sleep(0.5)
        if png.exists():
            break
    print(OUT, "and", SERVED, "->", png if png.exists() else "(no PNG)")


if __name__ == "__main__":
    main()
