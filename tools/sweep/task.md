You are reading ONE verse of the Bible, in its original language, to settle its sentence structure. You are given the verse as a parser has already read it, and closed lists to choose from. Your job is to CHOOSE from the lists, never to invent.

Use no tools. Do not read files or search. Everything you need is below; answer from it alone.

## What you are given (the JSON at the end)

- `text`: the verse in the Berean Standard Bible; `before`: the verses before it in the same chapter, each with its clauses and groups by id.
- `clauses`: this verse's clauses in order. `gloss` is a word-by-word rendering of the original, so it follows the original's word order; `mood` is the verb form (wayyiqtol, weqatal, yiqtol, qatal, imperative, jussive, ...; for Greek: indicative, imperative, participle, ...); `verb` is its person/gender/number; `opens_with` is the conjunction or particle that begins the clause, in the original.
- `slots`: every pronoun and every subject the verb implies but does not name. `morph` is its person/gender/number. `builder_says` is the parser's current referent, which may be wrong.
- `candidates`: what a slot may refer to: nouns of this verse (local ids like `w7`), people and groups named in the verses before (full ids like `Exo.8.12#w4`), and composites (several people taken together).
- `builder_links`: the parser's clause-to-clause links. `builder_groups`: the parser's groups and their members.
- `link_types`: the only link types you may use, each with what it means. `group_kinds`: the only group kinds, each with its member roles.

## What to decide

1. **Each slot's referent.** Choose a candidate id, or `none` (no candidate fits), or `cant_tell` (the text does not settle it). Rules:
   - The original's morphology must agree: a masculine plural cannot refer to one woman.
   - A first or second person inside someone's speech refers to the speaker or the addressee of THAT speech; a command's implied "you" is the person the command is spoken to. Work out which speech a clause belongs to before resolving it: a clause that introduces a speech belongs to the speech around it, not to the one it introduces.
   - A third person most often refers to the nearest earlier agreeing referent that is a sensible doer of the act, but the act decides: an implied subject can be what the clause before it acted on.
   - A plural "they" that did what a command told two people to do refers to those people together (a composite candidate).
   - In a psalm, "I", "me", "my" are the psalm's own voice (a `voice` candidate) unless the psalm quotes someone else.

2. **Each builder link: keep or remove.** Remove one that the conjunction or the sense does not support. A plain "and" (וְ, καί) is not a cause, a result or a purpose unless the sense requires it.

3. **Links to add.** Use only `link_types`. Typical additions: a report that a command was carried out (`fulfils`, pointing at the command or its group, possibly in an earlier verse); someone doing the same as a deed just done (`likewise`); an outcome (`result`), and an attempt whose outcome failed (`failed_result`); a clause that gives the detail of an earlier one (`elaborates`); "so that" (`purpose`); "because/for" (`because`); "just as" (`as`). A link may point into an earlier verse with a full id.

4. **Groups.** Confirm, correct or add groups of the declared kinds, naming each member by its role. A group may contain another group (a speech that contains a command; a speech nested in a speech). Give new groups ids `g1`, `g2`, ...; refer to existing ones by their id.
   - Commands joined by "and" at one level are ONE imperative group with several `command` members; what the commands bring about (waw + a third-person weqatal after them) is that group's `effect`.
   - Speech nests: when one speaker tells another to say something to a third, the outer turn has the commanded turn as a part, and that turn has what is to be said as its part. Each turn's `sender` and `addressee` are candidates.

## Rulings to apply

These are the owner's rulings on how structure is recorded. Apply them as stated.

R1. **Speech content.** When a clause of saying (say, speak, call out, command) introduces what is said, link the saying clause to what is said with `content`: to the said clause, or to the imperative group when what is said is a collection of commands. Do this AS WELL AS putting both in a turn (`frame`, `part`); the turn does not replace the `content` link. Each level of nested speech gets its own `content` link.

R2. **Who speaks.** A turn's `sender` is the one the text has speaking. In a commanded speech (one person commanded to speak to another), the commanded words are spoken by the one commanded to speak them, not by the one who gives the command. A message they are told to deliver, quoting someone else, is a third, innermost turn whose sender is the one quoted. Where a dialogue does not name the speaker of each turn, take the speakers from its alternation: a reply is spoken by the other party. A clause that is a part of a turn is spoken by that turn's sender.

R3. **A condition inside a speech.** A conditional ("if ... then ...") that someone says is a part of that speaker's turn as a whole group: the turn's `part` is the conditional group. A Hebrew condition comes before the clause it governs.

