import pygame
import random
import time
import math
import os

from pygame.locals import *

from pygame.math import Vector2

from OpenGL.GL import *

HERE = os.path.dirname(__file__) or '.'

LEFT_MOUSE_BUTTON = 1
MIDDLE_MOUSE_BUTTON = 2
RIGHT_MOUSE_BUTTON = 3

(CLICK_PRIORITY_FRUIT,
 CLICK_PRIORITY_PLANT,
 CLICK_PRIORITY_SECTOR,
 CLICK_PRIORITY_OTHER) = range(4)


class Sprite(object):
    def __init__(self, img, *, want_mipmap: bool):
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


class Texture(object):
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


class ResourceManager(object):
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


class Artwork(object):
    def __init__(self, resources: ResourceManager):
        self.tomato = [resources.sprite(filename) for filename in (
            'tomato-fresh.png',
            'tomato-yellow.png',
            'tomato-ripe.png',
            'tomato-bad.png',
        )]
        self.leaves = [resources.sprite(f'leaf{num}.png') for num in (1, 2, 3)]
        self.houses = [resources.sprite(f'house{num}.png') for num in (1, 2, 3, 4)]
        self.planet = resources.sprite('mars.png')

    def is_tomato_ripe(self, tomato: Sprite):
        return tomato == self.tomato[-2]

    def get_tomato_sprite(self, factor: float, rotten: bool):
        if rotten:
            return self.tomato[-1]

        return self.tomato[max(0, min(2, int(factor*2.3)))]

    def get_random_leaf(self):
        return random.choice(self.leaves)

    def get_random_house(self):
        return random.choice(self.houses)

    def get_mars(self):
        return self.planet


def aabb_from_points(points: [Vector2]):
    x = min(point.x for point in points)
    y = min(point.y for point in points)
    w = max(point.x for point in points) - x
    h = max(point.y for point in points) - y
    return Rect(x, y, w, h)


def multiply_vec4_mat4(v, m):
    return (
        m[0][0] * v[0] + m[1][0] * v[1] + m[2][0] * v[2] + m[3][0] * v[3],
        m[0][1] * v[0] + m[1][1] * v[1] + m[2][1] * v[2] + m[3][1] * v[3],
        m[0][2] * v[0] + m[1][2] * v[1] + m[2][2] * v[2] + m[3][2] * v[3],
        m[0][3] * v[0] + m[1][3] * v[1] + m[2][3] * v[2] + m[3][3] * v[3],
    )


