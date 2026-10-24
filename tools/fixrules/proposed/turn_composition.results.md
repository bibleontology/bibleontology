# turn_composition: run over the whole corpus (reviewed by Claude)

DETECT: 1,506 fired. That is far too broad: it fires wherever a turn's parts differ from the frame's `content` targets, and that difference is usually legitimate. From a sample of 3:
- 1Sa.7.5 | WRONG | "Gather all Israel to Mizpah, and I will pray": the part is `imp1`, a command-and-effect GROUP whose members include cl1. Groups nest inside turns by design (commands with their effects, parallels, acts of one agent). Replacing the group with its first clause loses the effect.
- 1Ki.18.44 | UNCLEAR | the part dropped is a nested turn (a speech inside a speech: "Go and tell Ahab, 'Prepare...'"). Nested quotation is also by design.
- 1Ki.2.17 | WRONG | a nested turn replaced by a clause, which loses the speech within the speech.

The fault found in 2Sa.17.14 was specific, and your audit stated it: a clause that begins with waw + an explicit subject + a finite verb (a narrative background clause, "and the LORD had ordained"), whose subject is neither the turn's speaker nor its addressee, is NARRATION. It is not part of the speech, and it is not a speech turn of its own. Narrow detect() to that. Only remove a part (and dissolve a turn that turn composition minted around such a clause) when the part is such a clause, or a turn framed by one. Never touch parts that are groups or nested turns framed by a verb of saying.
