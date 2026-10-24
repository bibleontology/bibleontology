# Security

This repository runs a live site, https://bibleontology.org.

## Reporting a vulnerability

Please report it privately, not in a public issue:

- **On GitHub:** the repository's **Security** tab → **Report a vulnerability** (private vulnerability reporting); or
- **By email:** bible.ontology@gmail.com.

Say what you found and how to reproduce it. You will get a reply. There is no bounty: this is a one-person project with
no budget.

## Scope

- **In scope:** the server (`app2/`), its deployment files (`deploy/`), and anything that could expose what the site
  keeps private. That means readers' feedback notes and the operator's report.
- **Not a vulnerability:** an error in the graph itself (a wrong relation, a misattributed speaker). Please open an
  issue with the verse instead (`CONTRIBUTING.md`).

Please test against a local copy, not the live site. A local copy runs from this repository (`README.md`, "Run the
site").
