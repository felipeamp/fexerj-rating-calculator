from classes import FexerjRatingCycle
import sys

# EXAMPLE
# new_cycle = FexerjRatingCycle("torneios_2024R2.csv", 20, 2, "0_FexerjRating_202402.csv")
new_cycle = FexerjRatingCycle(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
new_cycle.run_cycle()

