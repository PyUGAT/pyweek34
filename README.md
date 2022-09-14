# [PyWeek 34](https://pyweek.org/34/): Red Planted

PyUGAT's project repository for PyWeek 34.

- [PyWeek entry](https://pyweek.org/e/RedPlanted/)
- [PyUGAT PyWeek](https://pyug.at/PyWeek)
- [PyConSK lightning talk by thp](https://youtu.be/yvEUoTkUoiA?t=34035)
- [Game artwork on OpenGameArt.org](https://opengameart.org/content/red-planted-game-artwork)

## Play

To play, install the requirements with

```console
python -m pip install -r requirements.txt
```

then run the game with

```console
python run_game.py
```

If you get a libGL error and use conda for package management,
you can solve it within your environment by `conda install -c conda-forge libstdcxx-ng`.


## Setup & Development

Using your favorite tool to create an environment, do something
equivalent to

```console
python -m pip install -r requirements.txt -r dev-requirements.txt
```

You want to update the requirements?

Add/Remove entries from `requirements.in` or `dev-requirements.in`, run
`pip-compile requirements.in` or `pip-compile dev-requirements.in` to regenerate the
actual requirements txt files and finally run
`pip-sync requirements.txt dev-requirements.txt`
to update the installed packages in your virtual environment.

You want to automatically restart the game after a change?

```console
ls run_game.py | entr -r python run_game.py
```

Adjust `ls` argument to watch for other changes as well.

Low key automation

```console
find . -name '*.py' | entr sh -c "black . && isort . && pytest -vv"  # but only on your code ;)
```

See also the [entr man page](https://www.systutorials.com/docs/linux/man/1-entr/).


## Packaging for PyWeek

Run below command to create a ZIP file containing all necessary resources.

```console
python package_for_pyweek.py
```


## Daily

We meet every day at 20:00 in [Gather](https://app.gather.town/invite?token=9sXyCr7GdMGEpeNHcGCinsalCna3_b2w).

Whoever has time is invited to join.

## Collaboration

To simplify collaboration, we agreed to directly commit to `main`.
Please avoid rewriting history, e.g. `git push --force`.
If you want to share your work, feel free to create a folder.

Feel free to format you code using [black](https://black.readthedocs.io/).

## Useful Resources

You need shared documents? Consider [C3W's cryptpad instance](https://pads.c3w.at/).

You want another shared whiteboard? Consider [cocreate](https://cocreate.csail.mit.edu/).

You want sound effects? Consider [freesound](https://freesound.org/).

You want images/art? Consider [OpenGameArt](https://opengameart.org/).
