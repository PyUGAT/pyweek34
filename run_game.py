from __future__ import annotations

import argparse
import array
import ctypes
import logging
import math
import os
import random
import textwrap
import time

import pygame
from OpenGL.GL import *
from pygame.locals import *
from pygame.math import Vector2
from pygame.mixer import Sound

HERE = os.path.dirname(__file__) or "."

LEFT_MOUSE_BUTTON = 1
MIDDLE_MOUSE_BUTTON = 2
RIGHT_MOUSE_BUTTON = 3

(
    CLICK_PRIORITY_FRUIT,
    CLICK_PRIORITY_PLANT,
    CLICK_PRIORITY_FLY,
    CLICK_PRIORITY_SECTOR,
    CLICK_PRIORITY_OTHER,
) = range(5)

LABEL_FRUIT = "fruit"
LABEL_MINIMAP = "minimap"
LABEL_PLANT = "plant"
LABEL_SECTOR = "sector"
LABEL_FLY = "fly"

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

logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.DEBUG if CLIARGS.debug else logging.WARNING,
)


class ImportantParameterAffectingGameplay:
    GAMEOVER_THRESHOLD_FLIES_WIN = (
        4 if CLIARGS.fast else 15
    )  # Flies win when they steal N tomatoes
    GAMEOVER_THRESHOLD_PLAYER_WINS = (
        4 if CLIARGS.fast else 30
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
        10,
        50,
    )  # Increase/decrease values for stronger/weaker plants (with more/less tomatoes)


def multiply_3x3(a, b):
    return array.array(
        "f",
        (
            a[0] * b[0] + a[1] * b[3] + a[2] * b[6],
            a[0] * b[1] + a[1] * b[4] + a[2] * b[7],
            a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
            a[3] * b[0] + a[4] * b[3] + a[5] * b[6],
            a[3] * b[1] + a[4] * b[4] + a[5] * b[7],
            a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
            a[6] * b[0] + a[7] * b[3] + a[8] * b[6],
            a[6] * b[1] + a[7] * b[4] + a[8] * b[7],
            a[6] * b[2] + a[7] * b[5] + a[8] * b[8],
        ),
    )


class Matrix3x3:
    def __init__(self, initial=None):
        self.m = array.array(
            "f",
            initial.m
            if initial is not None
            else (
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ),
        )

    def apply(self, v):
        m = self.m

        v = (v[0], v[1], 1.0)

        v = (
            m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
            m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
            m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
        )

        return (v[0] / v[2], v[1] / v[2])

    def translate(self, x, y):
        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    1.0,
                    0.0,
                    x,
                    0.0,
                    1.0,
                    y,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def scale(self, x, y):
        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    x,
                    0.0,
                    0.0,
                    0.0,
                    y,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def rotate(self, angle_radians):
        s = math.sin(angle_radians)
        c = math.cos(angle_radians)

        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    c,
                    -s,
                    0.0,
                    s,
                    c,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )

    def ortho(self, left, right, bottom, top):
        w = right - left
        tx = -(right + left) / w
        h = top - bottom
        ty = -(top + bottom) / h

        self.m = multiply_3x3(
            self.m,
            array.array(
                "f",
                (
                    2.0 / w,
                    0.0,
                    tx,
                    0.0,
                    2.0 / h,
                    ty,
                    0.0,
                    0.0,
                    1.0,
                ),
            ),
        )


def test_matrix3x3():
    def degrees_to_radians(deg):
        return deg / 180 * math.pi

    test_ops = [
        ("scale", 0.5, 2.0),
        ("translate", 30, 40),
        ("rotate", degrees_to_radians(-90)),
        ("ortho", 0, 1000, 1000, 0),
    ]

    for method, *args in test_ops:
        m = Matrix3x3()
        for v in ((100, 200), (0, 0)):
            getattr(m, method)(*args)
            logging.debug(f"{v} -> {method}{tuple(args)} -> {m.apply(v)}")


class ImageSprite:
    def __init__(self, img: pygame.surface.Surface, *, want_mipmap: bool):
        self.img = img
        self.width, self.height = self.img.get_size()
        self.want_mipmap = want_mipmap
        self._texture = None

    @classmethod
    def load(cls, filename: str):
        return cls(pygame.image.load(filename).convert_alpha(), want_mipmap=True)

    @property
    def size(self):
        return Vector2(self.width, self.height)

    def _get_texture(self):
        if self._texture is None:
            self._texture = Texture(self, generate_mipmaps=self.want_mipmap)

        return self._texture


class AnimatedImageSprite:
    def __init__(self, frames: list[ImageSprite], *, delay_ms: int):
        self.frames = frames
        self.delay_ms = delay_ms

    def get(self, ctx):
        pos = int((ctx.now * 1000) / self.delay_ms)
        return self.frames[pos % len(self.frames)]


class Texture:
    def __init__(self, sprite: ImageSprite, *, generate_mipmaps: bool):
        self.id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.id)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            sprite.width,
            sprite.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        view = sprite.img.get_buffer()
        for y in range(sprite.height):
            start = y * sprite.img.get_pitch()
            pixeldata = view.raw[
                start : start + sprite.width * sprite.img.get_bytesize()
            ]
            glTexSubImage2D(
                GL_TEXTURE_2D,
                0,
                0,
                y,
                sprite.width,
                1,
                GL_BGRA,
                GL_UNSIGNED_BYTE,
                pixeldata,
            )

        if generate_mipmaps:
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(
                GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR
            )
        else:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glBindTexture(GL_TEXTURE_2D, 0)

    def __del__(self):
        glDeleteTextures([self.id])


# class CustomCursor:
#     def show(self, type):
#         pass


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

        # TODO: Use animated cursors
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


def aabb_from_points(points: [Vector2]):
    """
    Compute axis-aligned bounding box from points.
    """
    x = min(point.x for point in points)
    y = min(point.y for point in points)
    w = max(point.x for point in points) - x
    h = max(point.y for point in points) - y
    return Rect(x, y, w, h)


class IDrawTask:
    def draw(self):
        raise NotImplementedError("Do not know how to draw this task")


class DrawSpriteTask(IDrawTask):
    def __init__(self, sprite: ImageSprite):
        self.sprite = sprite
        self.data = array.array("f")

    def append(self, position: Vector2, scale: Vector2, apply_modelview_matrix):
        if scale is None:
            scale = Vector2(1, 1)

        right = Vector2(self.sprite.width * scale.x, 0)
        bottom = Vector2(0, self.sprite.height * scale.y)

        tl = Vector2(position)
        tr = tl + right
        bl = tl + bottom
        br = bl + right

        corners_in_modelview_space = [tl, tr, bl, br]

        tl = apply_modelview_matrix(tl)
        tr = apply_modelview_matrix(tr)
        bl = apply_modelview_matrix(bl)
        br = apply_modelview_matrix(br)

        self.data.extend(
            (
                0.0,
                0.0,
                tl.x,
                tl.y,
                1.0,
                0.0,
                tr.x,
                tr.y,
                1.0,
                1.0,
                br.x,
                br.y,
                0.0,
                0.0,
                tl.x,
                tl.y,
                1.0,
                1.0,
                br.x,
                br.y,
                0.0,
                1.0,
                bl.x,
                bl.y,
            )
        )

        return corners_in_modelview_space

    def draw(self):
        texture = self.sprite._get_texture()
        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glColor4f(1, 1, 1, 1)

        buf = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buf)
        glBufferData(GL_ARRAY_BUFFER, self.data.tobytes(), GL_STATIC_DRAW)

        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(
            2, GL_FLOAT, 4 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0)
        )

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(
            2,
            GL_FLOAT,
            4 * ctypes.sizeof(ctypes.c_float),
            ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)),
        )

        glDrawArrays(GL_TRIANGLES, 0, int(len(self.data) / 4))

        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glDeleteBuffers(1, [buf])

        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)