R4. **Commands carried out, and their outcomes.**
   - A report that a command was carried out `fulfils` that command. When the command was a collection of commands joined by "and", a summary report (asah + ken, "did so") fulfils the WHOLE collection: point it at the imperative group. Each following clause that repeats one command's verb fulfils that command and `elaborates` the summary report.
   - Someone else then doing the same deed, uncommanded, is `likewise` to the deed just done. It is imitation, not fulfilment.
   - An attempt that has a `purpose`, then "and" + a negated verb of being able, is the attempt's `failed_result`.
   - A clause stating what an act or a state brings about is the earlier clause's `result`, not a plain `and` or `then`. Examples: an act done to something, then what that thing becomes; a will hardened, then the refusal that follows.
   - Do not make an `action-state` group whose second clause is already a fulfilment of a command.

R5. **Groups you may propose as readings.** `action-state`: a command or jussive, then the same act (the same verb) reported as having happened. `acts`: two or more clauses in a row that are acts of one agent, each stating its subject only in its verb, all resolving to the same referent. They are recorded as readings for review.

R6. **Two-line proverbs and couplets.** Two lines that answer each other, as in a proverb, form a `parallel` group (each a `line`) even when they are joined by a plain "and" and even when their subjects differ; the second answers the first. Where the lines share a subject, it is the group's `group_subject`.

R7. **A speech that runs across verses is one turn.** When a verse continues a speech begun in an earlier verse, its clauses are parts of THAT turn: give the earlier turn's full id (for example `Book.1.2#turn0`) with `"action": "extend"`, listing only this verse's new members. Do not start a new turn for the same speaker continuing the same speech.

R8. **Rhetorical questions have their own kind of answer.** The "who" or "what" of a rhetorical question, one asked so the hearer supplies the answer, resolves to the answer it implies, marked as a rhetorical answer: set `"rhetorical": true` on that referent, with the category "rhetorical answer". It is not an ordinary referent: the question points to the answer; the grammar does not name it. The answer a rhetorical question implies can be of three kinds, and you record whichever it is:
   - a person or thing among the candidates: choose it;
   - a concept, often a DENIAL ("who can be against us?" implies no one; "shall we go on sinning?" implies certainly not): choose `none` and write it in `"implied"` ("no one", "nothing", "certainly not", or the concept in a few words);
   - a passage: the text itself gives the answer, often in a clause after the question, possibly in a later verse of this passage. Give that clause's id in `"answered_by"` (a full id if it is in another verse).
   More than one may apply: a question answered by a later clause can also imply a concept.
   **Do not force it.** The graph is meant to interpret as little as it can. Record an answer only where the text makes it plain; otherwise mark the question `"rhetorical": true`, choose `none`, and leave `implied` and `answered_by` out. An unanswered rhetorical question is a good answer; a forced one is not.

5. **Say when the lists fail you.** If a relation the text plainly makes is not among `link_types` or `group_kinds`, record it in `none_fit`. If you cannot decide something, record it in `cant_tell`. Both are useful; a forced choice is not.

6. **Flag the divine persons.** If a choice you make identifies God, the LORD, the Father, Jesus or the Holy Spirit as a referent, sender or addressee, set `"divine": true` on it. Still make the choice; it will be reviewed.

Give every decision a `confidence`: `high` when the text settles it (the morphology, the conjunction or the speech structure leave no other reading), `medium` when it is the likely reading but another is possible, `low` when it is a guess. Be honest: a decision marked `high` that is wrong costs more than one marked `low`, because only the `medium` and `low` ones are reviewed.

Give every decision a short `why` that names the evidence (the morphology, the conjunction, the speech it is in, the word order), and a `category`: a few words naming the KIND of problem (for example "implied subject inside a commanded speech", "plain and read as result", "fulfilment of an earlier command"), never the particular verse.

## Answer

Reply with ONLY a JSON object, no prose before or after:

{"ref": "<the ref>",
 "referents": [{"slot": "<slot id>", "choice": "<candidate id>|none|cant_tell", "confidence": "high|medium|low", "divine": false, "rhetorical": false, "implied": "<rhetorical only: the concept implied, e.g. no one>", "answered_by": "<rhetorical only: the clause that answers it>", "why": "...", "category": "..."}],
 "links": [{"src": "<clause id>", "type": "<link type>", "dst": "<clause or group id>", "action": "keep|remove|add", "confidence": "high|medium|low", "why": "...", "category": "..."}],
 "groups": [{"id": "<existing id, g1, g2 ..., or an earlier verse's turn by full id>", "kind": "<group kind>", "action": "keep|change|add|remove|extend",
             "members": [{"role": "<member role>", "node": "<clause, group or candidate id>"}], "confidence": "high|medium|low", "divine": false, "why": "...", "category": "..."}],
 "none_fit": [{"where": "...", "what": "..."}],
 "cant_tell": [{"what": "...", "why": "..."}]}

Include every slot and every builder link exactly once. Include every builder group (keep, change or remove) and any new ones.

## The verse
