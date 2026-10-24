# parallel_lines_agree: run over the whole corpus (reviewed by Claude)

DETECT: 214 groups fired, every one on a subject whose person differs
between the two lines (the negation test never fired alone). A sample of 5
was judged, 5 RIGHT:
- 1Ki.1.18 | RIGHT | "Adonijah has become king" (3rd) // "you do not know" (2nd)
- 1Sa.16.12 | RIGHT | 3rd vs 2nd: the lines do not share a subject
- 1Sa.1.22 | RIGHT | 3rd vs 1st
- 1Ki.2.31 | RIGHT | 2nd vs 3rd
- Exo.4.6 | RIGHT | "Put your hand inside your cloak" (2nd) // "he put his hand" (3rd)

FIX, two failures:
- WRONG in all 214: the second line's content keeps the subject the group
  CARRIED onto it: an `s` role edge marked
  `inferred: "carried from the parallel line above"` (1Ki.1.18: ct1 -s->
  Adonijah, so the graph still says "Adonijah does not know"). The group
  node also has its own `s` edge to that subject. Ungrouping must remove
  the carried subject, since that is the part of the fault that changes what
  the verse says. validate() did not check for it.
- WRONG in 55 of 214: an `and` link was added where the clauses had no
  clause link at all. Nothing in the text was shown to have a conjunction
  there. Do not add a link the text does not show; in the other 159 a link
  already exists.