class RenderContext(object):
    Z_BACK = 1
    Z_FRONT = 99

    def __init__(self, width, height, resources: ResourceManager):
        self.width = width
        self.height = height
        self.font = resources.font('RobotoMono-SemiBold.ttf', 16)
        self.queue = []
        self.started = time.time()
        self.now = 0
        self.clock = pygame.time.Clock()
        self.fps = 0

    def __enter__(self):
        self.now = time.time() - self.started
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, 0, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pygame.display.flip()
        self.clock.tick()
        self.fps = self.clock.get_fps()
        return False

    def camera_mode_overlay(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, 0, 1)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def camera_mode_world(self, planet, zoom, rotate):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        left = -self.width / 2
        right = self.width / 2
        bottom = self.height / 2
        top = -self.height / 2

        glOrtho(left, right, bottom, top, 0, 1)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        min_zoom = min(self.width, self.height) / ((planet.radius + planet.atmosphere_height) * 2)

        factor = min_zoom + (1.0 - min_zoom) * (1 - (1 - zoom))
        glTranslatef(-planet.position.x, -planet.position.y, 0)
        glTranslatef(0, (zoom**.8) * (planet.radius + self.height / 3), 0)
        glScalef(factor, factor, factor)
        glRotatef(rotate * 360, 0, 0, 1)

    def clear(self, color: Color):
        glClearColor(*color.normalize())
        glClear(GL_COLOR_BUFFER_BIT)

    def sprite(self, sprite: Sprite, position: Vector2, scale: float = 1, z_order: int = 0):
        matrix = glGetFloatv(GL_MODELVIEW_MATRIX)
        self.queue.append((z_order, sprite, position, scale, matrix))

    def text(self, text: str, color: Color, position: Vector2):
        self._blit(Sprite(self.font.render(text, True, color), want_mipmap=False), position)

    def rect(self, color: Color, rectangle: Rect):
        glBegin(GL_TRIANGLES)
        glColor4f(*color.normalize())
        glVertex2f(*rectangle.topleft)
        glVertex2f(*rectangle.topright)
        glVertex2f(*rectangle.bottomright)
        glVertex2f(*rectangle.topleft)
        glVertex2f(*rectangle.bottomright)
        glVertex2f(*rectangle.bottomleft)
        glEnd()

    def aabb(self, color: Color, rectangle: Rect):
        glBegin(GL_LINE_STRIP)
        glColor4f(*color.normalize())
        glVertex2f(*rectangle.topleft)
        glVertex2f(*rectangle.topright)
        glVertex2f(*rectangle.bottomright)
        glVertex2f(*rectangle.bottomleft)
        glVertex2f(*rectangle.topleft)
        glEnd()

    def circle(self, color: Color, center: Vector2, radius: float):
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(*color.normalize())
        glVertex2f(*center)

        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius * 2 * math.pi) / 30))

        for angle in range(0, 361, int(360 / steps)):
            glVertex2f(*(center + Vector2(radius, 0).rotate(angle)))
        glEnd()

    def textured_circle(self, sprite: Sprite, center: Vector2, radius: float):
        texture = sprite._get_texture()

        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glBegin(GL_TRIANGLE_FAN)
        glColor4f(1, 1, 1, 1)
        glTexCoord2f(.5, .5)
        glVertex2f(*center)

        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = min(100, max(20, (radius * 2 * math.pi) / 30))

        for angle in range(0, 361, int(360 / steps)):
            direction = Vector2(radius, 0).rotate(angle)
            glTexCoord2f(0.5 + 0.5 * direction.x / radius, 0.5 + 0.5 * direction.y / radius)
            glVertex2f(*(center + direction))
        glEnd()
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)

    def line(self, color: Color, from_point: Vector2, to_point: Vector2, width: float):
        width = max(1, width)

        side = (to_point - from_point).normalize().rotate(90) * (width / 2)
        a = from_point + side
        b = from_point - side
        c = to_point + side
        d = to_point - side

        glBegin(GL_TRIANGLE_STRIP)
        glColor4f(*color.normalize())

        glVertex2f(*a)
        glVertex2f(*b)
        glVertex2f(*c)
        glVertex2f(*d)

        glEnd()

    def _blit(self, sprite: Sprite, position, scale: float = 1):
        width, height = sprite.width, sprite.height

        rectangle = Rect(position.x, position.y, width * scale, height * scale)

        texture = sprite._get_texture()

        glBindTexture(GL_TEXTURE_2D, texture.id)

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBegin(GL_TRIANGLES)
        glColor4f(1, 1, 1, 1)
        glTexCoord2f(0, 0)
        glVertex2f(*rectangle.topleft)
        glTexCoord2f(1, 0)
        glVertex2f(*rectangle.topright)
        glTexCoord2f(1, 1)
        glVertex2f(*rectangle.bottomright)
        glTexCoord2f(0, 0)
        glVertex2f(*rectangle.topleft)
        glTexCoord2f(1, 1)
        glVertex2f(*rectangle.bottomright)
        glTexCoord2f(0, 1)
        glVertex2f(*rectangle.bottomleft)
        glEnd()
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)

        glBindTexture(GL_TEXTURE_2D, 0)

    def flush(self):
        for z_order, sprite, position, scale, matrix in sorted(self.queue, key=lambda item: item[0]):
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadMatrixf(matrix)
            self._blit(sprite, position, scale)
            glPopMatrix()
        self.queue = []


class IClickReceiver(object):
    def clicked(self):
        # Return true to prevent propagation of event
        return False


class IMouseReceiver(object):
    def mousedown(self, position: Vector2):
        ...

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        ...

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...


class IUpdateReceiver(object):
    def update(self):
        ...


class IDrawable(object):
    def draw(self, ctx: RenderContext):
        ...


