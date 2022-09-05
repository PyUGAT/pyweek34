import pygame


class Planet:
    def __init__(self, radius, color, horizon_height):
        self.radius = radius
        self.color = color
        self.horizon_height = horizon_height

    def draw(self, surface):
        a, b = 1.1 * self.radius, 0.9 * self.radius
        rect = pygame.Rect(
            surface.get_width() / 2 - a,
            surface.get_height() / 2 - b,
            2 * a,
            2 * b,
        )
        pygame.draw.ellipse(surface, self.color, rect)
