# fexerj-rating-calculator

Code to calculate the FEXERJ rating based on chess-results pages. Code is still somewhat rough. Some functionality, documentation and unit/integration testing are missing.


## How to use

There are two CSV needed: one for players with established rating and another for players with temporary rating. The separator should be a semicolon ";". The first CSV should have the following header/columns:
Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames
while the second CSV should have:
Id_No;Title;Name;Rtg_Nat;ClubName;Birthday;Sex;Fed;TotalNumGames;AvgOpponRating;TotalPoints

The user should run the following command:

```python3 calculator.py```

and answer the given questions. All players in the tournament should already be in one of the CSV's.


## TODO

* User can manually input player IDs in real-time when calculating rating for a tournament
* Add flags to do batch processing (including which type of tournament it is)
* Print tournament name when calculating its rating
* Save average opponent rating instead of opponent rating sum for players with temporary rating
* Create parser for Round Robin and Swiss Team tournaments (the latter needs multiple HTTP GET requests)
* Error handling for common mistakes and errors
* Split code in modules
* Unit testing
* Integration testing
