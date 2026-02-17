import json
import math
import os
from urllib.parse import urlparse, parse_qs
import csv

import requests
from bs4 import BeautifulSoup

_CSV_DELIMITER = ';'
_URLDOMAIN = "https://s3.chess-results.com"
_RATING_LIST_HEADER = 'Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating' \
                      ';TotalPoints'
# -- Audit File Columns --
# Id_Fexerj = ID of the player within FEXERJ
# Name = Name of the player
# No = Number of the player within Chess Result tournament
# Ro = Rating before tournament
# Ind = Total games before tournament
# K = K before tournament
# PG = Points against opponents on valid games in the current tournament
# N = Valid games in the current tournament
# Erm = SUM of opponents' ratings in the current tournament
# Rm = Average rating of opponents in the current tournament
# Dif = Difference between Ro and Rm
# We = Nwe divided by N (zero if N is zero)
# Nwe = Expected points in the current tournament
# Dw = Points above expected in the current tournament
# kDw = K * Dw
# Rn = New rating
# Nind = New total games
# P = PG / N
# Calc_Rule = Calculation Rule used (NORMAL, TEMPORARY, RATING_PERFORMANCE or DOUBLE_K)
_AUDIT_FILE_HEADER = 'Id_Fexerj;Name;No;Ro;Ind;K;PG;N;Erm;Rm;Dif;We;Nwe;Dw;kDw;Rn;Nind;P;Calc_Rule'
_MAX_NUM_GAMES_TEMP_RATING = 15
_K_STARTING_NUM_GAMES = [(30, 0),  # grampo
                         (25, _MAX_NUM_GAMES_TEMP_RATING),  # 15
                         (15, 40),
                         (10, 80)]
_CURRENT_TOURNAMENT_SNR = 0


class FexerjRatingCycle:
    def __init__(self, tournaments_file, first_item, items_to_process, initial_rating_filepath):
        self.tournaments_file = tournaments_file
        self.first_item = first_item
        self.items_to_process = items_to_process
        self.initial_rating_filepath = initial_rating_filepath
        self.final_rating_filepath = ""
        self.rating_list = {}
        self.tournaments = {}
        self.cbx_to_fexerj = {}
        self.manual_entries = {}

    def run_cycle(self):
        with open(self.tournaments_file, 'r') as f:
            reader = csv.reader(f, delimiter=_CSV_DELIMITER)
            self.tournaments = list(reader)[1:]
            for tournament in self.tournaments:
                self.final_rating_filepath = "RatingList_after_%s.csv" % (tournament[0])
                tournament_audit_filepath = "Audit_of_Tournament_%s.csv" % (tournament[0])
                if int(tournament[0]) in range(self.first_item, self.first_item + self.items_to_process):
                    print("\nRunning tournament %s (%s)...\n" % (tournament[0], tournament[2]))
                    self.get_rating_list(self.initial_rating_filepath)
                    print("Reading from %s" % self.initial_rating_filepath)
                    print("Writing to %s" % self.final_rating_filepath)
                    trn_type = tournament[4]
                    if trn_type == 'SS':
                        tournament = SwissSingleTournament(self, tournament)
                    elif trn_type == 'RR':
                        tournament = RoundRobinTournament(self, tournament)
                    elif trn_type == 'ST':
                        tournament = SwissTeamTournament(self, tournament)
                    else:
                        raise ValueError('Wrong tournament type: %s' % trn_type)
                    tournament.load_player_list()
                    tournament.complete_players_info()
                    tournament.calculate_players_ratings()
                    tournament.write_new_ratings_list(self.final_rating_filepath)
                    tournament.write_tournament_audit(tournament_audit_filepath)
                self.initial_rating_filepath = self.final_rating_filepath

    def get_rating_list(self, initial_rating_filepath):
        with open(initial_rating_filepath) as rating_list:
            reader = csv.reader(rating_list, delimiter=_CSV_DELIMITER)
            next(reader, None)  # Skip the headers
            for row in reader:
                player = FexerjPlayer(int(row[0]),  # ID FEXERJ
                                      row[1],  # ID CBX
                                      row[2],  # TITLE
                                      row[3],  # NAME
                                      int(row[4]),  # RATING
                                      row[5],  # CLUB
                                      row[6],  # BIRTHDAY
                                      row[7],  # SEX
                                      row[8],  # FEDERATION
                                      int(row[9]),  # TOTAL NUM OF GAMES
                                      row[10],  # SUM OF OPPONENT RATINGS
                                      row[11])  # POINTS AGAINST OPPONENTS
                self.rating_list.update({int(row[0]): player})
                if len(row[1]) > 0:
                    self.cbx_to_fexerj[int(row[1])] = int(row[0])

    def load_manual_entry_dict(self):
        if os.path.exists('manual_entry_list.json'):
            with open('manual_entry_list.json', 'r') as manual_entry_dict_file:
                self.manual_entries = json.load(manual_entry_dict_file)

    def write_manual_entry_dict(self):
        with open('manual_entry_list.json', 'w') as manual_entry_dict_file:
            manual_entry_dict_file.write(json.dumps(self.manual_entries))


