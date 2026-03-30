"""
Wolf-Sheep Predation Model
==============================

Replication of the model found in NetLogo:
    Wilensky, U. (1997). NetLogo Wolf Sheep Predation model.
    http://ccl.northwestern.edu/netlogo/models/WolfSheepPredation.
    Center for Connected Learning and Computer-Based Modeling,
    Northwestern University, Evanston, IL.
"""

import math

from mesa import Model
from mesa.discrete_space import OrthogonalVonNeumannGrid
from mesa.experimental.scenarios import Scenario
from mesa.experimental.data_collection import DataRecorder

from agents import GrassPatch, Sheep, Wolf


class WolfSheepScenario(Scenario):
    """Parameters for the Wolf-Sheep model.

    Attributes:
        width: Grid width.
        height: Grid height.
        initial_sheep: Starting sheep count.
        initial_wolves: Starting wolf count.
        sheep_reproduce: Per-step reproduction probability for sheep.
        wolf_reproduce: Per-step reproduction probability for wolves.
        wolf_gain_from_food: Energy a wolf gains from eating one sheep.
        grass: Whether sheep consume grass for energy.
        grass_regrowth_time: Steps until a eaten grass patch regrows.
        sheep_gain_from_food: Energy sheep gain from eating fully-grown grass.
    """

    width: int = 20
    height: int = 20
    initial_sheep: int = 100
    initial_wolves: int = 50
    sheep_reproduce: float = 0.04
    wolf_reproduce: float = 0.05
    wolf_gain_from_food: float = 20.0
    grass: bool = True
    grass_regrowth_time: int = 30
    sheep_gain_from_food: float = 4.0


class WolfSheep(Model):
    """Wolf-Sheep Predation Model."""

    description = (
        "A model for simulating wolf and sheep (predator-prey) ecosystem modelling."
    )

    def __init__(self, scenario: WolfSheepScenario = WolfSheepScenario):
        super().__init__(scenario=scenario)

        self.height = scenario.height
        self.width = scenario.width
        self.grass = scenario.grass

        self.grid = OrthogonalVonNeumannGrid(
            [self.height, self.width],
            torus=True,
            capacity=math.inf,
            random=self.random,
        )

        self.recorder = DataRecorder(self)

        tracked = ["count_wolves", "count_sheep"]
        if self.grass:
            tracked.append("count_grass")

        self.data_registry.track_model(
            self, "model_data", tracked
        ).record(self.recorder)

        Sheep.create_agents(
            self,
            scenario.initial_sheep,
            energy=self.rng.random((scenario.initial_sheep,))
                   * 2 * scenario.sheep_gain_from_food,
            p_reproduce=scenario.sheep_reproduce,
            energy_from_food=scenario.sheep_gain_from_food,
            cell=self.random.choices(
                self.grid.all_cells.cells, k=scenario.initial_sheep
            ),
        )

        Wolf.create_agents(
            self,
            scenario.initial_wolves,
            energy=self.rng.random((scenario.initial_wolves,))
                   * 2 * scenario.wolf_gain_from_food,
            p_reproduce=scenario.wolf_reproduce,
            energy_from_food=scenario.wolf_gain_from_food,
            cell=self.random.choices(
                self.grid.all_cells.cells, k=scenario.initial_wolves
            ),
        )

        if self.grass:
            for cell in self.grid:
                fully_grown = self.random.choice([True, False])
                countdown = (
                    0 if fully_grown
                    else self.random.randrange(0, scenario.grass_regrowth_time)
                )
                GrassPatch(self, countdown, scenario.grass_regrowth_time, cell)

        self.running = True


    @property
    def count_sheep(self) -> int:
        return len(self.agents_by_type.get(Sheep, []))

    @property
    def count_wolves(self) -> int:
        return len(self.agents_by_type.get(Wolf, []))

    @property
    def count_grass(self) -> int:
        """Number of fully-grown grass patches."""
        patches = self.agents_by_type.get(GrassPatch, [])
        return sum(1 for p in patches if p.fully_grown)

    def step(self) -> None:
        """Activate all sheep, then all wolves."""
        self.agents_by_type[Sheep].shuffle_do("step")
        self.agents_by_type[Wolf].shuffle_do("step")


if __name__ == "__main__":
    for rng in [42,99,1234,1467]:
        model = WolfSheep(scenario=WolfSheepScenario(rng=rng))
        model.run_for(150)
        df = model.recorder.get_table_dataframe("model_data")
        df.to_csv(f"data/wolf_sheep_rng{rng}.csv", index=False)