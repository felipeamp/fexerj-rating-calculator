"""Unit tests for Tournament class methods.

Uses the make_tournament and make_tournament_player fixtures from conftest.py.
Network calls are patched out via load_player_page.
"""
import csv
import pytest
from unittest.mock import MagicMock, patch

from classes import Tournament, TournamentPlayer, FexerjPlayer, CalcRule, _MAX_NUM_GAMES_TEMP_RATING, _AUDIT_FILE_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fexerj_player(id_fexerj, total_games, last_rating, sum_oppon=0, pts_oppon=0.0, id_cbx=""):
    return FexerjPlayer(id_fexerj, id_cbx, "", f"Player {id_fexerj}", last_rating,
                        "CLUB", "01/01/1990", "M", "BRA", total_games, sum_oppon, pts_oppon)


def _make_tp(tournament, fexerj_id, snr, opponents_list=None):
    """Build a TournamentPlayer without HTTP, with opponents as a list (pre-complete_players_info format)."""
    with patch.object(TournamentPlayer, "load_player_page"):
        tp = TournamentPlayer(tournament, "http://fake")
    tp.id = fexerj_id
    tp.snr = snr
    tp.name = f"Player {fexerj_id}"
    tp.opponents = opponents_list if opponents_list is not None else []
    tp.is_unrated = None
    tp.is_temp = None
    return tp


def _make_tournament(is_irt=0, is_fexerj=1, rating_list=None, cbx_to_fexerj=None):
    rc = MagicMock()
    rc.rating_list = rating_list or {}
    rc.cbx_to_fexerj = cbx_to_fexerj or {}
    data = ["1", "12345", "Test Tournament", "2025-01-01", "SS", str(is_irt), str(is_fexerj)]
    return Tournament(rc, data)


# ---------------------------------------------------------------------------
# complete_players_info
# ---------------------------------------------------------------------------

