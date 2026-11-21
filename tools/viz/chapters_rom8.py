"""ROMANS 8 DRAWN WHOLE (plan A.57; Doug, 2026-11-17: "Romans 8 looks great - the user will need to scroll but that is
not a problem"). The overview and the five sections the Berean editors mark, each drawn from its own connectives;
tools/viz/chapters.py serves them at /visual/chapters#rom8 beside Psalm 23 (`rom8_html`). Run alone, the mockup:
    python tools/viz/chapters_rom8.py  -> docs/review/mockups/chapters-rom8.html and chapters-rom8.png
"""
import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "tools" / "viz"))
from verse_layers import ARROW, _arrow, gk, node  # noqa: E402
from share_ideas import BROWSERS  # noqa: E402

HERE = WT / "docs" / "review" / "mockups"
CSS = (WT / "tools" / "viz" / "_layers.css").read_text(encoding="utf-8")


def head(x, y, text, col, anchor="middle"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="font:600 11px system-ui;letter-spacing:.12em;'
            f'fill:{col}">{text}</text>')


def gmember(grp, x, y, w, eng, greek, col="var(--action)", h=74, eng2=None, dashed=False):
    lines = (f'<text x="{x + w / 2}" y="{y + 29}" text-anchor="middle" style="font:18px Georgia;fill:var(--ink)">'
             f'{html.escape(eng)}</text>')
    gy = y + 54
    if eng2:
        lines += (f'<text x="{x + w / 2}" y="{y + 50}" text-anchor="middle" style="font:italic 15px Georgia;'
                  f'fill:var(--ink)">{html.escape(eng2)}</text>')
        gy = y + 74
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    return (f'<g class="node" data-c="{grp}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="var(--bg)" '
            f'stroke="{col}" stroke-width="2"{dash}/>{lines}<text x="{x + w / 2}" y="{gy}" text-anchor="middle">'
            f'{gk(greek, 14)}</text></g>')


# ------------------------------------------------------------------ the whole: five sections and three words
SECTIONS = [  # (verses, the Berean editors' heading, the line that carries it, its Greek)
    ("8:1–11", "Walking by the Spirit", "no condemnation", "οὐδὲν ἄρα νῦν κατάκριμα"),
    ("8:12–17", "Heirs with Christ", "heirs of God, co-heirs with Christ", "κληρονόμοι μὲν Θεοῦ"),
    ("8:18–27", "Future Glory", "the glory to be revealed", "τὴν μέλλουσαν δόξαν"),
    ("8:28–34", "God Works in All Things", "If God is for us, who can be against us?", "εἰ ὁ Θεὸς ὑπὲρ ἡμῶν"),
    ("8:35–39", "More than Conquerors", "nothing able to separate us", "δυνήσεται ἡμᾶς χωρίσαι"),
]
THREAD = [  # MACULA's own counts, per section (2026-11-16)
    ("Spirit · πνεῦμα", [11, 6, 4, 0, 0], "var(--cond)"),
    ("flesh · σάρξ", [10, 3, 0, 0, 0], "var(--mute)"),
    ("love · ἀγάπη, ἀγαπάω", [0, 0, 0, 1, 3], "var(--life)"),
]


