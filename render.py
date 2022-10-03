import math
from tasks import DrawColoredVerticesTask, DrawSpriteTask
from vectormath import Matrix3x3
from pygame import Rect, Vector2, Color

from sprite import ImageSprite
from artwork import ResourceManager

import time
import pygame

from OpenGL.GL import *

class MatrixStack:
    # TODO: What is the difference between a matrix and a matrix stack - and why does it make sense?
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
