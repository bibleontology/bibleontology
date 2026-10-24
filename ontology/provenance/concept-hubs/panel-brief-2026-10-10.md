# Panel review: one concept hub

A non-profit website (bibleontology.org) shows a knowledge graph of the Bible
built from the original Hebrew, Aramaic and Greek, with the Berean Standard
Bible's English. A concept's **hub** sets out its verses in rows by the forms
its words take and the words beside them -- every row a set of verses, its
label in the text's words, sometimes a note. The hubs for love and
righteousness are live. Yours was built by another worker and is not yet
shown.

Repository: `<local> Ontology`. **Read only. Edit
nothing in the repository.**

## Read

- `out/concept-hubs/<id>.json` -- the built hub: `words` (its original words),
  `own_words` (key verses), `forms` -> `rows` (label, note, n verses, `eg` the
  examples a reader sees first, `verses` all of them), `others` (different
  words English renders the same way, shown apart).
- `ontology/concept-hubs/<id>.json` -- the spec, with the builder's `_why`
  notes.
- The worker's report: `<local>`
  -- especially its list of contested points for the panel.
- Any verse in the Berean: `curl -s "http://localhost:8002/api/verse?ref=Book.c.v"`.
- For comparison, the live hubs: `out/concept-hubs/love.json`,
  `out/concept-hubs/righteousness.json`.

## The rules the hub must keep

1. **True to the text, first.** Nothing softened, nothing added; a label says
   only what its verses say.
2. **No doctrine.** Where Christian traditions part, the text's verses stand
   side by side with a note that the page takes no side; never a verdict.
3. **The divine persons by hand**, never by an inferred rule.
4. **Different words informed**: a row never equates two different original
   words; one sense of a word is never presented as its whole.
5. **The Hebrew Scriptures heard on their own terms first**: an Old Testament
   verse is not filed under a New Testament heading as if it belonged there.
6. **Every example shows its label.**

## The panel (eleven seats; a change ships only if all could accept it)

Lutheran; Reformed; Wesleyan; Baptist / free church (leans conservative);
Pentecostal / Charismatic; secular academic scholar of the Bible; Catholic
and Eastern Orthodox (within the 66 books shown); biblical-theological
(literary); a rabbi (reads the Hebrew Scriptures on their own terms; may
object to framing or missing context the text supplies, but cannot block a
fair representation of the text; defers to the other seats on how a Christian
tradition reads its own text); a young African American believer (deep faith,
high view of Scripture, attentive to justice; guards against US political
framing either way and against culturally insensitive presentation). The
panel is a cross-section on purpose: every reader it represents should be
welcome on the site.

## Return

Write JSON to `<id>-panel.json` in the scratchpad hubs folder:

```json
{"id": "<id>",
 "overall": "ship" | "ship after fixes" | "do not ship",
 "fixes": [{"row": "<label>", "kind": "tilt" | "misfit" | "different words" | "OT framing" | "label" | "note",
            "verses": ["..."], "readers": ["..."], "why": "...", "fix": "<concrete: relabel to X / move V to row Y / add note Z / split>"}],
 "worker_points": [{"point": "<from the report>", "verdict": "fine" | "fix", "why": "..."}],
 "missing": [{"what": "...", "verses": ["..."]}],
 "summary": "<two sentences>"}
```

At most 3 "missing". Flag only what a reader would actually object to or be
misled by -- not what is merely difficult. Check every row's four examples
against its label (read them in the Berean). Reply with one line: overall and
the number of fixes.