def overview_svg():
    a = ARROW.replace("{id}", "r8o")
    W, bw, gap, x0 = 1000, 176, 20, 12
    parts = [head(500, 18, "THE MOVEMENT · FIVE SECTIONS, AS THE BEREAN EDITORS DIVIDE THE CHAPTER", "var(--mute)")]
    xs = [x0 + i * (bw + gap) for i in range(5)]
    for i, (vv, title, line, greek) in enumerate(SECTIONS):
        x = xs[i]
        col = "var(--basis)" if i in (0, 4) else "var(--action)"
        # the long lines wrap in two
        words, l1, l2 = line.split(), "", ""
        for wd in words:
            (l1 := l1 + (" " if l1 else "") + wd) if len(l1) + len(wd) < 22 and not l2 else None
            if len(l1) + len(wd) >= 22 or l2:
                if wd not in l1.split():
                    l2 += (" " if l2 else "") + wd
        parts.append(
            f'<a href="#rom8-s{i + 1}"><g class="node" data-c="s{i + 1}"><rect x="{x}" y="32" width="{bw}" height="136" rx="10" '
            f'fill="var(--bg)" stroke="{col}" stroke-width="2"/>'
            + head(x + bw / 2, 52, vv, col)
            + f'<text x="{x + bw / 2}" y="74" text-anchor="middle" style="font:600 13px Georgia;fill:var(--ink)">'
              f'{html.escape(title)}</text>'
            + f'<line x1="{x + 30}" y1="86" x2="{x + bw - 30}" y2="86" stroke="var(--rule)"/>'
            + f'<text x="{x + bw / 2}" y="108" text-anchor="middle" style="font:italic 15px Georgia;fill:var(--ink)">'
              f'{html.escape(l1)}</text>'
            + (f'<text x="{x + bw / 2}" y="127" text-anchor="middle" style="font:italic 15px Georgia;fill:var(--ink)">'
               f'{html.escape(l2)}</text>' if l2 else "")
            + f'<text x="{x + bw / 2}" y="{150 if l2 else 132}" text-anchor="middle">{gk(greek, 12)}</text></g></a>')
        if i < 4:
            parts.append(_arrow(x + bw + 2, 100, x + bw + gap - 3, 100, "r8o"))
    # the same root at 8:1 and 8:34: condemnation, and who condemns
    x1, x4 = xs[0] + bw / 2, xs[3] + bw / 2
    parts.append(f'<path d="M{x1} 170 C{x1} 214 {x4} 214 {x4} 170" fill="none" stroke="var(--basis)" stroke-width="1.4" '
                 f'stroke-dasharray="3 4"/>')
    parts.append(f'<text x="{(x1 + x4) / 2}" y="222" text-anchor="middle" style="font:italic 13px Georgia;fill:var(--basis)">'
                 f'the same root: {gk("κατάκριμα", 13, False, "var(--basis)")} “condemnation” (8:1) · '
                 f'{gk("τίς ὁ κατακρινῶν", 13, False, "var(--basis)")} “who is there to condemn?” (8:34)</text>')
    # the thread: three words, counted in each section
    ty = 252
    parts.append(head(12, ty, "THREE WORDS THROUGH THE CHAPTER · EACH DOT ONE USE, IN THE ORIGINAL", "var(--mute)", "start"))
    lx = 12
    for label, counts, col in THREAD:
        parts.append(f'<circle cx="{lx + 5}" cy="{ty + 18}" r="5" fill="{col}"/><text x="{lx + 15}" y="{ty + 23}" '
                     f'style="font:13px system-ui;fill:var(--ink)">{html.escape(label)} · {sum(counts)}</text>')
        lx += 250
    for k, (label, counts, col) in enumerate(THREAD):
        y = ty + 46 + k * 26
        for i, n in enumerate(counts):
            c = xs[i] + bw / 2
            for d in range(n):
                parts.append(f'<circle cx="{c - (n - 1) * 5.5 + d * 11}" cy="{y}" r="4" fill="{col}"/>')
            if n == 0:
                parts.append(f'<line x1="{c - 7}" y1="{y}" x2="{c + 7}" y2="{y}" stroke="var(--rule)" stroke-width="2"/>')
    return f'<svg viewBox="0 0 1000 {ty + 46 + 3 * 26}" role="img" aria-label="Romans 8: the movement of the chapter">{a}{"".join(parts)}</svg>'


