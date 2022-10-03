import logging
import math
import random

from .artwork import Artwork
from .config import CLIARGS, ImportantParameterAffectingGameplay
from .gui import IClickReceiver, IDrawable, IUpdateReceiver
from pygame import Color, Rect
from pygame.math import Vector2
from .vectormath import aabb_from_points

(
    CLICK_PRIORITY_FRUIT,
    CLICK_PRIORITY_PLANT,
    CLICK_PRIORITY_FLY,
    CLICK_PRIORITY_SECTOR,
    CLICK_PRIORITY_OTHER,
) = range(5)

LABEL_FRUIT = "fruit"
LABEL_MINIMAP = "minimap"
LABEL_PLANT = "plant"
LABEL_SECTOR = "sector"
LABEL_FLY = "fly"


class Branch(IClickReceiver):
    CURSOR = "harvest"

    def __init__(self, phase, length, leftright, depth, plant):
        self.plant = plant
        self.phase = phase
        self.depth = depth
        self.angle = (
            leftright * random.uniform(50, 70) * (0 if (depth == 0) else depth / 2.0)
        )
        self.length = length
        if depth == 0:
            self.length += 40
        self.thickness = max(
            8, int((self.plant.fertility / 5) / (1 if not depth else depth))
        )
        self.children = []
        self.color_mod = random.uniform(0.4, 1.0)
        self.color_mod2 = random.uniform(0.4, 1.0)
        self.has_fruit = random.uniform(0, 300) < (self.plant.fertility + 10)
        self.has_leaf = not self.has_fruit
        self.fruit_rotten = False
        self.leaf = plant.artwork.get_random_leaf()
        self.random_leaf_appearance_value = random.uniform(20, 70)
        self.random_fruit_appearance_value = random.uniform(40, 70)
        self.fruit_world_position = Vector2(0, 0)
        self.was_ripe = False

    def get_world_position(self):
        return self.fruit_world_position

    def clicked(self):
        if self.has_fruit:
            self.has_fruit = False
            self.plant.shake()
            self.plant.artwork.get_random_pick_sound().play()
            return True

        return False

    def grow(self):
        phase = random.uniform(0.1, 0.9)
        if self.depth == 0:
            phase = max(phase, 1.0 - max(0.4, min(0.6, self.plant.fertility)))
        flength = random.uniform(0.2, 0.3) * 2
        self.children.append(
            Branch(
                phase,
                self.length * flength,
                1 - 2 * (len(self.children) % 2),
                self.depth + 1,
                plant=self.plant,
            )
        )

    def moregrow(self, recurse=True):
        if not self.children:
            if random.choice([False, False, False, True]):
                self.grow()
            return

        candidates = list(self.children) * int(max(1, self.plant.fertility / 20))

        for i in range(int(self.plant.fertility / 5)):
            if not candidates:
                break

            candidate = random.choice(candidates)
            candidates.remove(candidate)

            if (
                random.choice(
                    [True, False] if self.plant.fertility > 30 else [False, False, True]
                )
                or not recurse
            ):
                candidate.grow()
            else:
                candidate.moregrow(recurse=False)

    def update(self):
        if self.plant.health < 25:
            self.fruit_rotten = True

        for child in self.children:
            child.update()

    def draw(self, ctx, pos, factor, angle, health):
        if factor < 0.01:
            return

        angle *= factor
        angle += self.angle * self.plant.growth / 100
        angle *= 1.0 + 0.01 * (100 - health)

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
        wind_angle = (
            10
            * math.sin(self.plant.wind_phase + self.plant.wind_speed * ctx.now)
            / max(1, 5 - self.depth)
        )
        wind_angle += (self.plant.wind_amplitude / 10) * math.sin(ctx.now * 5)

        direction = Vector2(0, -self.length).rotate(angle + wind_angle)

        to_point = pos + direction * factor
        cm1 = 1.0 - ((1.0 - self.color_mod) * health / 100)
        cm2 = 1.0 - ((1.0 - self.color_mod2) * health / 100)
        color = Color((cm1 * (100 - health), cm2 * (244 - 150 + health * 1.5), 0))

        if self.plant.need_aabb:
            self.plant.aabb_points.extend(
                (
                    ctx.transform_to_screenspace(pos),
                    ctx.transform_to_screenspace(to_point),
                )
            )

        zoom_adj = self.plant.sector.game.get_zoom_adjustment()

        ctx.line(
            color,
            pos,
            to_point,
            self.thickness * self.plant.growth / 100 + 15 * zoom_adj,
            z_layer=ctx.LAYER_BRANCHES,
        )

        for child in self.children:
            child_factor = max(0, (factor - child.phase) / (1 - child.phase))
            child.draw(
                ctx, pos + direction * child.phase * factor, child_factor, angle, health
            )

        if not self.children and self.has_fruit:
            if self.plant.growth > self.random_fruit_appearance_value:
                ff = factor + zoom_adj
                tomato = self.plant.artwork.get_tomato_sprite(factor, self.fruit_rotten)
                topleft = to_point + Vector2(-(tomato.width * ff) / 2, 0)
                ctx.sprite(
                    tomato, topleft, scale=Vector2(ff, ff), z_layer=ctx.LAYER_FRUIT
                )

                # You can only click on ripe tomatoes
                if self.plant.artwork.is_tomato_ripe(tomato):
                    if not self.was_ripe:
                        self.plant.artwork.get_ripe_sound().play()
                        self.was_ripe = True

                    aabb = aabb_from_points(
                        [
                            ctx.transform_to_screenspace(topleft),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(0, ff * tomato.height)
                            ),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(ff * tomato.width, 0)
                            ),
                            ctx.transform_to_screenspace(
                                topleft + Vector2(ff * tomato.width, ff * tomato.height)
                            ),
                        ]
                    )

                    # insert front, so that the layer ordering/event handling works correctly
                    game = self.plant.sector.game
                    game.debug_aabb.insert(
                        0,
                        (
                            LABEL_FRUIT,
                            Color(255, 255, 255),
                            aabb,
                            self,
                            CLICK_PRIORITY_FRUIT,
                        ),
                    )

                    ctx.modelview_matrix_stack.push()
                    ctx.modelview_matrix_stack.identity()
                    game.planet.apply_planet_surface_transform(self.plant.position)
                    self.fruit_world_position = ctx.modelview_matrix_stack.apply(
                        topleft + tomato.size / 2
                    )
                    ctx.modelview_matrix_stack.pop()

                    self.plant.sector.ripe_fruits.append(self)
        elif self.has_leaf:
            if self.plant.growth > self.random_leaf_appearance_value:
                ff = (self.plant.growth - self.random_leaf_appearance_value) / (
                    100 - self.random_leaf_appearance_value
                )
                ctx.sprite(
                    self.leaf,
                    to_point + Vector2(-(self.leaf.width * ff) / 2, 0),
                    scale=Vector2(ff, ff),
                    z_layer=ctx.LAYER_LEAVES,
                )


