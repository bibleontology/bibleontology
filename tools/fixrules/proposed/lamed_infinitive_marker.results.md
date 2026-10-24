# lamed_infinitive_marker: run over the whole corpus (reviewed by Claude)

DETECT: 0 fired anywhere, including 2Sa.17.14 itself.
- WRONG (a bug): `_nested_infinitives` looks for `content` / `within` edges
  from the CONTENT node (`v.content(c)`). Clause links run CLAUSE -> CLAUSE
  (the framework docstring: "CLAUSE LINKS, clause_link: True, clause ->
  clause"). In 2Sa.17.14 they are `2Sa.17.14#cl2 -within-> #cl3` and
  `#cl2 -content-> #cl3`, where cl3 is the infinitive construct.
- The pp edge there is `2Sa.17.14#ct2 -pp-> 2Sa.17.14#lord` with
  `prep: "לְ"`, and the clause's subject is also `#lord`. Keep the test that
  the pp's object is also the subject: that is what marks it as a false
  participant. Consider whether requiring it makes the rule too narrow; a
  לְ immediately before an infinitive construct is a marker whatever its pp
  points to.
