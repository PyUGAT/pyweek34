# [PyWeek 34](https://pyweek.org/34/): Red Planted

PyUGAT's project repository for PyWeek 34.

- PyWeek Entry: https://pyweek.org/e/RedPlanted/
- PyUGAT PyWeek: https://pyug.at/PyWeek

## Play

To play, install the requirements as outlined below and run

```console
python run_game.py
```

## Setup & Development

Using your favorite tool to create an environment, do something
equivalent to

```console
python -m pip install -r requirements.txt
```

Low key automation

```console
find . -name '*.py' | entr sh -c "black . && isort . && pytest -vv"  # but only on your code ;)
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
