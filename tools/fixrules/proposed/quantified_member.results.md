# quantified_member: run over the whole corpus (reviewed by Claude)

DETECT: 473 fired; fixed 332, invalid 42, rejected 99. The detection is right: a coordination member that is the quantifier כֹּל. The fix is WRONG where both members are "all X", because of a known limit of the graph: a word is ONE node per word text per verse. So "every spring and every valley" has a single node `#all` that stands for BOTH quantifiers, and the composite `#allandall` has two `member` edges to it (or one, deduplicated).
- 1Ki.18.5 | WRONG | "every spring and every valley" became text "springs and springs": both member slots were re-pointed to the first quantified noun.
- 1Ki.8.48 | WRONG | "all their heart and all their soul" became "heart and heart".
- 1Ch.26.30 | RIGHT | "all the work ... and the service" became "work and service".
- 1Ki.9.19 | refused by your own validate: three member edges to `#cities`.

Each quantified noun is the one the quantifier's `quantity` qualifier edge points FROM (noun -qualifier rel=quantity-> all). Where a verse has several, pair each member slot with a DIFFERENT quantified noun, in word order (use `w` positions, or the order of the qualifier edges). Never re-point two members to the same node. Where the pairing cannot be decided, skip it (detect nothing) rather than guess. Composite text: the member texts joined by " and ", in order.
