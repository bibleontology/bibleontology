# DeepSeek passes held for the Mac (2026-11-18)

Built on the night of 2026-11-18 and held by Doug ("anything that depends on DeepSeek comes later as the Mac is still
offline"). Scratch scripts, kept so the run need not be rebuilt; paths inside point at that night's session scratchpad
and must be changed before use.

- **Cards with no relation (P-2026-11-18-5):** `zero_rel.py` (list them) -> `zero_cand.py` (verses, the three before
  as context, candidates) -> `zero_brief.py` (briefs of five, the published definitions as the only types) ->
  `zero_run.sh` (waits for off-peak, stops at the first empty answer). Sample: 2 of 5 with context.
- **Option C, names and plurals (P-2026-11-18-3):** `merge_evidence.py` (38 pairs, both records) -> `merge_brief.py`
  (one question per pair; no pair named as an example) -> `merge_run.sh` (two blind runs). Then Doug's sheet, then
  ontology/aliases.jsonl.
