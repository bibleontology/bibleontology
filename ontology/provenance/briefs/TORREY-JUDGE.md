# Does this topic have a home among the site's themes?

A Bible website has 24 major themes. Each theme has sub-themes and a table of
wordings several books share; all are listed in `themes.md`. The site is
checking its themes for completeness against an old public-domain topical
index, Torrey's *New Topical Textbook* (1897). Your batch is a list of Torrey
topics. For each you are given Torrey's own sub-headings (what he lists under
it), how many Bible verses he cites for it, and how many of those verses each
theme already holds (the four themes holding most).

Decide, for each topic, **two things at once** (the site's owner: *"it has
to fit within the overall theme as well as the topic"*):

1. **Kind**: `teaching` (about God, Christ, the Spirit, salvation, sin, the
   last things...), `practice` (prayer, fasting, giving, worship, work,
   marriage...), `virtue_or_vice` (love, joy, pride, anger...), `office`
   (priests, prophets, kings, servants...), `people` (a nation, tribe or
   group), `person`, `place`, `thing` (an object, animal, plant, material),
   `event`, or `other`.
2. **Home**: is there a theme whose **subject** the topic belongs to -- not
   merely one that shares some of its verses? Name it, and the sub-theme or
   row it fits under if one does. A topic belongs to a theme only if both
   hold: the theme holds a fair share of its verses (as a rule, at least a
   tenth, or 10 or more), **and** a reader of that theme would expect to meet
   this topic there. Shared verses alone are not a home (Prayer is not
   Mercy & Restoration because some prayers ask for mercy).

   - `home`: it belongs to a theme's subject, and is at home there.
   - `partial`: a theme holds part of it, but the topic is wider than the
     theme, or the theme touches it only in passing.
   - `none`: no theme's subject includes it.

People, places, things and events are usually the site's cards' business,
not its themes'; judge them the same way, but they will often be `none`.

Write a JSON list to the path you are given, one object per topic, in the
batch's order:

```json
[{"topic": "<as given>", "kind": "...", "fit": "home" | "partial" | "none",
  "theme": "<theme id or null>", "under": "<sub-theme or row, or null>",
  "why": "<one short sentence>"}]
```

Count the entries before you finish. Reply with one line: how many home,
partial, none.
