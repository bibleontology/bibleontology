"""The four divine-person cards' shared header (2026-10-31).

One header, four cards: a sketch, the name, and the verse, with only the data
changed. The sketches come from ``deity_sketches.SKETCHES`` and are inserted
verbatim; every string taken from the card is escaped first.
"""
import html

try:  # imported as ``app2.deity_face``
    from .deity_sketches import SKETCHES
except ImportError:  # imported as ``deity_face``, with app2 on the path
    from deity_sketches import SKETCHES


CSS = """
.deity {
  padding: 0 0 14px;
  border-bottom: 1px solid var(--rule);
  color: var(--ink);
}
.deity .deity-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 16px;
}
.deity .deity-sketch {
  flex: 0 0 80px;
  width: 80px;
  height: 80px;
  color: var(--ochre-text);
}
.deity .deity-sketch svg {
  display: block;
  width: 80px;
  height: 80px;
}
.deity .deity-body {
  flex: 1 1 18em;
  min-width: 0;
}
.deity .deity-name {
  margin: 0;
  font-family: var(--ff-text);
  font-size: 30px;
  font-weight: 600;
  line-height: 1.15;
}
.deity .deity-verse {
  margin: 8px 0 0;
  font-family: var(--ff-text);
  font-size: 15px;
  line-height: 1.5;
}
.deity .deity-ref {
  margin-left: 0.35em;
  font-family: var(--ff-data);
  font-size: 13px;
  color: var(--muted);
  text-decoration: none;
  white-space: nowrap;
}
.deity .deity-ref:hover,
.deity .deity-ref:focus {
  color: var(--ochre-text);
  text-decoration: underline;
}
@media (max-width: 26em) {
  .deity .deity-row {
    display: block;
  }
  .deity .deity-sketch {
    margin-bottom: 10px;
  }
}
"""


def plate(card):
    """One card's header: the sketch, the name, then the verse and its reference."""
    name = html.escape(str(card["name"]), quote=True)
    text = html.escape(str(card["text"]), quote=True)
    ref = html.escape(str(card["ref"]), quote=True)
    go = html.escape(str(card["go"]), quote=True)
    sketch = SKETCHES[card["sketch"]]
    return (
        '<header class="deity">'
        '<div class="deity-row">'
        f'<div class="deity-sketch">{sketch}</div>'
        '<div class="deity-body">'
        f'<h1 class="deity-name">{name}</h1>'
        f'<p class="deity-verse">{text} '
        f'<a class="deity-ref" href="/p/{go}">{ref}</a></p>'
        "</div>"
        "</div>"
        "</header>"
    )
