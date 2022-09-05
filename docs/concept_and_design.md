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
* Fruit flies reproduce (if the find more food) -- in subsequent levels, maybe they get reinforcements (new spaceship, etc..)

*Thought: this sounds like an unstable ecosystem :D*

## User Interactions

As a user you can
* Plant seeds (do you buy seeds with the "tomato score money"?)
  * Can be implemented later
* Water the plants (unlimited water supply?)
* Scare aways (kill?) fruit flies with Good Old Martian Fruit Fly Repellent Spray(tm) -- modeled after Batman Shark Repellent spray?
* Hit (kill?) fruit flies with a fly flap
* Harvest (pick, drag and drop) tomatoes -- if you don't harvest, flies eat it or they spoil and drop to the floor (increases ground fertility? attracts flies?)
* Cut off plants -- scissor tool? (needs to be done for spoiled/dead plants, also for plants that have been fully harvested)
  * Pull out empty plants
* Maybe throw tomatoes at fruit flies as an additional bonus interaction if there's time

For now, we focus on click-actions, i.e. every interaction is a click on the respective item:
- On fly: kill
- On tomato: pick
- On empty plant: pull out

Harvesting tomatoes earns you *tomato scores*! (love it!)

## Objects

Our world consists of...

**Main view**
- Rotate planet by scrolling mouse wheel
- Indicate time (day and night) by changing background color (relates to growth)
- Maybe color gradient for background
- Ideas for later:
  - At night, plants only grow slowly and flies sleep
  - Gardening dynamics could depend on day-night

**The red planet**
- Forms the center of the coordinate system
- Has a local water level (that plants draw from), i.e. their own "ground water"

**Plants**
- Has a location
- Spawn at random
- Needs water (and light), possibly nutrients from the ground (= ground fertility)
  - For now, we only model water
- Grows organically based on algorithmic generation
- Evolves, states: seed, seedling, plant, dead (?)

**Tomatoes**
- Grow on plants
- Attract flies
- Evolves, states: green, yellow, red
- Interactive only when red

**Fruit flies**
- Has a location (is there a 'source' location, some kind of "fruit fly house"? or maybe a "fruit fly spaceship" in orbit?) TODO
- Moves at random (needs SOME kind of state machine probably, e.g. "roam around", "get hungry", "fly towards fruit", "eat", "go back to spaceship?") TODO
- Is attracted to tomatoes within a certain radius
- Can steal tomato
- Click on fly with tomato to kill fly, tomato splashed onto the ground

Nice to have:
There could be a fly spaceship where the tomatoes are collected. Flies depart from this ship.
Flies wear a spacehelmet.
Initially, flies just leave to "off screen".

## Technical Aspects

The planet coordinate system is the global coordinate system.
Planet coordinates are [polar coordinates](https://en.wikipedia.org/wiki/Polar_coordinate_system), i.e.
- r: radius
- phi: angle (in degree (not radians) because pygame like degrees)

![Cartesian and polar coordinates](https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Polar_to_cartesian.svg/1024px-Polar_to_cartesian.svg.png)

Objects (plants, flies, tomatoes, ...) that live on the planet,
use the planet's coordinate system (is this useful? might make sense
that some things just use local coordinates, but are "grafted" to a
certain location on the planet).

Every object we want to draw needs a `draw(self, context)` method.
The "context" provides high-level drawing and can abstract away things
like assets, planet scrolling, etc. -- scene can be drawn "once" to
the context and then we can draw the scene from the context multiple
times (e.g. zoomed-in view and zoomed-out view).

Every object has an `update(self)` method -- delta time could be passed
in or we just grab the time from some global game object?
