#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''Module used to calculate the FEXERJ rating.'''

from collections import namedtuple
import csv
from enum import Enum
import math
import requests
from bs4 import BeautifulSoup


_MAX_NUM_GAMES_TEMP_RATING = 15
_PERFORMANCE_DIFFERENCE_FOR_PERFECT_TOURNAMENT = 800.0
_CSV_DELIMITER = ';'
_RATING_LIST_HEADER = 'Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames'
_RATING_LIST_HEADER_LEN = len(_RATING_LIST_HEADER.split(_CSV_DELIMITER))
_TEMP_RATING_LIST_HEADER = ('Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;'
                            'Fed;TotalNumGames;SumOpponRating;TotalPoints')
_TEMP_RATING_LIST_HEADER_LEN = len(_TEMP_RATING_LIST_HEADER.split(_CSV_DELIMITER))


TournamentResult = namedtuple('TournamentResult',
                              ['avg_oppon_rating', # float
                               'expected_num_points', # float
                               'total_num_points', # float,
                               'num_valid_games', # int
                               'performance_rating', # float
                              ])


class UnkownPlayerException(Exception):
    pass


class CalculationRule(Enum):
    NORMAL = 'Normal'
    DOUBLE_K = 'K duplo'
    RATING_PERFORMANCE = 'Rating performance'
    TEMPORARY = 'Temporary rating'


# For permanent rating, current_k is set, while sum_prev_oppon_rating and
# total_prev_points are None and is_temp_rating is False.
# For temporary rating, current_k is None, while sum_prev_oppon_rating and
# total_prev_points are set and is_temp_rating is True.
RatingInfo = namedtuple('RatingInfo',
                        ['rating', # int
                         'last_tournament_name', # str
                         'last_tournament_result', # TournamentResult
                         'last_tournament_calculation_rule', # CalculationRule
                         'num_games', # int
                         'current_k', # int or None for temporary rating
                         'is_temp_rating', # bool
                         'sum_prev_oppon_rating', # None or int for temp rating
                         'total_prev_points', # None or float for temp rating
                        ])


PlayerInfo = namedtuple('PlayerInfo',
                        ['player_id', # int
                         'title', # str
                         'name', # str
                         'birthdate', # str
                         'current_club', # str
                         'sex', # str
                         'federation', # str
                        ])


PlayerState = namedtuple('PlayerState',
                         ['player_info', # PlayerInfo
                          'rating_infos', # list of RatingInfo (starting & after each tournament)
                         ])


class Result(Enum):
    LOSS = 0
    DRAW = 0.5
    WIN = 1.0


GameInfo = namedtuple('GameInfo',
                      ['opponent_id', # int
                       'result', # Result
                      ])


FullTournamentInfo = namedtuple('FullTournamentInfo',
                                ['tournament_name', # str
                                 'chess_results_id', # int
                                 # Each actual game appears twice in the dict below.
                                 'valid_games', # dict of int (player_id) to list of GameInfo.
                                ])


_K_STARTING_NUM_GAMES = [(30, 0), # grampo
                         (25, _MAX_NUM_GAMES_TEMP_RATING), # 15
                         (15, 40),
                         (10, 80)]


def _get_current_k(num_games):
    # Assumes rating is not temporary
    for (k, starting_num_games) in _K_STARTING_NUM_GAMES:
        if num_games >= starting_num_games:
            current_k = k
    return current_k


def _is_double_k_rule(tournament_result):
    points_above_expected = (
        tournament_result.total_num_points - tournament_result.expected_num_points)
    if tournament_result.num_valid_games < 4:
        return False
    elif tournament_result.num_valid_games == 4:
        return points_above_expected >= 1.65
    elif tournament_result.num_valid_games == 5:
        return points_above_expected >= 1.43
    elif tournament_result.num_valid_games == 6:
        return points_above_expected >= 1.56
    elif tournament_result.num_valid_games == 7:
        return points_above_expected >= 1.69
    raise NotImplementedError(
        'Unknown condition for double K rule with more than 7 games.')


