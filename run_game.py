import pygame

WIDTH, HEIGHT = 1920, 1080
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Red Planted")

BACKGROUND_COLOR = (204, 255, 255)  # TODO: use gradient from blue to black
FPS = 60


def draw_window():
    WIN.fill(BACKGROUND_COLOR)
    pygame.display.update()


def main():
    clock = pygame.time.Clock()
    run = True
    while run:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
        draw_window()
    pygame.quit()


if __name__ == "__main__":
    main()