class DrawColoredVerticesTask(IDrawTask):
    def __init__(self, mode):
        self.data = array.array("f")
        self.mode = mode

    def append(self, color: Color, vertices: [Vector2], apply_modelview_matrix):
        r, g, b, a = color.normalize()

        for v in vertices:
            vertex = apply_modelview_matrix(v)
            self.data.extend((vertex.x, vertex.y, r, g, b, a))

    def append_separate(
        self, colors: [Color], vertices: [Vector2], apply_modelview_matrix
    ):
        for color, vertex in zip(colors, vertices):
            vertex = apply_modelview_matrix(vertex)
            r, g, b, a = color.normalize()

            self.data.extend((vertex.x, vertex.y, r, g, b, a))

    def draw(self):
        buf = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buf)
        glBufferData(GL_ARRAY_BUFFER, self.data.tobytes(), GL_STATIC_DRAW)

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(
            2, GL_FLOAT, 6 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0)
        )

        glEnableClientState(GL_COLOR_ARRAY)
        glColorPointer(
            4,
            GL_FLOAT,
            6 * ctypes.sizeof(ctypes.c_float),
            ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)),
        )

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glDrawArrays(self.mode, 0, int(len(self.data) / 6))

        glDisable(GL_BLEND)

        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glDeleteBuffers(1, [buf])


class MatrixStack:
    def __init__(self):
        self.stack = [Matrix3x3()]

    def push(self):
        self.stack.append(Matrix3x3(self.stack[-1]))

    def pop(self):
        self.stack.pop()

    def identity(self):
        self.stack[-1] = Matrix3x3()

    def translate(self, x: float, y: float):
        self.stack[-1].translate(x, y)

    def rotate(self, angle_radians: float):
        self.stack[-1].rotate(angle_radians)

    def scale(self, x: float, y: float):
        self.stack[-1].scale(x, y)

    def ortho(self, left: float, right: float, bottom: float, top: float):
        self.stack[-1].ortho(left, right, bottom, top)

    def apply(self, v: Vector2):
        return Vector2(self.stack[-1].apply(v))


class FontCacheEntry:
    def __init__(self, text: str, sprite: ImageSprite):
        self.generation = -1
        self.text = text
        self.sprite = sprite


class FontCache:
    EXPIRE_GENERATIONS = 20

    def __init__(self, font):
        self.font = font
        self.generation = 0
        self.cache = {}

    def lookup(self, text: str, color: Color):
        key = (text, tuple(color))

        if key not in self.cache:
            sprite = ImageSprite(self.font.render(text, True, color), want_mipmap=False)
            self.cache[key] = FontCacheEntry(text, sprite)

        entry = self.cache[key]
        entry.generation = self.generation
        return entry.sprite

    def gc(self):
        self.generation += 1

        keys_to_erase = set()
        for key, value in self.cache.items():
            if self.generation - value.generation > self.EXPIRE_GENERATIONS:
                keys_to_erase.add(key)

        for key in keys_to_erase:
            del self.cache[key]


class RenderContext:
    LAYER_BRANCHES = 60
    LAYER_LEAVES = 70
    LAYER_FRUIT = 80
    LAYER_FLIES = 90

    LAYER_BTN_BG = 100
    LAYER_BTN_TEXT = 110

    def __init__(self, width, height, resources: ResourceManager):
        self.width = width
        self.height = height
        self.font_cache = FontCache(resources.font("RobotoMono-SemiBold.ttf", 16))
        self.font_cache_big = FontCache(resources.font("RobotoMono-SemiBold.ttf", 24))
        self.queue = {}
        self.started = time.time()
        self.paused_started = None
        self.now = 0
        self.clock = pygame.time.Clock()
        self.fps = 0
        self.projection_matrix_stack = MatrixStack()
        self.modelview_matrix_stack = MatrixStack()

    def __enter__(self):
        self.now = time.time() - self.started
        if self.paused_started:
            self.now -= time.time() - self.paused_started
        self.camera_mode_overlay()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pygame.display.flip()
        self.font_cache.gc()
        self.font_cache_big.gc()
        self.clock.tick()
        self.fps = self.clock.get_fps()
        return False

    def transform_to_screenspace(self, p):
        p = self.modelview_matrix_stack.apply(p)
        p = self.projection_matrix_stack.apply(p)

        p.x = self.width * (p.x + 1) / 2
        p.y = self.height * (1 - ((p.y + 1) / 2))

        return p

    def setup_matrices(self, left, right, bottom, top):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.projection_matrix_stack.identity()

        glOrtho(left, right, bottom, top, 0, 1)
        self.projection_matrix_stack.ortho(left, right, bottom, top)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.modelview_matrix_stack.identity()

    def camera_mode_overlay(self):
        self.setup_matrices(0, self.width, self.height, 0)

    def camera_mode_world(self, planet, zoom, rotate):
        left = -self.width / 2
        right = self.width / 2
        bottom = self.height / 2
        top = -self.height / 2

        self.setup_matrices(left, right, bottom, top)

        # Adjust minimum zoom factor (used for the minimap display, i.e. fully zoomed out)
        min_zoom = min(self.width, self.height) / (
            (planet.radius + planet.atmosphere_height) * 2.5
        )

        factor = min_zoom + (1.0 - min_zoom) * (1 - (1 - zoom))

        self.modelview_matrix_stack.translate(-planet.position.x, -planet.position.y)
        self.modelview_matrix_stack.translate(
            0, (zoom**0.8) * (planet.radius + self.height / 8)
        )
        self.modelview_matrix_stack.scale(factor, factor)
        self.modelview_matrix_stack.rotate(rotate * 2 * math.pi)

    def clear(self, color: Color):
        glClearColor(*color.normalize())
        glClear(GL_COLOR_BUFFER_BIT)

    def sprite(
        self,
        sprite: ImageSprite,
        position: Vector2,
        scale: Vector2 = None,
        z_layer: int = 0,
    ):
        key = (z_layer, sprite)
        if key not in self.queue:
            self.queue[key] = DrawSpriteTask(sprite)

        return self.queue[key].append(
            position, scale, self.modelview_matrix_stack.apply
        )

    def text(self, text: str, color: Color, position: Vector2, big=False):
        if text:
            self.sprite((self.font_cache if not big else self.font_cache_big).lookup(text, color), position)

    def text_centered(self, text: str, color: Color):
        if text:
            sprite = self.font_cache.lookup(text, color)
            self.sprite(
                sprite,
                (
                    Vector2(self.width, self.height)
                    - Vector2(sprite.width, sprite.height)
                )
                / 2,
            )

    def text_centered_rect(self, text: str, color: Color, rect: Rect, *, z_layer: int = 0):
        if text:
            sprite = self.font_cache_big.lookup(text, color)
            self.sprite(sprite, rect.topleft + (rect.size - sprite.size) / 2, z_layer=z_layer)

    def rect(self, color: Color, rectangle: Rect, *, z_layer: int = 0):
        self._colored_vertices(
            GL_TRIANGLES,
            color,
            [
                rectangle.topleft,
                rectangle.topright,
                rectangle.bottomright,
                rectangle.topleft,
                rectangle.bottomright,
                rectangle.bottomleft,
            ],
            z_layer=z_layer,
        )

    def aabb(self, color: Color, rectangle: Rect):
        self._colored_vertices(
            GL_LINES,
            color,
            [
                rectangle.topleft,
                rectangle.topright,
                rectangle.topright,
                rectangle.bottomright,
                rectangle.bottomright,
                rectangle.bottomleft,
                rectangle.bottomleft,
                rectangle.topleft,
            ],
        )

    def circle(self, color: Color, center: Vector2, radius: float):
        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius * 2 * math.pi) / 30))

        vertices = []
        for angle in range(0, 361, int(360 / steps)):
            vertices.append(center)
            vertices.append(center + Vector2(radius, 0).rotate(angle))

        # break triangle strip (duplicate first and last vertex -> degenerate triangle)
        vertices.append(vertices[-1])
        vertices.insert(0, vertices[0])

        self._colored_vertices(GL_TRIANGLE_STRIP, color, vertices)

    def donut(
        self,
        color_inner: Color,
        color_outer: Color,
        center: Vector2,
        radius_outer: float,
        radius_inner: float,
    ):
        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius_outer * 2 * math.pi) / 30))

        vertices = []
        colors = []
        for angle in range(0, 361, int(360 / steps)):
            colors.append(color_inner)
            vertices.append(center + Vector2(radius_inner, 0).rotate(angle))
            colors.append(color_outer)
            vertices.append(center + Vector2(radius_outer, 0).rotate(angle))

        # Close the triangle strip by connecting to the starting point)
        colors.append(colors[0])
        vertices.append(vertices[0])

        # break triangle strip (duplicate first and last vertex -> degenerate triangle)
        vertices.append(vertices[-1])
        vertices.insert(0, vertices[0])

        self._separately_colored_vertices(GL_TRIANGLE_STRIP, colors, vertices)

    def textured_circle(self, sprite: ImageSprite, center: Vector2, radius: float):
        texture = sprite._get_texture()

        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glBegin(GL_TRIANGLE_FAN)
        glColor4f(1, 1, 1, 1)
        glTexCoord2f(0.5, 0.5)
        glVertex2f(*self.modelview_matrix_stack.apply(center))

        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius * 2 * math.pi) / 30))

        for angle in range(0, 361, int(360 / steps)):
            direction = Vector2(radius, 0).rotate(angle)
            glTexCoord2f(
                0.5 + 0.5 * direction.x / radius, 0.5 + 0.5 * direction.y / radius
            )
            glVertex2f(*self.modelview_matrix_stack.apply(center + direction))
        glEnd()
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)

    def line(
        self,
        color: Color,
        from_point: Vector2,
        to_point: Vector2,
        width: float,
        *,
        z_layer: int = 0,
    ):
        width = max(1, width)

        side = (to_point - from_point).normalize().rotate(90) * (width / 2)
        a = from_point + side
        b = from_point - side
        c = to_point + side
        d = to_point - side

        self._colored_vertices(GL_TRIANGLES, color, [a, b, c, b, c, d], z_layer=z_layer)

    def _colored_vertices(
        self, mode: int, color: Color, vertices: [Vector2], *, z_layer: int = 0
    ):
        key = (z_layer, mode)
        if key not in self.queue:
            self.queue[key] = DrawColoredVerticesTask(mode)

        self.queue[key].append(color, vertices, self.modelview_matrix_stack.apply)

    def _separately_colored_vertices(
        self, mode: int, colors: [Color], vertices: [Vector2], *, z_layer: int = 0
    ):
        key = (z_layer, mode)
        if key not in self.queue:
            self.queue[key] = DrawColoredVerticesTask(mode)

        self.queue[key].append_separate(
            colors, vertices, self.modelview_matrix_stack.apply
        )

    def flush(self):
        for (z_layer, *key_args), task in sorted(
            self.queue.items(), key=lambda kv: kv[0][0]
        ):
            task.draw()

        self.queue = {}


