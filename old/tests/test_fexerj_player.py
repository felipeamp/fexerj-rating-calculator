"""Unit tests for the FexerjPlayer data class."""
import pytest

from classes import FexerjPlayer


class TestFexerjPlayerInit:
    def test_stores_all_attributes(self):
        player = FexerjPlayer(
            id_fexerj=42,
            id_cbx="12345",
            title="GM",
            name="GARRY KASPAROV",
            last_rating=2851,
            club="FIDE",
            birthday="13/04/1963",
            sex="M",
            federation="RUS",
            total_games=200,
            sum_opponents_ratings=500000,
            points_against_opponents=130.0,
        )
        assert player.id_fexerj == 42
        assert player.id_cbx == "12345"
        assert player.title == "GM"
        assert player.name == "GARRY KASPAROV"
        assert player.last_rating == 2851
        assert player.club == "FIDE"
        assert player.birthday == "13/04/1963"
        assert player.sex == "M"
        assert player.federation == "RUS"
        assert player.total_games == 200
        assert player.sum_opponents_ratings == 500000
        assert player.points_against_opponents == 130.0

    def test_empty_optional_fields(self):
        """id_cbx and title are often empty strings in the CSV."""
        player = FexerjPlayer(1, "", "", "PLAYER NAME", 1000, "", "", "M", "BRA", 0, 0, 0.0)
        assert player.id_cbx == ""
        assert player.title == ""

    def test_zero_games_unrated_player(self):
        player = FexerjPlayer(99, "", "", "NEW PLAYER", 1000, "CLUB", "01/01/2005", "M", "BRA", 0, 0, 0.0)
        assert player.total_games == 0
        assert player.sum_opponents_ratings == 0
        assert player.points_against_opponents == 0.0