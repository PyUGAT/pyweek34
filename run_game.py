import pygame

from planet.planet import Planet

WIDTH, HEIGHT = 1920, 1080
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

BACKGROUND_COLOR = (204, 255, 255)  # TODO: use gradient from blue to black
FPS = 60
START_ROTATION = 0
ROTATION_VELOCITY = 2


PLANET = Planet(4000, (255, 0, 0), 200)


def draw_window(rotation):
    WIN.fill(BACKGROUND_COLOR)
    pygame.display.set_caption(f"Red Planted {rotation}")
    PLANET.draw(WIN, rotation)
    pygame.display.update()


def main():
    clock = pygame.time.Clock()
    rotation = START_ROTATION
    run = True
    while run:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
        keys_pressed = pygame.key.get_pressed()
        if keys_pressed[pygame.K_a]:
            rotation = (rotation - ROTATION_VELOCITY) % 360
        if keys_pressed[pygame.K_d]:
            rotation = (rotation + ROTATION_VELOCITY) % 360
        draw_window(rotation)
    pygame.quit()


if __name__ == "__main__":
    main()