# ------------------------------------------------------------------ 8:1-11, Walking by the Spirit
def s1_svg():
    a = ARROW.replace("{id}", "r81")
    parts = [
        # the claim
        node("nocond", 290, 10, 420, 92, "basis", "8:1 · THE CLAIM · THEREFORE, NOW", "no condemnation", "x"),
        f'<text x="500" y="122" text-anchor="middle" style="font:italic 15px Georgia;fill:var(--ink)">for those who are in Christ Jesus</text>',
        # 8:2 the reason: one law sets free from another
        _arrow(500, 160, 500, 132, "r81", "var(--basis)", 2),
        f'<text x="512" y="152" style="font:italic 13px Georgia;fill:var(--mute)">for · {gk("γάρ", 13, False)} · the reason</text>',
        gmember("spiritlaw", 150, 164, 360, "the law of the Spirit of life", "ὁ νόμος τοῦ Πνεύματος τῆς ζωῆς",
                "var(--cond)", 92, "set you free"),
        _arrow(512, 210, 572, 210, "r81", "var(--mute)", 1.4),
        f'<text x="542" y="200" text-anchor="middle" style="font:italic 12px Georgia;fill:var(--mute)">from</text>',
        gmember("sinlaw", 576, 164, 300, "the law of sin and death", "τοῦ νόμου τῆς ἁμαρτίας καὶ τοῦ θανάτου",
                "var(--mute)", 92, dashed=True),
        # 8:3 what the law could not, God did
        head(500, 288, "8:3 · FOR · WHAT ONE COULD NOT, ANOTHER DID", "var(--mute)"),
        gmember("powerless", 90, 300, 330, "what the law was powerless to do", "τὸ γὰρ ἀδύνατον τοῦ νόμου", "var(--mute)",
                92, "weakened by the flesh", dashed=True),
        _arrow(422, 346, 476, 346, "r81", "var(--basis)", 2.2),
        node("goddid", 480, 300, 430, 92, "basis", "GOD DID · SENDING HIS OWN SON", "condemned sin in the flesh", "x"),
        # 8:4 purpose
        _arrow(695, 394, 695, 430, "r81", "var(--life)", 2),
        f'<text x="707" y="420" style="font:italic 13px Georgia;fill:var(--mute)">so that · {gk("ἵνα", 13, False)}</text>',
        gmember("fulfilled", 480, 434, 430, "the righteous standard of the law fulfilled in us",
                "ἵνα τὸ δικαίωμα τοῦ νόμου πληρωθῇ ἐν ἡμῖν", "var(--life)", 92,
                "who walk not by the flesh but by the Spirit"),
        # 8:5-8 the two minds
        head(500, 556, "8:5–8 · TWO MINDS, SET AGAINST EACH OTHER", "var(--mute)"),
        gmember("fleshmind", 90, 568, 360, "the mind of the flesh", "τὸ φρόνημα τῆς σαρκὸς", "var(--mute)", 74),
        _arrow(270, 644, 270, 670, "r81", "var(--mute)", 1.6),
        gmember("death", 160, 674, 220, "death", "θάνατος", "var(--mute)", 66),
        gmember("spiritmind", 550, 568, 360, "the mind of the Spirit", "τὸ φρόνημα τοῦ πνεύματος", "var(--cond)", 74),
        _arrow(730, 644, 730, 670, "r81", "var(--cond)", 1.6),
        gmember("lifepeace", 600, 674, 260, "life and peace", "ζωὴ καὶ εἰρήνη", "var(--life)", 66),
        f'<text x="500" y="610" text-anchor="middle" style="font:600 16px Georgia;fill:var(--mute)">but · {gk("δέ", 15, False)}</text>',
        # 8:9-11 the condition and its promise
        head(500, 774, "8:9–11 · IF THE SPIRIT LIVES IN YOU", "var(--mute)"),
        gmember("dwells", 90, 786, 380, "if the Spirit of Him who raised Jesus", "εἰ δὲ τὸ Πνεῦμα … οἰκεῖ ἐν ὑμῖν", "var(--cond)", 92,
                "is living in you"),
        _arrow(472, 832, 526, 832, "r81", "var(--life)", 2.2),
        gmember("mortal", 530, 786, 380, "He will also give life", "ζωοποιήσει καὶ τὰ θνητὰ σώματα ὑμῶν", "var(--life)", 92,
                "to your mortal bodies"),
    ]
    svg = "".join(parts)
    import re
    greek = {"nocond": "οὐδὲν ἄρα νῦν κατάκριμα", "goddid": "κατέκρινεν τὴν ἁμαρτίαν ἐν τῇ σαρκί"}
    for g, t in greek.items():
        svg = re.sub(rf'(<g class="node" data-c="{g}">.*?<text [^>]*text-anchor="middle">)<tspan[^>]*>x</tspan>',
                     lambda m: m.group(1) + gk(t, 15), svg, count=1, flags=re.S)
    # the same root inside the section: κατάκριμα (8:1), κατέκρινεν (8:3)
    svg += ('<path d="M712 34 L956 34 L956 346 L914 346" fill="none" stroke="var(--basis)" stroke-width="1.2" '
            'stroke-dasharray="3 4"/>'
            f'<text x="718" y="24" style="font:italic 11px Georgia;fill:var(--basis)">the same root: '
            f'{gk("κατέκρινεν", 11, False, "var(--basis)")} “condemned” (8:3)</text>')
    return f'<svg viewBox="0 0 1000 890" role="img" aria-label="Romans 8:1-11 drawn">{a}{svg}</svg>'


# ------------------------------------------------------------------ sections 2-5
def note(x, y, text, col="var(--mute)", anchor="start", size=13):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="font:italic {size}px Georgia;fill:{col}">{text}</text>')


