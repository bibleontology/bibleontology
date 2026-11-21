"""Claude's reading of each mechanically-passed proposal against its verse (2026-11-19).
KEEP as proposed; FIX = replace with the given relation(s); DROP with the reason. Keyed by (src, type, dst, ref)."""

DROP = {
    ("divers_lusts_and_pleasures", "composed_of", "lusts"): "the card's name is the Berean's 'all sorts of desires and pleasures'; 'lusts' is not in it",
    ("wings", "likened_to", "feathers"): "Job 39:13 says the ostrich's wings 'cannot match' the stork's: a contrast, not a likeness",
    ("theme_sacrifice_r4", "grounds", "image_leaven"): "1Cor 5:7: Christ's sacrifice grounds the command to clear out the leaven, not the leaven itself",
    ("aquila", "issues_from", "italy"): "Acts 18:2: Aquila was 'a native of Pontus' who had lately come from Italy; issues_from would record Italy as his origin",
    ("have_you_considered_my_servant_job", "composed_of", "like"): "records only that the word 'like' is in the sentence",
    ("job_2_3_lord_speech", "composed_of", "like"): "records only that the word 'like' is in the sentence",
    ("mount_ephron", "composed_of", "ephron"): "'ephron' is Ephron the Hittite, a person; Mount Ephron is not named from him in the text",
    ("mount_seir_judah", "composed_of", "seir"): "'seir' is Edom's Seir; Mount Seir on Judah's border is another place",
    ("see", "conditional_on", "pass_over"): "wires two general word cards ('see', 'pass over') on one verse's grammar; would show on every use of 'see'",
    ("poor_person", "issues_from", "hand"): "'hand' is the general card for the body part; the proverb's point is idleness, not hands",
    ("self", "contrary_to", "sluggard"): "Prov 13:4 sets the diligent against the slacker; 'self' is the general card for the soul",
    ("the_shulamite", "charged", "daughters_of_jerusalem"): "the Shulammite is named only at Song 6:13; that she speaks Song 2:7 is a reading (doubt keeps it out)",
    ("the_lord_is_my_shepherd", "part_of", "psalm_of_david"): "psalm_of_david is the superscription of Psalm 23, not the psalm; the line is not part of it",
    ("i_shall_not_want", "part_of", "psalm_of_david"): "psalm_of_david is the superscription of Psalm 23, not the psalm; the line is not part of it",
    # read 2026-11-19, the last ten briefs
    ("image_diadem", "drawn_from", "the_diadem"): "the object card it would join is named 'the turban' but gathers three Hebrew words over four verses (Isa 28:5 and 62:3 read 'diadem'); held until that card is sorted",
    ("god", "likened_to", "the_diadem"): "held until the card is sorted: it is named 'the turban' (from Job 29:14), so this would read 'God is likened to the turban' where Isa 28:5 says 'a diadem of splendor'",
    ("zion", "likened_to", "the_diadem"): "held until the card is sorted: it is named 'the turban', where Isa 62:3 says 'a royal diadem'",
    ("the_rich_man_of_luke_16", "spoke_to", "abraham"): "said by 'besought' from the same words, which is the more specific",
    ("the_three_named_together", "quoted", "jesus"): "Matt 28:19 is Jesus' own command, not his words taken up by another; and the card touches the divine persons, which are Doug's",
    ("the_touching_of_jacobs_thigh", "recounts", "abstinence_from_the_sinew_which_shrank"): "Gen 32:32 gives the touching as the reason for the custom; it is not an account of it",
    ("women", "described_as", "female"): "'women' is the general card; Gen 1:27 says 'male and female', not of women",
    ("women", "present_with", "joanna_wife_of_chuza"): "'women' is the general card, not the women at the tomb",
    ("theme_messiah", "asserted_by", "angel_to_the_shepherds"): "a major theme is the site's grouping of passages, not a claim anyone in the text makes",
    ("theme_messiah_r33", "asserted_by", "angel_to_the_shepherds"): "a sub-theme is the site's grouping of passages, not a claim anyone in the text makes",
    # a theme is never the end of a textual relation in the graph (284 spoken_in, 1 aspect_of, nothing else)
    ("theme_kingdom_r22", "likened_to", "image_leaven"): "ends on a sub-theme (the site's grouping); no record for the kingdom of heaven itself",
    ("image_mountain", "contrary_to", "theme_covenant_r33"): "ends on a sub-theme; the only 'covenant of peace' record is Phinehas's (Num 25), not Isa 54:10's",
}
# symmetric named_with / contrary_to: keep one direction; and one of two addressees named together
DROP_DUP = {("matthias", "named_with", "joseph_barsabas"), ("mikloth_the_ruler", "named_with", "dodai_the_ahohite"),
            ("wicked_people", "contrary_to", "righteous_people"), ("jerusalem", "likened_to", "the_diadem")}

