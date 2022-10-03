"""
TBD: different kinds of configuration
- run time
- game play
"""
import argparse


parser = argparse.ArgumentParser()
parser.add_argument(
    "--debug",
    action="store_true",
    help="Show debug info",
)
parser.add_argument(
    "--fast", action="store_true", help="Fast growth to accelerate startup"
)
parser.add_argument(
    "--no-multisample",
    action="store_true",
    help="Disable OpenGL multi-sampling (for old GPUs)",
)
CLIARGS = parser.parse_args()


class ImportantParameterAffectingGameplay:
    GAMEOVER_THRESHOLD_FLIES_WIN = (
        4 if CLIARGS.fast else 10
    )  # Flies win when they steal N tomatoes
    GAMEOVER_THRESHOLD_PLAYER_WINS = (
        4 if CLIARGS.fast else 25
    )  # Player wins when harvested N tomatoes
    BREEDING_EVERY_N_TICKS = (
        100 if CLIARGS.fast else 400
    )  # Reproduction interval to maintain MIN_NUM_FLIES, increase/decrease value to slow down/seep up reproduction
    MOVING_TO_OTHER_SECTOR_EVERY_N_TICKS = (
        10 if CLIARGS.fast else 50
    )  # How often the spaceship changes location, increase/decrease value to decrease/increase changes
    TOMATO_TO_FLY = 1  # N collected tomatoes result in 1 fly; min value 1, increase to slow down reproduction
    MIN_NUM_FLIES = 3  # There are at least N flies
    MAX_NUM_FLIES = 12  # There are at most N flies
    GROWTH_SPEED = (
        100 if CLIARGS.fast else 3
    )  # How fast the plants grow, increase/decrease value to speed up/slow down growth
    FERTILITY = (
        20,
        50,
    )  # Increase/decrease values for stronger/weaker plants (with more/less tomatoes)