def greek_into(svg, mapping, size=15):
    for g, t in mapping.items():
        svg = re.sub(rf'(<g class="node" data-c="{g}">.*?<text [^>]*text-anchor="middle">)<tspan[^>]*>x</tspan>',
                     lambda m: m.group(1) + gk(t, size), svg, count=1, flags=re.S)
    return svg


# ------------------------------------------------------------------ 8:12-17, Heirs with Christ
def s2_svg():
    a = ARROW.replace("{id}", "r82")
    parts = [
        head(500, 16, "8:12 · AN OBLIGATION, BUT NOT TO THE FLESH", "var(--mute)"),
        gmember("debt", 260, 26, 480, "we have an obligation", "ὀφειλέται ἐσμέν, οὐ τῇ σαρκὶ", "var(--mute)", 92,
                "but it is not to the flesh"),
        head(500, 150, "8:14 · FOR · WHO THEY ARE", "var(--mute)"),
        gmember("led", 90, 162, 380, "all who are led by the Spirit of God", "ὅσοι γὰρ Πνεύματι Θεοῦ ἄγονται", "var(--cond)", 74),
        _arrow(472, 199, 526, 199, "r82", "var(--life)", 2.2),
        node("sons", 530, 162, 380, 74, "life", "THESE", "are sons of God", "x"),
        head(500, 270, "8:15 · NOT ONE SPIRIT, BUT ANOTHER", "var(--mute)"),
        gmember("slavery", 90, 282, 360, "a spirit of slavery", "οὐ … πνεῦμα δουλείας πάλιν εἰς φόβον", "var(--mute)", 92,
                "that returns you to fear", dashed=True),
        gmember("adoption", 550, 282, 360, "the Spirit of adoption to sonship", "ἀλλὰ … πνεῦμα υἱοθεσίας", "var(--cond)", 92,
                "by whom we cry, “Abba! Father!”"),
        f'<text x="500" y="334" text-anchor="middle" style="font:600 16px Georgia;fill:var(--mute)">but · {gk("ἀλλά", 15, False)}</text>',
        _arrow(730, 376, 730, 410, "r82", "var(--cond)", 1.8),
        gmember("testifies", 470, 414, 500, "the Spirit Himself testifies with our spirit", "συμμαρτυρεῖ τῷ πνεύματι ἡμῶν",
                "var(--cond)", 92, "that we are God's children"),
        # 8:17 the chain and its three "with" words
        head(500, 540, "8:17 · IF … THEN: THE CHAIN, AND THREE WORDS JOINED WITH “WITH” (σύν)", "var(--mute)"),
        gmember("children", 30, 556, 150, "children", "τέκνα", "var(--life)", 66),
        _arrow(182, 589, 250, 589, "r82", "var(--life)", 2),
        note(216, 578, "if … then", anchor="middle", size=12),
        gmember("heirs", 254, 556, 150, "heirs", "κληρονόμοι", "var(--life)", 66),
        _arrow(406, 589, 456, 589, "r82", "var(--life)", 2),
        # the pair: of God, and with Christ
        '<rect x="460" y="548" width="500" height="82" rx="14" fill="var(--life)" fill-opacity=".05" stroke="var(--life)" stroke-width="1.2"/>',
        gmember("ofgod", 474, 556, 220, "heirs of God", "κληρονόμοι μὲν Θεοῦ", "var(--life)", 66),
        gmember("coheirs", 724, 556, 222, "co-heirs with Christ", "συνκληρονόμοι δὲ Χριστοῦ", "var(--basis)", 66),
        _arrow(760, 632, 760, 668, "r82", "var(--mute)", 1.6),
        note(772, 656, "if indeed · εἴπερ", size=12),
        gmember("suffer", 520, 672, 260, "we suffer with Him", "συνπάσχομεν", "var(--basis)", 66),
        _arrow(782, 705, 856, 705, "r82", "var(--life)", 2),
        note(819, 694, "so that", anchor="middle", size=12),
        gmember("glorified", 860, 672, 130, "glorified", "συνδοξασθῶμεν", "var(--basis)", 66),
        note(40, 704, "<tspan style=\"fill:var(--basis);font-style:normal;font-weight:600\">σύν, “with”:</tspan> "
             "co-heirs with, suffer with, glorified with, in one verse", size=13),
    ]
    svg = greek_into("".join(parts), {"sons": "οὗτοι υἱοί εἰσιν Θεοῦ"})
    return f'<svg viewBox="0 0 1000 760" role="img" aria-label="Romans 8:12-17 drawn">{a}{svg}</svg>'