def _is_rating_performance_rule(tournament_result):
    points_above_expected = (
        tournament_result.total_num_points - tournament_result.expected_num_points)
    if tournament_result.num_valid_games < 5:
        return False
    elif tournament_result.num_valid_games == 5:
        return points_above_expected >= 1.84
    elif tournament_result.num_valid_games == 6:
        return points_above_expected >= 2.02
    elif tournament_result.num_valid_games == 7:
        return points_above_expected >= 2.16
    raise NotImplementedError(
        'Unknown condition for Rating performance rule with more than 7 games.')


def _get_calculation_rule(current_rating_info, tournament_result):
    if (current_rating_info.is_temp_rating and
            current_rating_info.num_games <= _MAX_NUM_GAMES_TEMP_RATING):
        return CalculationRule.TEMPORARY
    elif _is_double_k_rule(tournament_result):
        return CalculationRule.DOUBLE_K
    elif _is_rating_performance_rule(tournament_result):
        return CalculationRule.RATING_PERFORMANCE
    return CalculationRule.NORMAL


def _get_expected_num_points(current_rating_info, avg_oppon_rating, num_valid_games):
    rating_difference = avg_oppon_rating - current_rating_info.rating
    return num_valid_games / (1.0 + 10.0 ** (rating_difference / 400.0))


def _calculate_performance_rating(avg_oppon_rating, num_valid_games, total_num_points):
    # In case of perfect results, consider score as if there was an extra game that ended in a
    # draw.
    score = total_num_points / num_valid_games
    if score == 1.0:
        score = (num_valid_games + 0.5) / (num_valid_games + 1.0)
    elif score == 0.0:
        score = 0.5 / (num_valid_games + 1.0)
    return avg_oppon_rating + 400.0 * math.log10(score / (1.0 - score))


def _get_player_tournament_result(all_players, current_rating_info, games):
    if not games:
        raise ValueError('games should have at least one valid game.')
    sum_oppon_rating = 0
    num_valid_games = 0
    total_num_points = 0.0
    for game_info in games:
        sum_oppon_rating += _get_current_rating_info(all_players, game_info.opponent_id).rating
        num_valid_games += 1
        total_num_points += game_info.result.value
    avg_oppon_rating = sum_oppon_rating / num_valid_games
    expected_num_points = _get_expected_num_points(
        current_rating_info, avg_oppon_rating, num_valid_games)
    performance_rating = _calculate_performance_rating(avg_oppon_rating,
                                                       num_valid_games,
                                                       total_num_points)
    return TournamentResult(avg_oppon_rating=avg_oppon_rating,
                            expected_num_points=expected_num_points,
                            total_num_points=total_num_points,
                            num_valid_games=num_valid_games,
                            performance_rating=performance_rating)


def _get_new_temp_rating(current_rating_info, tournament_result):
    new_num_games = current_rating_info.num_games + tournament_result.num_valid_games
    total_avg_oppon_rating = (
        (current_rating_info.sum_prev_oppon_rating +
         tournament_result.avg_oppon_rating * tournament_result.num_valid_games)
        / new_num_games)
    performance_rating = _calculate_performance_rating(
        total_avg_oppon_rating,
        new_num_games,
        current_rating_info.total_prev_points + tournament_result.total_num_points)
    return int(performance_rating + 0.5) # Rounding to closest int


def _get_rating_performance(current_rating_info, tournament_result):
    # Calculation done as below avoids possible overflow.
    return (current_rating_info.rating +
            (tournament_result.performance_rating - current_rating_info.rating) / 2.0)


