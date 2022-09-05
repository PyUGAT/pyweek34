import pygame

from planet.planet import Planet

WIDTH, HEIGHT = 1920, 1080
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

BACKGROUND_COLOR = (204, 255, 255)  # TODO: use gradient from blue to black
FPS = 60
START_ROTATION = 0
ROTATION_VELOCITY = 2
MINI_DIM = 300
WORLD_DIM = 10_000


PLANET = Planet(4000, (255, 0, 0), 200)


def draw_window(rotation):
    pygame.display.set_caption(f"Red Planted {rotation}")
    WIN.fill(BACKGROUND_COLOR)
    world = pygame.Surface((WORLD_DIM, WORLD_DIM), pygame.SRCALPHA)
    PLANET.draw(world)
    pygame.draw.circle(world, (0, 0, 255), (5000, 500), 200)

    # draw viewport
    world_rotated_to_view = pygame.transform.rotate(world, rotation)
    WIN.blit(
        world_rotated_to_view,
        world_rotated_to_view.get_rect(center=(WIDTH / 2, 4000 + HEIGHT / 2)),
    )

    # draw mini map
    mini_map = pygame.transform.scale(world, (MINI_DIM, MINI_DIM))
    mini_map_rect = pygame.Rect(WIN.get_width() - MINI_DIM, 0, MINI_DIM, MINI_DIM)
    pygame.draw.rect(WIN, BACKGROUND_COLOR, mini_map_rect)
    WIN.blit(mini_map, mini_map_rect)
    pygame.draw.rect(WIN, (0, 0, 0), mini_map_rect, width=5)


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
        pygame.display.update()
    pygame.quit()


if __name__ == "__main__":
    main()