class PlanetSurfaceCoordinates:
    def __init__(self, angle_degrees: float, elevation: float = 0):
        self.angle_degrees = angle_degrees
        self.elevation = elevation

    def lerp(self, *, target, alpha: float):
        return PlanetSurfaceCoordinates(
            (1 - alpha) * self.angle_degrees + alpha * target.angle_degrees,
            (1 - alpha) * self.elevation + alpha * target.elevation,
        )


class Planet(IDrawable):
    def __init__(self, artwork: Artwork, renderer):
        self.renderer = renderer
        self.position = Vector2(0, 0)
        self.radius = 500
        self.atmosphere_height = max(100, self.radius * 0.4)
        self.sprite = artwork.get_planet()

    def get_circumfence(self):
        return self.radius * 2 * math.pi

    def draw(self, ctx):
        ctx.textured_circle(self.sprite, self.position, self.radius)

    def at(self, position: PlanetSurfaceCoordinates):
        return self.position + Vector2(0, -(self.radius + position.elevation)).rotate(
            position.angle_degrees
        )

    def apply_planet_surface_transform(self, position: PlanetSurfaceCoordinates):
        self.renderer.modelview_matrix_stack.translate(*self.at(position))
        self.renderer.modelview_matrix_stack.rotate(
            position.angle_degrees * math.pi / 180
        )