# ------------------------------------------------------------------ 8:18-27, Future Glory
def s3_svg():
    a = ARROW.replace("{id}", "r83")
    parts = [
        head(500, 16, "8:18 · THE SCALE: NOT WORTH COMPARING", "var(--mute)"),
        # the balance: a small weight and a large one
        '<line x1="260" y1="62" x2="740" y2="112" stroke="var(--mute)" stroke-width="2"/>',
        '<path d="M500 87 L484 132 L516 132 Z" fill="none" stroke="var(--mute)" stroke-width="1.6"/>',
        gmember("present", 160, 68, 200, "our present sufferings", "τὰ παθήματα τοῦ νῦν καιροῦ", "var(--mute)", 66),
        node("glory", 590, 120, 360, 100, "life", "THE GLORY THAT WILL BE REVEALED IN US", "the glory to come", "x"),
        note(330, 170, "“not comparable” · οὐκ ἄξια", anchor="middle"),
        # 8:19-21 creation waiting
        gmember("waits", 90, 234, 820, "the creation waits in eager expectation for the revealing of the sons of God",
                "ἡ γὰρ ἀποκαραδοκία τῆς κτίσεως τὴν ἀποκάλυψιν τῶν υἱῶν τοῦ Θεοῦ ἀπεκδέχεται", "var(--action)", 92,
                "subjected to futility, in hope, to be set free from its bondage to decay (8:20–21)"),
        # the three groanings, one root
        head(500, 362, "THREE GROANINGS · ONE ROOT · στεναζ-", "var(--basis)"),
        '<rect x="30" y="372" width="940" height="140" rx="18" fill="var(--basis)" fill-opacity=".05" stroke="var(--basis)" stroke-width="1.4"/>',
        gmember("creation", 44, 392, 296, "the whole creation", "πᾶσα ἡ κτίσις συνστενάζει", "var(--basis)", 104,
                "groans together · 8:22"),
        gmember("we", 352, 392, 296, "we ourselves groan inwardly", "ἐν ἑαυτοῖς στενάζομεν", "var(--basis)", 104,
                "awaiting adoption · 8:23"),
        gmember("spirit", 660, 392, 296, "the Spirit intercedes for us", "στεναγμοῖς ἀλαλήτοις", "var(--cond)", 104,
                "with groans too deep for words · 8:26"),
        # hope
        head(500, 544, "8:24–25 · HOPE", "var(--mute)"),
        gmember("hope", 160, 556, 340, "in this hope we were saved", "τῇ γὰρ ἐλπίδι ἐσώθημεν", "var(--life)", 74),
        gmember("unseen", 530, 556, 340, "hope that is seen is no hope at all", "ἐλπὶς δὲ βλεπομένη οὐκ ἔστιν ἐλπίς",
                "var(--mute)", 74),
        _arrow(500, 632, 500, 658, "r83", "var(--life)", 1.8),
        gmember("patience", 300, 662, 400, "we wait for it with patience", "δι’ ὑπομονῆς ἀπεκδεχόμεθα", "var(--life)", 74),
        # 8:27
        note(500, 768, "8:27: the Spirit “intercedes for the saints according to the will of God”, the verb again "
             "(ἐντυγχάνει)", anchor="middle"),
    ]
    svg = greek_into("".join(parts), {"glory": "τὴν μέλλουσαν δόξαν ἀποκαλυφθῆναι εἰς ἡμᾶς"}, 13)
    return f'<svg viewBox="0 0 1000 784" role="img" aria-label="Romans 8:18-27 drawn">{a}{svg}</svg>'


