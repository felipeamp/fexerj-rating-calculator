"""Shared pytest fixtures for the fexerj-rating-calculator test suite."""
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from classes import FexerjPlayer, TournamentPlayer, Tournament


@pytest.fixture
def sample_fexerj_player():
    """A fully populated FexerjPlayer instance."""
    return FexerjPlayer(
        id_fexerj=1,
        id_cbx="36633",
        title="",
        name="JOSE DA SILVA",
        last_rating=1500,
        club="CLUBE XADREZ RJ",
        birthday="01/01/1990",
        sex="M",
        federation="BRA",
        total_games=50,
        sum_opponents_ratings=0,
        points_against_opponents=0.0,
    )


def _make_tournament_player(tournament=None, **kwargs):
    """Helper: build a TournamentPlayer without making HTTP calls."""
    if tournament is None:
        tournament = MagicMock()
    with patch.object(TournamentPlayer, "load_player_page"):
        player = TournamentPlayer(tournament, "http://fake-url")
    player.snr = kwargs.get("snr", 1)
    player.name = kwargs.get("name", "Test Player")
    player.id = kwargs.get("id", 100)
    player.opponents = kwargs.get("opponents", {})
    player.is_unrated = kwargs.get("is_unrated", False)
    player.is_temp = kwargs.get("is_temp", False)
    player.last_rating = kwargs.get("last_rating", 1500)
    player.last_total_games = kwargs.get("last_total_games", 50)
    player.last_sum_oppon_ratings = kwargs.get("last_sum_oppon_ratings", 0)
    player.last_pts_against_oppon = kwargs.get("last_pts_against_oppon", 0.0)
    player.this_pts_against_oppon = kwargs.get("this_pts_against_oppon", None)
    player.this_sum_oppon_ratings = kwargs.get("this_sum_oppon_ratings", None)
    player.this_avg_oppon_rating = kwargs.get("this_avg_oppon_rating", None)
    player.this_games = kwargs.get("this_games", None)
    player.this_score = kwargs.get("this_score", None)
    player.this_expected_points = kwargs.get("this_expected_points", None)
    player.this_points_above_expected = kwargs.get("this_points_above_expected", None)
    player.new_rating = kwargs.get("new_rating", None)
    player.new_total_games = kwargs.get("new_total_games", None)
    player.new_sum_oppon_ratings = kwargs.get("new_sum_oppon_ratings", None)
    player.new_pts_against_oppon = kwargs.get("new_pts_against_oppon", None)
    player.calc_rule = kwargs.get("calc_rule", None)
    player.last_k = kwargs.get("last_k", None)
    return player


@pytest.fixture
def make_tournament_player():
    """Factory fixture: returns a callable that creates TournamentPlayer instances."""
    return _make_tournament_player


@pytest.fixture
def established_player(make_tournament_player):
    """An established player (>=15 games) with rating 1500."""
    return make_tournament_player(last_total_games=50, last_rating=1500, is_unrated=False, is_temp=False)


@pytest.fixture
def temp_player(make_tournament_player):
    """A temporary player (1-14 games)."""
    return make_tournament_player(last_total_games=5, last_rating=1400, is_unrated=False, is_temp=True)


@pytest.fixture
def unrated_player(make_tournament_player):
    """An unrated player (0 games)."""
    return make_tournament_player(last_total_games=0, last_rating=0, is_unrated=True, is_temp=False)


# ---- Rating-list CSV fixture ----

RATING_LIST_CSV = textwrap.dedent("""\
    Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints
    1;;; JOSE DA SILVA;1500;CLUBE A;01/01/1990;M;BRA;50;0;0
    2;36633;;MARIO SOUZA;1800;CLUBE B;15/06/1985;M;BRA;100;0;0
    3;;;ANA LIMA;1200;CLUBE C;20/03/2000;F;BRA;5;30000;2.5
""")


@pytest.fixture
def make_tournament():
    """Factory fixture: returns a callable that creates Tournament instances."""
    def _make(is_irt=0, is_fexerj=1, rating_list=None, cbx_to_fexerj=None):
        rc = MagicMock()
        rc.rating_list = rating_list if rating_list is not None else {}
        rc.cbx_to_fexerj = cbx_to_fexerj if cbx_to_fexerj is not None else {}
        data = ["1", "12345", "Test Tournament", "2025-01-01", "SS", str(is_irt), str(is_fexerj)]
        return Tournament(rc, data)
    return _make


@pytest.fixture
def rating_list_csv_path(tmp_path):
    """Write the sample rating list to a temp CSV file and return its path."""
    csv_file = tmp_path / "ratings.csv"
    csv_file.write_text(RATING_LIST_CSV)
    return str(csv_file)