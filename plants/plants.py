import pygame
import random
import time
import math

from pygame.math import Vector2

WIDTH, HEIGHT = 1920, 1080
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

BACKGROUND_COLOR = (30, 30, 30)


class Branch(object):
    def __init__(self, phase, length=500, angle=0., leftright=-1, depth=0):
        self.phase = phase
        self.depth = depth
        self.leftright = leftright
        self.angle = angle + self.leftright * random.uniform(30, 50) * (0 if (depth == 0) else depth/3.)
        self.length = length
        self.thickness = 4
        self.children = []
        self.has_fruit = random.choice([False, False, False, True])

    def grow(self):
        phase = random.uniform(0.4, 0.6)
        self.children.append(Branch(phase, self.length * phase, self.angle, random.choice([-1, +1]) * self.leftright,
            self.depth + 1))

    def moregrow(self):
        if not self.children:
            if random.choice([False, False, False, True]):
                self.grow()
            return

        for i in range(2):
            candidate = random.choice(self.children)
            if random.choice([True, True, False]):
                candidate.grow()
            else:
                candidate.moregrow()

    def draw(self, win, pos, factor):
        direction = Vector2(0, -self.length).rotate(self.angle + 10*math.sin(time.time())/max(1, 5-self.depth))

        points = [pos, pos + direction * factor]
        pygame.draw.polygon(win, (0, 255, 0), points, width=self.thickness)
        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(win, pos + direction * child.phase * factor, child_factor)

        if not self.children and self.has_fruit:
            pygame.draw.circle(win, (255, 0, 0), points[-1] + Vector2(0, +7), 15 * factor)


class Plant(object):
    def __init__(self, pos=None):
        self.started = time.time()
        self.duration = 3
        self.pos = pos
        self.root = Branch(phase=0, leftright=+1)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

    def draw(self, win, pos):
        factor = min(1, (time.time() - self.started) / self.duration)
        self.root.draw(win, pos + self.pos, factor)


def main():
    run = True

    plants = [Plant(Vector2(-WIDTH/12*(i-5), 0)) for i in range(10)]

    while run:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
        WIN.fill(BACKGROUND_COLOR)

        for plant in plants:
            plant.draw(WIN, Vector2((WIDTH/2), (HEIGHT - 10)))

        pygame.display.update()
    pygame.quit()


if __name__ == "__main__":
    main()