# ------------------------------------------------------------------ 8:28-34, God Works in All Things
def s4_svg():
    a = ARROW.replace("{id}", "r84")
    verbs = [("foreknew", "προέγνω"), ("predestined", "προώρισεν"), ("called", "ἐκάλεσεν"),
             ("justified", "ἐδικαίωσεν"), ("glorified", "ἐδόξασεν")]
    parts = [
        node("works", 150, 10, 700, 92, "basis", "8:28 · WE KNOW", "God works all things together for the good", "x"),
        note(500, 122, "of those who love Him, who are called according to His purpose", anchor="middle", size=15),
        head(500, 160, "8:29–30 · FOR · THE CHAIN AS THE GRAMMAR MAKES IT: “THOSE HE … THESE HE ALSO …”", "var(--mute)"),
    ]
    x = 30
    for i, (e, g) in enumerate(verbs):
        parts.append(gmember(e, x, 172, 164, e, g, "var(--action)", 66))
        if i < 4:
            parts.append(_arrow(x + 166, 205, x + 192, 205, "r84", "var(--action)", 1.8))
        x += 194
    parts += [
        note(500, 264, "conformed to the image of His Son, the firstborn among many brothers (8:29)", anchor="middle"),
        note(500, 286, "Drawn as the text links it. What “foreknew” and “those” mean, readers differ, and the drawing "
             "takes no side.", anchor="middle", size=12),
        head(500, 326, "8:31–34 · WHAT THEN SHALL WE SAY? FOUR QUESTIONS (τίς) AND THEIR ANSWERS", "var(--mute)"),
        # question / answer rows
        gmember("q1", 40, 338, 430, "If God is for us, who can be against us?", "εἰ ὁ Θεὸς ὑπὲρ ἡμῶν, τίς καθ’ ἡμῶν;", "var(--action)", 74),
        _arrow(472, 375, 526, 375, "r84", "var(--life)", 1.8),
        gmember("a1", 530, 338, 430, "He who did not spare His own Son", "ὅς γε τοῦ ἰδίου Υἱοῦ οὐκ ἐφείσατο", "var(--life)", 92,
                "how will He not also freely give us all things?"),
        gmember("q2", 40, 444, 430, "Who will bring any charge against God's elect?", "τίς ἐγκαλέσει κατὰ ἐκλεκτῶν Θεοῦ;",
                "var(--action)", 74),
        _arrow(472, 481, 526, 481, "r84", "var(--life)", 1.8),
        node("a2", 530, 444, 430, 74, "life", "", "It is God who justifies", "x"),
        gmember("q3", 40, 530, 430, "Who is there to condemn us?", "τίς ὁ κατακρινῶν;", "var(--action)", 74),
        _arrow(472, 567, 526, 567, "r84", "var(--life)", 1.8),
        gmember("a3", 530, 530, 430, "Christ Jesus, who died, and was raised,", "Χριστὸς Ἰησοῦς … ὃς καὶ ἐντυγχάνει ὑπὲρ ἡμῶν",
                "var(--life)", 92, "is at the right hand of God, interceding for us"),
        note(40, 650, "<tspan style=\"fill:var(--basis);font-style:normal;font-weight:600\">roots that return:</tspan> "
             "justified (8:30), God who justifies (8:33) · condemnation (8:1), who condemns (8:34) · "
             "the Spirit intercedes (8:26), Christ intercedes (8:34)", size=13),
    ]
    svg = greek_into("".join(parts), {"works": "τοῖς ἀγαπῶσιν τὸν Θεὸν πάντα συνεργεῖ εἰς ἀγαθόν",
                                      "a2": "Θεὸς ὁ δικαιῶν"}, 14)
    return f'<svg viewBox="0 0 1000 670" role="img" aria-label="Romans 8:28-34 drawn">{a}{svg}</svg>'


