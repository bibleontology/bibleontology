# A third reading: where two judges differed

Read `TORREY-JUDGE.md` first: it is the question both judges answered, and
`themes.md` lists the site's themes. For each topic in your batch, two
judges differed -- on whether a theme's subject takes it (home, partial,
none), or on which theme. You are given both verdicts with their reasons,
Torrey's sub-headings, and how many of the topic's verses each theme holds.

Decide yourself, on the same test: a topic has a **home** only if a theme
holds a fair share of its verses **and** a reader of that theme would expect
to meet it there; **partial** if a theme holds part of it but the topic is
wider; **none** if no theme's subject includes it. Agree with either judge
or with neither; say why in one sentence.

Write a JSON list to the path you are given, one object per topic, in the
batch's order:

```json
[{"topic": "...", "kind": "...", "fit": "home" | "partial" | "none",
  "theme": "<theme id or null>", "under": "<sub-theme or row, or null>",
  "why": "..."}]
```

**Do every topic in the batch; count them before you finish.** Reply with one
line: how many home, partial, none.