class IClickReceiver:
    def clicked(self):
        # Return true to prevent propagation of event
        return False


class IMouseReceiver:
    def mousedown(self, position: Vector2):
        ...

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        ...

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...


class IUpdateReceiver:
    def update(self):
        raise NotImplementedError("Update not implemented")


class IDrawable:
    def draw(self, ctx: RenderContext):
        raise NotImplementedError("Draw not implemented")


class Branch(IClickReceiver):
    CURSOR = "harvest"

    def __init__(self, phase, length, leftright, depth, plant):
        self.plant = plant
        self.phase = phase
        self.depth = depth
        self.angle = (
            leftright * random.uniform(50, 70) * (0 if (depth == 0) else depth / 2.0)
        )
        self.length = length
        if depth == 0:
            self.length += 40
        self.thickness = max(
            8, int((self.plant.fertility / 5) / (1 if not depth else depth))
        )
        self.children = []
        self.color_mod = random.uniform(0.4, 1.0)
        self.color_mod2 = random.uniform(0.4, 1.0)
        self.has_fruit = random.uniform(0, 300) < (self.plant.fertility + 10)
        self.has_leaf = not self.has_fruit
        self.fruit_rotten = False
        self.leaf = plant.artwork.get_random_leaf()
        self.random_leaf_appearance_value = random.uniform(20, 70)
        self.random_fruit_appearance_value = random.uniform(40, 70)
        self.fruit_world_position = Vector2(0, 0)
        self.was_ripe = False

    def get_world_position(self):
        return self.fruit_world_position

    def clicked(self):
        # TODO: Add score (check fruit_rotten first!)
        if self.has_fruit:
            self.has_fruit = False
            self.plant.shake()
            self.plant.artwork.get_random_pick_sound().play()  # Claus-TBD: artwork from plant
            return True

        return False

    def grow(self):
        phase = random.uniform(0.1, 0.9)
        if self.depth == 0:
            phase = max(phase, 1.0 - max(0.4, min(0.6, self.plant.fertility)))
        flength = random.uniform(0.2, 0.3) * 2
        self.children.append(
            Branch(
                phase,
                self.length * flength,
                1 - 2 * (len(self.children) % 2),
                self.depth + 1,
                plant=self.plant,
            )
        )

    def moregrow(self, recurse=True):
        if not self.children:
            if random.choice([False, False, False, True]):
                self.grow()
            return

        candidates = list(self.children) * int(max(1, self.plant.fertility / 20))

        for i in range(int(self.plant.fertility / 5)):
            if not candidates:
                break

            candidate = random.choice(candidates)
            candidates.remove(candidate)

            if (
                random.choice(
                    [True, False] if self.plant.fertility > 30 else [False, False, True]
                )
                or not recurse
            ):
                candidate.grow()
            else:
                candidate.moregrow(recurse=False)

    def update(self):
        if self.plant.health < 25:
            self.fruit_rotten = True

        for child in self.children:
            child.update()

    def draw(self, ctx, pos, factor, angle, health):
        if factor < 0.01:
            return

        angle *= factor
        angle += self.angle * self.plant.growth / 100
        angle *= 1.0 + 0.01 * (100 - health)

        # normalize angle to 0..1, store sign
        angle /= 180
        if angle < 0:
            f = -1
            angle = -angle
        else:
            f = 1

        # move angle towards 1.0 for bad health
        angle = angle ** (max(10, min(100, health)) / 100)
        # avoid over-rotating (limit to -180..+180 range)
        angle = min(+1, angle)

        # restore angle direction and amplitude
        angle *= 180 * f

        # angle added due to wind
        wind_angle = (
            10
            * math.sin(self.plant.wind_phase + self.plant.wind_speed * ctx.now)
            / max(1, 5 - self.depth)
        )
        wind_angle += (self.plant.wind_amplitude / 10) * math.sin(ctx.now * 5)

        direction = Vector2(0, -self.length).rotate(angle + wind_angle)

        to_point = pos + direction * factor
        cm1 = 1.0 - ((1.0 - self.color_mod) * health / 100)
        cm2 = 1.0 - ((1.0 - self.color_mod2) * health / 100)
        color = Color((cm1 * (100 - health), cm2 * (244 - 150 + health * 1.5), 0))

        if self.plant.need_aabb:
            self.plant.aabb_points.extend(
                (
                    ctx.transform_to_screenspace(pos),
                    ctx.transform_to_screenspace(to_point),
                )
            )

        zoom_adj = self.plant.sector.game.get_zoom_adjustment()

        ctx.line(
            color,
            pos,
            to_point,
            self.thickness * self.plant.growth / 100 + 15 * zoom_adj,
            z_layer=ctx.LAYER_BRANCHES,
        )

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(
                ctx, pos + direction * child.phase * factor, child_factor, angle, health
            )

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                ff = factor + zoom_adj
                tomato = self.plant.artwork.get_tomato_sprite(factor, self.fruit_rotten)
                topleft = to_point + Vector2(-(tomato.width * ff) / 2, 0)
                ctx.sprite(
                    tomato, topleft, scale=Vector2(ff, ff), z_layer=ctx.LAYER_FRUIT
                )

                # You can only click on ripe tomatoes
                if self.plant.artwork.is_tomato_ripe(tomato):
                    if not self.was_ripe:
                        self.plant.artwork.get_ripe_sound().play()
                        self.was_ripe = True

                    aabb = aabb_from_points(
                        [
                            ctx.transform_to_screenspace(topleft),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(0, ff * tomato.height)
                            ),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(ff * tomato.width, 0)
                            ),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(ff * tomato.width, ff * tomato.height)
                            ),
                        ]
                    )

                    # insert front, so that the layer ordering/event handling works correctly
                    game = self.plant.sector.game
                    game.debug_aabb.insert(
                        0,
                        (
                            LABEL_FRUIT,
                            Color(255, 255, 255),
                            aabb,
                            self,
                            CLICK_PRIORITY_FRUIT,
                        ),
                    )

                    ctx.modelview_matrix_stack.push()
                    ctx.modelview_matrix_stack.identity()
                    game.planet.apply_planet_surface_transform(self.plant.position)
                    self.fruit_world_position = ctx.modelview_matrix_stack.apply(
                        topleft + tomato.size / 2
                    )
                    ctx.modelview_matrix_stack.pop()

                    self.plant.sector.ripe_fruits.append(self)
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (
                    100 - self.random_leaf_appearance_value
                )
                ctx.sprite(
                    self.leaf,
                    to_point + Vector2(-(self.leaf.width * ff) / 2, 0),
                    scale=Vector2(ff, ff),
                    z_layer=ctx.LAYER_LEAVES,
                )