class FruitFly(IUpdateReceiver, IDrawable, IClickReceiver):
    AABB_PADDING_PX = 40
    CURSOR = "hunt"
    FLYING_SPEED_CARRYING = 2
    FLYING_SPEED_NON_CARRYING = 4

    def __init__(self, game, spaceship, artwork, phase):
        self.game = game
        self.spaceship = spaceship
        self.artwork = artwork
        self.phase = phase
        self.sprite_animation = artwork.get_fly()
        self.roaming_target = self.spaceship
        self.roaming_offset = Vector2(0, 0)
        self.x_direction = 1
        self.returning_to_spaceship = False
        self.carrying_fruit = False
        self.aabb = None

        self.trash_rotation_direction = random.choice([-1, +1])
        self.trash_time = 0

    def get_world_position(self):
        return self.roaming_target.get_world_position() + self.roaming_offset

    def reparent_to(self, new_target):
        here = self.get_world_position()
        self.roaming_offset = here - new_target.get_world_position()
        self.roaming_target = new_target

    def fly_towards_target(self, step):
        if self.roaming_offset.length() > 0:
            new_length = max(0, self.roaming_offset.length() - step)
            new_roaming_offset = self.roaming_offset.normalize() * new_length
            return new_roaming_offset, False
        else:
            return self.roaming_offset, True

    def clicked(self):
        is_fly_close_enough_to_surface = True
        if is_fly_close_enough_to_surface and self in self.spaceship.flies:
            logging.debug("Brzzzz... you hit a fly")
            self.artwork.get_random_slap_sound().play()
            self.spaceship.flies.remove(self)
            self.spaceship.dead_flies.append(self)
            return True
        return False

    def update(self):
        now = self.game.renderer.now
        angle = now * 1.1 + self.phase * 2 * math.pi

        if self.returning_to_spaceship:
            self.reparent_to(self.spaceship)
            new_roaming_offset, did_arrive = self.fly_towards_target(
                self.FLYING_SPEED_CARRYING
                if self.carrying_fruit
                else self.FLYING_SPEED_NON_CARRYING
            )
            if did_arrive:
                # ka'ching!
                self.returning_to_spaceship = False
                if self.carrying_fruit:
                    self.carrying_fruit = False
                    self.spaceship.add_tomato()
        else:
            if self.roaming_target != self.spaceship:
                fruit = self.roaming_target
            else:
                fruit = self.spaceship.get_available_fruit()

            if self.spaceship.near_target_sector and fruit is not None:
                if not fruit.has_fruit or fruit.plant.was_deleted:
                    # Return to space ship, as there's nothing to grab here
                    self.returning_to_spaceship = True

                self.reparent_to(fruit)
                new_roaming_offset, did_arrive = self.fly_towards_target(
                    self.FLYING_SPEED_NON_CARRYING
                )
                if did_arrive:
                    self.carrying_fruit = (
                        fruit.has_fruit and not fruit.plant.was_deleted
                    )
                    fruit.plant.shake()
                    fruit.has_fruit = False
                    self.returning_to_spaceship = True
            else:
                self.roaming_target = self.spaceship
                new_roaming_offset = Vector2(
                    self.spaceship.sprite.width / 2 * math.sin(angle),
                    self.spaceship.sprite.height / 2 * math.cos(angle),
                )

        self.x_direction = -1 if new_roaming_offset.x < self.roaming_offset.x else +1
        self.roaming_offset = new_roaming_offset

    def draw_fly_at(self, ctx, pos, direction, scale_up):
        self.aabb = None

        fly_sprite = self.sprite_animation.get(ctx)
        fly_offset = -fly_sprite.size / 2
        fly_offset.x *= direction

        ctx.modelview_matrix_stack.push()

        position = pos + fly_offset * scale_up
        rotation = self.spaceship.coordinates.angle_degrees / 180 * math.pi

        if self.trash_time > 0:
            # Fly escapes into space
            ctx.modelview_matrix_stack.translate(
                *(self.get_world_position().normalize() * (10 * self.trash_time))
            )
            rotation += self.trash_time * 0.1 * self.trash_rotation_direction

        ctx.modelview_matrix_stack.translate(*self.get_world_position())
        ctx.modelview_matrix_stack.rotate(rotation)
        ctx.modelview_matrix_stack.translate(*-self.get_world_position())

        corners = ctx.sprite(
            fly_sprite,
            position,
            scale=Vector2(direction, 1) * scale_up,
            z_layer=ctx.LAYER_FLIES,
        )

        if self.carrying_fruit:
            fly_offset += Vector2(0, fly_sprite.height / 2)
            corners.extend(
                ctx.sprite(
                    self.artwork.get_ripe_tomato(),
                    position,
                    scale=Vector2(direction, 1) * scale_up,
                    z_layer=ctx.LAYER_FRUIT,
                )
            )

        planet = self.game.planet

        if not self.game.drawing_minimap and self.get_world_position().length() < (
            planet.radius + planet.atmosphere_height
        ):
            self.aabb = aabb_from_points(
                [ctx.transform_to_screenspace(p) for p in corners]
            )
            self.aabb = self.aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )

        if self.aabb is not None:
            self.game.debug_aabb.insert(
                0, (LABEL_FLY, Color(255, 0, 0), self.aabb, self, CLICK_PRIORITY_FLY)
            )

        ctx.modelview_matrix_stack.pop()

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        self.draw_fly_at(ctx, self.get_world_position(), self.x_direction, scale_up)


