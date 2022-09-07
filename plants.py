import argparse
import pygame
import random
import time
import math
import os
import array
import ctypes

from pygame.locals import *
from pygame.math import Vector2
from pygame.mixer import Sound

from OpenGL.GL import *

HERE = os.path.dirname(__file__) or '.'

LEFT_MOUSE_BUTTON = 1
MIDDLE_MOUSE_BUTTON = 2
RIGHT_MOUSE_BUTTON = 3

(CLICK_PRIORITY_FRUIT,
 CLICK_PRIORITY_PLANT,
 CLICK_PRIORITY_SECTOR,
 CLICK_PRIORITY_OTHER) = range(4)

LABEL_FRUIT = "fruit"
LABEL_MINIMAP = "minimap"
LABEL_PLANT = "plant"
LABEL_SECTOR = "sector"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--debug",
    action="store_true",
    help="Show debug info",
)
parser.add_argument(
    "--fast",
    action="store_true",
    help="Fast growth to accelerate startup"
)
CLIARGS = parser.parse_args()


def multiply_3x3(a, b):
    return array.array('f', (
        a[0]*b[0] + a[1]*b[3] + a[2]*b[6],
        a[0]*b[1] + a[1]*b[4] + a[2]*b[7],
        a[0]*b[2] + a[1]*b[5] + a[2]*b[8],

        a[3]*b[0] + a[4]*b[3] + a[5]*b[6],
        a[3]*b[1] + a[4]*b[4] + a[5]*b[7],
        a[3]*b[2] + a[4]*b[5] + a[5]*b[8],

        a[6]*b[0] + a[7]*b[3] + a[8]*b[6],
        a[6]*b[1] + a[7]*b[4] + a[8]*b[7],
        a[6]*b[2] + a[7]*b[5] + a[8]*b[8],
    ))

class Matrix3x3:
    def __init__(self, initial=None):
        self.m = array.array('f', initial.m if initial is not None else (
            1., 0., 0.,
            0., 1., 0.,
            0., 0., 1.,
        ))

    def apply(self, v):
        m = self.m

        v = (v[0], v[1], 1.)

        v = (
            m[0]*v[0] + m[1]*v[1] + m[2]*v[2],
            m[3]*v[0] + m[4]*v[1] + m[5]*v[2],
            m[6]*v[0] + m[7]*v[1] + m[8]*v[2],
        )

        return (v[0]/v[2], v[1]/v[2])

    def translate(self, x, y):
        self.m = multiply_3x3(self.m, array.array('f', (
            1., 0., x,
            0., 1., y,
            0., 0., 1.,
        )))

    def scale(self, x, y):
        self.m = multiply_3x3(self.m, array.array('f', (
            x,  0., 0.,
            0., y,  0.,
            0., 0., 1.,
        )))

    def rotate(self, angle_radians):
        s = math.sin(angle_radians)
        c = math.cos(angle_radians)

        self.m = multiply_3x3(self.m, array.array('f', (
            c, -s,  0.,
            s,  c,  0.,
            0., 0., 1.,
        )))

    def ortho(self, left, right, bottom, top):
        w = (right - left)
        tx = - (right + left) / w
        h = (top - bottom)
        ty = - (top + bottom) / h

        self.m = multiply_3x3(self.m, array.array('f', (
            2. / w,     0., tx,
            0.,     2. / h, ty,
            0.,         0.,  1.,
        )))


def test_matrix3x3():
    def degrees_to_radians(deg):
        return deg / 180 * math.pi

    test_ops = [
        ('scale', 0.5, 2.0),
        ('translate', 30, 40),
        ('rotate', degrees_to_radians(-90)),
        ('ortho', 0, 1000, 1000, 0),
    ]

    for method, *args in test_ops:
        m = Matrix3x3()
        for v in ((100, 200), (0, 0)):
            getattr(m, method)(*args)
            print(f'{v} -> {method}{tuple(args)} -> {m.apply(v)}')


class Sprite:
    def __init__(self, img: pygame.surface.Surface, *, want_mipmap: bool):
        self.img = img
        self.width, self.height = self.img.get_size()
        self.want_mipmap = want_mipmap
        self._texture = None

    @classmethod
    def load(cls, filename: str):
        return cls(pygame.image.load(filename).convert_alpha(), want_mipmap=True)

    def _get_texture(self):
        if self._texture is None:
            self._texture = Texture(self, generate_mipmaps=self.want_mipmap)

        return self._texture


class AnimatedSprite:
    def __init__(self, frames: list[Sprite], *, delay_ms: int):
        self.frames = frames
        self.delay_ms = delay_ms

    def get(self, ctx):
        pos = int((ctx.now * 1000) / self.delay_ms)
        return self.frames[pos % len(self.frames)]