# ------------------------------------------------------------------ 8:35-39, More than Conquerors
def s5_svg():
    a = ARROW.replace("{id}", "r85")
    seven = [("trouble", "θλῖψις"), ("distress", "στενοχωρία"), ("persecution", "διωγμός"), ("famine", "λιμός"),
             ("nakedness", "γυμνότης"), ("danger", "κίνδυνος"), ("sword", "μάχαιρα")]
    ten = [("death", "θάνατος"), ("life", "ζωή"), ("angels", "ἄγγελοι"), ("principalities", "ἀρχαί"),
           ("the present", "ἐνεστῶτα"), ("the future", "μέλλοντα"), ("powers", "δυνάμεις"), ("height", "ὕψωμα"),
           ("depth", "βάθος"), ("anything else", "τις κτίσις ἑτέρα")]
    parts = [node("q", 200, 10, 600, 84, "action", "8:35 · THE QUESTION", "Who shall separate us from the love of Christ?", "x"),
             head(500, 128, "SEVEN THINGS NAMED · “SHALL … ?”", "var(--mute)"),
             '<rect x="30" y="138" width="940" height="74" rx="14" fill="var(--mute)" fill-opacity=".05" stroke="var(--mute)" stroke-width="1.2"/>']
    x = 44
    for e, g in seven:
        parts.append(gmember(e, x, 146, 124, e, g, "var(--mute)", 60))
        x += 131
    parts += [
        gmember("written", 200, 232, 600, "“For Your sake we face death all day long;", "καθὼς γέγραπται", "var(--mute)", 92,
                "we are considered as sheep to be slaughtered” · 8:36, from Ps 44:22"),
        _arrow(500, 326, 500, 352, "r85", "var(--life)", 2),
        node("conquer", 230, 356, 540, 84, "life", "8:37 · NO", "in all these things we are more than conquerors", "x"),
        note(500, 458, "through Him who loved us", anchor="middle", size=15),
        head(500, 492, "8:38–39 · FOR I AM CONVINCED · TEN THINGS NAMED, “NEITHER … NOR”", "var(--mute)"),
        '<rect x="30" y="502" width="940" height="136" rx="14" fill="var(--mute)" fill-opacity=".05" stroke="var(--mute)" stroke-width="1.2"/>',
    ]
    for k, (e, g) in enumerate(ten):
        row, col = divmod(k, 5)
        w = 176
        parts.append(gmember(e, 44 + col * 184, 510 + row * 64, w, e, g, "var(--mute)", 60))
    parts += [
        _arrow(500, 640, 500, 668, "r85", "var(--basis)", 2.4),
        node("separate", 110, 672, 780, 92, "basis", "8:39 · THE ANSWER · NEITHER … NOR …", "nothing will be able to separate us from the love of God", "x"),
        note(500, 790, "The question asked of “the love of Christ” (8:35); the answer names “the love of God that is in "
             "Christ Jesus our Lord” (8:39). “Anything else”: in the Berean, “anything else in all creation”.", anchor="middle", size=12),
    ]
    svg = greek_into("".join(parts), {"q": "τίς ἡμᾶς χωρίσει ἀπὸ τῆς ἀγάπης τοῦ Χριστοῦ;",
                                      "conquer": "ἐν τούτοις πᾶσιν ὑπερνικῶμεν",
                                      "separate": "οὔτε … δυνήσεται ἡμᾶς χωρίσαι ἀπὸ τῆς ἀγάπης τοῦ Θεοῦ"}, 14)
    return f'<svg viewBox="0 0 1000 806" role="img" aria-label="Romans 8:35-39 drawn">{a}{svg}</svg>'


# EVERY BOX OPENS ITS CARD, per drawing (a list item and a saying may share a group name across drawings)
LINKS = {
    "s1": {"nocond": "/e/no_condemnation", "spiritlaw": "/e/the_law_of_the_spirit_of_life", "sinlaw": "/p/Rom.8.2",
           "powerless": "/p/Rom.8.3", "goddid": "/p/Rom.8.3", "fulfilled": "/p/Rom.8.4",
           "fleshmind": "/e/to_be_carnally_minded_is_death", "death": "/e/to_be_carnally_minded_is_death",
           "spiritmind": "/p/Rom.8.6", "lifepeace": "/p/Rom.8.6", "dwells": "/p/Rom.8.11", "mortal": "/p/Rom.8.11"},
    "s2": {"debt": "/p/Rom.8.12", "led": "/e/led_by_the_spirit", "sons": "/e/led_by_the_spirit",
           "slavery": "/p/Rom.8.15", "adoption": "/e/the_spirit_of_adoption", "testifies": "/p/Rom.8.16",
           "children": "/p/Rom.8.17", "heirs": "/e/heirs_of_god_and_joint_heirs_with_christ",
           "ofgod": "/e/heirs_of_god_and_joint_heirs_with_christ", "coheirs": "/e/heirs_of_god_and_joint_heirs_with_christ",
           "suffer": "/p/Rom.8.17", "glorified": "/p/Rom.8.17"},
    "s3": {"present": "/e/the_sufferings_of_this_present_time", "glory": "/e/the_sufferings_of_this_present_time",
           "waits": "/p/Rom.8.19", "creation": "/e/the_whole_creation_groans", "we": "/p/Rom.8.23",
           "spirit": "/e/groanings_which_cannot_be_uttered", "hope": "/p/Rom.8.24",
           "unseen": "/e/hope_that_is_seen_is_not_hope", "patience": "/p/Rom.8.25"},
    "s4": {"works": "/e/all_things_work_together", "foreknew": "/e/those_he_predestined_he_also_called",
           "predestined": "/e/those_he_predestined_he_also_called", "called": "/e/those_he_predestined_he_also_called",
           "justified": "/e/those_he_predestined_he_also_called", "glorified": "/e/those_he_predestined_he_also_called",
           "q1": "/e/if_god_is_for_us_who_can_be_against_us", "a1": "/e/he_that_spared_not_his_own_son",
           "q2": "/p/Rom.8.33", "a2": "/p/Rom.8.33", "q3": "/p/Rom.8.34", "a3": "/p/Rom.8.34"},
    "s5": {"q": "/e/who_shall_separate_us_from_the_love_of_christ",
           "written": "/e/we_are_accounted_as_sheep_for_the_slaughter",
           "conquer": "/e/more_than_conquerors", "separate": "/p/Rom.8.39",
           **{k: "/p/Rom.8.35" for k in ("trouble", "distress", "persecution", "famine", "nakedness", "danger", "sword")}},
}
SECTIONS_HTML = [
    ("s1", "8:1–11 · Walking by the Spirit", "Why there is no condemnation, given in the text's own “for”, “so that” and “if”.", s1_svg),
    ("s2", "8:12–17 · Heirs with Christ", "Led by the Spirit, so sons; not slavery but adoption; and the chain of 8:17.", s2_svg),
    ("s3", "8:18–27 · Future Glory", "The scale of 8:18, the creation waiting, three groanings of one root, and hope.", s3_svg),
    ("s4", "8:28–34 · God Works in All Things", "The chain of 8:29–30 as the grammar makes it, and four questions.", s4_svg),
    ("s5", "8:35–39 · More than Conquerors", "One question, two lists, and the answer.", s5_svg),
]
DEFAULTS = {"s1": "/p/Rom.8.1", "s2": "/p/Rom.8.14", "s3": "/p/Rom.8.18", "s4": "/p/Rom.8.28", "s5": "/p/Rom.8.38"}


