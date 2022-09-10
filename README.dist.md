# Red Planted

You are the guardian of a red planet and its gardens of space tomatoes.
Unfortunately, space flies try to steal your tomatoes. They like them!

## Gameplay

Carry out gardening tasks (cut off old plants to grow new ones, swat
flies that try to steal tomatoes, harvest ripe, red space tomatoes)
and win against the space flies by collecting more space tomatoes!

## Controls

Apart from SPACEBAR on your keyboard, the game is controlled using your
mouse or touchpad.

 - Rotate the planet: Mouse wheel / touchpad scroll gesture
 - Cut off a plant: Click on the root (bottom) of the plant
 - Harvest a space tomato: Only when it's ripe (=red) - click on it
 - Swat a devilish space fly: Click on it (only within the atmosphere)

To pause the game if it's getting too intense, simply press SPACEBAR
during gameplay, and press SPACEBAR again to resume gameplay.

## Installation

Using Python 3.8 or newer:

```console
python -m pip install -r requirements.txt
```

If you get a libGL error and use conda for package management,
you can solve it within your environment by `conda install -c conda-forge libstdcxx-ng`.

If you use a Mac and get a `/bin/sh: sdl2-config: command not found` error,
you can solve that with `brew install sdl2`.

## Play

To run the game:

```console
python3 run_game.py
```

If your GPU doesn't support multi-sampling, you can disable it:

```console
python3 run_game.py --no-multisample
```

## Credits

A PyWeek#34 entry by the Python User Group in Vienna, Austria (https://pyug.at/).
Authors: Christian Knittl-Frank, Paul Reiter, Claus Aichinger and Thomas Perl.
See `ARTWORK.md` for a list of third party sound and graphic artwork used in this game.
