"""Wolf-Sheep Predation with Behavioral Framework - Updated API

Demonstrates the new convenience APIs:
- BehavioralAgent base class (wires Task, Decision, State together)
- @rule decorator for declarative rule definition
- Lazy decay BehavioralState (no event scheduling)
- Centralized decision evaluation in model
"""

from mesa.discrete_space import CellAgent
from mesa.experimental.behaviorals.behavioral_agent import BehavioralAgent
from mesa.experimental.behaviorals.state import BehavioralState
from mesa.experimental.behaviorals.decision import rule, RulePriority
from mesa.experimental.behaviorals.task import Task
from mesa.time import Priority


class Animal(BehavioralAgent, CellAgent):
    """Base animal using BehavioralAgent convenience class.
    
    BehavioralAgent automatically provides:
    - self.task_manager (TaskManager)
    - self.decision_system (DecisionSystem)
    - @rule decorator support
    - sync_states() for materializing lazy decay
    """
    
    # STATE - Energy decays automatically by 1 per time unit (lazy evaluation)
    energy = BehavioralState(
        decay_rate=-1.0,
        min_value=0.0,
        thresholds={"starving": 5.0, "hungry": 15.0}
    )

    def __init__(
        self, model, energy=8, p_reproduce=0.04, energy_from_food=4, cell=None
    ):
        # BehavioralAgent.__init__ sets up task_manager and decision_system
        super().__init__(model)
        
        self.p_reproduce = p_reproduce
        self.energy_from_food = energy_from_food
        self.cell = cell
        
        # Initialize state (triggers lazy decay clock)
        self.energy = energy

    # DECLARATIVE RULES using @rule decorator

    @rule(
        condition=lambda self: self.energy <= 0,
        priority=RulePriority.CRITICAL,
        name="die_of_starvation"
    )
    def die(self):
        """Critical: Die if starved."""
        return Task(self, duration=0.0, action=self.remove, priority=Priority.HIGH)

    @rule(
        condition=lambda self: self.energy > 15 and self.random.random() < self.p_reproduce,
        priority=RulePriority.URGENT,
        cooldown=3.0,
        name="reproduce"
    )
    def reproduce(self):
        """Urgent: Reproduce if well-fed and lucky."""
        return Task(
            self,
            duration=2.0,
            action=self.spawn_offspring,
            priority=Priority.DEFAULT
        )

    @rule(
        condition=lambda self: self.can_feed(),
        priority=RulePriority.HIGH,
        name="feed"
    )
    def feed_rule(self):
        """High: Feed if food is available."""
        return Task(
            self,
            duration=1.0,
            action=self.feed,
            priority=Priority.DEFAULT
        )

    @rule(
        condition=lambda self: True,  # Always available as fallback
        priority=RulePriority.DEFAULT,
        name="wander"
    )
    def wander_rule(self):
        """Default: Wander if nothing else to do."""
        return Task(
            self,
            duration=1.0,
            action=self.move,
            priority=Priority.LOW
        )

    # Action implementations

    def spawn_offspring(self):
        """Create offspring by splitting energy."""
        self.energy /= 2
        self.__class__(
            self.model,
            self.energy,
            self.p_reproduce,
            self.energy_from_food,
            self.cell,
        )

    def can_feed(self) -> bool:
        """Fast boolean check for food availability."""
        return False

    def feed(self):
        """Feed action - override in subclasses."""
        pass

    def move(self):
        """Blind movement: Move to any random neighboring cell."""
        self.cell = self.cell.neighborhood.select_random_cell()


class Sheep(Animal):
    """Sheep that graze on grass patches."""
    
    def can_feed(self):
        grass_patch = next(
            (obj for obj in self.cell.agents if isinstance(obj, GrassPatch)), None
        )
        return grass_patch is not None and grass_patch.fully_grown

    def feed(self):
        grass_patch = next(
            (obj for obj in self.cell.agents if isinstance(obj, GrassPatch)), None
        )
        if grass_patch and grass_patch.fully_grown:
            self.energy += self.energy_from_food
            grass_patch.get_eaten()


class Wolf(Animal):
    """Wolf that hunts sheep."""
    
    def can_feed(self):
        return any(isinstance(obj, Sheep) for obj in self.cell.agents)

    def feed(self):
        sheep = [obj for obj in self.cell.agents if isinstance(obj, Sheep)]
        if sheep:
            sheep_to_eat = self.random.choice(sheep)
            self.energy += self.energy_from_food
            sheep_to_eat.remove()


class GrassPatch(CellAgent):
    """Grass that regrows after being eaten."""
    
    def __init__(self, model, countdown, grass_regrowth_time, cell):
        super().__init__(model)
        self.fully_grown = countdown == 0
        self.grass_regrowth_time = grass_regrowth_time
        self.cell = cell

        if not self.fully_grown:
            self._schedule_regrowth(countdown)

    def _schedule_regrowth(self, delay: int):
        self.model.schedule_event(
            self.regrow, at=self.model.time + delay, priority=Priority.DEFAULT
        )

    def regrow(self):
        self.fully_grown = True

    def get_eaten(self):
        self.fully_grown = False
        self._schedule_regrowth(self.grass_regrowth_time)