def _get_new_rating(current_rating_info, tournament_result, is_double_k_rule):
    points_above_expected = (
        tournament_result.total_num_points - tournament_result.expected_num_points)
    rating_gain = (
        (1 + int(is_double_k_rule)) * # multiplies K by 2 when is_double_k_rule is True
        current_rating_info.current_k * points_above_expected)
    rating_gain_rounded = int(rating_gain + 0.5) # Rounding to closest int
    return max(current_rating_info.rating + rating_gain_rounded, 1)


def _is_unrated_player(current_rating_info):
    return current_rating_info.is_temp_rating and not current_rating_info.num_games


def _is_temp_player(current_rating_info):
    return (current_rating_info.is_temp_rating and
            current_rating_info.num_games and
            current_rating_info.num_games < _MAX_NUM_GAMES_TEMP_RATING)


def _get_current_rating_info(all_players, player_id):
    try:
        return all_players[player_id].rating_infos[-1]
    except KeyError:
        raise UnkownPlayerException(
            'Player with ID %d is not in rating list. Please add it and try again.' % player_id)


def _split_players_types(all_players, valid_games):
    # The sets below store the IDs of players of each type
    unrated_players = set()
    temp_players = set()
    established_players = set()
    for player_id in valid_games:
        current_rating_info = _get_current_rating_info(all_players, player_id)
        if _is_unrated_player(current_rating_info):
            unrated_players.add(player_id)
        elif _is_temp_player(current_rating_info):
            temp_players.add(player_id)
        else:
            established_players.add(player_id)
    return unrated_players, temp_players, established_players


def _remove_games_vs_unrateds(all_players, games):
    # Remove games in place
    games_cleaned = []
    for game_info in games:
        oppon_rating_info = _get_current_rating_info(all_players, game_info.opponent_id)
        if not _is_unrated_player(oppon_rating_info):
            games_cleaned.append(game_info)
    games = games_cleaned


def _calculate_temp_rating_info(current_rating_info, tournament_result, tournament_name):
    # Assumes the player has scored at least half a point previously or in this tournament.
    total_prev_points = (
        current_rating_info.total_prev_points + tournament_result.total_num_points)
    assert total_prev_points, 'Unrated player scoring zero cannot get temporary rating.'
    new_num_games = current_rating_info.num_games + tournament_result.num_valid_games
    new_rating = _get_new_temp_rating(current_rating_info, tournament_result)
    sum_prev_oppon_rating = (
        current_rating_info.sum_prev_oppon_rating +
        # Use int(... + 0.5) below for rounding
        int(tournament_result.avg_oppon_rating * tournament_result.num_valid_games + 0.5))
    return RatingInfo(rating=new_rating,
                      last_tournament_name=tournament_name,
                      last_tournament_result=tournament_result,
                      last_tournament_calculation_rule=CalculationRule.TEMPORARY,
                      num_games=new_num_games,
                      current_k=_get_current_k(new_num_games),
                      is_temp_rating=True,
                      sum_prev_oppon_rating=sum_prev_oppon_rating,
                      total_prev_points=total_prev_points)


def _calculate_rating_info(current_rating_info, tournament_result, tournament_name,
                           calculation_rule):
    # Assumes the player has an established rating
    new_num_games = current_rating_info.num_games + tournament_result.num_valid_games
    if calculation_rule is CalculationRule.RATING_PERFORMANCE:
        new_rating = _get_rating_performance(current_rating_info.rating, tournament_result)
    elif calculation_rule is CalculationRule.DOUBLE_K:
        new_rating = _get_new_rating(
            current_rating_info, tournament_result, is_double_k_rule=True)
    else:
        new_rating = _get_new_rating(
            current_rating_info, tournament_result, is_double_k_rule=False)
    return RatingInfo(rating=new_rating,
                      last_tournament_name=tournament_name,
                      last_tournament_result=tournament_result,
                      last_tournament_calculation_rule=calculation_rule,
                      num_games=new_num_games,
                      current_k=_get_current_k(new_num_games),
                      is_temp_rating=False,
                      sum_prev_oppon_rating=None,
                      total_prev_points=None)


