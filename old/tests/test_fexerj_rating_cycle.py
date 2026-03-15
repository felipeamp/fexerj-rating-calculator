"""Unit tests for FexerjRatingCycle."""
import json
import pytest

from classes import FexerjRatingCycle, FexerjPlayer


class TestFexerjRatingCycleInit:
    def test_initial_state(self):
        cycle = FexerjRatingCycle("tournaments.csv", 1, 10, "ratings.csv")
        assert cycle.tournaments_file == "tournaments.csv"
        assert cycle.first_item == 1
        assert cycle.items_to_process == 10
        assert cycle.initial_rating_filepath == "ratings.csv"
        assert cycle.rating_list == {}
        assert cycle.cbx_to_fexerj == {}
        assert cycle.manual_entries == {}


class TestGetRatingList:
    def test_loads_all_players(self, rating_list_csv_path):
        cycle = FexerjRatingCycle("t.csv", 1, 1, rating_list_csv_path)
        cycle.get_rating_list(rating_list_csv_path)
        assert len(cycle.rating_list) == 3

    def test_player_attributes_parsed_correctly(self, rating_list_csv_path):
        cycle = FexerjRatingCycle("t.csv", 1, 1, rating_list_csv_path)
        cycle.get_rating_list(rating_list_csv_path)

        player = cycle.rating_list[1]
        assert isinstance(player, FexerjPlayer)
        assert player.id_fexerj == 1
        assert player.last_rating == 1500
        assert player.total_games == 50
        assert player.name == " JOSE DA SILVA"

    def test_cbx_to_fexerj_mapping_built(self, rating_list_csv_path):
        """Players with a CBX ID should appear in the cbx→fexerj mapping."""
        cycle = FexerjRatingCycle("t.csv", 1, 1, rating_list_csv_path)
        cycle.get_rating_list(rating_list_csv_path)
        assert 36633 in cycle.cbx_to_fexerj
        assert cycle.cbx_to_fexerj[36633] == 2

    def test_players_without_cbx_not_in_mapping(self, rating_list_csv_path):
        """Players with empty CBX ID should NOT appear in the mapping."""
        cycle = FexerjRatingCycle("t.csv", 1, 1, rating_list_csv_path)
        cycle.get_rating_list(rating_list_csv_path)
        assert 1 not in cycle.cbx_to_fexerj

    def test_temp_player_has_correct_stats(self, rating_list_csv_path):
        """Verify partial-game stats for a temporary-rated player."""
        cycle = FexerjRatingCycle("t.csv", 1, 1, rating_list_csv_path)
        cycle.get_rating_list(rating_list_csv_path)
        player = cycle.rating_list[3]
        assert player.total_games == 5
        assert player.sum_opponents_ratings == "30000"
        assert player.points_against_opponents == "2.5"

    def test_cbx_id_zero_is_mapped(self, tmp_path):
        """CBX ID '0' has length > 0 so it is added to the mapping with key 0."""
        csv_content = (
            "Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints\n"
            "5;0;;PLAYER ZERO;1400;CLUB;01/01/1990;M;BRA;20;0;0\n"
        )
        csv_file = tmp_path / "ratings.csv"
        csv_file.write_text(csv_content)
        cycle = FexerjRatingCycle("t.csv", 1, 1, str(csv_file))
        cycle.get_rating_list(str(csv_file))
        assert 0 in cycle.cbx_to_fexerj
        assert cycle.cbx_to_fexerj[0] == 5

    def test_multiple_players_all_loaded(self, tmp_path):
        """All rows in the CSV, regardless of CBX presence, must be in rating_list."""
        csv_content = (
            "Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints\n"
            "10;;;PLAYER A;1500;C;01/01/1990;M;BRA;50;0;0\n"
            "11;99;;PLAYER B;1600;C;01/01/1985;M;BRA;80;0;0\n"
            "12;;;PLAYER C;1700;C;01/01/1980;M;BRA;0;0;0\n"
        )
        csv_file = tmp_path / "ratings.csv"
        csv_file.write_text(csv_content)
        cycle = FexerjRatingCycle("t.csv", 1, 1, str(csv_file))
        cycle.get_rating_list(str(csv_file))
        assert set(cycle.rating_list.keys()) == {10, 11, 12}
        assert cycle.cbx_to_fexerj == {99: 11}

    def test_empty_csv_yields_empty_rating_list(self, tmp_path):
        """A CSV with only the header and no data rows should produce an empty rating_list."""
        csv_content = (
            "Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints\n"
        )
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text(csv_content)
        cycle = FexerjRatingCycle("t.csv", 1, 1, str(csv_file))
        cycle.get_rating_list(str(csv_file))
        assert cycle.rating_list == {}
        assert cycle.cbx_to_fexerj == {}


class TestManualEntryDict:
    def test_load_when_file_missing(self, tmp_path, monkeypatch):
        """load_manual_entry_dict should leave manual_entries empty when no file."""
        monkeypatch.chdir(tmp_path)
        cycle = FexerjRatingCycle("t.csv", 1, 1, "r.csv")
        cycle.load_manual_entry_dict()
        assert cycle.manual_entries == {}

    def test_write_and_reload(self, tmp_path, monkeypatch):
        """Writing then loading manual entries should round-trip correctly."""
        monkeypatch.chdir(tmp_path)
        cycle = FexerjRatingCycle("t.csv", 1, 1, "r.csv")
        cycle.manual_entries = {"1.5": 999, "2.3": 888}
        cycle.write_manual_entry_dict()

        cycle2 = FexerjRatingCycle("t.csv", 1, 1, "r.csv")
        cycle2.load_manual_entry_dict()
        assert cycle2.manual_entries == {"1.5": 999, "2.3": 888}