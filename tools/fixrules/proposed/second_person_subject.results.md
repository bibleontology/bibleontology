# second_person_subject (refined): run over the whole corpus (reviewed by Claude)

DETECT: 64 fired. From a sample of 3:
- 2Sa.12.13 | RIGHT | "You will not die": the subject was the LORD, and is now David, whom Nathan addresses.
- 2Ch.6.9 | RIGHT | "you are not the one to build it": the subject was the adverb "nevertheless" (a parse artifact), and is now David, who is addressed.
- 1Ki.9.6 | WRONG | "if you or your sons turn away": the subject is EXPLICIT and includes the second person: "you and your descendants" (a coordination: a composite with `member` edges, one of which is a second-person pronoun). The rule dropped it and put the addressee in its place. A subject that is, or contains as a member, a second-person pronoun already agrees and must not be replaced. Nor should a composite whose members include the addressee.

Replacing is right when the existing subject is (a) carried or inferred (it has an `inferred` mark), or (b) a word that cannot be a subject at all (an adverb, a particle). Replacing an explicit noun subject is the risky case. Consider leaving explicit noun subjects alone, and only ADDING a subject where there is none.