def _calculate_rating_for_players(all_players, full_tournament_info, players_ids_to_calculate):
    new_rating_info = {} # player_id to RatingInfo after this tournament
    for player_id in players_ids_to_calculate:
        games = full_tournament_info.valid_games[player_id]
        _remove_games_vs_unrateds(all_players, games)
        current_rating_info = _get_current_rating_info(all_players, player_id)
        tournament_result = _get_player_tournament_result(
            all_players, current_rating_info, games)
        tournament_name = full_tournament_info.tournament_name
        calculation_rule = _get_calculation_rule(current_rating_info, tournament_result)
        if calculation_rule is CalculationRule.TEMPORARY:
            if not current_rating_info.num_games and not tournament_result.total_num_points:
                # If in a temporary player's first tournament he gets zero points, the
                # tournament result is discarded for rating purposes.
                continue
            new_rating_info[player_id] = _calculate_temp_rating_info(
                current_rating_info, tournament_result, tournament_name)
        else:
            new_rating_info[player_id] = _calculate_rating_info(
                current_rating_info, tournament_result, tournament_name, calculation_rule)
    for player_id, player_new_rating_info in new_rating_info.items():
        all_players[player_id].rating_infos.append(player_new_rating_info)


def _calculate_tournament_ratings(all_players, full_tournament_info):
    '''Calculates the new rating for all players involved in tournament.

    Assumes full_tournament_info only contains games valid for rating calculation. Each actual
    game should appear twice, once for the white player and another for the black player. If a
    player has no valid game in the tournament, it shouldn't appear in full_tournament_info.

    First we calculate the rating for new players, followed by players with temporary rating
    and, lastly, by players with an established rating.

    Raises:
        NotImplementedError: If tournament has more than 7 rounds, when the special rating
            rules are unknown.
        ValueError: If full_tournament_info has player with no valid games or if its
            valid_games attribute has an invalid game (in terms of rating calculation).
    '''
    unrated_players, temp_players, established_players = _split_players_types(
        all_players, full_tournament_info.valid_games)
    _calculate_rating_for_players(all_players, full_tournament_info, unrated_players)
    _calculate_rating_for_players(all_players, full_tournament_info, temp_players)
    _calculate_rating_for_players(all_players, full_tournament_info, established_players)



def _get_player_id_by_rank(chess_results_tournament_id):
    url = 'http://chess-results.com/tnr%d.aspx' % chess_results_tournament_id
    soup = BeautifulSoup(requests.get(url).content, 'html.parser')
    table = soup.find("table", attrs={"class": "CRs1"})
    has_parsed_header = False
    player_id_by_start_rank = {} # given starting rank, obtains player id
    for row_num, row in enumerate(table.find_all("tr")):
        cells = [td.get_text().strip() for td in row.find_all("td")]
        if not has_parsed_header:
            for cell_num, cell in enumerate(cells):
                if cell == 'ID':
                    id_cell_num = cell_num
                elif cell == 'Name':
                    name_cell_num = cell_num
            has_parsed_header = True
        else:
            curr_player_id = int(cells[id_cell_num])
            if not curr_player_id:
                print()
                print('\tPlayer with unkown ID: %s' % cells[name_cell_num])
                curr_player_id = input('\tPlease enter this player\'s ID: ')
            player_id_by_start_rank[row_num] = curr_player_id
    return player_id_by_start_rank


