# pip install code2flow
import subprocess

depths = range(5)

for depth in depths:
    subprocess.run(
        [
            "code2flow",
            "run_game.py",
            f"--downstream-depth {depth}",
            "--target-function main",
            f"--output downstream_depth_{depth}.png",
        ]
    )
