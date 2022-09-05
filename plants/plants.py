import pygame
import random
import time
import math
import os

from pygame.math import Vector2

HERE = os.path.dirname(__file__) or '.'

fontdir = os.path.join(HERE, 'font')

WIDTH, HEIGHT = 1920, 1080
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

pygame.font.init()
font = pygame.font.Font(os.path.join(fontdir, 'RobotoMono-SemiBold.ttf'), 16)

BACKGROUND_COLOR = (30, 30, 30)


class Branch(object):
    def __init__(self, phase, length=500, leftright=-1, depth=0):
        self.phase = phase
        self.depth = depth
        self.leftright = leftright
        self.angle = self.leftright * random.uniform(50, 70) * (0 if (depth == 0) else depth/2.)
        self.length = length
        self.thickness = 4
        self.children = []
        self.has_fruit = random.choice([False, False, False, True])

    def grow(self):
        phase = random.uniform(0.7, 0.95)
        flength = random.uniform(0.3, 0.5)
        self.children.append(Branch(phase, self.length * flength, random.choice([-1, +1]) * self.leftright, self.depth + 1))

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

    def draw(self, win, pos, factor, angle, health):
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
        color = (100-health, 255-150+health*1.5, 0)
        pygame.draw.polygon(win, color, points, width=self.thickness)
        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(win, pos + direction * child.phase * factor, child_factor, angle, health)

        if not self.children and self.has_fruit:
            pygame.draw.circle(win, (255, 0, 0), points[-1] + Vector2(0, +7), 15 * factor)


class Plant(object):
    def __init__(self, pos=None):
        self.started = time.time()
        self.duration = 1#3
        self.pos = pos
        self.root = Branch(length=random.uniform(300, 600), phase=0, leftright=+1)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()
        self.health = 100

    def update(self):
        self.health = 50 + 50 * math.sin(time.time()*2)

    def draw(self, win, pos):
        factor = min(1, (time.time() - self.started) / self.duration)

        rootpos = pos + self.pos

        self.root.draw(win, rootpos, factor, 0., self.health)
        win.blit(font.render(f'health={self.health:.0f}', True, (255, 255, 255)), rootpos - Vector2(0, 20))


def main():
    run = True

    plants = [Plant(Vector2(-WIDTH/7*(i-2), 0)) for i in range(5)]

    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
        WIN.fill(BACKGROUND_COLOR)

        center = Vector2((WIDTH/2), (HEIGHT - 10))

        for plant in plants:
            plant.update()
            plant.draw(WIN, center)

        pygame.display.update()
    pygame.quit()


if __name__ == "__main__":
    main()