class FexerjPlayer:
    def __init__(self, id_fexerj, id_cbx, title, name, last_rating, club, birthday, sex, federation, total_games,
                 sum_opponents_ratings, points_against_opponents):
        self.id_fexerj = id_fexerj
        self.id_cbx = id_cbx
        self.title = title
        self.name = name
        self.last_rating = last_rating
        self.club = club
        self.birthday = birthday
        self.sex = sex
        self.federation = federation
        self.total_games = total_games
        self.sum_opponents_ratings = sum_opponents_ratings
        self.points_against_opponents = points_against_opponents


class TournamentPlayer:
    def __init__(self, tournament, player_url):
        # Example of player_url: https://chess-results.com/tnr1043710.aspx?lan=1&art=9&fed=BRA&turdet=YES&flag=30&snr=1
        self.snr = 0
        self.name = ""
        self.id = 0
        self.opponents = []
        self.tournament = tournament
        self.load_player_page(player_url)
        self.is_unrated = None
        self.is_temp = None
        self.last_k = None
        self.last_rating = None
        self.last_total_games = None
        self.last_sum_oppon_ratings = None
        self.last_pts_against_oppon = None
        self.this_pts_against_oppon = None
        self.this_sum_oppon_ratings = None
        self.this_avg_oppon_rating = None
        self.this_games = None
        self.this_score = None
        self.this_expected_points = None
        self.this_points_above_expected = None
        self.new_rating = None
        self.new_total_games = None
        self.new_sum_oppon_ratings = None
        self.new_pts_against_oppon = None
        self.calc_rule = None

    def load_player_page(self, url):
        soup = BeautifulSoup(requests.get(url).content, 'lxml')
        tables = soup.find_all("table", class_="CRs1")
        if not len(tables):
            del self
            return
        table = tables[0]
        rows = table.find_all("tr")
        for i in range(len(rows)):
            cells = rows[i].find_all("td")
            cell_data = [cell.get_text().strip() for cell in cells]
            if cell_data[0] == "Name":
                self.name = cell_data[1]
            elif cell_data[0] == "Starting rank":
                self.snr = cell_data[1]
            elif cell_data[0] == "Ident-Number":
                self.id = int(cell_data[1])
                if not self.id:
                    manual_entry_key = str(self.tournament.ord) + '.' + str(self.snr)
                    if manual_entry_key in self.tournament.rating_cycle.manual_entries:
                        self.id = self.tournament.rating_cycle.manual_entries[manual_entry_key]
                    else:
                        print()
                        print('\tPlayer with unknown ID: %s' % self.name)
                        self.id = int(input('\tPlease enter this player\'s ID: '))
                        print()
                        self.tournament.rating_cycle.manual_entries[manual_entry_key] = self.id
        # Get Opponents and Results
        table = tables[1]
        header = table.select("tr")[0].find_all("th")
        header_data = [h.get_text().strip() for h in header]
        for cell_num, cell in enumerate(header_data):
            if cell == 'SNo':
                id_cell_num = cell_num
            elif cell == 'Name':
                name_cell_num = cell_num
            elif cell == 'Res.':
                result_cell_num = cell_num
        rows = table.find_all("tr", recursive=False)
        for i in range(1, len(rows)):
            cells = rows[i].find_all("td", recursive=False)
            id_opponent = cells[id_cell_num].get_text().strip()
            name_opponent = cells[name_cell_num].get_text().strip()
            result_opponent = cells[result_cell_num].get_text().strip()
            if name_opponent not in ['not paired', 'bye']:
                self.add_opponent(int(id_opponent), name_opponent, result_opponent)

    def add_opponent(self, sno, name, result):
        if result[-1] != "K":
            if result[-1] == "½":
                res = '0.5'
            else:
                res = result[-1]
            self.opponents.append([sno, name, float(res)])

    def keep_current_rating(self):
        # self.new_rating = self.this_rating = self.last_rating
        self.new_rating = self.last_rating
        self.new_total_games = self.last_total_games
        self.new_sum_oppon_ratings = self.last_sum_oppon_ratings
        self.new_pts_against_oppon = self.last_pts_against_oppon

    def calculate_new_rating(self, is_fexerj_tournament):
        invalid_opponents = []
        for k, tp_oppon in self.opponents.items():
            if tp_oppon[0].is_unrated:
                if self.is_unrated or (tp_oppon[0].new_rating is None) or tp_oppon[0].new_rating == 0:
                    invalid_opponents.append(k)
        for i in invalid_opponents:
            del self.opponents[i]
        self.this_games = len(self.opponents)
        if self.this_games == 0 or (self.is_unrated and self.this_pts_against_oppon == 0):
            self.keep_current_rating()
            return
        self.this_sum_oppon_ratings = 0
        self.this_pts_against_oppon = 0
        for snr_opp, oppon in self.opponents.items():
            # If the player is unrated, his unrated opponent will be moved to the invalid_opponents list in the first
            # part of this method. When the program reaches this FOR, self.opponents will never have an unrated player
            # if the current player is also unrated. Meaning that unrated x unrated will never happen.
            if oppon[0].is_unrated:
                self.this_sum_oppon_ratings += oppon[0].new_rating
            elif oppon[0].is_temp and not (self.is_unrated or self.is_temp):  # self established x oppon temporary
                self.this_sum_oppon_ratings += oppon[0].new_rating
            else:
                self.this_sum_oppon_ratings += oppon[0].last_rating
            self.this_pts_against_oppon += oppon[1]
        if self.is_unrated and self.this_pts_against_oppon == 0:
            self.keep_current_rating()
            return
        self.last_k = self.get_current_k()
        self.this_avg_oppon_rating = self.this_sum_oppon_ratings / self.this_games
        rating_diff = self.this_avg_oppon_rating - self.last_rating
        self.this_expected_points = self.this_games / (1.0 + 10.0 ** (rating_diff / 400.0))
        self.this_points_above_expected = (self.this_pts_against_oppon - self.this_expected_points)
        self.new_total_games = self.last_total_games + self.this_games
        self.calc_rule = self.get_calculation_rule(is_fexerj_tournament)
        if self.calc_rule == "TEMPORARY":
            if (self.this_games + self.last_total_games) == 0:
                # If in a temporary player's "first tournament he gets zero points", the
                # tournament result is discarded for rating purposes.
                pass
            else:
                self.new_sum_oppon_ratings = self.last_sum_oppon_ratings + self.this_sum_oppon_ratings
                self.new_avg_oppon_rating = self.new_sum_oppon_ratings / self.new_total_games
                self.new_pts_against_oppon = self.last_pts_against_oppon + self.this_pts_against_oppon
                self.new_rating = round(self.get_performance_rating(self.new_avg_oppon_rating, self.new_total_games,
                                                                    self.new_pts_against_oppon))
        elif self.calc_rule == "RATING_PERFORMANCE":
            self.this_avg_oppon_rating = self.this_sum_oppon_ratings / self.this_games
            performance_rating = self.get_performance_rating(self.this_avg_oppon_rating, self.this_games,
                                                             self.this_pts_against_oppon)
            # self.new_rating = round(self.this_rating + (performance_rating - self.this_rating) / 2)
            self.new_rating = round(self.last_rating + (performance_rating - self.last_rating) / 2)
        else:
            rating_gain = (1 + int(self.calc_rule == "DOUBLE_K")) * self.last_k * self.this_points_above_expected
            rating_gain_rounded = round(rating_gain)  # Rounding to the closest int
            # self.new_rating = max(self.this_rating + rating_gain_rounded, 1)
            self.new_rating = max(self.last_rating + rating_gain_rounded, 1)

        # print(str(self.id) + " | " + self.name + " | Old: " + str(self.last_rating) + " | New: " + str(self.new_rating))

        # For debug
        # print(str(self.id) + " | " + self.name + " | " + str(self.this_sum_oppon_ratings) + " | " + str(self.this_expected_points) + " | " + str(self.this_games))

    def get_calculation_rule(self, is_fexerj_tournament):
        if self.is_temp or self.is_unrated:
            return "TEMPORARY"
        elif self.check_rating_performance_rule() and is_fexerj_tournament:
            return "RATING_PERFORMANCE"
        elif self.check_double_k_rule():
            return "DOUBLE_K"
        return "NORMAL"

    def check_rating_performance_rule(self):
        if self.this_games < 5:
            return False
        elif self.this_games == 5:
            return self.this_points_above_expected >= 1.84
        elif self.this_games == 6:
            return self.this_points_above_expected >= 2.02
        elif self.this_games == 7:
            return self.this_points_above_expected >= 2.16
        else:
            print("WARNING: Unknown condition for RP rule with more than 7 games. Assuming FALSE for Rating Performance.")
            return False

    def check_double_k_rule(self):
        if self.this_games < 4:
            return False
        elif self.this_games == 4:
            return self.this_points_above_expected >= 1.65
        elif self.this_games == 5:
            return self.this_points_above_expected >= 1.43
        elif self.this_games == 6:
            return self.this_points_above_expected >= 1.56
        elif self.this_games == 7:
            return self.this_points_above_expected >= 1.69
        else:
            print("WARNING: Unknown condition for DK rule with more than 7 games. Assuming FALSE for Double K.")
            return False

    def get_current_k(self):
        # Assumes rating is not temporary
        for (k, starting_num_games) in _K_STARTING_NUM_GAMES:
            if self.last_total_games >= starting_num_games:
                current_k = k
        return current_k

    def get_performance_rating(self, avg_oppon_rating, num_valid_games, total_num_points):
        # In case of perfect results, consider score as if there was an extra game that ended in a
        # draw.
        score = total_num_points / num_valid_games
        if score == 1.0:
            score = (num_valid_games + 0.5) / (num_valid_games + 1.0)
        elif score == 0.0:
            score = 0.5 / (num_valid_games + 1.0)
        return avg_oppon_rating + 400.0 * math.log10(score / (1.0 - score))


