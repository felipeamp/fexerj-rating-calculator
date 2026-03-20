from classes import FexerjRatingCycle
import argparse

# EXAMPLE
# python fexerj-rating-calculator.py --tournaments torneios_2024R2.csv --players 0_FexerjRating_202402.csv --first 20 --count 2
parser = argparse.ArgumentParser(description="Calculate FEXERJ ratings from chess-results.com data.")
parser.add_argument("--tournaments", required=True, help="Path to the tournament list CSV file")
parser.add_argument("--players", required=True, help="Path to the players list CSV file")
parser.add_argument("--first", type=int, required=True, help="First tournament to run (1-based index)")
parser.add_argument("--count", type=int, default=1, help="Number of tournaments to run (default: 1)")
args = parser.parse_args()

new_cycle = FexerjRatingCycle(args.tournaments, args.first, args.count, args.players)
new_cycle.load_manual_entry_dict()
new_cycle.run_cycle()
new_cycle.write_manual_entry_dict()

