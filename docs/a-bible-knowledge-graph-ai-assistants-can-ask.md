# A Bible Knowledge Graph AI Assistants Can Ask
---

*Update, 3 November 2026: the server is live at `https://bibleontology.org/mcp`. This page first announced the
intent; it now says what the server does, and what comes next. How to connect is at bibleontology.org/mcp.*

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

## What it offers

A public, read-only **Model Context Protocol (MCP) server**: a standard way for an AI assistant (Claude, ChatGPT and
others that support it) to ask the graph a question and get a structured answer back. No account, no sign-in.

A small set of tools, shaped like the questions people ask:

- **start:** where to begin, for an assistant with no question yet.
- **search:** the people, places, events, verses and themes that match.
- **fetch:** one item whole, as text an assistant can read, with where to go next.
- **get_relations:** an item's relations, strongest first, page by page.
- **get_verse** and **get_word:** a verse by reference, in the Berean's words, with the passages that quote it or
  stand beside it; a Hebrew or Greek word by Strong's number, with its lexicon entry where the site shows one.

**Every answer carries its evidence:**
- the verses, each with a link to its page;
- who says it (the narrator, or a named speaker);
- how certain it is: stated, implied, or a reading;
- the page it comes from, so an assistant can cite it and a reader can check it.

## The answer is the map

The part I am most curious about: every answer ends with where to go next. Each link is a relation from the graph's
published vocabulary, with the verse that makes it, how sure it is, and whose words it rests on. This is what the
server returns, today, for Jesus' temptation:

- "the angels ministered to Jesus", Mark 1:13, stated;
- "Jesus quoted *Man shall not live on bread alone*", Matthew 4:4, stated;
- and a short map of everything else there: eight quotations, the places he went, and three echoes of Israel's
  wilderness years (the manna, the water from the rock, the giving of the law), each one marked as a reading;
- moves down to each of the three tellings, in Matthew, Mark and Luke.

A relation can itself be opened. Ask for *re-enacts* and the answer is its definition ("a later account is told so
as to re-enact an earlier one"), its inverse, and every place in the graph where it holds, each with its verse (for
*re-enacts*, so far, only the temptation's three; for *quoted*, 68; for *ministered to*, 24). The schema and the data are
one walk.

Web developers will recognize the idea: hypermedia, the answer telling the client what it can do next. It never
really took off for programs, which hard-code their routes. An AI assistant reads the labels and chooses, so perhaps
this time the idea has its client.

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

The graph is licensed CC BY 4.0, so anyone may use it, with credit. Every answer from the server carries a
ready-made citation and its page's address, so the credit is easy to give and the source easy to visit.

## How it is built

- **Small and inspectable:** a thin layer over the site's existing services, one source of truth, so the site and
  the server can never disagree.
- **Built with Python's standard library alone:** no new third-party software in the path.
- **Reviewed for security before it went live,** by a separate review that read the code cold, with limits on
  request size, answer size and rate, and on how many calls run at once.

## How to connect

bibleontology.org/mcp says how, for Claude (a custom connector, with no sign-in), for ChatGPT where its plans allow,
and for any other MCP client.

## What comes next

I am stating these in order, without dates:

1. **Expansion chosen by the assistant.** An assistant will be able to ask for a card *with* its quotations, or *with*
   the scene it sits in, in one call, choosing from what the answer offers. Measured against today's version: does
   it need fewer calls?
2. **Suggestions from assistants.** A way for an assistant to say "this link is missing" or "this one looks wrong",
   with its verses, into a review queue, never straight into the graph. The corrections made from them will be
   published, so an assistant can see that its suggestion was heard.
3. **The conventions, published.** How these links, maps and moves are shaped will be written up openly, so any MCP
   server could use them.

## An invitation

If you build AI tools, study the Bible, or work at one of the AI providers, I would value hearing from you, about
what would make a service like this most useful, and what would make it trustworthy. You can reach me at
bible.ontology@gmail.com, or join the conversation at r/BibleOntology.

*Doug Egge, November 2026*