class Texture:
    def __init__(self, sprite: Sprite, *, generate_mipmaps: bool):
        self.id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, sprite.width, sprite.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        view = sprite.img.get_buffer()
        for y in range(sprite.height):
            start = y * sprite.img.get_pitch()
            pixeldata = view.raw[start:start+sprite.width*sprite.img.get_bytesize()]
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, y, sprite.width, 1, GL_BGRA, GL_UNSIGNED_BYTE, pixeldata)

        if generate_mipmaps:
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
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
        return Sprite.load(self.dir('image').filename(filename))

    def font(self, filename: str, point_size: int):
        return pygame.font.Font(self.dir('font').filename(filename), point_size)

    def sound(self, filename: str):
        return Sound(self.dir('sound').filename(filename))

class Artwork:
    def __init__(self, resources: ResourceManager):
        # images
        self.tomato = [resources.sprite(filename) for filename in (
            'tomato2-fresh.png',
            'tomato2-yellow.png',
            'tomato2-ripe.png',
            'tomato2-bad.png',
        )]
        self.leaves = [resources.sprite(f'leaf{num}.png') for num in (1, 2, 3)]
        self.houses = [resources.sprite(f'house{num}.png') for num in (1, 2, 3, 4)]
        self.staengel = resources.sprite('staengel.png')
        self.planet = resources.sprite('mars.png')
        self.spaceship = resources.sprite('spaceship.png')

        # TODO: Use animated cursors
        self.cursors = {
            # None: ...,  # in case we also want a custom cursor if not on object
            "cut": resources.sprite('cursor_cut.png'),
            "harvest": resources.sprite('cursor_harvest.png'),
        }
        for mode, sprite in self.cursors.items():
            # TODO: Make cursor size dynamic??
            self.cursors[mode].img = pygame.transform.scale(sprite.img, Vector2(40, 40))
            self.cursors[mode].width, self.cursors[mode].height = self.cursors[mode].img.get_size()

        # animations (images)
        self.fly_animation = AnimatedSprite([
            resources.sprite('fly1.png'),
            resources.sprite('fly2.png'),
        ], delay_ms=200)

        # sounds
        self.pick = [resources.sound(f'pick{num}.wav') for num in (1, )]

    def is_tomato_ripe(self, tomato: Sprite):
        return tomato == self.get_ripe_tomato()

    def get_ripe_tomato(self):
        return self.tomato[-2]

    def get_tomato_sprite(self, factor: float, rotten: bool):
        if rotten:
            return self.tomato[-1]

        return self.tomato[max(0, min(2, int(factor*2.3)))]

    def get_random_leaf(self):
        return random.choice(self.leaves)

    def get_random_house(self):
        return random.choice(self.houses)

    def get_staengel(self):
        return self.staengel

    def get_mars(self):
        return self.planet

    def get_spaceship(self):
        return self.spaceship

    def get_fly(self):
        return self.fly_animation

    def get_cursor(self, mode: str | None):
        return self.cursors.get(mode, None)

    def get_random_pick_sound(self):
        return random.choice(self.pick)


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
    def __init__(self, sprite: Sprite):
        self.sprite = sprite
        self.data = array.array('f')

    def append(self, position: Vector2, scale: Vector2, apply_modelview_matrix):
        if scale is None:
            scale = Vector2(1, 1)

        right = Vector2(self.sprite.width * scale.x, 0)
        bottom = Vector2(0, self.sprite.height * scale.y)

        tl = Vector2(position)
        tr = tl + right
        bl = tl + bottom
        br = bl + right

        tl = apply_modelview_matrix(tl)
        tr = apply_modelview_matrix(tr)
        bl = apply_modelview_matrix(bl)
        br = apply_modelview_matrix(br)

        self.data.extend((
            0., 0., tl.x, tl.y,
            1., 0., tr.x, tr.y,
            1., 1., br.x, br.y,

            0., 0., tl.x, tl.y,
            1., 1., br.x, br.y,
            0., 1., bl.x, bl.y,
        ))

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
        glTexCoordPointer(2, GL_FLOAT, 4 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 4 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)))

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
        self.data = array.array('f')
        self.mode = mode

    def append(self, color: Color, vertices: [Vector2], apply_modelview_matrix):
        r, g, b, a = color.normalize()

        for v in vertices:
            vertex = apply_modelview_matrix(v)
            self.data.extend((vertex.x, vertex.y, r, g, b, a))

    def draw(self):
        buf = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buf)
        glBufferData(GL_ARRAY_BUFFER, self.data.tobytes(), GL_STATIC_DRAW)

        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 6 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

        glEnableClientState(GL_COLOR_ARRAY)
        glColorPointer(4, GL_FLOAT, 6 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)))

        glDrawArrays(self.mode, 0, int(len(self.data) / 6))

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
    def __init__(self, text: str, sprite: Sprite):
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
            sprite = Sprite(self.font.render(text, True, color), want_mipmap=False)
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

    def __init__(self, width, height, resources: ResourceManager):
        self.width = width
        self.height = height
        self.font_cache = FontCache(resources.font('RobotoMono-SemiBold.ttf', 16))
        self.queue = {}
        self.started = time.time()
        self.now = 0
        self.clock = pygame.time.Clock()
        self.fps = 0
        self.projection_matrix_stack = MatrixStack()
        self.modelview_matrix_stack = MatrixStack()

    def __enter__(self):
        self.now = time.time() - self.started
        self.camera_mode_overlay()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pygame.display.flip()
        self.font_cache.gc()
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

        min_zoom = min(self.width, self.height) / ((planet.radius + planet.atmosphere_height) * 2)

        factor = min_zoom + (1.0 - min_zoom) * (1 - (1 - zoom))

        self.modelview_matrix_stack.translate(-planet.position.x, -planet.position.y)
        self.modelview_matrix_stack.translate(0, (zoom**.8) * (planet.radius + self.height / 8))
        self.modelview_matrix_stack.scale(factor, factor)
        self.modelview_matrix_stack.rotate(rotate * 2 * math.pi)

    def clear(self, color: Color):
        glClearColor(*color.normalize())
        glClear(GL_COLOR_BUFFER_BIT)

    def sprite(self, sprite: Sprite, position: Vector2, scale: Vector2 = None, z_layer: int = 0):
        key = (z_layer, sprite)
        if key not in self.queue:
            self.queue[key] = DrawSpriteTask(sprite)

        self.queue[key].append(position, scale, self.modelview_matrix_stack.apply)

    def text(self, text: str, color: Color, position: Vector2):
        self.sprite(self.font_cache.lookup(text, color), position)

    def rect(self, color: Color, rectangle: Rect, *, z_layer: int = 0):
        self._colored_vertices(GL_TRIANGLES, color, [
            rectangle.topleft,
            rectangle.topright,
            rectangle.bottomright,

            rectangle.topleft,
            rectangle.bottomright,
            rectangle.bottomleft,
        ], z_layer=z_layer)

    def aabb(self, color: Color, rectangle: Rect):
        self._colored_vertices(GL_LINES, color, [
            rectangle.topleft,
            rectangle.topright,

            rectangle.topright,
            rectangle.bottomright,

            rectangle.bottomright,
            rectangle.bottomleft,

            rectangle.bottomleft,
            rectangle.topleft,
        ])

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

    def textured_circle(self, sprite: Sprite, center: Vector2, radius: float):
        texture = sprite._get_texture()

        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glBegin(GL_TRIANGLE_FAN)
        glColor4f(1, 1, 1, 1)
        glTexCoord2f(.5, .5)
        glVertex2f(*self.modelview_matrix_stack.apply(center))

        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius * 2 * math.pi) / 30))

        for angle in range(0, 361, int(360 / steps)):
            direction = Vector2(radius, 0).rotate(angle)
            glTexCoord2f(0.5 + 0.5 * direction.x / radius, 0.5 + 0.5 * direction.y / radius)
            glVertex2f(*self.modelview_matrix_stack.apply(center + direction))
        glEnd()
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)

    def line(self, color: Color, from_point: Vector2, to_point: Vector2, width: float, *, z_layer: int = 0):
        width = max(1, width)

        side = (to_point - from_point).normalize().rotate(90) * (width / 2)
        a = from_point + side
        b = from_point - side
        c = to_point + side
        d = to_point - side

        self._colored_vertices(GL_TRIANGLES, color, [a, b, c, b, c, d], z_layer=z_layer)

    def _colored_vertices(self, mode: int, color: Color, vertices: [Vector2], *, z_layer: int = 0):
        key = (z_layer, mode)
        if key not in self.queue:
            self.queue[key] = DrawColoredVerticesTask(mode)

        self.queue[key].append(color, vertices, self.modelview_matrix_stack.apply)

    def flush(self):
        for (z_layer, *key_args), task in sorted(self.queue.items(), key=lambda kv: kv[0][0]):
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
        self.angle = leftright * random.uniform(50, 70) * (0 if (depth == 0) else depth/2.)
        self.length = length
        if depth == 0:
            self.length += 40
        self.thickness = max(8, int((self.plant.fertility / 5) / (1 if not depth else depth)))
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

    def get_world_position(self):
        return self.fruit_world_position

    def clicked(self):
        # TODO: Add score (check fruit_rotten first!)
        if self.has_fruit and self.plant.sector.game.zoom_slider.value >= 95:
            self.has_fruit = False
            self.plant.artwork.get_random_pick_sound().play()  # Claus-TBD: artwork from plant
            return True

        return False

    def grow(self):
        phase = random.uniform(0.1, 0.9)
        if self.depth == 0:
            phase = max(phase, 1.0 - max(0.4, min(0.6, self.plant.fertility)))
        flength = random.uniform(0.2, 0.3) * 2
        self.children.append(Branch(phase, self.length * flength, 1-2*(len(self.children)%2), self.depth + 1,
                                    plant=self.plant))

    def moregrow(self, recurse=True):
        if not self.children:
            if random.choice([False, False, False, True]):
                self.grow()
            return

        candidates = list(self.children) * int(max(1, self.plant.fertility / 20))

        for i in range(int(self.plant.fertility/5)):
            if not candidates:
                break

            candidate = random.choice(candidates)
            candidates.remove(candidate)

            if random.choice([True, False] if self.plant.fertility > 30 else [False, False, True]) or not recurse:
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
        angle += self.angle * self.plant.growth/100
        angle *= 1.0 + 0.01 * (100-health)

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
        wind_angle = 10*math.sin(self.plant.wind_phase + self.plant.wind_speed * ctx.now)/max(1, 5-self.depth)

        direction = Vector2(0, -self.length).rotate(angle + wind_angle)

        to_point = pos + direction * factor
        cm1 = 1.0 - ((1.0 - self.color_mod) * health/100)
        cm2 = 1.0 - ((1.0 - self.color_mod2) * health/100)
        color = Color((cm1 * (100-health), cm2 * (244-150+health*1.5), 0))

        if self.plant.need_aabb:
            self.plant.aabb_points.extend((ctx.transform_to_screenspace(pos), ctx.transform_to_screenspace(to_point)))

        zoom_adj = self.plant.sector.game.get_zoom_adjustment()

        ctx.line(color, pos, to_point, self.thickness*self.plant.growth/100 + 15 * zoom_adj, z_layer=ctx.LAYER_BRANCHES)

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(ctx, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                ff = factor + zoom_adj
                tomato = self.plant.artwork.get_tomato_sprite(factor, self.fruit_rotten)
                topleft = to_point + Vector2(-(tomato.width*ff)/2, 0)
                ctx.sprite(tomato, topleft, scale=Vector2(ff, ff), z_layer=ctx.LAYER_FRUIT)

                # You can only click on ripe tomatoes
                if self.plant.artwork.is_tomato_ripe(tomato):
                    aabb = aabb_from_points([
                        ctx.transform_to_screenspace(topleft),
                        ctx.transform_to_screenspace(topleft + Vector2(0, ff * tomato.height)),
                        ctx.transform_to_screenspace(topleft + Vector2(ff * tomato.width, 0)),
                        ctx.transform_to_screenspace(topleft + Vector2(ff * tomato.width, ff * tomato.height)),
                    ])


                    # insert front, so that the layer ordering/event handling works correctly
                    game = self.plant.sector.game
                    game.debug_aabb.insert(0, (LABEL_FRUIT, Color(255, 255, 255), aabb, self, CLICK_PRIORITY_FRUIT))

                    ctx.modelview_matrix_stack.push()
                    ctx.modelview_matrix_stack.identity()
                    game.planet.apply_planet_surface_transform(self.plant.position)
                    self.fruit_world_position = ctx.modelview_matrix_stack.apply(topleft + Vector2(tomato.width, tomato.height)/2)
                    ctx.modelview_matrix_stack.pop()

                    self.plant.sector.ripe_fruits.append(self)
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (100 - self.random_leaf_appearance_value)
                ctx.sprite(self.leaf, to_point + Vector2(-(self.leaf.width*ff)/2, 0), scale=Vector2(ff, ff), z_layer=ctx.LAYER_LEAVES)


class PlanetSurfaceCoordinates:
    def __init__(self, angle_degrees: float, elevation: float = 0):
        self.angle_degrees = angle_degrees
        self.elevation = elevation

    def lerp(self, *, target, alpha: float):
        return PlanetSurfaceCoordinates((1 - alpha) * self.angle_degrees + alpha * target.angle_degrees,
                                        (1 - alpha) * self.elevation + alpha * target.elevation)


class Planet(IDrawable):
    def __init__(self, artwork, renderer):
        self.renderer = renderer
        self.position = Vector2(0, 0)
        self.radius = 500
        self.atmosphere_height = max(100, self.radius * 0.4)
        self.sprite = artwork.get_mars()

    def get_circumfence(self):
        return self.radius * 2 * math.pi

    def draw(self, ctx):
        ctx.textured_circle(self.sprite, self.position, self.radius)

    def at(self, position: PlanetSurfaceCoordinates):
        return self.position + Vector2(0, -(self.radius + position.elevation)).rotate(position.angle_degrees)

    def apply_planet_surface_transform(self, position: PlanetSurfaceCoordinates):
        self.renderer.modelview_matrix_stack.translate(*self.at(position))
        self.renderer.modelview_matrix_stack.rotate(position.angle_degrees * math.pi / 180)


class FruitFly(IUpdateReceiver, IDrawable):
    FLYING_SPEED_CARRYING = 1
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

    def update(self):
        now = self.game.renderer.now
        angle = now * 1.1 + self.phase * 2 * math.pi

        if self.returning_to_spaceship:
            self.reparent_to(self.spaceship)
            new_roaming_offset, did_arrive = self.fly_towards_target(self.FLYING_SPEED_CARRYING
                    if self.carrying_fruit else self.FLYING_SPEED_NON_CARRYING)
            if did_arrive:
                # ka'ching!
                self.carrying_fruit = False
                self.returning_to_spaceship = False
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
                new_roaming_offset, did_arrive = self.fly_towards_target(self.FLYING_SPEED_NON_CARRYING)
                if did_arrive:
                    self.carrying_fruit = fruit.has_fruit and not fruit.plant.was_deleted
                    fruit.has_fruit = False
                    self.returning_to_spaceship = True
            else:
                self.roaming_target = self.spaceship
                new_roaming_offset = Vector2(self.spaceship.sprite.width / 2 * math.sin(angle),
                                             self.spaceship.sprite.height / 2 * math.cos(angle))

        self.x_direction = -1 if new_roaming_offset.x < self.roaming_offset.x else +1
        self.roaming_offset = new_roaming_offset

    def draw_fly_at(self, ctx, pos, direction, scale_up):
        fly_sprite = self.sprite_animation.get(ctx)
        fly_offset = -Vector2(fly_sprite.width, fly_sprite.height) / 2
        fly_offset.x *= direction

        # FIXME: Rotation is all off, should use the current sector's modelview
        ctx.sprite(fly_sprite, pos + fly_offset * scale_up, scale=Vector2(direction, 1) * scale_up, z_layer=ctx.LAYER_FLIES)

        if self.carrying_fruit:
            fly_offset += Vector2(0, fly_sprite.height/2)
            ctx.sprite(self.artwork.get_ripe_tomato(), pos + fly_offset * scale_up,
                       scale=Vector2(direction, 1) * scale_up, z_layer=ctx.LAYER_FRUIT)

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        self.draw_fly_at(ctx, self.get_world_position(), self.x_direction, scale_up)


class Spaceship(IUpdateReceiver, IDrawable):
    ELEVATION_BEGIN = 2000
    #ELEVATION_BEGIN = 600
    ELEVATION_DOWN = 300

    def __init__(self, game, planet, artwork):
        self.game = game
        self.planet = planet
        self.sprite = artwork.get_spaceship()
        self.target_sector = self.pick_target_sector()
        self.near_target_sector = False
        self.coordinates = PlanetSurfaceCoordinates(self.target_sector.get_center_angle(), elevation=self.ELEVATION_BEGIN)
        self.target_coordinates = PlanetSurfaceCoordinates(self.target_sector.get_center_angle(), elevation=self.ELEVATION_DOWN)
        self.ticks = 0
        self.flies = []

        num_flies = 2
        for i in range(num_flies):
            self.flies.append(FruitFly(game, self, artwork, i / num_flies))

    def get_available_fruit(self):
        for fruit in self.target_sector.ripe_fruits:
            if not any(fly.roaming_target == fruit for fly in self.flies):
                return fruit

        return None

    def current_sector_cleared(self):
        return self.near_target_sector and all(fly.roaming_target == self and not fly.returning_to_spaceship
                                               for fly in self.flies)

    def pick_target_sector(self):
        # for debugging
        #return self.game.sectors[0]
        return random.choice(self.game.sectors)

    def get_world_position(self):
        return self.planet.at(self.coordinates)

    def update(self):
        self.ticks += 1

        if self.ticks % 1000 == 0 and self.current_sector_cleared():
            # pick another sector
            self.target_sector = self.pick_target_sector()

        now = self.game.renderer.now
        self.target_coordinates.angle_degrees = self.target_sector.get_center_angle() + 10 * math.sin(now/10)
        self.target_coordinates.elevation = self.ELEVATION_DOWN + 30 * math.cos(now)
        self.coordinates = self.coordinates.lerp(target=self.target_coordinates, alpha=0.01)

        self.near_target_sector = ((self.coordinates.elevation < self.ELEVATION_DOWN + 50) and
                                   (abs(self.coordinates.angle_degrees - self.target_sector.get_center_angle()) < 15))

        for fly in self.flies:
            fly.update()

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        ctx.modelview_matrix_stack.push()
        self.planet.apply_planet_surface_transform(self.coordinates)
        ctx.sprite(self.sprite, -Vector2(self.sprite.width, self.sprite.height) / 2 * scale_up, Vector2(scale_up, scale_up))

        ctx.modelview_matrix_stack.pop()

        for fly in self.flies:
            fly.draw(ctx)



class Sector(IUpdateReceiver, IDrawable, IClickReceiver):
    def __init__(self, game, index, base_angle):
        self.game = game
        self.index = index
        self.base_angle = base_angle
        self.number_of_plants = random.choice([2, 3, 5, 6])
        self.sector_width_degrees = {2: 5, 3: 6, 5: 14, 6: 14}[self.number_of_plants] * 3
        self.fertility = int(random.uniform(10, 70))
        growth_speed = 100 if CLIARGS.fast else 3
        self.growth_speed = random.uniform(0.02, 0.06) * growth_speed
        self.rotting_speed = random.uniform(0.01, 0.02)
        self.plants = []
        self.make_new_plants()
        self.aabb = None  # axis-aligned bounding box
        self.ripe_fruits = []

    def get_center_angle(self):
        return (self.base_angle + self.sector_width_degrees / 2)

    def clicked(self):
        print(f"ouch, i'm a sector! {self.index}")
        if self.game.zoom_slider.value < 50:
            print('zooming into sector')
            self.game.target_rotate = 360-self.get_center_angle()
            self.game.target_zoom = 100
            return True

        return False

    def make_new_plants(self):
        for plant in self.plants:
            plant.was_deleted = True

        self.plants = []
        for j in range(self.number_of_plants):
            coordinate = PlanetSurfaceCoordinates(self.base_angle +
                                                  self.sector_width_degrees * (j / (self.number_of_plants-1)))
            self.plants.append(Plant(self, self.game.planet, coordinate, self.fertility, self.game.artwork))

    def replant(self, plant):
        plant.was_deleted = True
        index = self.plants.index(plant)
        self.plants[index] = Plant(self, self.game.planet, plant.position, self.fertility, self.game.artwork)

    def invalidate_aabb(self):
        self.aabb = None
        for plant in self.plants:
            plant.need_aabb = True

    def update(self):
        for plant in self.plants:
            plant.update()

    def draw(self, ctx):
        self.aabb = None
        self.ripe_fruits = []

        for plant in self.plants:
            plant.draw(ctx)
            if plant.aabb is not None:
                self.game.debug_aabb.append((LABEL_PLANT, Color(0, 128, 128), plant.aabb, plant, CLICK_PRIORITY_PLANT))
                if self.aabb is None:
                    self.aabb = Rect(plant.aabb)
                else:
                    self.aabb = self.aabb.union(plant.aabb)

        if self.aabb is not None:
            self.game.debug_aabb.append((f'{LABEL_SECTOR} {self.index}', Color(128, 255, 128), self.aabb, self, CLICK_PRIORITY_SECTOR))


class Plant(IUpdateReceiver, IClickReceiver):
    AABB_PADDING_PX = 20
    CURSOR = "cut"

    def __init__(self, sector: Sector, planet: Planet, position: PlanetSurfaceCoordinates, fertility, artwork: Artwork):
        super().__init__()

        self.sector = sector
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.need_aabb = True
        self.aabb_points = []
        self.aabb = None

        self.growth = 0
        self.health = 100
        self.fertility = fertility

        self.wind_phase = random.uniform(0, 2*math.pi)
        self.wind_speed = random.uniform(0.9, 1.3)

        length = random.uniform(100, 500)*(0.5+0.5*self.fertility/100) / 2

        self.root = Branch(phase=0, length=length, leftright=+1, depth=0, plant=self)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

        self.was_deleted = False

    def clicked(self):
        # TODO: Replant? / FIXME: only when zoomed in
        if self.sector.game.zoom_slider.value > 95:
            self.sector.replant(self)
            return True
        else:
            print('ingoring plant click - not fully zoomed in!')

        return False

    def update(self):
        if self.growth < 100:
            self.growth += self.sector.growth_speed
            self.growth = min(100, self.growth)
            self.need_aabb = True
        else:
            self.health -= self.sector.rotting_speed
            self.health = max(0, self.health)
            self.need_aabb = True
        self.root.update()

    def draw(self, ctx):
        factor = self.growth / 100

        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        self.root.draw(ctx, Vector2(0, 0), factor, 0., self.health)

        if self.need_aabb and self.aabb_points:
            self.aabb = aabb_from_points(self.aabb_points)
            self.aabb = self.aabb.inflate(self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2)
            self.aabb_points = []
            self.need_aabb = False

        ctx.modelview_matrix_stack.pop()


class House(IDrawable):
    def __init__(self, planet: Planet, position: PlanetSurfaceCoordinates, artwork: Artwork):
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.house = artwork.get_random_house()

    def draw(self, ctx):
        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        ctx.sprite(self.house, Vector2(-self.house.width/2, -self.house.height + 10))

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


class Box(Container):
    def __init__(self, border=24, spacing=12):
        super().__init__()
        self.border = border
        self.spacing = spacing


class VBox(Box):
    def __init__(self, children=None):
        super().__init__()
        if children is not None:
            for child in children:
                self.add(child)

    def layout(self):
        pos = Vector2(self.rect.topleft) + Vector2(self.border, self.border)
        right = self.rect.left + self.border
        for child in self.children:
            child.layout()
            child.rect.topleft = pos
            right = max(right, child.rect.right)
            pos.y = child.rect.bottom + self.spacing

        if self.children:
            pos.y -= self.spacing

        self.rect.h = pos.y - self.rect.y
        self.rect.w = right - self.rect.x + self.border



class Slider(Widget):
    WIDTH = 200
    HEIGHT = 30

    def __init__(self, label, minimum, maximum, value, on_value_changed=None):
        super().__init__(self.WIDTH, self.HEIGHT)
        self.label = label
        self.min = minimum
        self.max = maximum
        self.value = value
        self._begin_drag = None
        self.on_value_changed = on_value_changed

    def layout(self):
        self.rect.size = (self.WIDTH, self.HEIGHT)

    def draw(self, ctx):
        super().draw(ctx)
        fraction = (self.value - self.min) / (self.max - self.min)
        radius = self.rect.height / 2
        center = self.rect.topleft + Vector2(radius + (self.rect.width - 2 * radius) * fraction, self.rect.height / 2)
        ctx.circle(Color(200, 200, 255), center, radius)
        ctx.text(f'{self.label}: {self.value:.0f}', Color(255, 255, 255), Vector2(self.rect.topleft))

    def mousedown(self, pos):
        self._begin_drag = Vector2(pos)

    def mousemove(self, pos):
        delta = (Vector2(pos).x - self._begin_drag.x) / self.rect.width
        self.value = max(self.min, min(self.max, self.value + delta * (self.max - self.min)))
        self._begin_drag = Vector2(pos)

    def mouseup(self, pos):
        if self.on_value_changed is not None:
            self.on_value_changed()


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

    def __init__(self, title: str, width: int = 1280, height: int = 720, updates_per_second: int = 60):
        self.title = title
        self.width = width
        self.height = height
        pygame.display.init()

        # If your GPU doesn't support this, uncomment the next two lines (TODO: Auto-detect / command-line args?)
        pygame.display.gl_set_attribute(GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(GL_MULTISAMPLESAMPLES, 4)

        self.screen = pygame.display.set_mode((width, height), DOUBLEBUF|OPENGL)
        pygame.display.set_caption(title)
        pygame.font.init()
        pygame.time.set_timer(self.EVENT_TYPE_UPDATE, int(1000 / updates_per_second))
        self.running = True

    def set_subtitle(self, subtitle):
        pygame.display.set_caption(f'{self.title}: {subtitle}')

    def process_events(self, *, mouse: IMouseReceiver, update: IUpdateReceiver):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.running = False
                return
            elif event.type == MOUSEBUTTONDOWN and event.button == LEFT_MOUSE_BUTTON:
                mouse.mousedown(event.pos)
            elif event.type == MOUSEMOTION and event.buttons:
                mouse.mousemove(event.pos)
            elif event.type == MOUSEBUTTONUP and event.button == LEFT_MOUSE_BUTTON:
                mouse.mouseup(event.pos)
            elif event.type == MOUSEWHEEL:
                mouse.mousewheel(event.x, event.y, event.flipped)
            elif event.type == self.EVENT_TYPE_UPDATE:
                update.update()

    def quit(self):
        pygame.quit()


class Minimap(IClickReceiver):
    def __init__(self, game):
        self.game = game

        fraction = 1/8
        border = 20

        size = Vector2(self.game.width, self.game.height) * fraction

        self.rect = Rect(self.game.width - border - size.x, border, size.x, size.y)

    def clicked(self):
        self.game.target_zoom = 0 if self.game.zoom_slider.value > 50 else 100
        return True


class Game(Window, IUpdateReceiver, IMouseReceiver):
    def __init__(self, data_path: str = os.path.join(HERE, 'data')):
        super().__init__('Red Planted')
        pygame.mixer.init()  # Claus-TBD: here? In tutorials, we often see pygame.init(), which part corresponds to that?

        self.resources = ResourceManager(data_path)
        self.artwork = Artwork(self.resources)
        self.renderer = RenderContext(self.width, self.height, self.resources)

        self.planet = Planet(self.artwork, self.renderer)

        self.sectors = []
        self.houses = []

        self.zoom_slider = Slider('zoom', 0, 100, 100)
        self.rotate_slider = Slider('rotate', 0, 360, 0)

        self.gui = DebugGUI(self, [
            VBox([
                self.zoom_slider,
                self.rotate_slider,
            ])
        ])

        self.minimap = Minimap(self)

        self.num_sectors = 5
        for i in range(self.num_sectors):
            sector = Sector(self, i, i*340/self.num_sectors)
            self.sectors.append(sector)

            #coordinate = PlanetSurfaceCoordinates(sector.get_center_angle() + 0.5 * 360 / self.num_sectors)
            #self.houses.append(House(self.planet, coordinate, self.artwork))

        staengel = House(self.planet, PlanetSurfaceCoordinates(-20), self.artwork)
        staengel.house = self.artwork.get_staengel()
        self.houses.append(staengel)

        self.spaceship = Spaceship(self, self.planet, self.artwork)

        self.target_zoom = None
        self.target_rotate = None

        self.debug_aabb = []
        self.draw_debug_aabb = CLIARGS.debug
        self.cull_via_aabb = False

        self.drawing_minimap = False

    def get_zoom_adjustment(self):
        if self.drawing_minimap:
            return 2

        return 0
        #return 2 * (100-self.zoom_slider.value)/100

    def process_events(self):
        super().process_events(mouse=self.gui, update=self)

        dy = self.gui.wheel_sum.y
        if dy != 0:
            self.invalidate_aabb()
        self.rotate_slider.value += (dy * (30000 / self.planet.get_circumfence()))
        self.rotate_slider.value %= self.rotate_slider.max
        self.gui.wheel_sum.y = 0

        self.set_subtitle(f'{self.renderer.fps:.0f} FPS')

    def invalidate_aabb(self):
        for sector in self.sectors:
            sector.invalidate_aabb()

    def mousedown(self, position: Vector2):
        for label, color, rect, obj, priority in sorted(self.debug_aabb, key=lambda t: t[-1]):
            if rect.collidepoint(position):
                print('Clicked on:', label)
                if isinstance(obj, IClickReceiver):
                    if obj.clicked():
                        print('click was handled -> breaking out')
                        break

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        ...

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...

    def make_new_plants(self):
        for sector in self.sectors:
            sector.make_new_plants()

    def update(self):
        if self.target_rotate is not None:
            alpha = 0.2
            if abs(self.target_rotate - self.rotate_slider.value) < 2:
                self.rotate_slider.value = self.target_rotate
                self.target_rotate = None
                self.invalidate_aabb()
            else:
                self.rotate_slider.value = alpha * self.target_rotate + (1 - alpha) * self.rotate_slider.value
        elif self.target_zoom is not None:
            alpha = 0.1
            if abs(self.target_zoom - self.zoom_slider.value) < 0.01:
                self.zoom_slider.value = self.target_zoom
                self.target_zoom = None
                self.invalidate_aabb()
            else:
                self.zoom_slider.value = alpha * self.target_zoom + (1 - alpha) * self.zoom_slider.value

        for sector in self.sectors:
            sector.update()

        self.spaceship.update()

    def draw_scene(self, ctx, *, bg_color: Color, details: bool, visible_rect: Rect):
        ctx.clear(bg_color)

        if details:
            for sector in self.sectors:
                if not self.cull_via_aabb or not sector.aabb or visible_rect.colliderect(sector.aabb):
                    sector.draw(ctx)

        for house in self.houses:
            house.draw(ctx)

        self.spaceship.draw(ctx)

        self.planet.draw(ctx)

        ctx.flush()

    def render_scene(self):
        with self.renderer as ctx:
            visible_rect = Rect(0, 0, self.width, self.height)

            self.debug_aabb = []

            # Draw screen content
            ctx.camera_mode_world(self.planet, self.zoom_slider.value / 100, self.rotate_slider.value / 360)
            self.draw_scene(ctx, bg_color=Color(30, 30, 30), details=True, visible_rect=visible_rect)

            # GL coordinate system origin = bottom left
            minimap_gl_rect = (int(self.minimap.rect.x),
                       int(self.height - self.minimap.rect.height - self.minimap.rect.y),
                       int(self.minimap.rect.width),
                       int(self.minimap.rect.height))

            glViewport(*minimap_gl_rect)
            glScissor(*minimap_gl_rect)
            glEnable(GL_SCISSOR_TEST)

            self.debug_aabb.append((LABEL_MINIMAP, Color(0, 255, 255), self.minimap.rect, self.minimap, CLICK_PRIORITY_OTHER))

            ctx.camera_mode_world(self.planet, zoom=0, rotate=self.rotate_slider.value / 360)

            # TODO: Draw stylized scene
            self.drawing_minimap = True
            self.draw_scene(ctx, bg_color=Color(10, 10, 10), details=False, visible_rect=visible_rect)
            self.drawing_minimap = False

            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, self.width, self.height)
            glScissor(0, 0, self.width, self.height)

            # Draw GUI overlay
            ctx.camera_mode_overlay()
            self.gui.draw(ctx)
            ctx.flush()

            if self.draw_debug_aabb:
                for label, color, rect, obj, priority in self.debug_aabb:
                    # only draw if it's visible
                    if not self.cull_via_aabb or visible_rect.colliderect(rect):
                        ctx.aabb(color, rect)
                        ctx.text(label, color, Vector2(rect.topleft))

            ctx.flush()

            # Update the cursor dependent on what is below
            mouse_pos = pygame.mouse.get_pos()
            cursor_mode = None
            for label, color, rect, obj, priority in sorted(self.debug_aabb, key=lambda t: t[-1]):
                if rect.collidepoint(mouse_pos):
                    cursor_mode = getattr(obj, "CURSOR", None)
                    break
            sprite = self.artwork.get_cursor(cursor_mode)
            pygame.mouse.set_visible(not bool(sprite))
            if sprite:
                ctx.sprite(sprite, Vector2(mouse_pos) - Vector2(sprite.img.get_size()) / 2)
            ctx.flush()

def main():
    #test_matrix3x3()

    game = Game()

    while game.running:
        game.process_events()
        game.render_scene()

    game.quit()


if __name__ == "__main__":
    main()