class Branch(IClickReceiver):
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

    def clicked(self):
        # TODO: Add score (check fruit_rotten first!)
        if self.has_fruit and self.plant.sector.game.zoom_slider.value >= 95:
            self.has_fruit = False
            return True

        return False

    def grow(self):
        phase = random.uniform(0.1, 0.9)
        if self.depth == 0:
            phase = max(phase, 1.0 - max(0.4, min(0.6, self.plant.fertility)))
        flength = random.uniform(0.2, 0.3)
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
            transform = self.plant.sector.game.transform_point_gl
            self.plant.aabb_points.extend((transform(pos), transform(to_point)))

        zoom_adj = (100-self.plant.sector.game.zoom_slider.value)/100

        ctx.line(color, pos, to_point, self.thickness*self.plant.growth/100 + 30 * zoom_adj)

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(ctx, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                ff = factor + 2 * zoom_adj
                tomato = self.plant.artwork.get_tomato_sprite(factor, self.fruit_rotten)
                topleft = to_point + Vector2(-(tomato.width*ff)/2, 0)
                ctx.sprite(tomato, topleft, scale=ff, z_order=ctx.Z_FRONT)

                # You can only click on ripe tomatoes
                if self.plant.artwork.is_tomato_ripe(tomato):
                    game = self.plant.sector.game
                    aabb = aabb_from_points([
                        game.transform_point_gl(topleft),
                        game.transform_point_gl(topleft + Vector2(ff * tomato.width, ff * tomato.height)),
                    ])

                    # insert front, so that the layer ordering/event handling works correctly
                    game.debug_aabb.insert(0, ('fruit', Color(255, 255, 255), aabb, self, CLICK_PRIORITY_FRUIT))
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (100 - self.random_leaf_appearance_value)
                ctx.sprite(self.leaf, to_point + Vector2(-(self.leaf.width*ff)/2, 0), scale=ff, z_order=ctx.Z_BACK)


class PlanetSurfaceCoordinates(object):
    def __init__(self, angle_degrees: float):
        self.angle_degrees = angle_degrees


class Planet(IDrawable):
    def __init__(self, artwork):
        self.position = Vector2(0, 0)
        self.radius = 3000
        self.atmosphere_height = max(500, self.radius * 0.2)
        self.sprite = artwork.get_mars()

    def get_circumfence(self):
        return self.radius * 2 * math.pi

    def draw(self, ctx):
        ctx.textured_circle(self.sprite, self.position, self.radius)

    def at(self, position: PlanetSurfaceCoordinates):
        return self.position + Vector2(0, -self.radius).rotate(position.angle_degrees)

    def apply_gl_transform(self, position: PlanetSurfaceCoordinates):
        glTranslatef(*self.at(position), 0)
        glRotatef(position.angle_degrees, 0, 0, 1)


class Sector(IUpdateReceiver, IDrawable, IClickReceiver):
    def __init__(self, game, index, base_angle):
        self.game = game
        self.index = index
        self.base_angle = base_angle
        self.number_of_plants = random.choice([2, 3, 5, 6])
        self.sector_width_degrees = {2: 5, 3: 6, 5: 14, 6: 14}[self.number_of_plants]
        self.fertility = int(random.uniform(10, 70))
        self.growth_speed = random.uniform(0.02, 0.06)
        self.rotting_speed = random.uniform(0.01, 0.02)
        self.plants = []
        self.make_new_plants()
        self.aabb = None

    def clicked(self):
        print(f"ouch, i'm a sector! {self.index}")
        if self.game.zoom_slider.value < 50:
            print('zooming into sector')
            self.game.target_rotate = 360-(self.base_angle + self.sector_width_degrees / 2)
            self.game.target_zoom = 100
            return True

        return False

    def make_new_plants(self):
        self.plants = []
        for j in range(self.number_of_plants):
            coordinate = PlanetSurfaceCoordinates(self.base_angle +
                                                  self.sector_width_degrees * (j / (self.number_of_plants-1)))
            self.plants.append(Plant(self, self.game.planet, coordinate, self.fertility, self.game.artwork))

    def replant(self, plant):
        index = self.plants.index(plant)
        self.plants[index] = Plant(self, self.game.planet, plant.position, self.fertility, self.game.artwork)

    def invalidate_aabb(self):
        self.aabb = None
        for plant in self.plants:
            plant.need_aabb = True

    def update(self):
        for plant in self.plants:
            #plant.health = self.game.health_slider.value
            #plant.growth = self.game.growth_slider.value
            plant.update()

    def draw(self, ctx):
        self.aabb = None

        for plant in self.plants:
            plant.draw(ctx)
            if plant.aabb is not None:
                self.game.debug_aabb.append(('plant', Color(0, 128, 128), plant.aabb, plant, CLICK_PRIORITY_PLANT))
                if self.aabb is None:
                    self.aabb = Rect(plant.aabb)
                else:
                    self.aabb = self.aabb.union(plant.aabb)

        if self.aabb is not None:
            self.game.debug_aabb.append((f'sector {self.index}', Color(128, 255, 128), self.aabb, self, CLICK_PRIORITY_SECTOR))


class Plant(IUpdateReceiver, IClickReceiver):
    AABB_PADDING_PX = 20

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

        length = random.uniform(100, 500)*(0.5+0.5*self.fertility/100)

        self.root = Branch(phase=0, length=length, leftright=+1, depth=0, plant=self)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

    def clicked(self):
        # TODO: Replant? / FIXME: only when zoomed in
        if self.sector.game.zoom_slider.value == 100:
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

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        self.planet.apply_gl_transform(self.position)

        self.root.draw(ctx, Vector2(0, 0), factor, 0., self.health)

        if self.need_aabb and self.aabb_points:
            self.aabb = aabb_from_points(self.aabb_points)
            self.aabb = self.aabb.inflate(self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2)
            self.aabb_points = []
            self.need_aabb = False

        glPopMatrix()


class House(IDrawable):
    def __init__(self, planet: Planet, position: PlanetSurfaceCoordinates, artwork: Artwork):
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.house = artwork.get_random_house()

    def draw(self, ctx):
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        self.planet.apply_gl_transform(self.position)

        ctx.sprite(self.house, Vector2(-self.house.width/2, -self.house.height + 10))

        glPopMatrix()


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
        ctx.rect(Color(200, 200, 255), Rect(center.x - radius, center.y - radius, 2 * radius, 2 * radius))
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


class Window(object):
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

    def transform_point_gl(self, p):
        v = (p.x, p.y, 0, 1)

        modelview = glGetFloatv(GL_MODELVIEW_MATRIX)
        v = multiply_vec4_mat4(v, modelview)

        projection = glGetFloatv(GL_PROJECTION_MATRIX)
        v = multiply_vec4_mat4(v, projection)

        result = Vector2(v[0] / v[3], v[1] / v[3])

        result.x = self.width * (result.x + 1) / 2
        result.y = self.height * (1 - ((result.y + 1) / 2))

        return result

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

        self.resources = ResourceManager(data_path)
        self.artwork = Artwork(self.resources)
        self.renderer = RenderContext(self.width, self.height, self.resources)

        self.planet = Planet(self.artwork)

        self.sectors = []
        self.houses = []

        self.health_slider = Slider('health', 0, 100, 100)
        self.growth_slider = Slider('growth', 0, 100, 100)
        self.fertility_slider = Slider('fertility', 0, 100, 100, self.make_new_plants)
        self.zoom_slider = Slider('zoom', 0, 100, 100)
        self.rotate_slider = Slider('rotate', 0, 360, 0)

        self.gui = DebugGUI(self, [
            VBox([
                self.health_slider,
                self.growth_slider,
                self.fertility_slider,
                self.zoom_slider,
                self.rotate_slider,
            ])
        ])

        self.minimap = Minimap(self)

        self.num_sectors = 8
        for i in range(self.num_sectors):
            sector = Sector(self, i, i*360/self.num_sectors)
            self.sectors.append(sector)

            coordinate = PlanetSurfaceCoordinates(sector.base_angle + 0.5 * 360 / self.num_sectors)
            self.houses.append(House(self.planet, coordinate, self.artwork))

        self.target_zoom = None
        self.target_rotate = None

        self.debug_aabb = []
        self.draw_debug_aabb = True
        self.cull_via_aabb = True

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

    def draw_scene(self, ctx, *, bg_color: Color, details: bool, visible_rect: Rect):
        ctx.clear(bg_color)

        if details:
            for sector in self.sectors:
                if not self.cull_via_aabb or not sector.aabb or visible_rect.colliderect(sector.aabb):
                    sector.draw(ctx)

        for house in self.houses:
            house.draw(ctx)

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

            self.debug_aabb.append(('minimap', Color(0, 255, 255), self.minimap.rect, self.minimap, CLICK_PRIORITY_OTHER))

            ctx.camera_mode_world(self.planet, zoom=0, rotate=self.rotate_slider.value / 360)
            # TODO: Draw stylized scene
            self.draw_scene(ctx, bg_color=Color(10, 10, 10), details=False, visible_rect=visible_rect)

            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, self.width, self.height)
            glScissor(0, 0, self.width, self.height)

            # Draw GUI overlay
            ctx.camera_mode_overlay()
            self.gui.draw(ctx)

            if self.draw_debug_aabb:
                for label, color, rect, obj, priority in self.debug_aabb:
                    # only draw if it's visible
                    if not self.cull_via_aabb or visible_rect.colliderect(rect):
                        ctx.aabb(color, rect)
                        ctx.text(label, color, Vector2(rect.topleft))


def main():
    game = Game()

    while game.running:
        game.process_events()
        game.render_scene()

    game.quit()


if __name__ == "__main__":
    main()
