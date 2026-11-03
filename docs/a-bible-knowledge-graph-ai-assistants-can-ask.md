# A Bible Knowledge Graph AI Assistants Can Ask
---

*What I'm building next, and why. Nothing described here is live yet.*

People ask AI assistants about the Bible every day. *What does 1 Timothy 2:5 mean? Who said this? Is this the
Bible's view, or a character's?* The assistants answer well, and they answer fast. But most of what they draw on is
text: the words of a verse, a commentary, a web page. What they rarely have is structure: who is speaking, about
whom, on which verse, how certain the reading is, and whose reading it is.

That is the gap I want Bible Ontology to fill.

## What Bible Ontology is

Bible Ontology (bibleontology.org) is a free study site built on a knowledge graph of what the Bible's text says.
It is built from the Hebrew and Greek (MACULA's linguistic data, © Biblica, CC BY 4.0), with the Berean Standard Bible
as its English. Its relations come with their own evidence:

- **Every link cites the verse it rests on**, and the graph is being checked against those verses, relation by
  relation, by two independent readers. Where a verse turns out not to support its link, the link is corrected or
  withdrawn. "The Father knows the Son" cites Matthew 11:27, in Jesus's words, and nothing else.
- **Every claim says whose it is.** When Eliphaz speaks in Job, his words are his, not the narrator's. When Paul
  later quotes Eliphaz, the graph can show both.
- **Every reading is marked as a reading.** Where the text states something, the graph says so. Where an
  identification or a connection is an interpretation, the graph says that too, and says how sure it is.
- **The original language decides.** Where English translations differ, the Hebrew or Greek settles it. "The
  original" means a named text: the Westminster Leningrad Codex for the Hebrew and Aramaic, and the Nestle 1904 Greek
  New Testament, as MACULA gives them.
- **It takes no side where Christian traditions divide.** Where readers disagree, it shows the verses each reading
  rests on, and leaves the tension open where the text leaves it open.

The demand is already visible. In Bing's AI performance report, the site's page for 1 Timothy 2:5 has been used as
a source for answers to that question 227 times, and its page on the Father, Son and Holy Spirit 128 times.
Assistants are already reaching for structured, sourced pages. I want to give them the structure directly.

## What I intend to offer

A public, read-only **Model Context Protocol (MCP) server**: a standard way for an AI assistant (Claude, ChatGPT and
others that support it) to ask the graph a question and get a structured answer back.

The plan is a small set of tools, shaped like the questions people ask:

- **search:** find the people, places, events, words, verses, questions and themes that match.
- **fetch:** the item whole, as text an assistant can read, with its relations and sources.
- **relations:** what the text says of a person, place, event or idea, strongest first, each with its verses.
- **verse:** a verse in the Berean's words, its original words, the passages the editors set beside it, and who is
  speaking.
- **word:** a Hebrew or Greek word: how it is rendered, where it is used, and its lexicon entry where the site
  shows one.

**Every answer will carry its evidence:**
- the verses, each with a link to its page;
- who says it (the narrator, or a named speaker);
- how certain it is (stated, implied, conjectured or disputed);
- whether it is a reading;
- the page it comes from, so an assistant can cite it and a reader can check it.

## What it will not do

- **It will not interpret.** The assistant does the conversation; the graph supplies the evidence. Bible Ontology
  is a source of structured evidence, not an authority on what the Bible means.
- **It will not return anything held back.** Readings and cards the site is not confident enough to show stay
  unshown.
- **It will not collect anyone's Bible study.** No accounts, no sign-in, no record of who asked what: only counts,
  as the site already keeps.
- **It will not change anything.** Read-only, with sensible limits so it stays available for everyone.

## Why provenance is the point

An answer that cites a verse and a voice can be checked. "The Bible says the crafty are caught in their craftiness"
is true in one sense, but it is Eliphaz who says it (Job 5:13), and God later says Eliphaz did not speak rightly
(Job 42:7). An assistant that knows *who* said a line, and on *which* verse, can tell its user the difference. That
is what this graph has been built to know, one verse at a time, and it is what I would like assistants to be able to
use.

The graph is licensed CC BY 4.0, so anyone may use it, with credit. Every answer from the server will carry a
ready-made citation and its page's address, so the credit is easy to give and the source easy to visit.

## How it will be built

- **Small and inspectable:** a thin layer over the site's existing services, one source of truth, so the site and
  the server can never disagree.
- **Built with Python's standard library alone:** no new third-party software in the path.
- **Reviewed for security before it goes live,** with limits on request size, answer size and rate.

## When, and how to connect

Not yet. When it is live, bibleontology.org/mcp will say how to connect it to Claude, to ChatGPT where its plans
allow, and to other MCP clients. I will not put a date on it; this page will be updated when it is real.

## An invitation

If you build AI tools, study the Bible, or work at one of the AI providers, I would value hearing from you, about
what would make a service like this most useful, and what would make it trustworthy. You can reach me at
bible.ontology@gmail.com, or join the conversation at r/BibleOntology.

*Doug Egge, November 2026*