class TestCompletePlersInfo:
    def test_unrated_player_classified(self):
        fp = _make_fexerj_player(1, total_games=0, last_rating=0)
        t = _make_tournament(rating_list={1: fp})
        tp = _make_tp(t, fexerj_id=1, snr=1)
        t.players = {1: tp}

        t.complete_players_info()

        assert tp.is_unrated is True
        assert 1 in t.unrated_keys
        assert 1 not in t.temp_keys
        assert 1 not in t.established_keys

    def test_temp_player_classified(self):
        fp = _make_fexerj_player(2, total_games=5, last_rating=1200)
        t = _make_tournament(rating_list={2: fp})
        tp = _make_tp(t, fexerj_id=2, snr=2)
        t.players = {2: tp}

        t.complete_players_info()

        assert tp.is_temp is True
        assert 2 in t.temp_keys
        assert 2 not in t.unrated_keys
        assert 2 not in t.established_keys

    def test_established_player_classified(self):
        fp = _make_fexerj_player(3, total_games=_MAX_NUM_GAMES_TEMP_RATING, last_rating=1500)
        t = _make_tournament(rating_list={3: fp})
        tp = _make_tp(t, fexerj_id=3, snr=3)
        t.players = {3: tp}

        t.complete_players_info()

        assert 3 in t.established_keys
        assert 3 not in t.unrated_keys
        assert 3 not in t.temp_keys

    def test_player_attributes_copied_from_fexerj_player(self):
        fp = _make_fexerj_player(4, total_games=50, last_rating=1700, sum_oppon=0, pts_oppon=0.0)
        t = _make_tournament(rating_list={4: fp})
        tp = _make_tp(t, fexerj_id=4, snr=4)
        t.players = {4: tp}

        t.complete_players_info()

        assert tp.last_rating == 1700
        assert tp.last_total_games == 50

    def test_boundary_exactly_15_games_is_established(self):
        fp = _make_fexerj_player(5, total_games=15, last_rating=1400)
        t = _make_tournament(rating_list={5: fp})
        tp = _make_tp(t, fexerj_id=5, snr=5)
        t.players = {5: tp}

        t.complete_players_info()

        assert 5 in t.established_keys

    def test_boundary_14_games_is_temp(self):
        fp = _make_fexerj_player(6, total_games=14, last_rating=1400)
        t = _make_tournament(rating_list={6: fp})
        tp = _make_tp(t, fexerj_id=6, snr=6)
        t.players = {6: tp}

        t.complete_players_info()

        assert 6 in t.temp_keys

    def test_opponents_converted_from_list_to_dict(self):
        """After complete_players_info, tp.opponents must be a dict keyed by SNR."""
        fp1 = _make_fexerj_player(1, total_games=50, last_rating=1500)
        fp2 = _make_fexerj_player(2, total_games=50, last_rating=1600)
        t = _make_tournament(rating_list={1: fp1, 2: fp2})

        tp1 = _make_tp(t, fexerj_id=1, snr=1, opponents_list=[[2, "Player 2", 1.0]])
        tp2 = _make_tp(t, fexerj_id=2, snr=2, opponents_list=[[1, "Player 1", 0.0]])
        t.players = {1: tp1, 2: tp2}

        t.complete_players_info()

        assert isinstance(tp1.opponents, dict)
        assert 2 in tp1.opponents
        assert tp1.opponents[2][0] is tp2   # points to the actual TournamentPlayer object
        assert tp1.opponents[2][1] == 1.0   # score preserved

    def test_irt_tournament_uses_cbx_to_fexerj_mapping(self):
        """In IRT tournaments, player lookup goes through cbx_to_fexerj."""
        fp = _make_fexerj_player(10, total_games=50, last_rating=1800)
        t = _make_tournament(is_irt=1, rating_list={10: fp}, cbx_to_fexerj={99: 10})
        tp = _make_tp(t, fexerj_id=99, snr=1)  # tp.id is CBX id
        t.players = {1: tp}

        t.complete_players_info()

        assert tp.last_rating == 1800
        assert tp.last_total_games == 50

    def test_all_player_types_classified_together(self):
        """Unrated, temp, and established players are correctly classified in a single call."""
        fp_unrated = _make_fexerj_player(1, total_games=0,  last_rating=0)
        fp_temp    = _make_fexerj_player(2, total_games=5,  last_rating=1200)
        fp_estab   = _make_fexerj_player(3, total_games=50, last_rating=1500)
        t = _make_tournament(rating_list={1: fp_unrated, 2: fp_temp, 3: fp_estab})

        tp1 = _make_tp(t, fexerj_id=1, snr=1)
        tp2 = _make_tp(t, fexerj_id=2, snr=2)
        tp3 = _make_tp(t, fexerj_id=3, snr=3)
        t.players = {1: tp1, 2: tp2, 3: tp3}

        t.complete_players_info()

        assert t.unrated_keys    == [1]
        assert t.temp_keys       == [2]
        assert t.established_keys == [3]
        assert tp1.is_unrated is True
        assert tp2.is_temp    is True


# ---------------------------------------------------------------------------
# write_tournament_audit
# ---------------------------------------------------------------------------

def _make_calculated_tp(tournament, fexerj_id=100, last_rating=1500, last_total_games=50,
                         last_k=15, this_pts=1.0, this_games=1, this_sum_oppon=1500,
                         this_avg_oppon=1500.0, this_expected=0.5, this_points_above=0.5,
                         new_rating=1508, new_total_games=51, calc_rule=CalcRule.NORMAL):
    """Build a TournamentPlayer with all post-calculation attributes set."""
    with patch.object(TournamentPlayer, "load_player_page"):
        tp = TournamentPlayer(tournament, "http://fake")
    tp.id = fexerj_id
    tp.name = f"Player {fexerj_id}"
    tp.last_rating = last_rating
    tp.last_total_games = last_total_games
    tp.last_k = last_k
    tp.this_pts_against_oppon = this_pts
    tp.this_games = this_games
    tp.this_sum_oppon_ratings = this_sum_oppon
    tp.this_avg_oppon_rating = this_avg_oppon
    tp.this_expected_points = this_expected
    tp.this_points_above_expected = this_points_above
    tp.new_rating = new_rating
    tp.new_total_games = new_total_games
    tp.calc_rule = calc_rule
    return tp


