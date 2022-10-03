import pygame
from OpenGL.GL import *
from pygame import Color, Rect
from pygame.locals import *
from pygame.math import Vector2

from .config import CLIARGS
from .render import RenderContext

LEFT_MOUSE_BUTTON = 1
MIDDLE_MOUSE_BUTTON = 2
RIGHT_MOUSE_BUTTON = 3


class IClickReceiver:
    def clicked(self):
        # TODO: What's the purpose of this method?
        # Return true to prevent propagation of event
        return False


class IMouseReceiver:
    def mousedown(self, position: Vector2):
        ...

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        ...

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...


class IUpdateReceiver:
    def update(self):
        raise NotImplementedError("Update not implemented")


class IDrawable:
    def draw(self, ctx: RenderContext):
        raise NotImplementedError("Draw not implemented")


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


class DebugGUI(Container):
    def __init__(self, default_handler: IMouseReceiver, widgets=None):
        super().__init__()
        self.default_handler = default_handler
        if widgets is not None:
            for widget in widgets:
                self.add(widget)
        self.focused = None
        self.wheel_sum = Vector2(0, 0)

    def mousedown(self, pos):
        self.focused = self.pick(pos) or self.default_handler
        self.focused.mousedown(pos)

    def mousemove(self, pos):
        if self.focused:
            self.focused.mousemove(pos)

    def mouseup(self, pos):
        if self.focused:
            self.focused.mouseup(pos)
            self.focused = None

    def mousewheel(self, x: float, y: float, flipped: bool):
        self.wheel_sum.x += x
        self.wheel_sum.y += y


class Window:
    EVENT_TYPE_UPDATE = pygame.USEREVENT + 42

    def __init__(
        self,
        title: str,
        width: int = 1280,
        height: int = 720,
        updates_per_second: int = 60,
    ):
        self.title = title
        self.width = width
        self.height = height
        pygame.display.init()

        if not CLIARGS.no_multisample:
            pygame.display.gl_set_attribute(GL_MULTISAMPLEBUFFERS, 1)
            pygame.display.gl_set_attribute(GL_MULTISAMPLESAMPLES, 4)

        self.screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption(title)
        pygame.font.init()
        pygame.time.set_timer(self.EVENT_TYPE_UPDATE, int(1000 / updates_per_second))

    def set_subtitle(self, subtitle):
        pygame.display.set_caption(f"{self.title}: {subtitle}")

    def start_game_or_toggle_pause(self):
        self.game_has_started = True
        self.is_running = not self.is_running
        if self.is_running:
            if self.renderer.paused_started is not None:
                self.renderer.started += time.time() - self.renderer.paused_started
            self.renderer.paused_started = None
            self.buttons[0] = ("Play Game", "play")
        else:
            self.renderer.paused_started = time.time()
            self.buttons[0] = ("Resume Game", "play")

    def process_events(
        self,
        *,
        mouse: IMouseReceiver,
        update: IUpdateReceiver,
        gamestate,  # TODO: type anotation
    ):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.quit()

            if self._is_spacebar_down(event):
                gamestate.start_game_or_toggle_pause()

            if event.type == pygame.KEYDOWN and self.want_tutorial and event.key == K_s:
                self.tutorial_pos = len(self.tutorial)
                self.want_tutorial = False
                self.start_game_or_toggle_pause()

            if not gamestate.is_running:
                # main menu
                if event.type == MOUSEBUTTONDOWN and event.button == LEFT_MOUSE_BUTTON:
                    gamestate.mousedown(event.pos)
                elif event.type == MOUSEMOTION and event.buttons:
                    gamestate.mousemove(event.pos)
                elif event.type == MOUSEBUTTONUP and event.button == LEFT_MOUSE_BUTTON:
                    gamestate.mouseup(event.pos)
                elif event.type == MOUSEWHEEL:
                    gamestate.mousewheel(event.x, event.y, event.flipped)
            elif gamestate.is_running:
                if event.type == MOUSEBUTTONDOWN and event.button == LEFT_MOUSE_BUTTON:
                    mouse.mousedown(event.pos)
                elif event.type == MOUSEMOTION and event.buttons:
                    mouse.mousemove(event.pos)
                elif event.type == MOUSEBUTTONUP and event.button == LEFT_MOUSE_BUTTON:
                    mouse.mouseup(event.pos)
                elif event.type == MOUSEWHEEL:
                    mouse.mousewheel(event.x, event.y, event.flipped)
                elif event.type == self.EVENT_TYPE_UPDATE:
                    update.update()

    def _is_spacebar_down(self, event):
        return event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE

    def quit(self):
        raise SystemExit()


class Minimap(IClickReceiver):
    def __init__(self, game):
        self.game = game

        fraction = 1 / 8
        border = 20

        size = Vector2(self.game.width, self.game.height) * fraction

        self.rect = Rect(self.game.width - border - size.x, border, size.x, size.y)

    def clicked(self):
        # TBD: Could do something with the minimap
        return False