class Spaceship(IUpdateReceiver, IDrawable):
    ELEVATION_BEGIN = 2000
    # ELEVATION_BEGIN = 600
    ELEVATION_DOWN = 300

    def __init__(self, game, planet, artwork):
        self.game = game
        self.planet = planet
        self.artwork = artwork
        self.sprite = artwork.get_spaceship()
        self.target_sector = self.pick_target_sector()
        self.near_target_sector = False
        self.coordinates = PlanetSurfaceCoordinates(
            self.target_sector.get_center_angle(), elevation=self.ELEVATION_BEGIN
        )
        self.target_coordinates = PlanetSurfaceCoordinates(
            self.target_sector.get_center_angle(), elevation=self.ELEVATION_DOWN
        )
        self.ticks = 0
        self.flies = []
        self.dead_flies = []

        self.total_collected_tomatoes = 0
        self.tomato_to_fly_counter = 0

        self.breed_flies_if_needed()

    def add_tomato(self):
        self.total_collected_tomatoes += 1
        self.tomato_to_fly_counter += 1
        if (
            self.tomato_to_fly_counter
            == ImportantParameterAffectingGameplay.TOMATO_TO_FLY
            and len(self.flies) < ImportantParameterAffectingGameplay.MAX_NUM_FLIES
        ):
            self.add_fly()
            self.tomato_to_fly_counter = 0

    def add_fly(self):
        self.flies.append(
            FruitFly(self.game, self, self.artwork, random.uniform(0, 2 * math.pi))
        )

    def breed_flies_if_needed(self):
        flies_to_add = ImportantParameterAffectingGameplay.MIN_NUM_FLIES - len(
            self.flies
        )
        for _ in range(
            flies_to_add
        ):  # we implicitly use that range of a negative value is an empty sequence
            self.add_fly()

    def get_available_fruit(self):
        for fruit in self.target_sector.ripe_fruits:
            if not any(fly.roaming_target == fruit for fly in self.flies):
                return fruit

        return None

    def current_sector_cleared(self):
        return self.near_target_sector and all(
            fly.roaming_target == self and not fly.returning_to_spaceship
            for fly in self.flies
        )

    def pick_target_sector(self):
        if CLIARGS.debug:
            return self.game.sectors[0]
        sectors_with_ripe_fruits = [
            sector for sector in self.game.sectors if len(sector.ripe_fruits) > 0
        ]
        sectors_to_choose = sectors_with_ripe_fruits or self.game.sectors
        return random.choice(sectors_to_choose)

    def get_world_position(self):
        return self.planet.at(self.coordinates)

    def update(self):
        self.ticks += 1

        if self.is_time_to_breed_flies():
            self.breed_flies_if_needed()

        if self.is_time_to_move_to_other_sector() and self.current_sector_cleared():
            self.target_sector = self.pick_target_sector()

        now = self.game.renderer.now
        self.target_coordinates.angle_degrees = (
            self.target_sector.get_center_angle() + 10 * math.sin(now / 10)
        )
        self.target_coordinates.elevation = self.ELEVATION_DOWN + 30 * math.cos(now)
        self.coordinates = self.coordinates.lerp(
            target=self.target_coordinates, alpha=0.01
        )

        self.near_target_sector = (
            self.coordinates.elevation < self.ELEVATION_DOWN + 50
        ) and (
            abs(self.coordinates.angle_degrees - self.target_sector.get_center_angle())
            < 15
        )

        for fly in self.flies:
            fly.update()

        for dead_fly in self.dead_flies:
            dead_fly.trash_time += 1

        self.dead_flies = [
            dead_fly for dead_fly in self.dead_flies if dead_fly.trash_time < 3 * 60
        ]

    def is_time_to_breed_flies(self):
        return (
            self.ticks % ImportantParameterAffectingGameplay.BREEDING_EVERY_N_TICKS == 0
        )

    def is_time_to_move_to_other_sector(self):
        return (
            self.ticks
            % ImportantParameterAffectingGameplay.MOVING_TO_OTHER_SECTOR_EVERY_N_TICKS
            == 0
        )

    def draw(self, ctx):
        scale_up = 1 + self.game.get_zoom_adjustment()

        ctx.modelview_matrix_stack.push()
        self.planet.apply_planet_surface_transform(self.coordinates)
        ctx.sprite(
            self.sprite,
            -self.sprite.size / 2 * scale_up,
            Vector2(scale_up, scale_up),
        )

        ctx.modelview_matrix_stack.pop()

        for fly in self.flies:
            fly.draw(ctx)

        for dead_fly in self.dead_flies:
            dead_fly.draw(ctx)