class Tournament:
    def __init__(self, rating_cycle, tournament):
        self.ord = int(tournament[0])
        self.id = int(tournament[1])
        self.name = tournament[2]
        self.date_end = tournament[3]
        self.type = tournament[4]
        self.is_irt = int(tournament[5])
        self.is_fexerj = int(tournament[6])
        self.players = {}
        self.unrated_keys = []
        self.temp_keys = []
        self.established_keys = []
        self.rating_cycle = rating_cycle

    def complete_players_info(self):
        for snr, tp in self.players.items():
            if self.is_irt:
                fp = self.rating_cycle.rating_list[self.rating_cycle.cbx_to_fexerj[tp.id]]
            else:
                fp = self.rating_cycle.rating_list[tp.id]
            tp.last_rating = int(fp.last_rating)
            tp.last_total_games = int(fp.total_games)
            tp.last_sum_oppon_ratings = int(fp.sum_opponents_ratings)
            tp.last_pts_against_oppon = float(fp.points_against_opponents)
            if int(fp.total_games) == 0:
                self.unrated_keys.append(snr)
                tp.is_unrated = True
            elif int(fp.total_games) < _MAX_NUM_GAMES_TEMP_RATING:
                self.temp_keys.append(snr)
                tp.is_temp = True
            else:
                self.established_keys.append(snr)

        # Convert each opponents array into dict and delete unrated opponents
        for snr, tp in self.players.items():
            tp.opponents = {opp[0]: [self.players[opp[0]], opp[2]] for opp in tp.opponents}

    def calculate_players_ratings(self):
        # First, calculates unrated
        for k in self.unrated_keys:
            self.players[k].calculate_new_rating(self.is_fexerj)
            # self.players[k].this_rating = self.players[k].new_rating

        # Second, calculates temporaries
        for k in self.temp_keys:
            self.players[k].calculate_new_rating(self.is_fexerj)
            # self.players[k].this_rating = self.players[k].new_rating

        # Third, calculates established
        for k in self.established_keys:
            self.players[k].calculate_new_rating(self.is_fexerj)

    def write_new_ratings_list(self, output_rating_filepath):
        for player in self.players.values():
            if self.is_irt:
                fp = self.rating_cycle.rating_list[self.rating_cycle.cbx_to_fexerj[player.id]]
            else:
                fp = self.rating_cycle.rating_list[player.id]
            fp.last_rating = player.new_rating
            fp.total_games = player.new_total_games
            if player.new_total_games < _MAX_NUM_GAMES_TEMP_RATING:
                fp.sum_opponents_ratings = player.new_sum_oppon_ratings
                fp.points_against_opponents = player.new_pts_against_oppon
            else:
                fp.sum_opponents_ratings = 0
                fp.points_against_opponents = 0

        with open(output_rating_filepath, 'w') as new_rating_list:
            print(_RATING_LIST_HEADER, file=new_rating_list)
            for key, player in self.rating_cycle.rating_list.items():
                line_list = [str(player.id_fexerj),
                             str(player.id_cbx),
                             player.title,
                             player.name,
                             str(player.last_rating),
                             player.club,
                             player.birthday,
                             player.sex,
                             player.federation,
                             str(player.total_games),
                             str(player.sum_opponents_ratings),
                             str(player.points_against_opponents)]
                print(_CSV_DELIMITER.join(line_list), file=new_rating_list)

    def write_tournament_audit(self, tournament_audit_filepath):
        #TODO Create pydoc to document corner cases on audit file creation
        # https://github.com/felipeamp/fexerj-rating-calculator/issues/22
        with open(tournament_audit_filepath, 'w') as new_audit_file:
            print(_AUDIT_FILE_HEADER, file=new_audit_file)
            for snr, tp in self.players.items():
                line_list = [str(tp.id),
                             tp.name,
                             str(snr),
                             str(tp.last_rating),
                             str(tp.last_total_games),
                             str(tp.last_k),
                             str(tp.this_pts_against_oppon),
                             str(tp.this_games),
                             str(tp.this_sum_oppon_ratings),
                             str(float(tp.this_avg_oppon_rating or 0)),
                             str(tp.last_rating - float(tp.this_avg_oppon_rating or 0)),
                             str(None if tp.this_games == 0 else (float(tp.this_expected_points or 0) / tp.this_games)),
                             str(float(tp.this_expected_points or 0)),
                             str(float(tp.this_points_above_expected or 0)),
                             str(int(tp.last_k or 0) * float(tp.this_points_above_expected or 0)),
                             str(tp.new_rating),
                             str(tp.new_total_games),
                             str(None if tp.this_games == 0 else float(tp.this_pts_against_oppon or 0) / tp.this_games), # To avoid division by zero
                             str(tp.calc_rule)]
                print(_CSV_DELIMITER.join(line_list), file=new_audit_file)

