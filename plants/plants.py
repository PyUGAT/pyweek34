import pygame
import random
import time
import math
import os

from pygame.locals import *

from pygame.math import Vector2

from OpenGL.GL import *

HERE = os.path.dirname(__file__) or '.'


class Texture(object):
    def __init__(self, sprite):
        self.id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, sprite.width, sprite.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        view = sprite.img.get_buffer()
        for y in range(sprite.height):
            start = y * sprite.img.get_pitch()
            pixeldata = view.raw[start:start+sprite.width*sprite.img.get_bytesize()]
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, y, sprite.width, 1, GL_BGRA, GL_UNSIGNED_BYTE, pixeldata)

        # TODO: Mipmaps, if requested

        glBindTexture(GL_TEXTURE_2D, 0)

    def __del__(self):
        glDeleteTextures([self.id])


class Sprite(object):
    def __init__(self, img):
        self.img = img
        self.width, self.height = self.img.get_size()
        self._texture = None

    @classmethod
    def load(cls, filename: str):
        return cls(pygame.image.load(filename).convert_alpha())

    def _get_texture(self):
        if self._texture is None:
            self._texture = Texture(self)

        return self._texture


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

    def get_tomato_sprite(self, factor: float, rotten: bool):
        if rotten:
            return self.tomato[-1]

        return self.tomato[max(0, min(2, int(factor*2.3)))]

    def get_random_leaf(self):
        return random.choice(self.leaves)


class RenderContext(object):
    Z_BACK = 1
    Z_FRONT = 99

    def __init__(self, width, height, win, resources: ResourceManager):
        self.width = width
        self.height = height
        self.win = win
        self.font = resources.font('RobotoMono-SemiBold.ttf', 16)
        self.queue = []
        self.started = time.time()
        self.now = 0

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
        return False

    def camera_mode_overlay(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def camera_mode_world(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        #glScalef(0.2, 0.2, 0.2)

    def clear(self, color: Color):
        glClearColor(*color.normalize())
        glClear(GL_COLOR_BUFFER_BIT)

    def sprite(self, sprite: Sprite, position: Vector2, scale: float = 1, z_order: int = 0):
        matrix = glGetFloatv(GL_MODELVIEW_MATRIX)
        self.queue.append((z_order, sprite, position, scale, matrix))

    def text(self, text: str, color: Color, position: Vector2):
        self._blit(Sprite(self.font.render(text, True, color)), position)

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

    def circle(self, color: Color, center: Vector2, radius: float):
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(*color.normalize())
        glVertex2f(*center)

        # Small circles can affort 20 steps, for bigger circles,
        # add enough steps that the largest line segment is 30 world units
        steps = max(20, (radius * 2 * math.pi) / 30)

        for angle in range(0, 361, int(360 / steps)):
            glVertex2f(*(center + Vector2(radius, 0).rotate(angle)))
        glEnd()

    def line(self, color: Color, from_point: Vector2, to_point: Vector2, width: float):
        glLineWidth(max(1, width))
        glBegin(GL_LINES)
        glColor4f(*color.normalize())
        glVertex2f(*from_point)
        glVertex2f(*to_point)
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


class IMouseReceiver(object):
    def mousedown(self, position: Vector2):
        ...

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        ...


class IUpdateReceiver(object):
    def update(self):
        ...


class IDrawable(object):
    def draw(self, ctx: RenderContext):
        ...


class Branch(object):
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
        if self.plant.health < 50:
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

        ctx.line(color, pos, to_point, self.thickness*self.plant.growth/100)

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(ctx, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                tomato = self.plant.artwork.get_tomato_sprite(factor, self.fruit_rotten)
                ctx.sprite(tomato, to_point + Vector2(-(tomato.width*factor)/2, 0), scale=factor, z_order=ctx.Z_FRONT)
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (100 - self.random_leaf_appearance_value)
                ctx.sprite(self.leaf, to_point + Vector2(-(self.leaf.width*ff)/2, 0), scale=ff, z_order=ctx.Z_BACK)


class Plant(IUpdateReceiver):
    def __init__(self, pos, fertility, artwork: Artwork):
        super().__init__()

        self.pos = pos
        self.artwork = artwork

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

    def update(self):
        #self.growth += 0.01
        #self.growth = min(100, self.growth)
        self.root.update()

    def draw(self, ctx):
        factor = self.growth / 100

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glTranslatef(self.pos.x, self.pos.y, 0)

        self.root.draw(ctx, Vector2(0, 0), factor, 0., self.health)

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
        right = self.rect.right
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
    def __init__(self, widgets=None):
        super().__init__()
        if widgets is not None:
            for widget in widgets:
                self.add(widget)
        self.focused = None

    def mousedown(self, pos):
        self.focused = self.pick(pos)
        if self.focused:
            self.focused.mousedown(pos)

    def mousemove(self, pos):
        if self.focused:
            self.focused.mousemove(pos)

    def mouseup(self, pos):
        if self.focused:
            self.focused.mouseup(pos)
            self.focused = None


class Window(object):
    EVENT_TYPE_UPDATE = pygame.USEREVENT + 42

    def __init__(self, title: str, width: int = 1280, height: int = 720, updates_per_second: int = 60):
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

    def process_events(self, *, mouse: IMouseReceiver, update: IUpdateReceiver):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.running = False
                return
            elif event.type == MOUSEBUTTONDOWN:
                mouse.mousedown(event.pos)
            elif event.type == MOUSEMOTION and event.buttons:
                mouse.mousemove(event.pos)
            elif event.type == MOUSEBUTTONUP:
                mouse.mouseup(event.pos)
            elif event.type == self.EVENT_TYPE_UPDATE:
                update.update()

    def quit(self):
        pygame.quit()


class Game(Window, IUpdateReceiver):
    def __init__(self, data_path: str = os.path.join(HERE, 'data')):
        super().__init__('Red Planted')

        self.resources = ResourceManager(data_path)
        self.artwork = Artwork(self.resources)
        self.renderer = RenderContext(self.width, self.height, self.screen, self.resources)

        self.plants = []

        self.health_slider = Slider('health', 0, 100, 100)
        self.growth_slider = Slider('growth', 0, 100, 0)
        self.fertility_slider = Slider('fertility', 0, 100, 5, self.make_new_plants)

        self.gui = DebugGUI([
            VBox([
                self.health_slider,
                self.growth_slider,
                self.fertility_slider,
            ])
        ])

        self.make_new_plants()

    def process_events(self):
        super().process_events(mouse=self.gui, update=self)

    def make_new_plants(self):
        # TODO: Make plant relative to something
        self.plants = [Plant(Vector2(self.width/2-self.width/7*(i-2), self.height - 10),
                             int(self.fertility_slider.value), self.artwork) for i in range(5)]

    def update(self):
        for plant in self.plants:
            plant.health = self.health_slider.value
            plant.growth = self.growth_slider.value
            plant.update()

    def render_scene(self):
        with self.renderer as ctx:
            ctx.clear(Color(30, 30, 30))

            ctx.camera_mode_world()

            for plant in self.plants:
                plant.draw(ctx)

            ctx.flush()

            # Planet
            ctx.circle(Color(200, 40, 0), Vector2(self.width / 2, self.height + 900), 1000)

            ctx.camera_mode_overlay()
            self.gui.draw(ctx)


def main():
    game = Game()

    while game.running:
        game.process_events()
        game.render_scene()

    game.quit()


if __name__ == "__main__":
    main()
