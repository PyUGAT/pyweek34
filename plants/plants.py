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

TOMATO = [
    [(scale, pygame.transform.scale(img, tuple(Vector2(img.get_size()) * scale * 3)))
        for scale in (0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
    for img in TOMATO]

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
    def __init__(self, phase, length, leftright, depth):
        self.phase = phase
        self.depth = depth
        self.leftright = leftright
        self.angle = self.leftright * random.uniform(50, 70) * (0 if (depth == 0) else depth/2.)
        self.length = length
        if depth == 0:
            self.length += 40
        self.thickness = int(10 / (1 if not depth else depth))
        self.children = []
        self.color_mod = random.uniform(0.4, 1.0)
        self.color_mod2 = random.uniform(0.4, 1.0)
        self.has_fruit = True#random.choice([False, True])
        self.leaf = random.choice(LEAVES)

    def grow(self):
        phase = random.uniform(0.1, 0.9)
        flength = random.uniform(0.2, 0.3)
        self.children.append(Branch(phase, self.length * flength, 1-2*(len(self.children)%2), self.depth + 1))

    def moregrow(self):
        if not self.children:
            if random.choice([False, False, False, True]):
                self.grow()
            return

        for i in range(2):
            candidate = random.choice(self.children)
            if random.choice([True, False, False]):
                candidate.grow()
            else:
                candidate.moregrow()

    def draw(self, ctx, pos, factor, angle, health):
        angle *= factor
        angle += self.angle
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
        wind_angle = 10*math.sin(time.time())/max(1, 5-self.depth)

        direction = Vector2(0, -self.length).rotate(angle + wind_angle)

        points = [pos, pos + direction * factor]
        cm1 = 1.0 - ((1.0 - self.color_mod) * health/100)
        cm2 = 1.0 - ((1.0 - self.color_mod2) * health/100)
        color = (cm1 * (100-health), cm2 * (244-150+health*1.5), 0)

        pygame.draw.polygon(ctx.win, color, points, width=self.thickness)

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(ctx, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            fruit_color_fresh = Color(100, 255, 0)
            fruit_color_ripe = Color(255, 50, 0)
            img = next(img for imgf, img in (TOMATO[int(factor*2.3)] if health > 50 else TOMATO[-1]) if imgf >= factor)
            #win.blit(img, points[-1] + Vector2(-img.get_width()/2, 0))
            ctx.queue.append((img, points[-1] + Vector2(-img.get_width()/2, 0)))
            #pygame.draw.circle(win, fruit_color_fresh.lerp(fruit_color_ripe, factor), points[-1] + Vector2(0, +7), 15 * factor)
        else:
            if factor > 0.5:
                ctx.win.blit(self.leaf, points[-1] + Vector2(-self.leaf.get_width()/2, 0))


class Plant(object):
    def __init__(self, pos=None):
        self.started = time.time()
        self.pos = pos
        self.root = Branch(phase=0, length=random.uniform(100, 500), leftright=+1, depth=0)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()
        self.growth = 0
        self.health = 100

    def update(self):
        #self.health = 50 + 50 * math.sin(time.time()*2)
        ...

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
        ...


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

    plants = [Plant(Vector2(-WIDTH/7*(i-2), 0)) for i in range(5)]

    health_slider = Slider('health', 0, 100, 100)
    growth_slider = Slider('growth', 0, 100, 0)

    gui = DebugGUI([
        VBox([
            health_slider,
            growth_slider,
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