class TestWriteTournamentAudit:
    def test_header_is_written(self, tmp_path):
        t = _make_tournament()
        t.players = {}
        output = str(tmp_path / "audit.csv")

        t.write_tournament_audit(output)

        with open(output) as f:
            first_line = f.readline().strip()
        assert first_line == _AUDIT_FILE_HEADER

    def test_one_line_per_player(self, tmp_path):
        t = _make_tournament()
        t.players = {
            1: _make_calculated_tp(t, fexerj_id=101),
            2: _make_calculated_tp(t, fexerj_id=102),
        }
        output = str(tmp_path / "audit.csv")

        t.write_tournament_audit(output)

        with open(output) as f:
            lines = [l for l in f.read().splitlines() if l]
        assert len(lines) == 3  # header + 2 player lines

    def test_correct_number_of_fields_per_line(self, tmp_path):
        """Each data line must have exactly 19 semicolon-separated fields."""
        t = _make_tournament()
        t.players = {1: _make_calculated_tp(t)}
        output = str(tmp_path / "audit.csv")

        t.write_tournament_audit(output)

        with open(output) as f:
            lines = f.read().splitlines()
        data_line = lines[1]
        assert len(data_line.split(";")) == 19

    def test_player_values_in_output(self, tmp_path):
        """Key player values should appear in the audit line."""
        t = _make_tournament()
        t.players = {1: _make_calculated_tp(t, fexerj_id=100, new_rating=1508, calc_rule=CalcRule.NORMAL)}
        output = str(tmp_path / "audit.csv")

        t.write_tournament_audit(output)

        with open(output) as f:
            content = f.read()
        assert "1508" in content
        assert "NORMAL" in content
        assert "100" in content

    def test_zero_games_player_we_and_p_are_none(self, tmp_path):
        """When this_games == 0, We and P columns must be 'None'."""
        t = _make_tournament()
        tp = _make_calculated_tp(t, this_games=0, this_pts=None,
                                  this_sum_oppon=None, this_avg_oppon=None,
                                  this_expected=None, this_points_above=None,
                                  new_rating=1500, new_total_games=50, calc_rule=None)
        t.players = {1: tp}
        output = str(tmp_path / "audit.csv")

        t.write_tournament_audit(output)

        with open(output) as f:
            reader = csv.reader(f, delimiter=";")
            next(reader)  # skip header
            row = next(reader)
        # We is column index 11, P is column index 17
        assert row[11] == "None"
        assert row[17] == "None"


# ---------------------------------------------------------------------------
# write_new_ratings_list
# ---------------------------------------------------------------------------

class TestWriteNewRatingsList:
    def _setup(self, new_total_games):
        fp = _make_fexerj_player(100, total_games=50, last_rating=1500)
        t = _make_tournament(rating_list={100: fp})
        with patch.object(TournamentPlayer, "load_player_page"):
            tp = TournamentPlayer(t, "http://fake")
        tp.id = 100
        tp.new_rating = 1520
        tp.new_total_games = new_total_games
        tp.new_sum_oppon_ratings = 3000
        tp.new_pts_against_oppon = 2.0
        t.players = {1: tp}
        return t, fp

    def test_fexerj_player_rating_updated(self, tmp_path):
        t, fp = self._setup(new_total_games=51)
        t.write_new_ratings_list(str(tmp_path / "out.csv"))
        assert fp.last_rating == 1520
        assert fp.total_games == 51

    def test_established_player_stats_reset_to_zero(self, tmp_path):
        """Players with >= 15 new games have sum_opponents_ratings and points reset."""
        t, fp = self._setup(new_total_games=51)
        t.write_new_ratings_list(str(tmp_path / "out.csv"))
        assert fp.sum_opponents_ratings == 0
        assert fp.points_against_opponents == 0

    def test_temp_player_stats_preserved(self, tmp_path):
        """Players with < 15 new games retain sum_opponents_ratings and points."""
        t, fp = self._setup(new_total_games=8)
        t.write_new_ratings_list(str(tmp_path / "out.csv"))
        assert fp.sum_opponents_ratings == 3000
        assert fp.points_against_opponents == 2.0

    def test_output_file_has_header(self, tmp_path):
        t, _ = self._setup(new_total_games=51)
        output = str(tmp_path / "out.csv")
        t.write_new_ratings_list(output)
        with open(output) as f:
            first_line = f.readline().strip()
        assert first_line.startswith("Id_No")

    def test_output_file_contains_new_rating(self, tmp_path):
        t, _ = self._setup(new_total_games=51)
        output = str(tmp_path / "out.csv")
        t.write_new_ratings_list(output)
        with open(output) as f:
            content = f.read()
        assert "1520" in content

    def test_boundary_exactly_15_new_games_resets_stats(self, tmp_path):
        """new_total_games == 15 is >= _MAX_NUM_GAMES_TEMP_RATING → stats must be reset."""
        t, fp = self._setup(new_total_games=15)
        t.write_new_ratings_list(str(tmp_path / "out.csv"))
        assert fp.sum_opponents_ratings == 0
        assert fp.points_against_opponents == 0

    def test_boundary_14_new_games_preserves_stats(self, tmp_path):
        """new_total_games == 14 is < _MAX_NUM_GAMES_TEMP_RATING → stats must be kept."""
        t, fp = self._setup(new_total_games=14)
        t.write_new_ratings_list(str(tmp_path / "out.csv"))
        assert fp.sum_opponents_ratings == 3000
        assert fp.points_against_opponents == 2.0