class PlanetSurfaceCoordinates:
    def __init__(self, angle_degrees: float, elevation: float = 0):
        self.angle_degrees = angle_degrees
        self.elevation = elevation

    def lerp(self, *, target, alpha: float):
        return PlanetSurfaceCoordinates(
            (1 - alpha) * self.angle_degrees + alpha * target.angle_degrees,
            (1 - alpha) * self.elevation + alpha * target.elevation,
        )


class Planet(IDrawable):
    def __init__(self, artwork: Artwork, renderer):
        self.renderer = renderer
        self.position = Vector2(0, 0)
        self.radius = 500
        self.atmosphere_height = max(100, self.radius * 0.4)
        self.sprite = artwork.get_planet()

    def get_circumfence(self):
        return self.radius * 2 * math.pi

    def draw(self, ctx):
        ctx.textured_circle(self.sprite, self.position, self.radius)

    def at(self, position: PlanetSurfaceCoordinates):
        return self.position + Vector2(0, -(self.radius + position.elevation)).rotate(
            position.angle_degrees
        )

    def apply_planet_surface_transform(self, position: PlanetSurfaceCoordinates):
        self.renderer.modelview_matrix_stack.translate(*self.at(position))
        self.renderer.modelview_matrix_stack.rotate(
            position.angle_degrees * math.pi / 180
        )


class FruitFly(IUpdateReceiver, IDrawable, IClickReceiver):
    AABB_PADDING_PX = 40
    CURSOR = "hunt"
    FLYING_SPEED_CARRYING = 1.5
    FLYING_SPEED_NON_CARRYING = 3

    def __init__(self, game, spaceship, artwork, phase):
        self.game = game
        self.spaceship = spaceship
        self.artwork = artwork
        self.phase = phase
        self.sprite_animation = artwork.get_fly()
        self.roaming_target = self.spaceship
        self.roaming_offset = Vector2(0, 0)
        self.x_direction = 1
        self.returning_to_spaceship = False
        self.carrying_fruit = False
        self.aabb = None

        self.trash_rotation_direction = random.choice([-1, +1])
        self.trash_time = 0

    def get_world_position(self):
        return self.roaming_target.get_world_position() + self.roaming_offset

    def reparent_to(self, new_target):
        here = self.get_world_position()
        self.roaming_offset = here - new_target.get_world_position()
        self.roaming_target = new_target

    def fly_towards_target(self, step):
        if self.roaming_offset.length() > 0:
            new_length = max(0, self.roaming_offset.length() - step)
            new_roaming_offset = self.roaming_offset.normalize() * new_length
            return new_roaming_offset, False
        else:
            return self.roaming_offset, True

    def clicked(self):
        # TODO: Add score, prevent player from clicking if fly is located too far out in space
        # Also, to simplify matters, make fruitfly with tomato invincible ;)
        is_fly_close_enough_to_surface = True
        if is_fly_close_enough_to_surface and self in self.spaceship.flies:
            logging.debug("Brzzzz... you hit a fly")
            self.artwork.get_random_slap_sound().play()
            self.spaceship.flies.remove(self)
            self.spaceship.dead_flies.append(self)
            return True
        return False

    def update(self):
        now = self.game.renderer.now
        angle = now * 1.1 + self.phase * 2 * math.pi

        if self.returning_to_spaceship:
            self.reparent_to(self.spaceship)
            new_roaming_offset, did_arrive = self.fly_towards_target(
                self.FLYING_SPEED_CARRYING
                if self.carrying_fruit
                else self.FLYING_SPEED_NON_CARRYING
            )
            if did_arrive:
                # ka'ching!
                self.returning_to_spaceship = False
                if self.carrying_fruit:
                    self.carrying_fruit = False
                    self.spaceship.add_tomato()
        else:
            if self.roaming_target != self.spaceship:
                fruit = self.roaming_target
            else:
                fruit = self.spaceship.get_available_fruit()

            if self.spaceship.near_target_sector and fruit is not None:
                if not fruit.has_fruit or fruit.plant.was_deleted:
                    # Return to space ship, as there's nothing to grab here
                    self.returning_to_spaceship = True

                self.reparent_to(fruit)
                new_roaming_offset, did_arrive = self.fly_towards_target(
                    self.FLYING_SPEED_NON_CARRYING
                )
                if did_arrive:
                    self.carrying_fruit = (
                        fruit.has_fruit and not fruit.plant.was_deleted
                    )
                    fruit.plant.shake()
                    fruit.has_fruit = False
                    self.returning_to_spaceship = True
            else:
                self.roaming_target = self.spaceship
                new_roaming_offset = Vector2(
                    self.spaceship.sprite.width / 2 * math.sin(angle),
                    self.spaceship.sprite.height / 2 * math.cos(angle),
                )

        self.x_direction = -1 if new_roaming_offset.x < self.roaming_offset.x else +1
        self.roaming_offset = new_roaming_offset

    def draw_fly_at(self, ctx, pos, direction, scale_up):
        self.aabb = None

        fly_sprite = self.sprite_animation.get(ctx)
        fly_offset = -fly_sprite.size / 2
        fly_offset.x *= direction

        ctx.modelview_matrix_stack.push()

        position = pos + fly_offset * scale_up
        rotation = self.spaceship.coordinates.angle_degrees / 180 * math.pi

        if self.trash_time > 0:
            # Fly escapes into space
            ctx.modelview_matrix_stack.translate(
                *(self.get_world_position().normalize() * (10 * self.trash_time))
            )
            rotation += self.trash_time * 0.1 * self.trash_rotation_direction

        ctx.modelview_matrix_stack.translate(*self.get_world_position())
        ctx.modelview_matrix_stack.rotate(rotation)
        ctx.modelview_matrix_stack.translate(*-self.get_world_position())

        corners = ctx.sprite(
            fly_sprite,
            position,
            scale=Vector2(direction, 1) * scale_up,
            z_layer=ctx.LAYER_FLIES,
        )

        if self.carrying_fruit:
            fly_offset += Vector2(0, fly_sprite.height / 2)
            corners.extend(
                ctx.sprite(
                    self.artwork.get_ripe_tomato(),
                    position,
                    scale=Vector2(direction, 1) * scale_up,
                    z_layer=ctx.LAYER_FRUIT,
                )
            )

        planet = self.game.planet

        if not self.game.drawing_minimap and self.get_world_position().length() < (
            planet.radius + planet.atmosphere_height
        ):
            self.aabb = aabb_from_points(
                [ctx.transform_to_screenspace(p) for p in corners]
            )
            self.aabb = self.aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )

        if self.aabb is not None:
            self.game.debug_aabb.insert(
                0, (LABEL_FLY, Color(255, 0, 0), self.aabb, self, CLICK_PRIORITY_FLY)
            )

        ctx.modelview_matrix_stack.pop()

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        self.draw_fly_at(ctx, self.get_world_position(), self.x_direction, scale_up)


