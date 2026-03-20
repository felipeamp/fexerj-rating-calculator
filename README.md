# fexerj-rating-calculator

Code to calculate the FEXERJ rating based on chess-results pages. Code is still somewhat rough. Some functionality, documentation and unit/integration testing are missing.


# How to use

## Pre-conditions

There are two CSV needed: one for players and another for tournaments to be processed. The separator should be a semicolon ";". The first CSV should have the following header/columns:

`Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints`

Example rows:

```
Id_No;Id_CBX;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;SumOpponRating;TotalPoints
1;1001;FM;JOAO DA SILVA;2100;CLUBE A;01/01/1985;M;BRA;350;0;0
2;1002;;MARIA SOUZA;1650;CLUBE B;15/06/1990;F;BRA;120;0;0
3;;;PEDRO OLIVEIRA;1450;CLUBE C;22/11/2005;M;BRA;40;0;0
```

Column notes:
- `Id_CBX` and `Title` may be left empty
- `Birthday` format: `DD/MM/YYYY`
- `Sex`: `M` or `F`
- `SumOpponRating` and `TotalPoints` accumulate across all cycles until the player becomes established, at which point both are set back to zero

The second CSV should have:

`#;CR_id;Name;EndDate;Type;isIRT?;isFEXERJ?`

Example rows:

```
#;CR_id;Name;EndDate;Type;isIRT?;isFEXERJ?
1;1000001;TORNEIO ABERTO RIO 2025;10.01.2025;RR;0;0
2;1000002;CAMPEONATO ESTADUAL SUB-12 2025;09.02.2025;SS;0;1
3;1000003;OPEN INTERNACIONAL RIO 2025;16.03.2025;ST;1;0
```

Column notes:
- `CR_id`: Chess Results tournament ID (from the tournament URL on chess-results.com)
- `EndDate` format: `DD.MM.YYYY`
- `Type`: must be one of `SS` (Swiss Single), `RR` (Round Robin), or `ST` (Swiss Team)
- `isIRT?` and `isFEXERJ?`: boolean flags — `1` = yes, `0` = no

All players in the tournaments should already be in the first CSV.

## How to run

The user should run the following command:

`python fexerj-rating-calculator.py --tournaments <tournament_list_file> --players <players_list_file> --first <first_tournament_to_run> --count <number_of_tournaments_to_run>`

`--count` is optional and defaults to `1`.

The program will create one intermediate players' list file for each tournament in the following format:
`RatingList_after_<number of the tournament>.csv`

Also, for each tournament, the program will create an audit file with the most important variables for the rating calculation in the following name format: `Audit_of_Tournament_<number of the tournament>.csv`

The program will also create a JSON file with all the players for which the ID was entered manually by the user. This is to avoid having to enter them again in a rerun. This file needs to be deleted by the user if the tournaments' file change.


## Command examples

To run the first 25 tournaments of the file:

```python fexerj-rating-calculator.py --tournaments tournaments.csv --players players.csv --first 1 --count 25```

To run only the 11th tournament of the file (for example, if you find some issue with a given tournament in Chess Results page, fix it and want to rerun from that point of the cycle):

```python fexerj-rating-calculator.py --tournaments tournaments.csv --players players.csv --first 11 --count 1```


## IDE setup (PyCharm)

To fix "unresolved reference" warnings in PyCharm, mark `old/` as a Sources Root:

Right-click the `old/` folder in the Project panel → **Mark Directory as** → **Sources Root**.

This is only needed for IDE highlighting — `pytest` resolves imports correctly for everyone via `pythonpath = old` in `pytest.ini`.

## Running the tests

Unit tests are located in `old/tests/` and use the [pytest](https://docs.pytest.org/) framework.

To run all tests from the project root:

```bash
python3 -m pytest
```

To run with detailed output:

```bash
python3 -m pytest -v
```

To run a specific test file:

```bash
python3 -m pytest old/tests/test_tournament_player.py -v
```

To run a specific test class or method:

```bash
python3 -m pytest old/tests/test_tournament_player.py::TestGetCurrentK -v
python3 -m pytest old/tests/test_tournament_player.py::TestGetCurrentK::test_entry_at_80_games -v
```


## TODO

* Error handling for common mistakes and errors
* Split code in modules
* Integration testing
