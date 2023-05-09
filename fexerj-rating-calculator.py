from classes import FexerjRatingCycle

if __name__ == "__main__":
    import sys
    # EXAMPLE: FexerjRatingCycle("torneios_2023R1.csv", 1, 1, "0_FexerjRating_202301.csv")
    FexerjRatingCycle(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
