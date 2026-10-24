"""Content coverage for server-owned followups; no chart or wording inference."""

VERSION = "question-recommendation-2026-10-10.1"

# These describe information in the supported answers, not astrological rules.
QUESTION_MEANINGS = {
    "chart.pillars": {"pillar_positions"},
    "luck.current_next": {"cycle_boundaries"},
    "period.this_year": {"annual_characters"},
    "stars.dohwa": {"dohwa_positions"},
    "wealth.locations": {"wealth_positions"},
    "features.dohwa": {"dohwa_method_difference"},
    "features.taegeuk": {"taegeuk_process_meaning"},
    "features.study_solitude": {"learning_relationship_distinction"},
}
ANSWER_MEANINGS = {
    **QUESTION_MEANINGS,
    # The answer itself also explains why learning blessings do not promise
    # comfortable relationships. Keep that answer complete, then omit repeats.
    "features.taegeuk": {"taegeuk_process_meaning", "learning_relationship_distinction"},
}


def select_followups(questions, answered_id):
    """Select only advertised questions with information the answer has not given."""
    current = next(q for q in questions if q.id == answered_id)
    covered = ANSWER_MEANINGS[answered_id]
    return [q for q in questions if q.id != answered_id
            and (not answered_id.startswith("features.") or
                 (q.id.startswith("features.") and q.category == current.category))
            and QUESTION_MEANINGS.get(q.id)
            and not QUESTION_MEANINGS[q.id] <= covered]
