# Contributing

Thank you for looking closely. The most useful thing you can send is a finding: a relation the verses do not support,
a person merged with someone else or split in two, a claim credited to the wrong voice, or a term that does not mean
what its definition says.

## How to send something

- **Open an issue.** Name the record or claim (its address, such as `https://bibleontology.org/e/kish`, or its claim
  id), the verse, and what you expected. A finding with its verse is checked first.
- **Pull requests are by invitation for now.** Open an issue first. If a change is wanted, the issue will say so, and
  a pull request is then welcome.
- **On the site,** "Something wrong or missing?" in the menu sends a note. What readers send there is read by the site's owner and the
  tools he builds with, and is not published.

## What "green" means

A change is ready when both of these pass in your checkout:

```bash
python -m bibleont.validate
```

```bash
python tools/run_tests.py
```

- **The validator** must end with 0 errors. Its warnings are leads for review, not failures.
- **`tools/run_tests.py`** runs the tests the project's own pre-deploy check runs, without needing the live server.
  `--all` adds the few that load the whole site (minutes each, about 2 GB of memory).
- **Tests that need files a public clone does not carry** (the KJV, MACULA's raw downloads) say "skipped" and pass.
- **Known red:** `tests/test_verse_structure.py` fails 144 checks after the October structure rebuilds. It is being
  diagnosed and is not run by either command.

Setup: Python 3.11 or later, then `pip install -e ".[rdf]"`. Add `".[rdf,wordnet]"` and
`python -m nltk.downloader wordnet` for the few checks that use WordNet; without it they are skipped, with a warning.

## The rules every change keeps

These are decisions, not oversights:

- **Every relation rests on verses.** A claim with no verse is not added.
- **No doctrine.** The graph records structure and who says what. Where traditions read a passage differently, each
  reading is credited to those who hold it, and none is chosen.
- **Readings are marked as readings,** with who made them: a person, a tradition, or a model run.
- **What a character says is that character's claim,** never the narrator's. Only what the text states or entails is
  asserted (`tests/test_assertion_policy.py`).
- **A held or uncertain reading is never quietly made a fact.**
- **The original language decides** where translations disagree.

## Licences

- Code you contribute is under the Apache License 2.0, as the code here is.
- Data you contribute is under CC BY 4.0, as the graph is.
- See `LICENSING.md`.
