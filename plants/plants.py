import pygame
import random
import time
import math
import os

from pygame.locals import *

from pygame.math import Vector2

HERE = os.path.dirname(__file__) or '.'

fontdir = os.path.join(HERE, 'font')
imgdir = os.path.join(HERE, 'images')

TOMATO = [
    pygame.image.load(os.path.join(imgdir, 'tomato-fresh.png')),
    pygame.image.load(os.path.join(imgdir, 'tomato-yellow.png')),
    pygame.image.load(os.path.join(imgdir, 'tomato-ripe.png')),
    pygame.image.load(os.path.join(imgdir, 'tomato-bad.png')),
]

LEAVES = [
    pygame.image.load(os.path.join(imgdir, 'leaf1.png')),
    pygame.image.load(os.path.join(imgdir, 'leaf2.png')),
    pygame.image.load(os.path.join(imgdir, 'leaf3.png')),
]

SCALING_FACTORS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

TOMATO = [
    [(scale, pygame.transform.scale(img, tuple(Vector2(img.get_size()) * scale * 3)))
        for scale in SCALING_FACTORS]
    for img in TOMATO]

LEAVES = [
    [(scale, pygame.transform.scale(img, tuple(Vector2(img.get_size()) * scale)))
        for scale in SCALING_FACTORS]
    for img in LEAVES]

WIDTH, HEIGHT = 1280, 720
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

pygame.font.init()
font = pygame.font.Font(os.path.join(fontdir, 'RobotoMono-SemiBold.ttf'), 16)

BACKGROUND_COLOR = (30, 30, 30)

class RenderContext():
    def __init__(self, win):
        self.win = win
        self.queue = []

    def flush(self):
        while self.queue:
            img, pos = self.queue.pop()
            self.win.blit(img, pos)


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
        self.leaf = random.choice(LEAVES)
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
        wind_angle = 10*math.sin(self.plant.wind_phase + self.plant.wind_speed * time.time())/max(1, 5-self.depth)

        direction = Vector2(0, -self.length).rotate(angle + wind_angle)

        points = [pos, pos + direction * factor]
        cm1 = 1.0 - ((1.0 - self.color_mod) * health/100)
        cm2 = 1.0 - ((1.0 - self.color_mod2) * health/100)
        color = (cm1 * (100-health), cm2 * (244-150+health*1.5), 0)

        pygame.draw.polygon(ctx.win, color, points, width=max(1, int(self.thickness*self.plant.growth/100)))

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(ctx, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                fruit_color_fresh = Color(100, 255, 0)
                fruit_color_ripe = Color(255, 50, 0)
                img = next(img for imgf, img in (TOMATO[int(factor*2.3)] if not self.fruit_rotten else TOMATO[-1]) if imgf >= factor)
                ctx.queue.append((img, points[-1] + Vector2(-img.get_width()/2, 0)))
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (100 - self.random_leaf_appearance_value)
                img = next(img for imgf, img in self.leaf if imgf >= ff)
                ctx.win.blit(img, points[-1] + Vector2(-img.get_width()/2, 0))


class Plant(object):
    def __init__(self, pos, fertility):
        self.started = time.time()
        self.pos = pos

        self.growth = 0
        self.health = 100
        self.fertility = fertility

        self.wind_phase = random.uniform(0, 2*math.pi)
        self.wind_speed = random.uniform(0.9, 1.3)

        self.root = Branch(phase=0, length=random.uniform(100, 500)*(0.5+0.5*self.fertility/100), leftright=+1, depth=0, plant=self)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

    def update(self):
        #self.growth += 0.01
        #self.growth = min(100, self.growth)
        self.root.update()

    def draw(self, ctx, pos):
        factor = self.growth / 100

        rootpos = pos + self.pos

        self.root.draw(ctx, rootpos, factor, 0., self.health)
        #ctx.win.blit(font.render(f'health={self.health:.0f}', True, (255, 255, 255)), rootpos - Vector2(0, 20))


class Widget:
    def __init__(self, w, h):
        self.rect = Rect(0, 0, w, h)

    def layout(self):
        ...

    def pick(self, pos):
        if self.rect.collidepoint(pos):
            return self

        return None

    def draw(self, ctx):
        pygame.draw.rect(ctx.win, (70, 70, 70), self.rect)

    def mousedown(self, pos):
        ...

    def mousemove(self, pos):
        ...

    def mouseup(self, pos):
        ...


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

    def __init__(self, label, minimum, maximum, value):
        super().__init__(self.WIDTH, self.HEIGHT)
        self.label = label
        self.min = minimum
        self.max = maximum
        self.value = value
        self._begin_drag = None
        self._callback = None

    def layout(self):
        self.rect.size = (self.WIDTH, self.HEIGHT)

    def draw(self, ctx):
        super().draw(ctx)
        fraction = (self.value - self.min) / (self.max - self.min)
        radius = self.rect.height / 2
        pygame.draw.circle(ctx.win, (200, 200, 255),
                self.rect.topleft + Vector2(radius + (self.rect.width - 2 * radius) * fraction, self.rect.height / 2), radius)
        ctx.win.blit(font.render(f'{self.label}: {self.value:.0f}', True, (255, 255, 255)), self.rect.topleft)

    def mousedown(self, pos):
        self._begin_drag = Vector2(pos)

    def mousemove(self, pos):
        delta = (Vector2(pos).x - self._begin_drag.x) / self.rect.width
        self.value = max(self.min, min(self.max, self.value + delta * (self.max - self.min)))
        self._begin_drag = Vector2(pos)

    def mouseup(self, pos):
        if self._callback is not None:
            self._callback(self)


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


def main():
    run = True

    health_slider = Slider('health', 0, 100, 100)
    growth_slider = Slider('growth', 0, 100, 0)
    fertility_slider = Slider('fertility', 0, 100, 5)

    plants = []

    def make_new_plants(fertility_slider):
        nonlocal plants
        plants = [Plant(Vector2(-WIDTH/7*(i-2), 0), int(fertility_slider.value)) for i in range(5)]

    fertility_slider._callback = make_new_plants

    make_new_plants(fertility_slider)

    gui = DebugGUI([
        VBox([
            health_slider,
            growth_slider,
            fertility_slider,
        ])
    ])

    while run:
        for event in pygame.event.get():
            if event.type == QUIT:
                run = False
            elif event.type == MOUSEBUTTONDOWN:
                gui.mousedown(event.pos)
            elif event.type == MOUSEMOTION and event.buttons:
                gui.mousemove(event.pos)
            elif event.type == MOUSEBUTTONUP:
                gui.mouseup(event.pos)
        WIN.fill(BACKGROUND_COLOR)

        center = Vector2((WIDTH/2), (HEIGHT - 10))

        ctx = RenderContext(WIN)

        for plant in plants:
            plant.health = health_slider.value
            plant.growth = growth_slider.value
            plant.update()
            plant.draw(ctx, center)

        points = []

        for x in range(-10, WIDTH+10, 30):
            points.append((x, HEIGHT-30+20*math.sin(x**77)))

        points.extend([
            (WIDTH + 10, HEIGHT - 30),
            (WIDTH + 10, HEIGHT + 10),
            (- 10, HEIGHT + 10),
            (- 10, HEIGHT - 30),
        ])

        gui.draw(ctx)

        ctx.flush()

        pygame.draw.polygon(ctx.win, (60, 50, 0), points)

        pygame.display.update()
    pygame.quit()


if __name__ == "__main__":
    main()