NAHOR_SONS = ["huz", "buz", "kemuel", "chesed", "hazo", "pildash", "jidlaph"]
# Every named_with among Nahor's sons is replaced by what Gen 22:20-23 states: Milcah bore them to Nahor.
REPLACE_NAMED_WITH_AMONG = set(NAHOR_SONS) | {"bethuel", "aram_son_of_kemuel"}
ADD = []   # Nahor's and Milcah's 14 were already recorded, held as quoted speech: see RELEASE
# Held 'inside quoted speech, speaker not on record' (Gen 22:20-22 is the unnamed report to Abraham). Gen 22:23 is the
# narrator's, outside the quotation: 'Milcah bore these eight sons to Abraham's brother Nahor.' Released by citing it.
RELEASE = [(p, t, s) for p, t in (("nahor_son_of_terah", "father_of"), ("milcah", "mother_of")) for s in NAHOR_SONS]
RELEASE_REF = "Gen 22:23"
RELEASE_NOTE = "'Milcah bore these eight sons to Abraham's brother Nahor' (Gen 22:23, the narrator, after the report to Abraham in vv20-22)"

FIX = {
    # Kemuel as Aram's father is said only inside the report (Gen 22:21) and is held as such: no copy, it stays held
    ("kemuel", "ancestor_of", "aram_son_of_kemuel"): [],
    ("aram_son_of_kemuel", "issues_from", "kemuel"): [],
    ("image_body", "signifies", "theme_church"): [("image_body", "signifies", "church_at_corinth")],
    ("manasseh_king_of_judah", "ancestor_of", "ashriel"): [("manasseh_son_of_joseph", "ancestor_of", "ashriel")],
    ("by_hearing_you_shall_hear_and_shall_not_understand", "ascribed_to", "isaiah"):
        [("by_hearing_you_shall_hear_and_shall_not_understand", "asserted_by", "isaiah")],
    ("counted_job_as_stranger", "asserted_by", "jobs_household"): [("counted_job_as_stranger", "asserted_by", "job")],
    ("counted_job_as_stranger", "asserted_by", "jobs_maids"): [],
    ("rebekahs_mother", "named_with", "laban"): [("rebekahs_mother", "mother_of", "rebekah")],
    # Neh 11:5: the man the verse is about is Maaseiah, 'a descendant of Shelah'; one edge, not one per link of the chain
    ("shiloni_neh11", "ancestor_of", "baruch_neh11"): [("shiloni_neh11", "ancestor_of", "maaseiah_son_of_baruch_neh11")],
    ("shiloni_neh11", "ancestor_of", "adaiah_son_of_joiarib_neh11"): [],
    ("shiloni_neh11", "ancestor_of", "joiarib_son_of_zechariah_neh11"): [],
}
# asserted_by a speech record -> the speaker (no relation in the graph names a speech as the asserting party)
SPEAKER = {
    "gen_15_15_speech": "god", "gen_17_6_speech": "god", "job_15_6_speech": "eliphaz_the_temanite",
    "gen_44_20_answer": "judah", "job_19_22_speech": "job", "job_35_15_speech": "elihu_son_of_barachel",
    "job_3_26_statement": "job", "job_25_6_speech": "bildad", "job_25_5_speech": "bildad", "job_19_7_speech": "job",
    "job_33_12_speech": "elihu_son_of_barachel", "job_36_10_speech": "elihu_son_of_barachel",
    "gen_37_33_jacob_speech": "jacob",
    "job_22_5_speech": "eliphaz_the_temanite", "job_15_13_speech": "eliphaz_the_temanite",
    "job_15_5_speech": "eliphaz_the_temanite", "job_15_20_speech": "eliphaz_the_temanite",
    "job_30_13_speech": "job", "gen_16_12_angel_speech": "angel_of_the_lord",
}
# The verse that names the speaker, cited beside the claim's own (each read in the Berean, 2026-11-19):
# (speaker, book chapter of the claim) -> opener
OPENER = {
    ("job", "Job 3"): "Job 3:1", ("eliphaz_the_temanite", "Job 15"): "Job 15:1", ("job", "Job 19"): "Job 19:1",
    ("eliphaz_the_temanite", "Job 22"): "Job 22:1", ("bildad", "Job 18"): "Job 18:1", ("bildad", "Job 25"): "Job 25:1",
    ("job", "Job 30"): "Job 29:1", ("elihu_son_of_barachel", "Job 33"): "Job 32:6",
    ("elihu_son_of_barachel", "Job 35"): "Job 35:1", ("elihu_son_of_barachel", "Job 36"): "Job 36:1",
    ("god", "Gen 15"): "Gen 15:1", ("god", "Gen 17"): "Gen 17:1", ("jacob", "Gen 37"): "Gen 37:34",
    ("judah", "Gen 44"): "Gen 44:18", ("angel_of_the_lord", "Gen 16"): "Gen 16:11",
}
EXTRA_REFS = {("image_body", "signifies", "church_at_corinth"): ["1Cor 1:2"]}
