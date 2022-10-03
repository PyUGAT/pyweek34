"""
TBD:
- Module name: artwork vs resources?
- Is ResourceManager used explicitely? Vs Artwork?
"""

import os
import random

import pygame
from pygame.mixer import Sound
from .sprite import AnimatedImageSprite, ImageSprite


class ResourceManager:
    def __init__(self, root):
        self.root = root

    def dir(self, category: str):
        return ResourceManager(self.filename(category))

    def filename(self, filename: str):
        return os.path.join(self.root, filename)

    def sprite(self, filename: str):
        return ImageSprite.load(self.dir("image").filename(filename))

    def font(self, filename: str, point_size: int):
        return pygame.font.Font(self.dir("font").filename(filename), point_size)

    def sound(self, filename: str):
        return Sound(self.dir("sound").filename(filename))


class Artwork:
    def __init__(self, resources: ResourceManager):
        # images
        self.tomato = [
            resources.sprite(filename)
            for filename in (
                "tomatopx-fresh.png",
                "tomatopx-yellow.png",
                "tomatopx-ripe.png",
                "tomato-bad.png",
            )
        ]
        self.leaves = [resources.sprite(f"leafpx{num}.png") for num in (1, 2, 3)]
        self.rocks = [resources.sprite(f"rockpx{num}.png") for num in (1, 2, 3, 4)]
        self.planet = resources.sprite("mars.png")
        self.spaceship = resources.sprite("spaceship.png")
        self.logo_text = resources.sprite("logo-text.png")
        self.logo_bg = resources.sprite("logo-bg.png")

        self.cursors = {
            # None: ...,  # in case we also want a custom cursor if not on object
            "cut": {
                False: resources.sprite("cursor_cut_open_px.png"),
                True: resources.sprite("cursor_cut_closed_px.png"),
            },
            "harvest": {
                False: resources.sprite("cursor_harvest_px.png"),
                True: resources.sprite("cursor_harvest_grab_px.png"),
            },
            "hunt": {
                False: resources.sprite("cursor_swatter_px.png"),
                True: resources.sprite("cursor_swatter_hit_px.png"),
            },
        }

        # animations (images)
        self.fly_animation = AnimatedImageSprite(
            [
                resources.sprite("fly1.png"),
                resources.sprite("fly2.png"),
            ],
            delay_ms=200,
        )

        # sounds
        self.pick = [resources.sound(f"pick{num}.wav") for num in (1,)]
        self.mowing = [resources.sound(f"mowing{num}.wav") for num in (1, 2, 3)]
        self.slap = [resources.sound(f"slap{num}.wav") for num in (1, 2, 3)]
        self.ripe_sound = resources.sound("ripe.wav")

    def is_tomato_ripe(self, tomato: ImageSprite):
        return tomato == self.get_ripe_tomato()

    def get_ripe_tomato(self):
        return self.tomato[-2]

    def get_tomato_sprite(self, factor: float, rotten: bool):
        if rotten:
            return self.tomato[-1]

        return self.tomato[max(0, min(2, int(factor * 2.3)))]

    def get_random_leaf(self):
        return random.choice(self.leaves)

    def get_random_rock(self):
        return random.choice(self.rocks)

    def get_planet(self):
        return self.planet

    def get_spaceship(self):
        return self.spaceship

    def get_fly(self):
        return self.fly_animation

    def get_cursor(self, mode: str):
        return self.cursors[mode]

    def get_random_pick_sound(self):
        return random.choice(self.pick)

    def get_random_mowing_sound(self):
        return random.choice(self.mowing)

    def get_random_slap_sound(self):
        return random.choice(self.slap)

    def get_ripe_sound(self):
        return self.ripe_sound