class Sector(IUpdateReceiver, IDrawable, IClickReceiver):
    def __init__(self, game, index, base_angle):
        self.game = game
        self.index = index
        self.base_angle = base_angle
        self.number_of_plants = random.choice([2, 3, 5, 6])
        self.sector_width_degrees = {2: 5, 3: 6, 5: 14, 6: 14}[
            self.number_of_plants
        ] * 3
        self.fertility = int(
            random.uniform(*ImportantParameterAffectingGameplay.FERTILITY)
        )
        self.growth_speed = (
            random.uniform(0.02, 0.06)
            * ImportantParameterAffectingGameplay.GROWTH_SPEED
        )
        self.rotting_speed = random.uniform(0.01, 0.02)
        self.plants = []
        self.make_new_plants()
        self.aabb = None  # axis-aligned bounding box
        self.ripe_fruits = []
        self.plant_trash_heap = []

    def get_center_angle(self):
        return self.base_angle + self.sector_width_degrees / 2

    def clicked(self):
        logging.debug(f"ouch, i'm a sector! {self.index}")
        return False

    def make_new_plants(self):
        for plant in self.plants:
            plant.was_deleted = True
            self.plant_trash_heap.append(plant)

        self.plants = []
        for j in range(self.number_of_plants):
            coordinate = PlanetSurfaceCoordinates(
                self.base_angle
                + self.sector_width_degrees * (j / (self.number_of_plants - 1))
            )
            self.plants.append(
                Plant(
                    self,
                    self.game.planet,
                    coordinate,
                    self.fertility,
                    self.game.artwork,
                )
            )

    def replant(self, plant):
        plant.was_deleted = True
        plant.artwork.get_random_mowing_sound().play()
        self.plant_trash_heap.append(plant)
        index = self.plants.index(plant)
        self.plants[index] = Plant(
            self, self.game.planet, plant.position, self.fertility, self.game.artwork
        )

    def invalidate_aabb(self):
        self.aabb = None
        for plant in self.plants:
            plant.need_aabb = True

    def update(self):
        for plant in self.plants:
            plant.update()

        for plant in self.plant_trash_heap:
            plant.trash_time += 1

        self.plant_trash_heap = [
            plant for plant in self.plant_trash_heap if plant.trash_time < 3 * 60
        ]

    def draw(self, ctx):
        self.aabb = None
        self.ripe_fruits = []

        for plant in self.plant_trash_heap:
            plant.draw(ctx)

        for plant in self.plants:
            plant.draw(ctx)
            if plant.root_aabb is not None:
                self.game.debug_aabb.append(
                    (
                        f"{LABEL_PLANT} ({plant.health:.0f}%)",
                        Color(0, 128, 128),
                        plant.root_aabb,
                        plant,
                        CLICK_PRIORITY_PLANT,
                    )
                )
                if self.aabb is None:
                    self.aabb = Rect(plant.aabb)
                else:
                    self.aabb = self.aabb.union(plant.aabb)

        if self.aabb is not None:
            self.game.debug_aabb.append(
                (
                    f"{LABEL_SECTOR} {self.index}",
                    Color(128, 255, 128),
                    self.aabb,
                    self,
                    CLICK_PRIORITY_SECTOR,
                )
            )