class SwissSingleTournament(Tournament):
    def load_player_list(self):
        # Access Chess Results (Starting Rank
        url = _URLDOMAIN + '/tnr%d.aspx?lan=1&art=0&turdet=YES' % self.id
        formdata = {"__VIEWSTATE": "",
                    "__VIEWSTATEGENERATOR": "",
                    "cb_alleDetails": "Show+tournament+details"}

        with requests.Session() as s:
            s.headers = {"User-Agent": "Mozilla/5.0"}
            res = s.post(url, data=formdata)

        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find("table", attrs={"class": "CRs1"})
        header = table.select("tr")[0].find_all("th")
        header_data = [h.get_text().strip() for h in header]

        for cell_num, cell in enumerate(header_data):
            if cell == 'Name':
                name_cell_num = cell_num

        for x in range(1, len(table.select("tr"))):
            td_row = table.select("tr")[x].find_all("td")
            url = td_row[name_cell_num].find("a").get("href")
            parsed = urlparse(url)
            snr = int(parse_qs(parsed.query).get('snr')[0])
            self.players[snr] = TournamentPlayer(self, url)
            if self.players[snr].snr == 0:
                del self.players[snr]


class RoundRobinTournament(Tournament):
    def load_player_list(self):
        # Access Chess Results (Starting Rank
        url = _URLDOMAIN + '/tnr%d.aspx?lan=1&art=0' % self.id
        formdata = {"__VIEWSTATE": "",
                    "__VIEWSTATEGENERATOR": "",
                    "cb_alleDetails": "Show+tournament+details"}

        with requests.Session() as s:
            s.headers = {"User-Agent": "Mozilla/5.0"}
            res = s.post(url, data=formdata)

        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find("table", attrs={"class": "CRs1"})
        header = table.select("tr")[0].find_all("th")
        header_data = [h.get_text().strip() for h in header]

        for cell_num, cell in enumerate(header_data):
            # if cell == 'ID':
            #     id_cell_num = cell_num
            # elif cell == 'Name':
            if cell == 'Name':
                name_cell_num = cell_num

        for x in range(1, len(table.select("tr"))):
            td_row = table.select("tr")[x].find_all("td")
            url = td_row[name_cell_num].find("a").get("href")
            parsed = urlparse(url)
            snr = int(parse_qs(parsed.query).get('snr')[0])

            self.players[snr] = TournamentPlayer(self, url)
            if self.players[snr].snr == 0:
                del self.players[snr]


class SwissTeamTournament(Tournament):
    def load_player_list(self):
        # Access Chess Results (Starting Rank
        url = _URLDOMAIN + '/tnr%d.aspx?lan=1&art=16&zeilen=99999' % self.id
        formdata = {"__VIEWSTATE": "",
                    "__VIEWSTATEGENERATOR": "",
                    "cb_alleDetails": "Show+tournament+details"}

        with requests.Session() as s:
            s.headers = {"User-Agent": "Mozilla/5.0"}
            res = s.post(url, data=formdata)

        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find("table", attrs={"class": "CRs1"})
        header = table.select("tr")[0].find_all("th")
        header_data = [h.get_text().strip() for h in header]

        for cell_num, cell in enumerate(header_data):
            if cell == 'Name':
                name_cell_num = cell_num

        for x in range(1, len(table.select("tr"))):
            td_row = table.select("tr")[x].find_all("td")
            url = td_row[name_cell_num].find("a").get("href")
            parsed = urlparse(url)
            snr = int(parse_qs(parsed.query).get('snr')[0])
            self.players[snr] = TournamentPlayer(self, url)
            if self.players[snr].snr == 0:
                del self.players[snr]
