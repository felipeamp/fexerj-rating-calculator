# fexerj-rating-calculator

Code to calculate the FEXERJ rating. Tournament data can be read either from chess-results.com (web method) or directly from Swiss Manager binary files (binary method).


# How to use

## Pre-conditions

There are two CSV files needed: one for players and another for tournaments to be processed. The separator should be a semicolon ";".

The players CSV should have the following header/columns:

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

The tournaments CSV should have:

`#;CR_id;Name;EndDate;Type;isIRT?;isFEXERJ?;CLUB?`

Example rows:

```
#;CR_id;Name;EndDate;Type;isIRT?;isFEXERJ?;CLUB?
1;1000001;TORNEIO ABERTO RIO 2025;10.01.2025;RR;0;0;0
2;1000002;CAMPEONATO ESTADUAL SUB-12 2025;09.02.2025;SS;0;1;1
3;1000003;OPEN INTERNACIONAL RIO 2025;16.03.2025;ST;1;0;0
```

Column notes:
- `CR_id`: Chess Results tournament ID (from the tournament URL on chess-results.com)
- `EndDate` format: `DD.MM.YYYY`
- `Type`: must be one of `SS` (Swiss System), `RR` (Round Robin), or `ST` (Swiss Team)
- `isIRT?`, `isFEXERJ?`, `CLUB?`: boolean flags — `1` = yes, `0` = no

All players in the tournaments should already be in the players CSV.

## Data source methods

### Web method (default)

The program scrapes tournament data from chess-results.com. An internet connection is required.

### Binary method

The program reads tournament data directly from Swiss Manager binary export files (`.TUNX` for Swiss System, `.TURX` for Round Robin, `.TUMX` for Swiss Team). No internet connection is needed.

Binary files must be placed in the same directory as the tournaments CSV and named using the following convention:

`<#>-<CR_id>.TUNX` / `<#>-<CR_id>.TURX` / `<#>-<CR_id>.TUMX`

where `<#>` is the tournament's order number in the CSV and `<CR_id>` is its Chess Results ID. For example, tournament 1 with CR ID 1333998 should be exported as `1-1333998.TUNX`.

The parser performs format validation on every file it reads and will raise an error or warning if the Swiss Manager binary format appears to have changed.

## How to run

```
python fexerj-rating-calculator.py --tournaments <tournament_list_file> --players <players_list_file> --first <first_tournament_to_run> --count <number_of_tournaments_to_run> [--method web|binary]
```

- `--count` is optional and defaults to `1`
- `--method` is optional and defaults to `web`

The program will create one intermediate players' list file for each tournament:
`RatingList_after_<number>.csv`

For each tournament it will also create an audit file:
`Audit_of_Tournament_<number>.csv`

The program creates a JSON file (`manual_entry_list.json`) to persist player IDs entered manually during a run, so they do not need to be re-entered on reruns. Delete this file if the tournaments CSV changes.


## Command examples

Run the first 25 tournaments using web scraping:

```bash
python fexerj-rating-calculator.py --tournaments tournaments.csv --players players.csv --first 1 --count 25
```

Run the first 15 tournaments using binary files:

```bash
python fexerj-rating-calculator.py --tournaments tournaments.csv --players players.csv --first 1 --count 15 --method binary
```

Rerun only the 11th tournament (e.g. after fixing data on chess-results.com):

```bash
python fexerj-rating-calculator.py --tournaments tournaments.csv --players players.csv --first 11 --count 1
```


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
* Integration testing
