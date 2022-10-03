from __future__ import annotations

import logging
import math
import os
import random
import textwrap
import time

import pygame
from OpenGL.GL import *
from pygame.locals import *
from pygame.math import Vector2

from .artwork import Artwork, ResourceManager
from .config import CLIARGS, ImportantParameterAffectingGameplay
from .game_elements import (CLICK_PRIORITY_OTHER, LABEL_FRUIT, LABEL_MINIMAP,
                            HarvestedTomato, Planet, PlanetSurfaceCoordinates,
                            Plant, Rock, Sector, Spaceship)
from .gui import (DebugGUI, IClickReceiver, IMouseReceiver, IUpdateReceiver,
                  Minimap, Window)
from .render import RenderContext

HERE = os.path.dirname(__file__) or "."

logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.DEBUG if CLIARGS.debug else logging.WARNING,
)


class Game(Window, IUpdateReceiver, IMouseReceiver):
    def __init__(self, data_path: str = os.path.join(HERE, "data")):
        super().__init__("Red Planted -- PyWeek#34 -- https://pyweek.org/e/RedPlanted/")
        pygame.mixer.init()

        self.resources = ResourceManager(data_path)
        self.artwork = Artwork(self.resources)
        self.renderer = RenderContext(self.width, self.height, self.resources)

        self.planet = Planet(self.artwork, self.renderer)

        self.sectors = []
        self.rocks = []

        self.rotation_angle_degrees = 0

        self.gui = DebugGUI(self)

        self.minimap = Minimap(self)

        self.num_sectors = 5
        for i in range(self.num_sectors):
            sector = Sector(self, i, i * 340 / self.num_sectors)
            self.sectors.append(sector)

            coordinate = PlanetSurfaceCoordinates(
                sector.get_center_angle() + 0.5 * 360 / self.num_sectors
            )
            self.rocks.append(Rock(self.planet, coordinate, self.artwork))

        self.spaceship = Spaceship(self, self.planet, self.artwork)

        self.debug_aabb = []
        self.draw_debug_aabb = CLIARGS.debug
        self.cull_via_aabb = False

        self.drawing_minimap = False

        self.tomato_score = 0

        stars_range = self.planet.radius * 2
        self.stars = [
            Vector2(
                random.uniform(-stars_range, +stars_range),
                random.uniform(-stars_range, +stars_range),
            )
            for i in range(100)
        ]

        self.is_running = False
        self.cursor_mode = None
        self.cursor_planet_coordinate = None

        self.harvest_on_mouseup = False
        self.harvested_tomatoes = []

        self.tutorial = [
            (
                self.resources.sprite("tutorial-incoming.png"),
                textwrap.dedent(
                    """
                Cmdr. Gardener, our sensors detect
                another hostile flyship incoming.
                """
                ).splitlines(),
            ),
            (
                self.resources.sprite("tutorial-squash.png"),
                textwrap.dedent(
                    f"""
                Fend them off and bring in our
                harvest before it is too late!
                """
                ).splitlines(),
            ),
            (
                self.resources.sprite("tutorial-steal.png"),
                textwrap.dedent(
                    f"""
                If the flies steal {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN} space
                tomatoes, we are doomed...
                """
                ).splitlines(),
            ),
            (
                self.resources.sprite("tutorial-harvest.png"),
                textwrap.dedent(
                    f"""
                Bring in {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS} space tomatoes and we will
                ketchdown the flies in this quadrant!
                """
                ).splitlines(),
            ),
            (
                self.resources.sprite("tutorial-cut.png"),
                textwrap.dedent(
                    """
                Plants grow tomatoes only once.
                Cut them to let another plant grow.
                """
                ).splitlines(),
            ),
        ]
        self.tutorial_pos = 0
        self.tutorial_pageflip_time = 0

        self.buttons = [
            ("Play Game", "play"),
            ("Instructions", "help"),
            ("Credits", "credits"),
            ("Quit", "quit"),
        ]
        self.active_button = None
        self.active_button_time = 0
        self.want_instructions = False
        self.want_credits = False
        self.want_tutorial = False
        self.game_has_started = False

    @property
    def is_startup(self):
        return not self.game_has_started

    @property
    def is_gameover_flies_win(self):
        return (
            self.spaceship.total_collected_tomatoes
            >= ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN
        )

    @property
    def is_gameover_player_wins(self):
        return (
            self.tomato_score
            >= ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS
        )

    def get_zoom_adjustment(self):
        if self.drawing_minimap:
            return 2

        return 0

    def tick(self):
        super().process_events(mouse=self.gui, update=self, gamestate=self)
        if self.is_startup:
            self.render_scene(startup=True)
        elif self.is_gameover_flies_win:
            self.render_gameover_flies_win()
        elif self.is_gameover_player_wins:
            self.render_gameover_player_wins()
        elif self.is_running:
            dy = self.gui.wheel_sum.y - self.gui.wheel_sum.x
            if dy != 0:
                self.invalidate_aabb()
            self.rotation_angle_degrees += dy * (30000 / self.planet.get_circumfence())
            self.rotation_angle_degrees %= 360
            self.gui.wheel_sum.x = 0
            self.gui.wheel_sum.y = 0

            self.set_subtitle(f"{self.renderer.fps:.0f} FPS")
            self.render_scene(paused=False)
        else:
            self.render_scene(paused=True)

    def invalidate_aabb(self):
        for sector in self.sectors:
            sector.invalidate_aabb()

    def mousedown(self, position: Vector2):
        if self.want_instructions:
            self.want_instructions = False

        if self.want_credits:
            self.want_credits = False

        if self.want_tutorial:
            self.tutorial_pos += 1
            self.tutorial_pageflip_time = time.time()
            if self.tutorial_pos == len(self.tutorial):
                self.start_game_or_toggle_pause()
                self.want_tutorial = False

        if (self.is_startup or not self.is_running) and self.active_button is not None:
            label, action = self.active_button
            if action == "play":
                if self.tutorial_pos == len(self.tutorial):
                    self.start_game_or_toggle_pause()
                else:
                    self.want_tutorial = True
                    self.tutorial_pageflip_time = time.time()
            elif action == "help":
                self.want_instructions = True
            elif action == "credits":
                self.want_credits = True
            elif action == "quit":
                self.quit()

        for label, color, rect, obj, priority in sorted(
            self.debug_aabb, key=lambda t: t[-1]
        ):
            if rect.collidepoint(position):
                logging.debug(f"Clicked on: {label}")
                if isinstance(obj, IClickReceiver):
                    if obj.clicked():
                        logging.debug("click was handled -> breaking out")
                        if label == LABEL_FRUIT:
                            self.harvest_on_mouseup = True
                        break

    def mousemove(self, position: Vector2):
        ...

    def mouseup(self, position: Vector2):
        if self.harvest_on_mouseup:
            self.harvest_on_mouseup = False
            target_pos = Vector2(
                self.minimap.rect.right - 55, self.minimap.rect.bottom + 23
            )
            duration = 0.6
            self.harvested_tomatoes.append(
                HarvestedTomato(self, pygame.mouse.get_pos(), target_pos, duration)
            )

    def mousewheel(self, x: float, y: float, flipped: bool):
        ...

    def make_new_plants(self):
        for sector in self.sectors:
            sector.make_new_plants()

    def update(self):
        for sector in self.sectors:
            sector.update()

        for harvested in self.harvested_tomatoes:
            harvested.update()
        self.harvested_tomatoes = [
            harvested for harvested in self.harvested_tomatoes if not harvested.done
        ]

        self.spaceship.update()

    def draw_scene(self, ctx, *, bg_color: Color, details: bool, visible_rect: Rect):
        ctx.clear(bg_color)

        for idx, star in enumerate(self.stars):
            size = 1 + (idx % 3)
            ctx.rect(Color(255, 255, 255, 128), Rect(star.x, star.y, size, size))

        ctx.flush()

        atmosphere_color_ground = Color(30, 60, 150)
        atmosphere_color_sky = Color(atmosphere_color_ground)
        atmosphere_color_sky.a = 0

        ctx.donut(
            atmosphere_color_ground,
            atmosphere_color_sky,
            self.planet.position,
            self.planet.radius,
            self.planet.radius + self.planet.atmosphere_height,
        )
        ctx.flush()

        if details:
            for sector in self.sectors:
                if (
                    not self.cull_via_aabb
                    or not sector.aabb
                    or visible_rect.colliderect(sector.aabb)
                ):
                    sector.draw(ctx)

        for rock in self.rocks:
            rock.draw(ctx)

        self.spaceship.draw(ctx)

        self.planet.draw(ctx)

        ctx.flush()

    def render_credits(self, ctx):
        self._draw_lines_over(
            ctx,
            textwrap.dedent(
                """
        A PyWeek#34 entry by the Python User Group
        in Vienna, Austria (https://pyug.at/).

        Authors:
            Christian Knittl-Frank,
            Paul Reiter,
            Claus Aichinger and
            Thomas Perl.

        See ARTWORK.txt for a list of third party
        sound and graphic artwork used in this game.
        """
            ).splitlines(),
            big=True,
        )

    def render_tutorial(self, ctx):
        sprite, lines = self.tutorial[self.tutorial_pos]
        xpos = (self.width - sprite.width) / 2
        ypos = (self.height - sprite.height) / 3
        ctx.sprite(sprite, Vector2(xpos, ypos))

        margin = 10 + sprite.height

        offset = 30
        initial_position = ypos + sprite.height + offset / 2

        font_lines = [
            ctx.font_cache_big.lookup(line or " ", Color(255, 255, 255))
            for line in lines
        ]

        max_line_width = max(line.width for line in font_lines)
        xpos = (self.width - max_line_width) / 2
        ypos = initial_position

        for line in font_lines:
            ctx.sprite(line, Vector2(xpos, ypos))
            ypos += offset

        tutline = ctx.font_cache.lookup(
            '(click to continue, "s" to skip tutorial)', Color(128, 128, 128)
        )

        ctx.sprite(
            tutline,
            Vector2(max(xpos, xpos + max_line_width - tutline.width), ypos + 20),
        )
        ctx.flush()

        tuta = self.get_tutorial_alpha()
        if tuta < 1:
            ctx.rect(
                Color(10, 10, 20, 255 - int(255 * tuta)),
                Rect(0, 0, self.width, self.height),
            )
            ctx.flush()

    def render_instructions(self, ctx):
        self._draw_lines_over(
            ctx,
            textwrap.dedent(
                f"""
            How to play:
            Use the scroll wheel (or touchpad scroll) to move around the planet.
            Click on a tomato fruit to harvest it.
            Click on a fly (within the atmosphere) to kick it out of orbit.
            Click on the roots of plants to cut them off and let a new one sprout.
            A plant will only grow tomatoes once! Cut it off to grow a new one.
        """
            ).splitlines(),
        )

    def render_gameover_flies_win(self):
        with self.renderer as ctx:
            ctx.clear(Color(10, 10, 20))
            self._draw_lines_over(
                ctx,
                textwrap.dedent(
                    f"""
            Oh nooo! It's too late!
            They got all the {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_FLIES_WIN} space tomatoes they need...
            Prepare for evacuation immediately!

            But also, thanks for playing our
            little game -- try again, maybe?
            """
                ).splitlines(),
                big=True,
            )
            ctx.flush()

    def render_gameover_player_wins(self):
        with self.renderer as ctx:
            ctx.clear(Color(10, 10, 20))
            self._draw_lines_over(
                ctx,
                textwrap.dedent(
                    f"""
            Oh yesss! You did it!
            With these additional {ImportantParameterAffectingGameplay.GAMEOVER_THRESHOLD_PLAYER_WINS} space tomatoes
            we will finally ketchdown the flies.
            Good job!

            And thanks for playing our little
            game, we hope you enjoyed it :)
            """
                ).splitlines(),
                big=True,
            )
            ctx.flush()

    def _draw_lines_over(self, ctx, lines, big=False):
        offset = 30 if big else 25
        initial_position = (self.height - len(lines) * offset) / 2
        for i, line in enumerate(lines):
            ctx.text(
                line,
                Color(255, 255, 255)
                if line.startswith("    ")
                else Color(200, 200, 200),
                Vector2(330 if big else 220, initial_position + i * offset),
                big=big,
            )
        ctx.flush()

    def get_tutorial_alpha(self):
        return min(1, max(0, (time.time() - self.tutorial_pageflip_time) / 0.4))

    def render_scene(self, *, paused=False, startup=False):
        with self.renderer as ctx:
            visible_rect = Rect(0, 0, self.width, self.height)

            self.debug_aabb = []

            # Draw screen content
            ctx.camera_mode_world(
                self.planet, zoom=1.0, rotate=self.rotation_angle_degrees / 360
            )
            self.draw_scene(
                ctx, bg_color=Color(10, 10, 20), details=True, visible_rect=visible_rect
            )

            # GL coordinate system origin = bottom left
            minimap_gl_rect = (
                int(self.minimap.rect.x),
                int(self.height - self.minimap.rect.height - self.minimap.rect.y),
                int(self.minimap.rect.width),
                int(self.minimap.rect.height),
            )

            glViewport(*minimap_gl_rect)
            glScissor(*minimap_gl_rect)
            glEnable(GL_SCISSOR_TEST)

            self.debug_aabb.append(
                (
                    LABEL_MINIMAP,
                    Color(0, 255, 255),
                    self.minimap.rect,
                    self.minimap,
                    CLICK_PRIORITY_OTHER,
                )
            )

            self.drawing_minimap = True

            ctx.camera_mode_world(
                self.planet, zoom=0, rotate=self.rotation_angle_degrees / 360
            )
            self.draw_scene(
                ctx,
                bg_color=Color(10, 10, 10),
                details=False,
                visible_rect=visible_rect,
            )
            self.drawing_minimap = False

            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, self.width, self.height)
            glScissor(0, 0, self.width, self.height)

            # Draw GUI overlay
            ctx.camera_mode_overlay()
            self.gui.draw(ctx)
            for harvested in self.harvested_tomatoes:
                harvested.draw(ctx)
            ctx.flush()

            if self.draw_debug_aabb:
                for label, color, rect, obj, priority in self.debug_aabb:
                    # only draw if it's visible
                    if not self.cull_via_aabb or visible_rect.colliderect(rect):
                        ctx.aabb(color, rect)
                        ctx.text(label, color, Vector2(rect.topleft))

            ctx.flush()

            # Update the cursor dependent on what is below
            left_mouse_pressed, *_ = pygame.mouse.get_pressed()
            mouse_pos = pygame.mouse.get_pos()

            if not left_mouse_pressed:
                self.cursor_mode = None
                self.cursor_planet_coordinate = None

                for label, color, rect, obj, priority in sorted(
                    self.debug_aabb, key=lambda t: t[-1]
                ):
                    if rect.collidepoint(mouse_pos):
                        self.cursor_mode = getattr(obj, "CURSOR", None)
                        if isinstance(obj, Plant):
                            self.cursor_planet_coordinate = getattr(
                                obj, "position", None
                            )
                        break

            if not self.is_running:
                self.cursor_mode = None

            if self.cursor_mode:
                pygame.mouse.set_visible(False)
                sprite = self.artwork.get_cursor(self.cursor_mode)

                if isinstance(sprite, dict):
                    sprite = sprite[left_mouse_pressed]

                cursor_position = Vector2(mouse_pos) - sprite.size / 2
                cursor_center_offset = sprite.size / 2

                ctx.modelview_matrix_stack.push()
                if self.cursor_planet_coordinate is not None:
                    ctx.modelview_matrix_stack.translate(
                        *(cursor_position + cursor_center_offset)
                    )
                    ctx.modelview_matrix_stack.rotate(
                        (
                            self.rotation_angle_degrees
                            + self.cursor_planet_coordinate.angle_degrees
                        )
                        / 180
                        * math.pi
                    )
                    ctx.modelview_matrix_stack.translate(
                        *-(cursor_position + cursor_center_offset)
                    )
                ctx.sprite(sprite, cursor_position)
                ctx.modelview_matrix_stack.pop()
            else:
                pygame.mouse.set_visible(True)

            ctx.flush()

            text = f"Tomatoes: {self.tomato_score}"
            ctx.text(
                text,
                Color(0, 255, 255),
                Vector2(self.minimap.rect.left, self.minimap.rect.bottom + 10),
            )

            text = f"Stolen: {self.spaceship.total_collected_tomatoes}"
            ctx.text(
                text,
                Color(0, 255, 255),
                Vector2(self.minimap.rect.left, self.minimap.rect.bottom + 30),
            )
            ctx.flush()

            if paused or startup:
                ctx.rect(Color(0, 0, 0, 200), Rect(0, 0, self.width, self.height))
                ctx.flush()

                bg_pos = Vector2((self.width - self.artwork.logo_bg.width) / 2, 20)

                ctx.sprite(self.artwork.logo_bg, bg_pos)

                scl = 1 + 0.1 * math.sin(ctx.now * 6.4)
                scaling = Vector2(scl, scl)

                fg_pos = Vector2(
                    (self.width - self.artwork.logo_bg.width * scl) / 2,
                    30
                    - (scl - 1) * self.artwork.logo_bg.height / 2
                    - 10
                    + 3 * math.sin(ctx.now * 3.3),
                )

                ctx.sprite(self.artwork.logo_text, fg_pos, scale=scaling)

                btn_width = 400
                btn_height = 60
                spacing = 10

                top_margin = self.artwork.logo_text.height

                x = (self.width - btn_width) / 2
                y = (
                    top_margin
                    + (
                        self.height
                        - top_margin
                        - len(self.buttons) * btn_height
                        - (len(self.buttons) - 1) * spacing
                    )
                    / 2
                )

                last_active_button = self.active_button
                self.active_button = None
                for label, key in self.buttons:
                    rr = Rect(x, y, btn_width, btn_height)
                    if rr.collidepoint(pygame.mouse.get_pos()) and (
                        not self.want_instructions
                        and not self.want_credits
                        and not self.want_tutorial
                    ):
                        color = Color(90, 90, 90)
                        self.active_button = (label, key)
                        if self.active_button != last_active_button:
                            self.active_button_time = time.time()
                    else:
                        color = Color(50, 50, 50)
                    ctx.rect(color, rr, z_layer=ctx.LAYER_BTN_BG)
                    if (label, key) == self.active_button:
                        alpha = min(
                            1, max(0, (time.time() - self.active_button_time) / 0.2)
                        )
                        ctx.rect(
                            Color(240, 240, 240),
                            Rect(
                                rr.x + rr.w * (1 - alpha) / 2, rr.y, rr.w * alpha, rr.h
                            ),
                            z_layer=ctx.LAYER_BTN_BG,
                        )
                    else:
                        alpha = 0
                    rr.topleft += (
                        (1 - abs(1 - 2 * alpha))
                        * 10
                        * Vector2(math.sin(alpha * 23), math.cos(alpha * 23))
                    )
                    intens = 255 - int(255 * alpha)
                    ctx.text_centered_rect(
                        label,
                        Color(intens, intens, intens),
                        rr,
                        z_layer=ctx.LAYER_BTN_TEXT,
                    )
                    y += btn_height + spacing

                ctx.flush()

                if self.want_instructions:
                    self.active_button = None
                    ctx.rect(Color(0, 0, 0, 230), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_instructions(ctx)
                    ctx.flush()

                if self.want_credits:
                    self.active_button = None
                    ctx.rect(Color(0, 0, 0, 230), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_credits(ctx)
                    ctx.flush()

                if self.want_tutorial:
                    self.active_button = None
                    ctx.rect(Color(10, 10, 20), Rect(0, 0, self.width, self.height))
                    ctx.flush()
                    self.render_tutorial(ctx)
                    ctx.flush()