# ---------------------------------------------------------------------------
# calculate_players_ratings — processing order
# ---------------------------------------------------------------------------

class TestCalculatePlayersRatings:
    def test_unrated_processed_before_established(self):
        """Unrated players must be processed first so their new_rating is available
        when established players reference them as opponents."""
        t = _make_tournament()

        fp_unrated = _make_fexerj_player(1, total_games=0, last_rating=0)
        fp_established = _make_fexerj_player(2, total_games=50, last_rating=1500)
        t.rating_cycle.rating_list = {1: fp_unrated, 2: fp_established}

        # Build players with opponents already in dict format (post complete_players_info)
        with patch.object(TournamentPlayer, "load_player_page"):
            tp_unrated = TournamentPlayer(t, "http://fake")
        tp_unrated.id = 1
        tp_unrated.name = "Unrated"
        tp_unrated.is_unrated = True
        tp_unrated.is_temp = False
        tp_unrated.last_rating = 0
        tp_unrated.last_total_games = 0
        tp_unrated.last_sum_oppon_ratings = 0
        tp_unrated.last_pts_against_oppon = 0.0

        with patch.object(TournamentPlayer, "load_player_page"):
            tp_established = TournamentPlayer(t, "http://fake")
        tp_established.id = 2
        tp_established.name = "Established"
        tp_established.is_unrated = False
        tp_established.is_temp = False
        tp_established.last_rating = 1500
        tp_established.last_total_games = 50
        tp_established.last_sum_oppon_ratings = 0
        tp_established.last_pts_against_oppon = 0.0

        # Unrated beats established; established loses to unrated
        tp_unrated.opponents = {2: [tp_established, 1.0]}
        tp_established.opponents = {1: [tp_unrated, 0.0]}

        t.players = {1: tp_unrated, 2: tp_established}
        t.unrated_keys = [1]
        t.temp_keys = []
        t.established_keys = [2]

        t.calculate_players_ratings()

        # Unrated player's new_rating must be set before established player ran
        assert tp_unrated.new_rating is not None
        assert tp_unrated.new_rating > 0
        # Established player must have used unrated player's new_rating (not last_rating=0)
        assert tp_established.this_sum_oppon_ratings == tp_unrated.new_rating

    def test_all_player_types_are_processed(self):
        """All players (unrated, temp, established) must have new_rating set after the call."""
        t = _make_tournament()

        def _build_tp(fexerj_id, is_unrated, is_temp, last_rating, last_total_games):
            with patch.object(TournamentPlayer, "load_player_page"):
                tp = TournamentPlayer(t, "http://fake")
            tp.id = fexerj_id
            tp.name = f"P{fexerj_id}"
            tp.is_unrated = is_unrated
            tp.is_temp = is_temp
            tp.last_rating = last_rating
            tp.last_total_games = last_total_games
            tp.last_sum_oppon_ratings = 0
            tp.last_pts_against_oppon = 0.0
            tp.opponents = {}   # no opponents → keep_current_rating
            return tp

        tp1 = _build_tp(1, is_unrated=True,  is_temp=False, last_rating=0,    last_total_games=0)
        tp2 = _build_tp(2, is_unrated=False, is_temp=True,  last_rating=1200, last_total_games=5)
        tp3 = _build_tp(3, is_unrated=False, is_temp=False, last_rating=1500, last_total_games=50)

        t.players = {1: tp1, 2: tp2, 3: tp3}
        t.unrated_keys = [1]
        t.temp_keys = [2]
        t.established_keys = [3]

        t.calculate_players_ratings()

        assert tp1.new_rating is not None
        assert tp2.new_rating is not None
        assert tp3.new_rating is not None
