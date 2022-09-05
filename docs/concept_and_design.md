# Red Planted Design Considerations

This document is a work in progress.
It aims to facilitate collaboration and make it easier
to join our project.

## Game Objective

Tend to your plants, defend you garden against nasty fruit flies
and harvest as many tomatoes as possible.

![Overview](init_discussion/red_planted.png)

Dynamics:
* You can grow your garden by tending to it.
* You need to defend your fruits against fruit flies.
* Fruit flies reproduce (if the find more food).

*Thought: this sounds like an unstable ecosystem :D*

## User Interactions

As a user you can
* Plant seeds
* Water the plants
* Scare aways (kill?) fruit flies with gas (naming)
* Hit (kill?) fruit flies with a fly flap
* Harvest (pick) tomatoes

Harvesting tomatoes earns you *tomato scores*!

## Objects

Our world consists of...

**The red planet**
- Forms the center of the coordinate system
- Has a water level (that plants draw from)

**Plants**
- Has a location
- Needs water (and light)
- Evolves, states: seed, seedling, plant, dead (?)

**Tomatoes**
- Grow on plants
- Attract flies
- Evolves, states: green, yellow, red

**Fruit flies**
- Has a location
- Moves at random
- Is attracted to tomatoes

## Technical Aspects

The planet coordinate system is the global coordinate system.
Planet coordinates are [polar coordinates](https://en.wikipedia.org/wiki/Polar_coordinate_system), i.e.
- r: radius
- phi: angle (in degree (not radians) because pygame like degrees)

![Cartesian and polar coordinates](https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Polar_to_cartesian.svg/1024px-Polar_to_cartesian.svg.png)

Objects (plants, flies, tomatoes, …) that live on the planet, use the planet's coordinate system.

Every object we want to draw needs a `draw(self, window)` method (IDrawable?)
Every object that evolves has an `update(self, *args, **kwargs)` method (IUpdateable?)
