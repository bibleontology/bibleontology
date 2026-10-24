#!/usr/bin/env bash
# Pre-deploy check. RUNS ON YOUR LAPTOP, from the repo root, before pushing.
#
#   bash deploy/preflight.sh
#
# Answers one question: is there anything outstanding that should be dealt
# with before this goes live. It does not deploy anything and changes nothing.
#
# Exit 0 means the mechanical checks pass. It does not mean "push now" --
# timing is a judgement, and the last section is there to prompt it.
set -uo pipefail

REMOTE="${REMOTE:-live}"
BRANCH="${BRANCH:-master}"
PY="${PY:-python}"
export PYTHONPATH="${PYTHONPATH:-src}"

fail=0
warn=0

ok()   { printf '  \033[32mok\033[0m    %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }
note() { printf '  \033[33mnote\033[0m  %s\n' "$1"; warn=$((warn+1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "Working tree"

# A CHANGED TRACKED FILE FAILS; AN UNTRACKED ONE IS A NOTE.
# 2026-10-02. Untracked files were a FAIL too, so preflight failed on every
# run for a month over September's experiments and a test's leftovers, and
# a real blocker would have read as the usual noise. Untracked work still
# does not go with a push -- the note says so and lists it.
tracked="$(git status --porcelain --untracked-files=no)"
untracked="$(git status --porcelain | grep '^??' || true)"
if [ -n "$tracked" ]; then
	bad "uncommitted changes -- a push sends commits, so these would not go"
	printf '%s\n' "$tracked" | sed 's/^/        /'
else
	ok "no uncommitted changes to tracked files"
fi
if [ -n "$untracked" ]; then
	note "untracked files -- not part of any commit, so a push does not send them"
	printf '%s\n' "$untracked" | sed 's/^/        /'
fi

head_ "What would go live"

# WHAT IS CHECKED IS HEAD, NOT LOCAL master. 2026-10-04: the work sat on
# another branch; this compared live/master..master -- an empty range -- so
# it skipped the suites "no changes under app2/" while index.html had
# changed, and printed `git push live master`, which pushed nothing
# ("Everything up-to-date"). The push command at the end now names HEAD
# whenever the checkout is not on $BRANCH.
here="$(git rev-parse --abbrev-ref HEAD)"
range="$REMOTE/$BRANCH..HEAD"
if [ "$here" = "$BRANCH" ]; then
	push="git push $REMOTE $BRANCH"
else
	push="git push $REMOTE HEAD:$BRANCH"
	note "on branch '$here', not '$BRANCH' -- checking and pushing HEAD"
fi
if git rev-parse --verify -q "$REMOTE/$BRANCH" >/dev/null && \
		! git merge-base --is-ancestor "$REMOTE/$BRANCH" HEAD; then
	bad "HEAD does not contain $REMOTE/$BRANCH -- the push would be refused (or would discard live commits)"
fi
if ! git rev-parse --verify -q "$REMOTE/$BRANCH" >/dev/null; then
	note "no $REMOTE/$BRANCH ref yet -- first push, or run: git fetch $REMOTE"
	range=""
	changed=""
else
	changed="$(git diff --name-only "$range")"
	n="$(git rev-list --count "$range")"
	if [ "$n" = "0" ]; then
		ok "nothing pending -- live is already at $(git rev-parse --short "$REMOTE/$BRANCH")"
	else
		ok "$n commit(s) pending"
		git log --oneline "$range" | sed 's/^/        /'
	fi
fi

head_ "The graph"

# Always. The data is the product, and validating it costs seconds.
out="$($PY -m bibleont.validate 2>&1)"
summary="$(printf '%s' "$out" | tail -1)"
if grep -qE ', 0 errors' <<<"$summary"; then
	ok "$summary"
	# Warnings are not failures -- some are known and deliberate -- but they
	# should be seen rather than counted.
	printf '%s' "$out" | grep -E '^WARNING' | sed 's/^/        /'
else
	bad "validator reports errors"
	printf '%s' "$out" | tail -20 | sed 's/^/        /'
fi

head_ "Prebuilt representations"

# app2 loads two prebuilt files only when they were built from the data now
# in the tree (by fingerprint). If not, it rebuilds them in memory at start --
# the clause structure as text, the verse matches as 1.1 GB of records --
# which the 4 GB droplet cannot afford. Stale means: rebuild, commit, then push.
# (2026-10-01, docs/LAUNCH.md.)
fp="$($PY - <<'EOF' 2>&1
import gzip, json, sys
sys.path.insert(0, "tools")
import structure as S
with open(S.BLOCKS, "rb") as f:
    print("structure", json.loads(f.readline()).get("_inputs") == S._inputs())
import importlib.util
spec = importlib.util.spec_from_file_location("srv", "app2/server.py")
m = importlib.util.module_from_spec(spec); sys.argv = ["x"]; spec.loader.exec_module(m)
h = json.loads(gzip.open("out/aligned-verses.jsonl.gz", "rt", encoding="utf-8").readline())
print("aligned", h.get("_inputs") == m.aligned_inputs())
EOF
)"
if grep -q '^structure True' <<<"$fp"; then
	ok "out/structure-chapters.bin matches the graph files"
else
	bad "out/structure-chapters.bin is stale or missing -- python tools/structure.py --blocks, then commit"
fi
if grep -q '^aligned True' <<<"$fp"; then
	ok "out/aligned-verses.jsonl.gz matches its inputs"
else
	bad "out/aligned-verses.jsonl.gz is stale or missing -- python tools/patterns/aligned_verses.py, then commit"
fi

head_ "Regression suites"

# NEVER `printf "$changed" | grep -q` HERE. grep -q stops reading at the first
# match, printf then fails on the closed pipe, and under `pipefail` the whole
# test reads as NO match. On a small range it happened to work; on the app2
# deploy (923 commits, 2026-10-01) preflight reported "no changes under src/"
# with 41 of them, and "no system config" with the Caddyfile and the unit
# both changed -- skipping the suites and the reinstall reminder in silence.
# `has` reads the list directly, with no pipe.
has() { grep -qE "$1" <<<"$changed"; }

# Only when the code that could break them has changed. Running them on a
# data-only change proves nothing and trains you to skim the output.
if [ -z "$range" ] || has '^src/'; then
	for t in tests/test_citations.py tests/test_phrases.py; do
		if $PY "$t" >/dev/null 2>&1; then
			ok "$(basename "$t")"
		else
			bad "$(basename "$t") -- run it directly to see why"
		fi
	done
else
	ok "skipped -- no changes under src/"
fi

# The site-voice text of the readings (plan 6.17), on EVERY push: a data-only
# change is exactly what can put a misquote or a site-voice "fulfils" in
# front of readers, and it takes two seconds. 2026-10-04: only spot checks of this work are
# possible by hand, so the checks must be vigilant now that this
# is released to the public frequently. Proven by planting one fault
# of each kind: all six caught.
if out="$($PY tests/test_readings_text.py 2>&1)"; then
	ok "readings text: $(head -1 <<<"$out")"
else
	bad "readings text failed -- python tests/test_readings_text.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The theme tags in the reader (2026-10-08): exactly the verses each theme's
# own table and front page set out, brackets opening the table at the row,
# and none of the retired September theme stamps. Three planted faults caught.
if out="$($PY tests/test_theme_tags.py 2>&1)"; then
	ok "theme tags: $(head -1 <<<"$out")"
else
	bad "theme tags failed -- python tests/test_theme_tags.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The declared lists (A.34, 2026-10-07): one card each, every member a node,
# every member and move in its verse's words, and the card's links served by
# the page's delegated listener. Proven by planting nine faults: all caught.
if out="$($PY tests/test_aggregate_hubs.py 2>&1)"; then
	ok "declared lists: $(head -1 <<<"$out")"
else
	bad "declared lists failed -- python tests/test_aggregate_hubs.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The marks beside the Berean's words (2026-10-08): the Berean's manuscript
# note on every verse of Mark 16:9-20 and John 7:53-8:11, and each finding on
# the original at a word that is in its verse. A planted fault proves it.
# A card's words, one definition (plan 4.8 step 0(a), 2026-10-19): the server,
# the concept audit and the resolution layer all ask tools/meaning/membership.py.
# Its rules each with a planted case, and no caller keeping its own copy.
if out="$($PY tests/test_membership.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "card membership failed -- python tests/test_membership.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The filter policy is the one source (plan 8.1f): ontology/schema/salience.json
# read by membership.py, served to the navigator, the page's fallbacks equal.
if out="$($PY tests/test_salience.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "filter policy failed -- python tests/test_salience.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The filter, published (plan 8.1f): the shown card words pass their SHACL
# shape and a planted weak word fails; the published CONSTRUCT gives the shown
# graph; each centre's floor is the policy's rule over the published ties.
if out="$($PY tests/test_filter_exports.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "filter exports failed -- python tests/test_filter_exports.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# Verb statements keep their rules (plan 2.17 step 3): only a statement made
# outright is asserted; every family is in the declared scheme. Planted faults.
if out="$($PY tests/test_statements.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "verb statements failed -- python tests/test_statements.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# About's pictures (the hybrid, 2026-10-20): the four statements it shows keep
# the standing it claims for them, or About would say something false.
if out="$($PY tests/test_about_primer.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "About's pictures failed -- python tests/test_about_primer.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The relation vocabulary's "one of" shapes (before 1.2.0): where a relation's
# end allows several classes, a SHACL list means either; the whole store, typed
# by kind, conforms, and two planted faults are caught.
if out="$($PY tests/test_relation_shapes.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "relation shapes failed -- python tests/test_relation_shapes.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The schema map (2026-10-20: not all deeplinks worked): every link lands
# on an entry of the vocabulary page 1.2.0 publishes, or on a picture in the
# map; the committed map is what tools/ns_map.py draws; a planted bad link fails.
if out="$($PY tests/test_ns_map.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "schema map failed -- python tests/test_ns_map.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# No character's words stated as the text's own (third sitting, D1): none of
# the narrator's shown statements inside the Berean's quotation marks, in
# Psalms, or addressed in the second person; planted releases caught.
if out="$($PY tests/test_quoted_speech.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "quoted speech failed -- python tests/test_quoted_speech.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The alignment file (plan 8.1e): every mapping's term of ours exists, every
# target was checked against its specification (ontology/align/targets.json),
# no exact matches, and the published copy is the generator's.
if out="$($PY tests/test_alignment.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "alignment failed -- python tests/test_alignment.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# Readers on /ops (2026-10-22): a visitor counts as a reader only once the
# page's script sends /api/open; referrers ride on it; a farm that never runs
# the page stays out of readers, devices and referrers.
if out="$($PY tests/test_activity_readers.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "readers on /ops failed -- python tests/test_activity_readers.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The browsers that open /ops are not counted (2026-10-22): bo_uncounted,
# site-wide and secretless, set when /ops opens; the token stays on /ops
if out="$($PY tests/test_ops_uncounted.py 2>&1)"; then
	ok "own browsers uncounted: $(tail -1 <<<"$out")"
else
	bad "own browsers on /ops failed -- python tests/test_ops_uncounted.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The exports' terms (plan 8.3): every header, the VoID/DCAT description and
# the graph_license switch say one thing; MACULA credited in its own words.
if out="$($PY tests/test_export_terms.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "export terms failed -- python tests/test_export_terms.py (rebuild: tools/export_*.py)"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The 1.2.0 shape against one worked example of each lift (plan 8.1e item 5):
# every term declared, the named gaps exactly those proposed, and a command or
# a prediction described, never stated, by the export's own rule. Planted faults.
if out="$($PY tests/test_lift_shapes.py 2>&1)"; then
	ok "$(head -1 <<<"$out")"
else
	bad "lift shapes failed -- python tests/test_lift_shapes.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
if out="$($PY tests/test_verse_marks.py 2>&1)"; then
	ok "verse marks: $(head -1 <<<"$out")"
else
	bad "verse marks failed -- python tests/test_verse_marks.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# Coordination members (plan 2.15, 2026-10-17): a coordination's members are
# its conjuncts, never the conjunction ("Peter and and", Luke 22:8, and 2,188
# Greek coordinations like it). The builder on Luke 22:8 and the graph served;
# a planted fault proves it.
if out="$($PY tests/test_coordination_members.py 2>&1)"; then
	ok "coordinations: $(head -1 <<<"$out")"
else
	bad "coordinations failed -- python tests/test_coordination_members.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The closed world (plan 1.42, 2026-10-18): ontology/kinds.json and the graph
# agree in both directions -- every kind declared built exists, nothing exists
# undeclared, every edge within its declared ends. It drifted to 84
# disagreements unseen when the builder was replaced; three planted faults
# prove it. Reads the whole graph: a few minutes.
if out="$($PY tests/test_ontology_closed_world.py 2>&1)"; then
	ok "closed world: $(head -1 <<<"$out")"
else
	bad "closed world failed -- python tests/test_ontology_closed_world.py"
	grep -E "FAIL" <<<"$out" | head -8
fi
# The claim export (plan 8.1a, 2026-10-14): every claim conforms to its
# shapes, and a planted fault per rule is caught
if out="$($PY tests/test_claims.py 2>&1)"; then
	ok "claims: $(tail -1 <<<"$out")"
else
	bad "claim export broken -- python tests/test_claims.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The published shapes pass on the published data, and every record a claim
# names has a label (the code review, 2026-10-22: it failed 2,828 times)
if out="$($PY tests/test_export_shapes.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "the exports fail their own shapes -- python tests/test_export_shapes.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# What the export asserts is the narrator's, as the README claims (plan 8.3f,
# 2026-10-22): counted in the published files, with planted faults
if out="$($PY tests/test_assertion_policy.py 2>&1)"; then
	ok "$(tail -1 <<<"$out")"
else
	bad "the export asserts what the narrator does not state -- python tests/test_assertion_policy.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The stylesheet (2026-10-13): no CSS line a stray quote has broken -- five
# had silently deleted rules, unnoticed since they were written
if out="$($PY tests/test_css.py 2>&1)"; then
	ok "stylesheet: $(tail -1 <<<"$out")"
else
	bad "stylesheet broken -- python tests/test_css.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The crawler line (2026-10-05): robots.txt and the Caddyfile's @training
# refuse the same training crawlers, and the rule lets Googlebot, Bingbot and
# the AI search fetchers through -- Cloudflare's own training block once
# kept Google out of every page. Proven by planting Googlebot in the rule.
if out="$($PY tests/test_crawlers.py 2>&1)"; then
	ok "crawlers: $(tail -1 <<<"$out")"
else
	bad "crawler line broken -- python tests/test_crawlers.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi
# The blog (2026-10-05): every post's page built from its current text, so
# what goes live is what the author wrote -- an edited post not rebuilt fails
if out="$($PY tests/test_blog.py 2>&1)"; then
	ok "blog: $(tail -1 <<<"$out")"
else
	bad "blog pages out of date -- python tools/blog_build.py"
	grep -E "^FAIL" <<<"$out" | head -8
fi

head_ "Search smoke sweep"

# Plan A.24 (P-89 approved 2026-10-02). A shadowed variable in search
# answered 400 to ~10% of everyday words for most of a day and nothing ran
# search. In-process, ~1 minute; proven by reintroducing that bug (60 of 625
# failed). Only when the app itself changed, like the suites above.
if [ -z "$range" ] || has '^app2/'; then
	if out="$($PY tools/search_smoke.py 2>&1)"; then
		ok "$(grep -E 'searches in' <<<"$out")"
	else
		bad "search smoke sweep failed -- python tools/search_smoke.py"
		grep -E "searches in|^  '" <<<"$out" | head -8
	fi
	# THE ONE WRITE PATH (A.27): every rule reader feedback holds -- origin,
	# type, size, the hidden field, the rate limit, escaping on /ops --
	# against the real handler, writing to a temporary folder
	if out="$($PY tests/test_feedback_intake.py 2>&1)"; then
		ok "feedback intake: every rule held"
	else
		bad "feedback intake test failed -- python tests/test_feedback_intake.py"
		grep -E "^FAIL" <<<"$out" | head -8
	fi
	# EVERY LINK A CRAWLER IS GIVEN ANSWERS WITHOUT A REDIRECT (2026-10-05):
	# card pages linked verses by the dataset's book code and AhrefsBot spent
	# 926 requests in a few hours on 301s. ~1 minute, in process
	if out="$($PY tests/test_card_links.py 2>&1)"; then
		ok "card pages: $(tail -1 <<<"$out")"
	else
		bad "card pages link redirecting addresses -- python tests/test_card_links.py"
		grep -E "^FAIL" <<<"$out" | head -8
	fi
	# NO TOOL NAMED, NO AI POINTED AT, OUTSIDE ABOUT (2026-10-16: make
	# sure none are in the UI except in the about). ~1 minute, in process;
	# proven by --plant (the server's rewriting off: 131 replies caught)
	if out="$($PY tests/test_no_ai_names.py 2>&1)"; then
		ok "no tool names: $(tail -2 <<<"$out" | head -1)"
	else
		bad "a reply names a tool or says 'a model' -- python tests/test_no_ai_names.py"
		grep -E "^FAIL" <<<"$out" | head -8
	fi
	# A WORD'S ADDRESS IS ITS STRONG'S NUMBER (2026-10-16): /word/H1254, one
	# spelling, and its verse links answer. ~1 minute, in process
	if out="$($PY tests/test_word_addresses.py 2>&1)"; then
		ok "word pages: $(tail -2 <<<"$out" | head -1)"
	else
		bad "word addresses -- python tests/test_word_addresses.py"
		grep -E "^FAIL" <<<"$out" | head -8
	fi
else
	ok "skipped -- no changes under app2/"
fi

head_ "Things a push does not do for you"

if [ -n "$range" ] && has '^deploy/(Caddyfile|bibleontology\.service)$'; then
	note "this range changes system config -- the hook restarts the app but does"
	note "NOT reinstall Caddy or systemd config. After pushing, on the server:"
	has '^deploy/Caddyfile$' && \
		printf '        sudo cp /srv/bibleontology/deploy/Caddyfile /etc/caddy/Caddyfile && \\\n        sudo -u caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && \\\n        sudo systemctl reload caddy\n'
	has '^deploy/bibleontology.service$' && \
		printf '        sudo cp /srv/bibleontology/deploy/bibleontology.service /etc/systemd/system/ && \\\n        sudo systemctl daemon-reload && sudo systemctl restart bibleontology\n'
else
	ok "no system config in this range"
fi

# app2 is the site served since 2026-10 (deploy/bibleontology.service); app/
# stays as the way back, so both count
if [ -n "$range" ] && has '^(src/|app2?/|deploy/|ontology/)' ; then
	if has '^app2?/static/index.html$'; then
		ok "About view touched in this range"
	else
		note "does anything here make the About view false? it is the project's"
		note "claim about its own trustworthiness, and must not go stale"
	fi
fi

if [ -n "$range" ] && has '^deploy/'; then
	if has '^(docs/OPERATIONS\.md|deploy/README\.md)$'; then
		ok "runbook updated alongside the config change"
	else
		bad "config changed without a doc change -- accurate AND complete, same commit"
	fi
fi

head_ "Your call, not mine"

cat <<'EOF'
  - Is anyone likely mid-session? The restart is about a second, but a reader
    with a graph open loses their view and has to find their way back.
  - Did invites go out in the last hour? A first impression that reloads
    under them is a worse one.
  - Anything here touching external exposure -- the gate, the proxy, the
    headers, the log -- gets a security review before it goes, not after.
EOF

head_ "Result"

if [ "$fail" -gt 0 ]; then
	printf '  \033[31m%d blocking issue(s).\033[0m Fix before pushing.\n\n' "$fail"
	exit 1
fi
printf '  \033[32mMechanical checks pass'
[ "$warn" -gt 0 ] && printf ' (%d thing(s) to read above)' "$warn"
printf '.\033[0m\n\n  To deploy:  %s\n\n' "$push"