def _get_valid_games(chess_results_tournament_id, player_id_by_start_rank):
    valid_games = {} # dict of int (player_id) to list of GameInfo.
    url = 'http://chess-results.com/tnr%d.aspx?art=5' % chess_results_tournament_id
    soup = BeautifulSoup(requests.get(url).content, 'html.parser')
    table = soup.find("table", attrs={"class": "CRs1"})
    has_parsed_header = False
    for row in table.find_all("tr"):
        cells = [td.get_text().strip() for td in row.find_all("td")]
        if not has_parsed_header:
            for cell_num, cell in enumerate(cells):
                if cell == '1.Rd':
                    first_round_cell_num = cell_num
                elif cell == 'Pts.':
                    last_round_cell_num = cell_num - 1
                    break
            has_parsed_header = True
        else:
            player_start_rank = int(cells[0])
            player_full_results = [
                cells[cell_num]
                for cell_num in range(first_round_cell_num, last_round_cell_num + 1)]
            player_valid_games = _extract_valid_games(
                player_full_results, player_id_by_start_rank)
            if player_valid_games:
                valid_games[player_id_by_start_rank[player_start_rank]] = player_valid_games
    return valid_games


def _extract_valid_games(player_full_results, player_id_by_start_rank):
    player_valid_games = []
    for result_txt in player_full_results:
        if result_txt == '-1' or result_txt == '-0':
            continue
        if result_txt[-1] == '1':
            result = Result.WIN
        elif result_txt[-1] == '0':
            result = Result.LOSS
        elif result_txt[-1] == '½':
            result = Result.DRAW
        else:
            continue
        oppon_rank = int(result_txt[:-2])
        player_valid_games.append(
            GameInfo(opponent_id=player_id_by_start_rank[oppon_rank],
                     result=result))
    return player_valid_games


def _load_full_tournament_info(chess_results_tournament_id, tournament_name):
    # Assumes a rating list with all players has already been loaded.
    # TODO: implement for team tournaments and for round robin tournaments
    player_id_by_rank = _get_player_id_by_rank(chess_results_tournament_id)
    valid_games = _get_valid_games(chess_results_tournament_id, player_id_by_rank)
    return FullTournamentInfo(tournament_name=tournament_name,
                              chess_results_id=chess_results_tournament_id,
                              valid_games=valid_games)


def _load_rating_list(rating_list_filepath, temp_rating_list_filepath):
    '''Loads rating list from CSV file using ";" as separator.

    For rating list, assumes the fields are, in order:
    Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames
    For temporary rating list, assumes the fields are, in order:
    Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints
    '''
    all_players = {} # dict int (player_id) to PlayerState (not thread-safe).
    # Should not be changed in the middle of a tournament rating calculation for players of same
    # type, so that each player's last RatingInfo corresponds to its rating before the
    # tournament.
    with open(rating_list_filepath) as rating_list:
        reader = csv.reader(rating_list, delimiter=_CSV_DELIMITER, quoting=csv.QUOTE_NONE)
        next(reader, None)  # skip the headers
        for row in reader:
            if len(row) != _RATING_LIST_HEADER_LEN:
                raise ValueError('Wrong number of columns in %s.' % rating_list_filepath)
            player_info = PlayerInfo(player_id=int(row[0]),
                                     name=row[2],
                                     title=row[1],
                                     birthdate=row[5],
                                     current_club=row[4],
                                     sex=row[6],
                                     federation=row[7])
            num_games = int(row[8])
            rating_info = RatingInfo(rating=int(row[3]),
                                     last_tournament_name=None,
                                     last_tournament_result=None,
                                     last_tournament_calculation_rule=None,
                                     num_games=num_games,
                                     current_k=_get_current_k(num_games),
                                     is_temp_rating=False,
                                     sum_prev_oppon_rating=None,
                                     total_prev_points=None)
            player_state = PlayerState(player_info=player_info, rating_infos=[rating_info])
            all_players[player_info.player_id] = player_state
    with open(temp_rating_list_filepath) as rating_list:
        reader = csv.reader(rating_list, delimiter=_CSV_DELIMITER, quoting=csv.QUOTE_NONE)
        next(reader, None)  # skip the headers
        for row in reader:
            if len(row) != _TEMP_RATING_LIST_HEADER_LEN:
                raise ValueError('Wrong number of columns in %s.' % temp_rating_list_filepath)
            player_info = PlayerInfo(player_id=int(row[0]),
                                     name=row[2],
                                     title=row[1],
                                     birthdate=row[5],
                                     current_club=row[4],
                                     sex=row[6],
                                     federation=row[7])
            num_games = int(row[8])
            rating_info = RatingInfo(rating=int(row[3]),
                                     last_tournament_name=None,
                                     last_tournament_result=None,
                                     last_tournament_calculation_rule=None,
                                     num_games=num_games,
                                     current_k=None,
                                     is_temp_rating=True,
                                     sum_prev_oppon_rating=int(row[9]),
                                     total_prev_points=float(row[10]))
            player_state = PlayerState(player_info=player_info, rating_infos=[rating_info])
            all_players[player_info.player_id] = player_state
    return all_players