class Spaceship(IUpdateReceiver, IDrawable):
    ELEVATION_BEGIN = 2000
    # ELEVATION_BEGIN = 600
    ELEVATION_DOWN = 300

    def __init__(self, game, planet, artwork):
        self.game = game
        self.planet = planet
        self.artwork = artwork
        self.sprite = artwork.get_spaceship()
        self.target_sector = self.pick_target_sector()
        self.near_target_sector = False
        self.coordinates = PlanetSurfaceCoordinates(
            self.target_sector.get_center_angle(), elevation=self.ELEVATION_BEGIN
        )
        self.target_coordinates = PlanetSurfaceCoordinates(
            self.target_sector.get_center_angle(), elevation=self.ELEVATION_DOWN
        )
        self.ticks = 0
        self.flies = []
        self.dead_flies = []

        self.total_collected_tomatoes = 0
        self.tomato_to_fly_counter = 0

        self.breed_flies_if_needed()

    def add_tomato(self):
        self.total_collected_tomatoes += 1
        self.tomato_to_fly_counter += 1
        if (
            self.tomato_to_fly_counter
            == ImportantParameterAffectingGameplay.TOMATO_TO_FLY
            and len(self.flies) < ImportantParameterAffectingGameplay.MAX_NUM_FLIES
        ):
            self.add_fly()
            self.tomato_to_fly_counter = 0

    def add_fly(self):
        self.flies.append(
            FruitFly(self.game, self, self.artwork, random.uniform(0, 2 * math.pi))
        )

    def breed_flies_if_needed(self):
        flies_to_add = ImportantParameterAffectingGameplay.MIN_NUM_FLIES - len(
            self.flies
        )
        for _ in range(
            flies_to_add
        ):  # we implicitly use that range of a negative value is an empty sequence
            self.add_fly()

    def get_available_fruit(self):
        for fruit in self.target_sector.ripe_fruits:
            if not any(fly.roaming_target == fruit for fly in self.flies):
                return fruit

        return None

    def current_sector_cleared(self):
        return self.near_target_sector and all(
            fly.roaming_target == self and not fly.returning_to_spaceship
            for fly in self.flies
        )

    def pick_target_sector(self):
        if CLIARGS.debug:
            return self.game.sectors[0]
        sectors_with_ripe_fruits = [sector for sector in self.game.sectors if len(sector.ripe_fruits) > 0]
        sectors_to_choose = sectors_with_ripe_fruits or self.game.sectors
        return random.choice(sectors_to_choose)

    def get_world_position(self):
        return self.planet.at(self.coordinates)

    def update(self):
        self.ticks += 1

        if self.is_time_to_breed_flies():
            self.breed_flies_if_needed()

        if self.is_time_to_move_to_other_sector() and self.current_sector_cleared():
            self.target_sector = self.pick_target_sector()

        now = self.game.renderer.now
        self.target_coordinates.angle_degrees = (
            self.target_sector.get_center_angle() + 10 * math.sin(now / 10)
        )
        self.target_coordinates.elevation = self.ELEVATION_DOWN + 30 * math.cos(now)
        self.coordinates = self.coordinates.lerp(
            target=self.target_coordinates, alpha=0.01
        )

        self.near_target_sector = (
            self.coordinates.elevation < self.ELEVATION_DOWN + 50
        ) and (
            abs(self.coordinates.angle_degrees - self.target_sector.get_center_angle())
            < 15
        )

        for fly in self.flies:
            fly.update()

        for dead_fly in self.dead_flies:
            dead_fly.trash_time += 1

        self.dead_flies = [
            dead_fly for dead_fly in self.dead_flies if dead_fly.trash_time < 3 * 60
        ]

    def is_time_to_breed_flies(self):
        return (
            self.ticks % ImportantParameterAffectingGameplay.BREEDING_EVERY_N_TICKS == 0
        )

    def is_time_to_move_to_other_sector(self):
        return (
            self.ticks
            % ImportantParameterAffectingGameplay.MOVING_TO_OTHER_SECTOR_EVERY_N_TICKS
            == 0
        )

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        ctx.modelview_matrix_stack.push()
        self.planet.apply_planet_surface_transform(self.coordinates)
        ctx.sprite(
            self.sprite,
            -self.sprite.size / 2 * scale_up,
            Vector2(scale_up, scale_up),
        )

        ctx.modelview_matrix_stack.pop()

        for fly in self.flies:
            fly.draw(ctx)

        for dead_fly in self.dead_flies:
            dead_fly.draw(ctx)


class Sector(IUpdateReceiver, IDrawable, IClickReceiver):
    def __init__(self, game, index, base_angle):
        self.game = game
        self.index = index
        self.base_angle = base_angle
        self.number_of_plants = random.choice([2, 3, 5, 6])
        self.sector_width_degrees = {2: 5, 3: 6, 5: 14, 6: 14}[
            self.number_of_plants
        ] * 3
        self.fertility = int(
            random.uniform(*ImportantParameterAffectingGameplay.FERTILITY)
        )
        self.growth_speed = (
            random.uniform(0.02, 0.06)
            * ImportantParameterAffectingGameplay.GROWTH_SPEED
        )
        self.rotting_speed = random.uniform(0.01, 0.02)
        self.plants = []
        self.make_new_plants()
        self.aabb = None  # axis-aligned bounding box
        self.ripe_fruits = []
        self.plant_trash_heap = []

    def get_center_angle(self):
        return self.base_angle + self.sector_width_degrees / 2

    def clicked(self):
        logging.debug(f"ouch, i'm a sector! {self.index}")
        return False

    def make_new_plants(self):
        for plant in self.plants:
            plant.was_deleted = True
            self.plant_trash_heap.append(plant)

        self.plants = []
        for j in range(self.number_of_plants):
            coordinate = PlanetSurfaceCoordinates(
                self.base_angle
                + self.sector_width_degrees * (j / (self.number_of_plants - 1))
            )
            self.plants.append(
                Plant(
                    self,
                    self.game.planet,
                    coordinate,
                    self.fertility,
                    self.game.artwork,
                )
            )

    def replant(self, plant):
        plant.was_deleted = True
        plant.artwork.get_random_mowing_sound().play()
        self.plant_trash_heap.append(plant)
        index = self.plants.index(plant)
        self.plants[index] = Plant(
            self, self.game.planet, plant.position, self.fertility, self.game.artwork
        )

    def invalidate_aabb(self):
        self.aabb = None
        for plant in self.plants:
            plant.need_aabb = True

    def update(self):
        for plant in self.plants:
            plant.update()

        for plant in self.plant_trash_heap:
            plant.trash_time += 1

        self.plant_trash_heap = [
            plant for plant in self.plant_trash_heap if plant.trash_time < 3 * 60
        ]

    def draw(self, ctx):
        self.aabb = None
        self.ripe_fruits = []

        for plant in self.plant_trash_heap:
            plant.draw(ctx)

        for plant in self.plants:
            plant.draw(ctx)
            if plant.root_aabb is not None:
                self.game.debug_aabb.append(
                    (
                        f"{LABEL_PLANT} ({plant.health:.0f}%)",
                        Color(0, 128, 128),
                        plant.root_aabb,
                        plant,
                        CLICK_PRIORITY_PLANT,
                    )
                )
                if self.aabb is None:
                    self.aabb = Rect(plant.aabb)
                else:
                    self.aabb = self.aabb.union(plant.aabb)

        if self.aabb is not None:
            self.game.debug_aabb.append(
                (
                    f"{LABEL_SECTOR} {self.index}",
                    Color(128, 255, 128),
                    self.aabb,
                    self,
                    CLICK_PRIORITY_SECTOR,
                )
            )


class Plant(IUpdateReceiver, IClickReceiver):
    AABB_PADDING_PX = 40
    CURSOR = "cut"

    def __init__(
        self,
        sector: Sector,
        planet: Planet,
        position: PlanetSurfaceCoordinates,
        fertility,
        artwork: Artwork,
    ):
        super().__init__()

        self.sector = sector
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.need_aabb = True
        self.aabb_points = []
        self.aabb = None
        self.root_aabb = None

        self.growth = 0
        self.health = 100
        self.fertility = fertility

        self.wind_phase = random.uniform(0, 2 * math.pi)
        self.wind_speed = random.uniform(0.9, 1.3)
        self.wind_amplitude = 0

        length = random.uniform(100, 500) * (0.5 + 0.5 * self.fertility / 100) / 2

        self.root = Branch(phase=0, length=length, leftright=+1, depth=0, plant=self)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

        self.was_deleted = False

        self.trash_rotation_direction = random.choice([-1, +1])
        self.trash_time = 0

    def clicked(self):
        logging.debug("in class Plant.clicked")
        self.sector.replant(self)
        return True

    def shake(self):
        # shake the plant
        if self.wind_amplitude <= 0:
            self.wind_amplitude = 90
        else:
            # if we have already been shaking,
            # shake in the other direction
            self.wind_amplitude = -90

    def update(self):
        if self.growth < 100:
            self.growth += self.sector.growth_speed
            self.growth = min(100, self.growth)
            self.need_aabb = True
        else:
            self.health -= self.sector.rotting_speed
            self.health = max(0, self.health)
            self.need_aabb = True

        if self.wind_amplitude > 0:
            self.wind_amplitude -= 1
        elif self.wind_amplitude < 0:
            self.wind_amplitude += 1

        self.root.update()

    def draw(self, ctx):
        factor = self.growth / 100

        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        if self.trash_time > 0:
            # Plant escapes into space
            approx_height = self.root.length * self.growth / 100
            ctx.modelview_matrix_stack.translate(0, -self.trash_time * 10)
            ctx.modelview_matrix_stack.translate(0, -approx_height / 2)
            ctx.modelview_matrix_stack.rotate(
                self.trash_time * 0.1 * self.trash_rotation_direction
            )
            ctx.modelview_matrix_stack.translate(0, +approx_height / 2)

        self.root.draw(ctx, Vector2(0, 0), factor, 0.0, self.health)

        if self.need_aabb and self.aabb_points:
            self.aabb = aabb_from_points(self.aabb_points)
            self.aabb = self.aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )
            self.root_aabb = aabb_from_points(self.aabb_points[:1])
            self.root_aabb = self.root_aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )
            self.aabb_points = []
            self.need_aabb = False

        ctx.modelview_matrix_stack.pop()