def linked(svg, links, default):
    """Each box a link: its card, or its verse; a list item with no card of its own opens the section's verse."""
    return re.sub(r'(<g class="node" data-c="([^"]+)">.*?</g>)',
                  lambda m: f'<a href="{links.get(m.group(2), default)}">{m.group(1)}</a>', svg, flags=re.S)


def rom8_html():
    out = ['<h1>Romans 8</h1><p class="s">From “no condemnation” to “nothing able to separate us”, in the five sections '
           'the Berean editors mark. The Spirit is named 21 times, and not once after 8:27; love is named only at the '
           'end. Each box opens its card.</p>', '<p class="fig-hint">Swipe sideways inside the drawing to see all of it.</p>', '<div class="fig">' + overview_svg() + '</div>']
    for key, title, sub, fn in SECTIONS_HTML:
        out.append(f'<h2 id="rom8-{key}">{html.escape(title)}</h2><p class="s">{html.escape(sub)}</p>'
                   + '<div class="fig">' + linked(fn(), LINKS[key], DEFAULTS[key]) + '</div>')
    return "".join(out)


def main():
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Romans 8 (mockup)</title><style>{CSS}
body{{margin:0;background:var(--bg);color:var(--ink)}} .wrap{{max-width:1000px;margin:0 auto;padding:24px 16px}}
h1{{font:700 34px Georgia;margin:8px 0 4px}} h2{{font:700 22px Georgia;margin:26px 0 2px}} .s{{font:17px/1.5 Georgia;color:var(--mute);margin:0 0 14px}}
svg{{width:100%;height:auto;display:block}}</style></head><body><div class="wrap">
<div class="kicker">CHAPTERS HAND-SELECTED BY THE SITE MAKER, DRAWN WHOLE</div>
{rom8_html()}
</div></body></html>"""
    out = HERE / "chapters-rom8.html"
    out.write_text(page, encoding="utf-8")
    png = HERE / "chapters-rom8.png"
    png.unlink(missing_ok=True)
    exe = next(b for b in BROWSERS if Path(b).exists())
    for _ in range(3):
        with tempfile.TemporaryDirectory(prefix="rom8-", ignore_cleanup_errors=True) as prof:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            "--window-size=1040,5000", f"--user-data-dir={prof}", f"--screenshot={png}", out.as_uri()],
                           check=False, timeout=120, capture_output=True)
            for _ in range(20):
                if png.exists():
                    break
                time.sleep(0.5)
        if png.exists():
            break
    print(out, "->", png if png.exists() else "(no PNG)")


if __name__ == "__main__":
    main()
