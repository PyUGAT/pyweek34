import pygame


class Planet:
    def __init__(self, radius, color, horizon_height):
        self.radius = radius
        self.color = color
        self.horizon_height = horizon_height

    def draw(self, win):
        rect = pygame.Rect(
            -self.radius + win.get_width() / 2,
            win.get_height() - self.horizon_height,
            2 * self.radius,
            2 * self.radius,
        )
        pygame.draw.ellipse(win, self.color, rect)