class Rock(IDrawable):
    def __init__(
        self, planet: Planet, position: PlanetSurfaceCoordinates, artwork: Artwork
    ):
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.rock = artwork.get_random_rock()

    def draw(self, ctx):
        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        ctx.sprite(self.rock, Vector2(-self.rock.width / 2, -self.rock.height + 10))

        ctx.modelview_matrix_stack.pop()


class Widget(IMouseReceiver, IDrawable):
    def __init__(self, w, h):
        self.rect = Rect(0, 0, w, h)

    def layout(self):
        ...

    def pick(self, pos):
        if self.rect.collidepoint(pos):
            return self

        return None

    def draw(self, ctx):
        ctx.rect(Color(70, 70, 70), self.rect)


class Container(Widget):
    def __init__(self):
        super().__init__(10, 10)
        self.children = []

    def add(self, widget):
        self.children.append(widget)

    def pick(self, pos):
        for child in self.children:
            candidate = child.pick(pos)
            if candidate is not None:
                return candidate

        return super().pick(pos)

    def draw(self, ctx):
        for child in self.children:
            child.layout()
            child.draw(ctx)


class DebugGUI(Container):
    def __init__(self, default_handler: IMouseReceiver, widgets=None):
        super().__init__()
        self.default_handler = default_handler
        if widgets is not None:
            for widget in widgets:
                self.add(widget)
        self.focused = None
        self.wheel_sum = Vector2(0, 0)

    def mousedown(self, pos):
        self.focused = self.pick(pos) or self.default_handler
        self.focused.mousedown(pos)

    def mousemove(self, pos):
        if self.focused:
            self.focused.mousemove(pos)

    def mouseup(self, pos):
        if self.focused:
            self.focused.mouseup(pos)
            self.focused = None

    def mousewheel(self, x: float, y: float, flipped: bool):
        self.wheel_sum.x += x
        self.wheel_sum.y += y


class Window:
    EVENT_TYPE_UPDATE = pygame.USEREVENT + 42

    def __init__(
        self,
        title: str,
        width: int = 1280,
        height: int = 720,
        updates_per_second: int = 60,
    ):
        self.title = title
        self.width = width
        self.height = height
        pygame.display.init()

        if not CLIARGS.no_multisample:
            pygame.display.gl_set_attribute(GL_MULTISAMPLEBUFFERS, 1)
            pygame.display.gl_set_attribute(GL_MULTISAMPLESAMPLES, 4)

        self.screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption(title)
        pygame.font.init()
        pygame.time.set_timer(self.EVENT_TYPE_UPDATE, int(1000 / updates_per_second))

    def set_subtitle(self, subtitle):
        pygame.display.set_caption(f"{self.title}: {subtitle}")

    def start_game_or_toggle_pause(self):
        self.game_has_started = True
        self.is_running = not self.is_running
        if self.is_running:
            if self.renderer.paused_started is not None:
                self.renderer.started += (
                    time.time() - self.renderer.paused_started
                )
            self.renderer.paused_started = None
            self.buttons[0] = ('Play Game', 'play')
        else:
            self.renderer.paused_started = time.time()
            self.buttons[0] = ('Resume Game', 'play')

    def process_events(
        self, *, mouse: IMouseReceiver, update: IUpdateReceiver, gamestate: Game
    ):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit()

            if self._is_spacebar_down(event):
                gamestate.start_game_or_toggle_pause()

            if event.type == pygame.KEYDOWN and self.want_tutorial and event.key == K_s:
                self.tutorial_pos = len(self.tutorial)
                self.want_tutorial = False
                self.start_game_or_toggle_pause()

            if not gamestate.is_running:
                # main menu
                if event.type == MOUSEBUTTONDOWN and event.button == LEFT_MOUSE_BUTTON:
                    gamestate.mousedown(event.pos)
                elif event.type == MOUSEMOTION and event.buttons:
                    gamestate.mousemove(event.pos)
                elif event.type == MOUSEBUTTONUP and event.button == LEFT_MOUSE_BUTTON:
                    gamestate.mouseup(event.pos)
                elif event.type == MOUSEWHEEL:
                    gamestate.mousewheel(event.x, event.y, event.flipped)
            elif gamestate.is_running:
                if event.type == MOUSEBUTTONDOWN and event.button == LEFT_MOUSE_BUTTON:
                    mouse.mousedown(event.pos)
                elif event.type == MOUSEMOTION and event.buttons:
                    mouse.mousemove(event.pos)
                elif event.type == MOUSEBUTTONUP and event.button == LEFT_MOUSE_BUTTON:
                    mouse.mouseup(event.pos)
                elif event.type == MOUSEWHEEL:
                    mouse.mousewheel(event.x, event.y, event.flipped)
                elif event.type == self.EVENT_TYPE_UPDATE:
                    update.update()

    def _is_spacebar_down(self, event):
        return event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE

    def quit(self):
        pygame.quit()
        quit()


class Minimap(IClickReceiver):
    def __init__(self, game):
        self.game = game

        fraction = 1 / 8
        border = 20

        size = Vector2(self.game.width, self.game.height) * fraction

        self.rect = Rect(self.game.width - border - size.x, border, size.x, size.y)

    def clicked(self):
        # TODO: Could do something with the minimap
        return False

class HarvestedTomato(IUpdateReceiver, IDrawable):
    def __init__(self, game, screenspace_position, target_position, duration):
        self.game = game
        self.sprite = game.artwork.get_ripe_tomato()
        self.position = screenspace_position
        self.start_position = Vector2(screenspace_position)
        self.target_position = Vector2(target_position)
        self.duration = duration
        self.started = game.renderer.now
        self.done = False

    def update(self):
        alpha = max(0, min(1, (self.game.renderer.now - self.started) / self.duration))
        if alpha == 1 and not self.done:
            self.done = True
            self.game.tomato_score += 1
        alpha = 1 - (1 - alpha) ** 2
        self.position = (1 - alpha) * self.start_position + alpha * self.target_position

    def draw(self, ctx):
        ctx.sprite(self.sprite, self.position - self.sprite.size / 2)


