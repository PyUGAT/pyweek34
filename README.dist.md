# Red Planted

You are the gardener of The Red Planet, the best source for
homeplanet-grown space tomatoes!

Your life is nice, you harvest space tomatoes all day and cut back
plants to make sure new plants can sprout and flourish.

However....

The devilish space flies are on the case again, and would just LOVE to
steal your space tomatoes that you worked so hard to nourish and grow.
So you better use your trusty fly swatter to get rid of them.

In summary, you have to:

 - Harvest space tomatoes (click on them)
 - Cut back old plants to let new tomatoes grow (click on the plant roots)
 - Swat away any flies when they enter the red planet's orbit (click on them)
 - Make sure you keep the whole planet in view (mouse wheel / touchpad scroll)

So yeah, scrolling and clicking, scrolling and clicking. Good luck,
commander! Erm.. gardener. Space gardener? Good luck, in any case!


## Gameplay

Carry out gardening tasks (cut off old plants to grow new ones, swat
flies that try to steal tomatoes, harvest ripe, red space tomatoes)
and win against the space flies by collecting more space tomatoes!

## Controls

The game is controlled using your mouse or touchpad:

 - Rotate the planet: Mouse wheel / touchpad scroll gesture
 - Cut off a plant: Click on the root (bottom) of the plant
 - Harvest a space tomato: Only when it's ripe (=red) - click on it
 - Swat a devilish space fly: Click on it (only within the atmosphere)

To pause the game if it's getting too intense, simply press ESCAPE
during gameplay to bring up the main menu.

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

## Related links

- [Github source repository](https://github.com/PyUGAT/pyweek34)
- [PyWeek entry](https://pyweek.org/e/RedPlanted/)
- [PyUGAT PyWeek](https://pyug.at/PyWeek)
- [PyConSK lightning talk by thp](https://youtu.be/yvEUoTkUoiA?t=34035)

## Credits

A PyWeek#34 entry by the Python User Group in Vienna, Austria (https://pyug.at/).
Authors: Christian Knittl-Frank, Paul Reiter, Claus Aichinger and Thomas Perl.
See `ARTWORK.txt` for a list of third party sound and graphic artwork used in this game.