class Plant(IUpdateReceiver, IClickReceiver):
    AABB_PADDING_PX = 40
    CURSOR = "cut"

    def __init__(
        self,
        sector: Sector,
        planet: Planet,
        position: PlanetSurfaceCoordinates,
        fertility,
        artwork: Artwork,
    ):
        super().__init__()

        self.sector = sector
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.need_aabb = True
        self.aabb_points = []
        self.aabb = None
        self.root_aabb = None

        self.growth = 0
        self.health = 100
        self.fertility = fertility

        self.wind_phase = random.uniform(0, 2 * math.pi)
        self.wind_speed = random.uniform(0.9, 1.3)
        self.wind_amplitude = 0

        length = random.uniform(100, 500) * (0.5 + 0.5 * self.fertility / 100) / 2

        self.root = Branch(phase=0, length=length, leftright=+1, depth=0, plant=self)
        self.root.grow()
        self.root.grow()
        self.root.grow()
        self.root.moregrow()

        self.was_deleted = False

        self.trash_rotation_direction = random.choice([-1, +1])
        self.trash_time = 0

    def clicked(self):
        logging.debug("in class Plant.clicked")
        self.sector.replant(self)
        return True

    def shake(self):
        # shake the plant
        if self.wind_amplitude <= 0:
            self.wind_amplitude = 90
        else:
            # if we have already been shaking,
            # shake in the other direction
            self.wind_amplitude = -90

    def update(self):
        if self.growth < 100:
            self.growth += self.sector.growth_speed
            self.growth = min(100, self.growth)
            self.need_aabb = True
        else:
            self.health -= self.sector.rotting_speed
            self.health = max(0, self.health)
            self.need_aabb = True

        if self.wind_amplitude > 0:
            self.wind_amplitude -= 1
        elif self.wind_amplitude < 0:
            self.wind_amplitude += 1

        self.root.update()

    def draw(self, ctx):
        factor = self.growth / 100

        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        if self.trash_time > 0:
            # Plant escapes into space
            approx_height = self.root.length * self.growth / 100
            ctx.modelview_matrix_stack.translate(0, -self.trash_time * 10)
            ctx.modelview_matrix_stack.translate(0, -approx_height / 2)
            ctx.modelview_matrix_stack.rotate(
                self.trash_time * 0.1 * self.trash_rotation_direction
            )
            ctx.modelview_matrix_stack.translate(0, +approx_height / 2)

        self.root.draw(ctx, Vector2(0, 0), factor, 0.0, self.health)

        if self.need_aabb and self.aabb_points:
            self.aabb = aabb_from_points(self.aabb_points)
            self.aabb = self.aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )
            self.root_aabb = aabb_from_points(self.aabb_points[:1])
            self.root_aabb = self.root_aabb.inflate(
                self.AABB_PADDING_PX * 2, self.AABB_PADDING_PX * 2
            )
            self.aabb_points = []
            self.need_aabb = False

        ctx.modelview_matrix_stack.pop()


class Rock(IDrawable):
    def __init__(
        self, planet: Planet, position: PlanetSurfaceCoordinates, artwork: Artwork
    ):
        self.planet = planet
        self.position = position
        self.artwork = artwork

        self.rock = artwork.get_random_rock()

    def draw(self, ctx):
        ctx.modelview_matrix_stack.push()

        self.planet.apply_planet_surface_transform(self.position)

        ctx.sprite(self.rock, Vector2(-self.rock.width / 2, -self.rock.height + 10))

        ctx.modelview_matrix_stack.pop()


class HarvestedTomato(IUpdateReceiver, IDrawable):
    def __init__(self, game, screenspace_position, target_position, duration):
        self.game = game
        self.sprite = game.artwork.get_ripe_tomato()
        self.position = screenspace_position
        self.start_position = Vector2(screenspace_position)
        self.target_position = Vector2(target_position)
        self.duration = duration
        self.started = game.renderer.now
        self.done = False

    def update(self):
        alpha = max(0, min(1, (self.game.renderer.now - self.started) / self.duration))
        if alpha == 1 and not self.done:
            self.done = True
            self.game.tomato_score += 1
        alpha = 1 - (1 - alpha) ** 2
        self.position = (1 - alpha) * self.start_position + alpha * self.target_position

    def draw(self, ctx):
        ctx.sprite(self.sprite, self.position - self.sprite.size / 2)
