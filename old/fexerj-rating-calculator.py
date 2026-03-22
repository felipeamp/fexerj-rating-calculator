from classes import FexerjRatingCycle
import argparse

# EXAMPLE (web method)
# python fexerj-rating-calculator.py --tournaments torneios_2024R2.csv --players 0_FexerjRating_202402.csv --first 20 --count 2
# EXAMPLE (binary method — tournament CSV must have a TUNX filename in column 8)
# python fexerj-rating-calculator.py --tournaments torneios_2025R2.csv --players 0_FexerjRating_2025.csv --first 1 --count 1 --method binary
parser = argparse.ArgumentParser(description="Calculate FEXERJ ratings from chess-results.com or .TUNX binary data.")
parser.add_argument("--tournaments", required=True, help="Path to the tournament list CSV file")
parser.add_argument("--players", required=True, help="Path to the players list CSV file")
parser.add_argument("--first", type=int, required=True, help="First tournament to run (1-based index)")
parser.add_argument("--count", type=int, default=1, help="Number of tournaments to run (default: 1)")
parser.add_argument("--method", choices=["web", "binary"], default="web",
                    help="Data source: 'web' scrapes chess-results.com (default), "
                         "'binary' reads .TUNX files listed in the tournament CSV")
args = parser.parse_args()

new_cycle = FexerjRatingCycle(args.tournaments, args.first, args.count, args.players, method=args.method)
new_cycle.load_manual_entry_dict()
new_cycle.run_cycle()

