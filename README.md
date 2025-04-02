# fexerj-rating-calculator

Code to calculate the FEXERJ rating based on chess-results pages. Code is still somewhat rough. Some functionality, documentation and unit/integration testing are missing.


# How to use

## Pre-conditions

There are two CSV needed: one for players and another for tournaments to be processed. The separator should be a semicolon ";". The first CSV should have the following header/columns:

`Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;AvgOpponRating;TotalPoints`

While the second CSV should have:

`#;CR_id;Name;EndDate;Type;isIRT?;isFEXERJ?`

All players in the tournaments should already be in the first CSV.

## How to run

The user should run the following command:

`python fexerj-rating-calculator.py <tournament_list_file> <first_torunament_to_run> <number_of_tournaments_to_run> <players_list_file>`

The program will create one intermediate players' list file for each tournament in the following format:
`RatingList_after_<number of the tournament>.csv`

Also, for each tournament, the program will create an audit file with the most important variables for the rating calculation in the following name format: `Audit_of_Tournament_<number of the tournament>.csv`

The program will also create a JSON file with all the players for which the ID was entered manually by the user. This is to avoid having to enter them again in a rerun. This file needs to be deleted by the user if the tournaments' file change.


## Command examples

To run the first 25 tournaments of the file:

```python fexerj-rating-calculator.py tournaments.csv 1 25 players.csv```

To run only the 11th tournaments of the file (for example, if you find some issue with a given tournament in Chess Results page, fix it and want to rerun from that point of the cycle):

```python fexerj-rating-calculator.py tournaments.csv 11 1 players.csv```


## TODO

* Error handling for common mistakes and errors
* Split code in modules
* Unit testing
* Integration testing
