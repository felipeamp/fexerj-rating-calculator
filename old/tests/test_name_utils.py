"""Unit tests for name_utils functions."""
from name_utils import normalize_name, name_similarity
from classes import _NAME_SIMILARITY_ACCEPT_THRESHOLD, _NAME_SIMILARITY_WARN_THRESHOLD


class TestNormalizeName:
    def test_lowercases(self):
        assert normalize_name("SILVA") == "silva"

    def test_strips_accents(self):
        assert normalize_name("José") == "jose"

    def test_removes_commas(self):
        assert normalize_name("Silva, Jose") == "jose silva"

    def test_sorts_tokens(self):
        assert normalize_name("Jose Silva") == normalize_name("Silva Jose")

    def test_name_order_invariant(self):
        assert normalize_name("SILVA, José") == normalize_name("Jose Silva")


class TestNameSimilarity:
    def test_identical_names_score_100(self):
        assert name_similarity("Jose Silva", "Jose Silva") == 100

    def test_accent_difference_scores_above_accept_threshold(self):
        assert name_similarity("José Silva", "Jose Silva") >= _NAME_SIMILARITY_ACCEPT_THRESHOLD

    def test_reversed_name_order_scores_above_accept_threshold(self):
        assert name_similarity("SILVA, José", "Jose Silva") >= _NAME_SIMILARITY_ACCEPT_THRESHOLD

    def test_completely_different_names_score_below_warn_threshold(self):
        assert name_similarity("Jose Silva", "Carlos Pereira") < _NAME_SIMILARITY_WARN_THRESHOLD

    def test_similar_but_different_name_scores_between_thresholds(self):
        score = name_similarity("Jose Silverio", "Jose Silva")
        assert _NAME_SIMILARITY_WARN_THRESHOLD <= score < _NAME_SIMILARITY_ACCEPT_THRESHOLD