class Game(Window, IUpdateReceiver, IMouseReceiver):
    def __init__(self, data_path: str = os.path.join(HERE, "data")):
        super().__init__("Red Planted -- PyWeek#34 -- https://pyweek.org/e/RedPlanted/")
        pygame.mixer.init()  # Claus-TBD: here? In tutorials, we often see pygame.init(), which part corresponds to that?

        self.resources = ResourceManager(data_path)
        self.artwork = Artwork(self.resources)
        self.renderer = RenderContext(self.width, self.height, self.resources)

        self.planet = Planet(self.artwork, self.renderer)

        self.sectors = []
        self.rocks = []

        self.rotation_angle_degrees = 0

        self.gui = DebugGUI(self)

        self.minimap = Minimap(self)

        self.num_sectors = 5
        for i in range(self.num_sectors):
            sector = Sector(self, i, i * 340 / self.num_sectors)
            self.sectors.append(sector)

            coordinate = PlanetSurfaceCoordinates(
                sector.get_center_angle() + 0.5 * 360 / self.num_sectors
            )
            self.rocks.append(Rock(self.planet, coordinate, self.artwork))

        self.spaceship = Spaceship(self, self.planet, self.artwork)

        self.debug_aabb = []
        self.draw_debug_aabb = CLIARGS.debug
        self.cull_via_aabb = False

        self.drawing_minimap = False

        self.tomato_score = 0

        stars_range = self.planet.radius * 2
        self.stars = [
            Vector2(
                random.uniform(-stars_range, +stars_range),
                random.uniform(-stars_range, +stars_range),
            )
            for i in range(100)
        ]

        self.is_running = False
        self.cursor_mode = None
        self.cursor_planet_coordinate = None

        self.harvest_on_mouseup = False
        self.harvested_tomatoes = []

        self.tutorial = [
                (self.resources.sprite('tutorial-incoming.png'), textwrap.dedent("""
                Cmdr. Gardener, our sensors detect
                another hostile flyship incoming.
                """).splitlines()),
                (self.resources.sprite('tutorial-squash.png'), textwrap.dedent(f"""
                Fend them off and bring in our
                harvest before it is too late!
                """).splitlines()),
                (self.resources.sprite('tutorial-steal.png'), textwrap.dedent(f"""
                If the flies steal {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN} space
                tomatoes, we are doomed...
                """).splitlines()),
                (self.resources.sprite('tutorial-harvest.png'), textwrap.dedent(f"""
                Bring in {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS} space tomatoes and we will
                ketchdown the flies in this quadrant!
                """).splitlines()),
                (self.resources.sprite('tutorial-cut.png'), textwrap.dedent("""
                Plants grow tomatoes only once.
                Cut them to let another plant grow.
                """).splitlines()),
        ]
        self.tutorial_pos = 0
        self.tutorial_pageflip_time = 0

        self.buttons = [
                ('Play Game', 'play'),
                ('Instructions', 'help'),
                ('Credits', 'credits'),
                ('Quit', 'quit'),
        ]
        self.active_button = None
        self.active_button_time = 0
        self.want_instructions = False
        self.want_credits = False
        self.want_tutorial = False
        self.game_has_started = False

    @property
    def is_startup(self):
        return not self.game_has_started

    @property
    def is_gameover_flies_win(self):
        return (
            self.spaceship.total_collected_tomatoes
            >= ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN
        )

    @property
    def is_gameover_player_wins(self):
        return (
            self.tomato_score
            >= ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS
        )

    def get_zoom_adjustment(self):
        if self.drawing_minimap:
            return 2

        return 0

    def tick(self):
        super().process_events(mouse=self.gui, update=self, gamestate=self)
        if self.is_startup:
            self.render_scene(startup=True)
        elif self.is_gameover_flies_win:
            self.render_gameover_flies_win()
        elif self.is_gameover_player_wins:
            self.render_gameover_player_wins()
        elif self.is_running:
            dy = (self.gui.wheel_sum.y - self.gui.wheel_sum.x)
            if dy != 0:
                self.invalidate_aabb()
            self.rotation_angle_degrees += dy * (30000 / self.planet.get_circumfence())
            self.rotation_angle_degrees %= 360
            self.gui.wheel_sum.x = 0
            self.gui.wheel_sum.y = 0

            self.set_subtitle(f"{self.renderer.fps:.0f} FPS")
            self.render_scene(paused=False)
        else:
            self.render_scene(paused=True)

    def invalidate_aabb(self):
        for sector in self.sectors:
            sector.invalidate_aabb()

    def mousedown(self, position: Vector2):
        if self.want_instructions:
            self.want_instructions = False

        if self.want_credits:
            self.want_credits = False

        if self.want_tutorial:
            self.tutorial_pos += 1
            self.tutorial_pageflip_time = time.time()
            if self.tutorial_pos == len(self.tutorial):
                self.start_game_or_toggle_pause()
                self.want_tutorial = False

        if (self.is_startup or not self.is_running) and self.active_button is not None:
            label, action = self.active_button
            if action == 'play':
                if self.tutorial_pos == len(self.tutorial):
                    self.start_game_or_toggle_pause()
                else:
                    self.want_tutorial = True
                    self.tutorial_pageflip_time = time.time()
            elif action == 'help':
                self.want_instructions = True
            elif action == 'credits':
                self.want_credits = True
            elif action == 'quit':
                self.quit()

        for label, color, rect, obj, priority in sorted(
            self.debug_aabb, key=lambda t: t[-1]
        ):
            if rect.collidepoint(position):
                logging.debug(f"Clicked on: {label}")
                if isinstance(obj, IClickReceiver):
                    if obj.clicked():
                        logging.debug("click was handled -> breaking out")
                        if (
                            label == LABEL_FRUIT
                        ):  # Claus-TBD: if we process that in Branch, how does game know?
                            self.harvest_on_mouseup = True
                        break

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        if self.harvest_on_mouseup:
            self.harvest_on_mouseup = False
            target_pos = Vector2(self.minimap.rect.right - 55, self.minimap.rect.bottom + 23)
            duration = .6
            self.harvested_tomatoes.append(HarvestedTomato(self,
                                                           pygame.mouse.get_pos(),
                                                           target_pos,
                                                           duration))

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...

    def make_new_plants(self):
        for sector in self.sectors:
            sector.make_new_plants()

    def update(self):
        for sector in self.sectors:
            sector.update()

        for harvested in self.harvested_tomatoes:
            harvested.update()
        self.harvested_tomatoes = [harvested for harvested in self.harvested_tomatoes if not harvested.done]

        self.spaceship.update()

    def draw_scene(self, ctx, *, bg_color: Color, details: bool, visible_rect: Rect):
        ctx.clear(bg_color)

        for idx, star in enumerate(self.stars):
            size = 1 + (idx % 3)
            ctx.rect(Color(255, 255, 255, 128), Rect(star.x, star.y, size, size))

        ctx.flush()

        atmosphere_color_ground = Color(30, 60, 150)
        atmosphere_color_sky = Color(atmosphere_color_ground)
        atmosphere_color_sky.a = 0

        ctx.donut(
            atmosphere_color_ground,
            atmosphere_color_sky,
            self.planet.position,
            self.planet.radius,
            self.planet.radius + self.planet.atmosphere_height,
        )
        ctx.flush()

        if details:
            for sector in self.sectors:
                if (
                    not self.cull_via_aabb
                    or not sector.aabb
                    or visible_rect.colliderect(sector.aabb)
                ):
                    sector.draw(ctx)

        for rock in self.rocks:
            rock.draw(ctx)

        self.spaceship.draw(ctx)

        self.planet.draw(ctx)

        ctx.flush()

    def render_credits(self,ctx):
        self._draw_lines_over(
            ctx,
            textwrap.dedent("""
        A PyWeek#34 entry by the Python User Group
        in Vienna, Austria (https://pyug.at/).

        Authors:
            Christian Knittl-Frank,
            Paul Reiter,
            Claus Aichinger and
            Thomas Perl.

        See ARTWORK.md for a list of third party
        sound and graphic artwork used in this game.
        """).splitlines(), big=True)

    def render_tutorial(self, ctx):
        sprite, lines = self.tutorial[self.tutorial_pos]
        xpos = (self.width - sprite.width) / 2
        ypos = (self.height - sprite.height) / 3
        ctx.sprite(sprite, Vector2(xpos, ypos))

        margin = 10 + sprite.height

        offset = 30
        initial_position = ypos + sprite.height + offset / 2

        font_lines = [ctx.font_cache_big.lookup(line or ' ', Color(255, 255, 255)) for line in lines]

        max_line_width = max(line.width for line in font_lines)
        xpos = (self.width - max_line_width) / 2
        ypos = initial_position

        for line in font_lines:
            ctx.sprite(line, Vector2(xpos, ypos))
            ypos += offset

        tutline = ctx.font_cache.lookup('(click to continue, "s" to skip tutorial)', Color(128, 128, 128))

        ctx.sprite(tutline, Vector2(max(xpos, xpos + max_line_width - tutline.width), ypos + 20))
        ctx.flush()

        tuta = self.get_tutorial_alpha()
        if tuta < 1:
            ctx.rect(Color(10, 10, 20, 255 - int(255 * tuta)), Rect(0, 0, self.width, self.height))
            ctx.flush()

    def render_instructions(self, ctx):
        self._draw_lines_over(
            ctx,
            textwrap.dedent(
                f"""
            How to play:
            Use the scroll wheel (or touchpad scroll) to move around the planet.
            Click on a tomato fruit to harvest it.
            Click on a fly (within the atmosphere) to kick it out of orbit.
            Click on the roots of plants to cut them off and let a new one sprout.
            A plant will only grow tomatoes once! Cut it off to grow a new one.
        """
            ).splitlines(),
        )

    def render_gameover_flies_win(self):
        with self.renderer as ctx:
            ctx.clear(Color(10, 10, 20))
            self._draw_lines_over(
                ctx,
                textwrap.dedent(f"""
            Oh nooo! It's too late!
            They got all the {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN} space tomatoes they need...
            Prepare for evacuation immediately!

            But also, thanks for playing our
            little game -- try again, maybe?
            """).splitlines(), big=True)
            ctx.flush()

    def render_gameover_player_wins(self):
        with self.renderer as ctx:
            ctx.clear(Color(10, 10, 20))
            self._draw_lines_over(
                ctx,
                textwrap.dedent(f"""
            Oh yesss! You did it!
            With these additional {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS} space tomatoes
            we will finally ketchdown the flies.
            Good job!

            And thanks for playing our little
            game, we hope you enjoyed it :)
            """).splitlines(), big=True)
            ctx.flush()

    def _draw_lines_over(self, ctx, lines, big=False):
        offset = 30 if big else 25
        initial_position = (self.height - len(lines) * offset) / 2
        for i, line in enumerate(lines):
            ctx.text(
                line,
                Color(255, 255, 255) if line.startswith("    ") else Color(200, 200, 200),
                Vector2(330 if big else 220, initial_position + i * offset),
                big=big
            )
        ctx.flush()

    def get_tutorial_alpha(self):
        return min(1, max(0, (time.time() - self.tutorial_pageflip_time) / .4))

    def render_scene(self, *, paused=False, startup=False):
        with self.renderer as ctx:
            visible_rect = Rect(0, 0, self.width, self.height)

            self.debug_aabb = []

            # Draw screen content
            ctx.camera_mode_world(
                self.planet, zoom=1.0, rotate=self.rotation_angle_degrees / 360
            )
            self.draw_scene(
                ctx, bg_color=Color(10, 10, 20), details=True, visible_rect=visible_rect
            )

            # GL coordinate system origin = bottom left
            minimap_gl_rect = (
                int(self.minimap.rect.x),
                int(self.height - self.minimap.rect.height - self.minimap.rect.y),
                int(self.minimap.rect.width),
                int(self.minimap.rect.height),
            )

            glViewport(*minimap_gl_rect)
            glScissor(*minimap_gl_rect)
            glEnable(GL_SCISSOR_TEST)

            self.debug_aabb.append(
                (
                    LABEL_MINIMAP,
                    Color(0, 255, 255),
                    self.minimap.rect,
                    self.minimap,
                    CLICK_PRIORITY_OTHER,
                )
            )

            self.drawing_minimap = True

            # TODO: Draw stylized scene
            ctx.camera_mode_world(
                self.planet, zoom=0, rotate=self.rotation_angle_degrees / 360
            )
            self.draw_scene(
                ctx,
                bg_color=Color(10, 10, 10),
                details=False,
                visible_rect=visible_rect,
            )
            self.drawing_minimap = False

            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, self.width, self.height)
            glScissor(0, 0, self.width, self.height)

            # Draw GUI overlay
            ctx.camera_mode_overlay()
            self.gui.draw(ctx)
            for harvested in self.harvested_tomatoes:
                harvested.draw(ctx)
            ctx.flush()

            if self.draw_debug_aabb:
                for label, color, rect, obj, priority in self.debug_aabb:
                    # only draw if it's visible
                    if not self.cull_via_aabb or visible_rect.colliderect(rect):
                        ctx.aabb(color, rect)
                        ctx.text(label, color, Vector2(rect.topleft))

            ctx.flush()

            # Update the cursor dependent on what is below
            left_mouse_pressed, *_ = pygame.mouse.get_pressed()
            mouse_pos = pygame.mouse.get_pos()

            if not left_mouse_pressed:
                self.cursor_mode = None
                self.cursor_planet_coordinate = None

                for label, color, rect, obj, priority in sorted(
                    self.debug_aabb, key=lambda t: t[-1]
                ):
                    if rect.collidepoint(mouse_pos):
                        self.cursor_mode = getattr(obj, "CURSOR", None)
                        if isinstance(obj, Plant):
                            self.cursor_planet_coordinate = getattr(
                                obj, "position", None
                            )
                        break

            if not self.is_running:
                self.cursor_mode = None

            if self.cursor_mode:
                pygame.mouse.set_visible(False)
                sprite = self.artwork.get_cursor(self.cursor_mode)

                if isinstance(sprite, dict):
                    sprite = sprite[left_mouse_pressed]

                cursor_position = (
                    Vector2(mouse_pos) - sprite.size / 2
                )
                cursor_center_offset = sprite.size / 2

                ctx.modelview_matrix_stack.push()
                if self.cursor_planet_coordinate is not None:
                    ctx.modelview_matrix_stack.translate(
                        *(cursor_position + cursor_center_offset)
                    )
                    ctx.modelview_matrix_stack.rotate(
                        (
                            self.rotation_angle_degrees
                            + self.cursor_planet_coordinate.angle_degrees
                        )
                        / 180
                        * math.pi
                    )
                    ctx.modelview_matrix_stack.translate(
                        *-(cursor_position + cursor_center_offset)
                    )
                ctx.sprite(sprite, cursor_position)
                ctx.modelview_matrix_stack.pop()
            else:
                pygame.mouse.set_visible(True)

            ctx.flush()

            # Claus-NEXT
            text = f"Tomatoes: {self.tomato_score}"
            ctx.text(
                text,
                Color(0, 255, 255),
                Vector2(self.minimap.rect.left, self.minimap.rect.bottom + 10),
            )

            text = f"Stolen: {self.spaceship.total_collected_tomatoes}"
            ctx.text(
                text,
                Color(0, 255, 255),
                Vector2(self.minimap.rect.left, self.minimap.rect.bottom + 30),
            )
            ctx.flush()

            if paused or startup:
                ctx.rect(Color(0, 0, 0, 200), Rect(0, 0, self.width, self.height))
                ctx.flush()

                bg_pos = Vector2((self.width - self.artwork.logo_bg.width) / 2, 20)

                ctx.sprite(self.artwork.logo_bg, bg_pos)

                scl = 1 + .1*math.sin(ctx.now*6.4)
                scaling = Vector2(scl, scl)

                fg_pos = Vector2((self.width - self.artwork.logo_bg.width * scl) / 2,
                                  30 - (scl - 1) * self.artwork.logo_bg.height / 2 - 10 + 3 * math.sin(ctx.now*3.3))

                ctx.sprite(self.artwork.logo_text, fg_pos, scale=scaling)

                btn_width = 400
                btn_height = 60
                spacing = 10

                top_margin = self.artwork.logo_text.height

                x = (self.width - btn_width) / 2
                y = top_margin + (self.height - top_margin - len(self.buttons) * btn_height - (len(self.buttons) - 1) * spacing) / 2

                last_active_button = self.active_button
                self.active_button = None
                for label, key in self.buttons:
                    rr = Rect(x, y, btn_width, btn_height)
                    if rr.collidepoint(pygame.mouse.get_pos()) and (not self.want_instructions and
                                                                    not self.want_credits and
                                                                    not self.want_tutorial):
                        color = Color(90, 90, 90)
                        self.active_button = (label, key)
                        if self.active_button != last_active_button:
                            self.active_button_time = time.time()
                    else:
                        color = Color(50, 50, 50)
                    ctx.rect(color, rr, z_layer=ctx.LAYER_BTN_BG)
                    if (label, key) == self.active_button:
                        alpha = min(1, max(0, (time.time() - self.active_button_time) / .2))
                        ctx.rect(Color(240, 240, 240), Rect(rr.x + rr.w * (1-alpha) / 2, rr.y, rr.w * alpha, rr.h), z_layer=ctx.LAYER_BTN_BG)
                    else:
                        alpha = 0
                    rr.topleft += (1-abs(1-2*alpha)) * 10 * Vector2(math.sin(alpha*23), math.cos(alpha*23))
                    intens = 255 - int(255 * alpha)
                    ctx.text_centered_rect(label, Color(intens, intens, intens), rr, z_layer=ctx.LAYER_BTN_TEXT)
                    y += btn_height + spacing

                ctx.flush()

                if self.want_instructions:
                    self.active_button = None
                    ctx.rect(Color(0, 0, 0, 230), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_instructions(ctx)
                    ctx.flush()

                if self.want_credits:
                    self.active_button = None
                    ctx.rect(Color(0, 0, 0, 230), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_credits(ctx)
                    ctx.flush()

                if self.want_tutorial:
                    self.active_button = None
                    ctx.rect(Color(10, 10, 20), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_tutorial(ctx)
                    ctx.flush()


def main():
    # test_matrix3x3()

    game = Game()

    while True:
        game.tick()


if __name__ == "__main__":
    main()
