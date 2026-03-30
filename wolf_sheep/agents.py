from mesa.discrete_space import CellAgent, FixedAgent
from mesa.experimental.behaviorals.behavioral_agent import BehavioralAgent
from mesa.experimental.behaviorals.state import BehavioralState
from mesa.experimental.behaviorals.decision import rule, RulePriority

class Animal(BehavioralAgent, CellAgent):
    """Base animal using BehavioralAgent convenience class."""
    
    energy = BehavioralState(decay_rate=-1.0, min_value=0.0, thresholds={"starving": 0.0})

    def __init__(
        self, model, energy=8, p_reproduce=0.04, energy_from_food=4, cell=None
    ):
        super().__init__(model)
        self.p_reproduce = p_reproduce
        self.energy_from_food = energy_from_food
        self.cell = cell
        self.energy = energy

    def step(self):
        self.sync_states()
        super().step()

    # DECLARATIVE RULES (Parent defines the rules)

    @rule(
        condition=lambda self: self.energy <= 0, 
        priority=RulePriority.CRITICAL
    )
    def die(self):
        """Critical: Die if starved."""
        self.remove()

    @rule(
        condition=lambda self: self.energy > 15 and self.random.random() < self.p_reproduce,
        priority=RulePriority.URGENT
    )
    def reproduce(self):
        """Urgent: Reproduce if well-fed and lucky."""
        self.spawn_offspring()

    @rule(
        condition=lambda self: self.can_feed(), 
        priority=RulePriority.HIGH
    )
    def feed(self):
        """High: Feed if food is available. 
        (Implementation overridden by subclasses!)"""
        pass

    @rule(
        condition=lambda self: True, 
        priority=RulePriority.DEFAULT
    )
    def move(self):
        """Default: Wander if nothing else to do."""
        self.cell = self.cell.neighborhood.select_random_cell()

    # Base Implementations

    def spawn_offspring(self):
        self.energy /= 2
        self.__class__(
            self.model, self.energy, self.p_reproduce, self.energy_from_food, self.cell
        )

    def can_feed(self) -> bool:
        return False


class Sheep(Animal):
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

    def move(self):
        """Move towards a cell where there isn't a wolf, and preferably with grown grass."""
        cells_without_wolves = []
        cells_with_grass = []

        for cell in self.cell.neighborhood:
            has_wolf = False
            has_grass = False

            for obj in cell.agents:
                # If there's a wolf, we can early exit
                if isinstance(obj, Wolf):
                    has_wolf = True
                    break
                elif isinstance(obj, GrassPatch) and obj.fully_grown:
                    has_grass = True

            # Prefer cells without wolves
            if not has_wolf:
                cells_without_wolves.append(cell)

                # Among safe cells, pick those with grown grass
                if has_grass:
                    cells_with_grass.append(cell)

        # If all surrounding cells have wolves, stay put
        if len(cells_without_wolves) == 0:
            return

        # Move to a cell with grass if available, otherwise move to any safe cell
        target_cells = (
            cells_with_grass if len(cells_with_grass) > 0 else cells_without_wolves
        )
        self.cell = self.random.choice(target_cells)


class Wolf(Animal):
    def can_feed(self):
        return any(isinstance(obj, Sheep) for obj in self.cell.agents)

    def feed(self):
        sheep = [obj for obj in self.cell.agents if isinstance(obj, Sheep)]
        if sheep:
            sheep_to_eat = self.random.choice(sheep)
            self.energy += self.energy_from_food
            sheep_to_eat.remove()

    def move(self):
        """Smart Hunting: Track adjacent sheep instead of wandering blindly."""
        sheep_cells = []
        for cell in self.cell.neighborhood:
            if any(isinstance(obj, Sheep) for obj in cell.agents):
                sheep_cells.append(cell)
        
        # If there are sheep nearby, chase them! Otherwise, wander.
        if sheep_cells and self.random.random() > 0.3:  # 70% chance to chase if sheep are nearby
            self.cell = self.random.choice(sheep_cells)
        else:
            self.cell = self.cell.neighborhood.select_random_cell()


class GrassPatch(FixedAgent):
    """Grass that regrows after being eaten. Inherits FixedAgent."""
    
    def __init__(self, model, countdown, grass_regrowth_time, cell):
        super().__init__(model)
        self.fully_grown = countdown == 0
        self.grass_regrowth_time = grass_regrowth_time
        self.cell = cell

        if not self.fully_grown:
            self._schedule_regrowth(countdown)

    def _schedule_regrowth(self, delay: int):
        self.model.schedule_event(self.regrow, after=delay)

    def regrow(self):
        self.fully_grown = True

    def get_eaten(self):
        self.fully_grown = False
        self._schedule_regrowth(self.grass_regrowth_time)