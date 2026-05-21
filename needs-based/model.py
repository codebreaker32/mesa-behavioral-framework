"""Needs-Based Homeostatic Agent Model."""

from __future__ import annotations

import mesa
from mesa.discrete_space import OrthogonalMooreGrid
from mesa.experimental.data_collection import DataRecorder
from mesa.experimental.scenarios import Scenario

from agents import FoodPatch, NeedsAgent, WaterPatch


# Scenario

class NeedsBasedScenario(Scenario):
    """All tunable parameters for the needs-based model.

    Symbol comments map directly to README.md §2 variable definitions.
    """

    # Grid
    width: int = 25
    height: int = 25

    # Population
    initial_population: int = 50
    initial_energy_min: float = 60.0
    initial_energy_max: float = 90.0
    initial_hydration_min: float = 60.0
    initial_hydration_max: float = 90.0

    # Biology
    energy_max: float = 100.0
    hydration_max: float = 100.0
    decay_energy: float = 1.0        # λ_E
    decay_hydration: float = 1.5     # λ_H
    vision: int = 3                  # v

    # Reproduction
    repro_energy_cost: float = 15.0       # ΔE_cost
    repro_hydration_cost: float = 10.0    # ΔH_cost
    repro_cooldown: float = 5.0           # τ

    # Decision thresholds (Eq. 14)
    theta_energy: float = 30.0      # θ_E
    theta_hydration: float = 30.0   # θ_H
    phi_energy: float = 70.0        # φ_E
    phi_hydration: float = 70.0     # φ_H

    # Environment
    food_patch_density: float = 0.15
    water_patch_density: float = 0.10
    food_regrowth_time: int = 8      # T_F
    water_regrowth_time: int = 12    # T_W
    food_energy_value: float = 40.0
    water_hydration_value: float = 50.0


# Model

class NeedsBasedModel(mesa.Model):
    """Needs-based homeostatic model with FoodPatch and WaterPatch agents."""

    def __init__(self, scenario: NeedsBasedScenario = None):
        if scenario is None:
            scenario = NeedsBasedScenario()
        super().__init__(scenario=scenario)

        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height),
            torus=True,
            random=self.random,
        )

        # Step-level birth/death counters reset at the top of each step
        self._deaths_this_step = 0
        self._births_this_step = 0

        self._seed_patches(scenario)
        self._spawn_agents(scenario)
        self._setup_data_collection()

        self.running = True

    # Initialisation helpers

    def _seed_patches(self, s: NeedsBasedScenario) -> None:
        """Place FoodPatch and WaterPatch agents across the grid."""
        for cell in self.grid:
            if self.random.random() < s.food_patch_density:
                FoodPatch(self, cell,
                          regrowth_time=s.food_regrowth_time,
                          energy_value=s.food_energy_value)
            if self.random.random() < s.water_patch_density:
                WaterPatch(self, cell,
                           regrowth_time=s.water_regrowth_time,
                           hydration_value=s.water_hydration_value)

    def _spawn_agents(self, s: NeedsBasedScenario) -> None:
        """Place N agents on random cells with randomised initial states."""
        cells = list(self.grid)
        for cell in self.random.choices(cells, k=s.initial_population):
            NeedsAgent(
                self,
                cell,
                energy=self.random.uniform(s.initial_energy_min, s.initial_energy_max),
                hydration=self.random.uniform(s.initial_hydration_min, s.initial_hydration_max),
                energy_max=s.energy_max,
                hydration_max=s.hydration_max,
                decay_energy=s.decay_energy,
                decay_hydration=s.decay_hydration,
                vision=s.vision,
                repro_energy_cost=s.repro_energy_cost,
                repro_hydration_cost=s.repro_hydration_cost,
                repro_cooldown=s.repro_cooldown,
                theta_energy=s.theta_energy,
                theta_hydration=s.theta_hydration,
                phi_energy=s.phi_energy,
                phi_hydration=s.phi_hydration,
            )

    def _setup_data_collection(self) -> None:
        self.recorder = DataRecorder(self)
        self.data_registry.track_model(
            self,
            "model_data",
            [
                "count_agents",
                "mean_energy",
                "mean_hydration",
                "deaths_this_step",
                "births_this_step",
                "food_available",
                "water_available",
            ],
        ).record(self.recorder)

    # Metrics (referenced by name in data_registry.track_model)

    @property
    def count_agents(self) -> int:
        return len(self.agents_by_type.get(NeedsAgent, []))

    @property
    def mean_energy(self) -> float:
        agents = list(self.agents_by_type.get(NeedsAgent, []))
        return sum(a.energy for a in agents) / len(agents) if agents else 0.0

    @property
    def mean_hydration(self) -> float:
        agents = list(self.agents_by_type.get(NeedsAgent, []))
        return sum(a.hydration for a in agents) / len(agents) if agents else 0.0

    @property
    def deaths_this_step(self) -> int:
        return self._deaths_this_step

    @property
    def births_this_step(self) -> int:
        return self._births_this_step

    @property
    def food_available(self) -> int:
        return sum(
            1 for p in self.agents_by_type.get(FoodPatch, []) if p.has_food
        )

    @property
    def water_available(self) -> int:
        return sum(
            1 for p in self.agents_by_type.get(WaterPatch, []) if p.has_water
        )

    # Step

    def step(self) -> None:
        """Activate all NeedsAgents in random order, then record metrics."""
        self._deaths_this_step = 0
        self._births_this_step = 0

        # Snapshot the living agent list before activation
        agents_this_step = list(self.agents_by_type.get(NeedsAgent, []))
        pop_start = len(agents_this_step)
        
        self.random.shuffle(agents_this_step)
        for agent in agents_this_step:
            agent.step()
            
            # Count births natively via the flag
            if agent.gave_birth_this_step:
                self._births_this_step += 1

        # Calculate deaths cleanly via population delta
        pop_end = self.count_agents
        self._deaths_this_step = (pop_start + self._births_this_step) - pop_end

        # DataRecorder samples all tracked properties automatically
        # when the model time advances.


# Entry point

if __name__ == "__main__":
    STEPS = 200
    SEED  = 42

    model = NeedsBasedModel(scenario=NeedsBasedScenario(seed=SEED))
    model.run_for(STEPS)
    df = model.recorder.get_table_dataframe("model_data")
    print(df.to_string())