def _save_new_rating_lists(all_players, output_rating_filepath, output_temp_rating_filepath):
    with open(output_rating_filepath, 'w') as new_rating_list:
        with open(output_temp_rating_filepath, 'w') as new_temp_rating_list:
            print(_RATING_LIST_HEADER, file=new_rating_list)
            print(_TEMP_RATING_LIST_HEADER, file=new_temp_rating_list)
            for player_id in sorted(all_players):
                player_info = all_players[player_id].player_info
                last_rating_info = _get_current_rating_info(all_players, player_id)
                if (_is_unrated_player(last_rating_info) or
                        _is_temp_player(last_rating_info)):
                    line_list = [str(player_info.player_id),
                                 player_info.title,
                                 player_info.name,
                                 str(last_rating_info.rating),
                                 player_info.current_club,
                                 player_info.birthdate,
                                 player_info.sex,
                                 player_info.federation,
                                 str(last_rating_info.num_games),
                                 str(last_rating_info.sum_prev_oppon_rating),
                                 str(last_rating_info.total_prev_points)
                                ]
                    print(_CSV_DELIMITER.join(line_list), file=new_temp_rating_list)
                else:
                    line_list = [str(player_info.player_id),
                                 player_info.title,
                                 player_info.name,
                                 str(last_rating_info.rating),
                                 player_info.current_club,
                                 player_info.birthdate,
                                 player_info.sex,
                                 player_info.federation,
                                 str(last_rating_info.num_games)
                                ]
                    print(_CSV_DELIMITER.join(line_list), file=new_rating_list)


def update_rating_list(initial_rating_filepath, initial_temp_rating_filepath,
                       chess_results_tournament_id, tournament_name, output_rating_filepath,
                       output_temp_rating_filepath):
    all_players = _load_rating_list(
        initial_rating_filepath, initial_temp_rating_filepath)
    full_tournament_info = _load_full_tournament_info(
        chess_results_tournament_id, tournament_name)
    _calculate_tournament_ratings(all_players, full_tournament_info)
    _save_new_rating_lists(
        all_players, output_rating_filepath, output_temp_rating_filepath)


def main():
    initial_rating_filepath = input('Enter the path to the most recent rating list: ')
    initial_temp_rating_filepath = input(
        'Enter the path to the most recent rating list '
        'containing only players with temporary rating: ')
    chess_results_tournament_id = int(input(
        'Enter the chess-results id of the tournament to be calculated for rating: '))
    tournament_name = input(
        'Enter the Tournament Name (for informational purposes only): ')
    output_rating_filepath = input(
        'Enter the path where you want to save the new rating list '
        '(will overwrite file if it exists): ')
    output_temp_rating_filepath = input(
        'Enter the path where you want to save the new rating list '
        'containing only players with temporary rating (will overwrite file if it exists): ')
    update_rating_list(initial_rating_filepath,
                       initial_temp_rating_filepath,
                       chess_results_tournament_id,
                       tournament_name,
                       output_rating_filepath,
                       output_temp_rating_filepath)


if __name__ == '__main__':
    main()
