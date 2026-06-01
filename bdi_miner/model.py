"""BDI Gold Miner Model"""

from __future__ import annotations

import mesa
from mesa.discrete_space import OrthogonalMooreGrid
from mesa.experimental.data_collection import DataRecorder
from mesa.experimental.scenarios import Scenario

from agents import BDIMiner, GoldMine, Market


class BDIScenario(Scenario):
    """Tunable parameters for the BDI Gold Miner model."""

    # Symbol comments map directly to ARCHITECTURE.pdf §2.

    # Grid
    width: int  = 30
    height: int = 30

    # Population
    initial_miners: int = 30

    # Agent parameters
    vision: int           = 5
    carry_capacity: int   = 5
    energy_max: float     = 100.0

    # Environment
    n_mines: int             = 8
    mine_capacity: int       = 5      # κ_M
    mine_regen_time: int     = 20     # T_M
    n_markets: int           = 3
    market_base_price: float = 10.0   # p_0


class BDIModel(mesa.Model):
    """BDI Gold Miner model."""

    def __init__(self, scenario: BDIScenario = None) -> None:
        if scenario is None:
            scenario = BDIScenario()
        super().__init__(scenario=scenario)

        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height),
            torus=True,
            random=self.random,
        )

        self._deaths_this_step = 0

        self._place_mines(scenario)
        self._place_markets(scenario)
        self._spawn_miners(scenario)
        self._setup_data_collection()

        self.running = True

    # Initialisation

    def _place_mines(self, s: BDIScenario) -> None:
        """Seed n_mines GoldMine agents on distinct random cells."""
        for cell in self.random.sample(list(self.grid), k=s.n_mines):
            GoldMine(self, cell,
                     capacity=s.mine_capacity,
                     regen_time=s.mine_regen_time)

    def _place_markets(self, s: BDIScenario) -> None:
        for cell in self.random.sample(list(self.grid), k=s.n_markets):
            Market(self, cell, base_price=s.market_base_price)

    def _spawn_miners(self, s: BDIScenario) -> None:
        """Place initial_miners BDIMiner agents on random cells."""
        for cell in self.random.choices(list(self.grid), k=s.initial_miners):
            BDIMiner(self, cell,
                     vision=s.vision,
                     carry_capacity=s.carry_capacity,
                     energy_max=s.energy_max)

    def _setup_data_collection(self) -> None:
        """Wire DataRecorder to model-level metric properties."""
        self.recorder = DataRecorder(self)
        self.data_registry.track_model(
            self,
            "model_data",
            [
                "count_miners",
                "mean_wealth",
                "mean_gold_held",
                "mean_energy",
                "gold_in_mines",
                "deaths_this_step",
            ],
        ).record(self.recorder)

    # Metrics

    @property
    def count_miners(self) -> int:
        return len(self.agents_by_type.get(BDIMiner, []))

    @property
    def mean_wealth(self) -> float:
        miners = list(self.agents_by_type.get(BDIMiner, []))
        return sum(a.wealth for a in miners) / len(miners) if miners else 0.0

    @property
    def mean_gold_held(self) -> float:
        miners = list(self.agents_by_type.get(BDIMiner, []))
        return sum(a.gold_held for a in miners) / len(miners) if miners else 0.0

    @property
    def mean_energy(self) -> float:
        miners = list(self.agents_by_type.get(BDIMiner, []))
        return sum(a.energy for a in miners) / len(miners) if miners else 0.0

    @property
    def gold_in_mines(self) -> int:
        return sum(m.gold for m in self.agents_by_type.get(GoldMine, []))

    @property
    def deaths_this_step(self) -> int:
        return self._deaths_this_step

    # Step

    def step(self) -> None:
        """Activate all miners in random order, then record metrics.

        Market prices reset before agent activation so all miners see a
        consistent price baseline at the start of each step. Because all
        miners activate within the same synchronous tick, a miner cannot
        observe price changes from miners that activate later — true
        asynchronous price discovery is impossible in a synchronous scheduler.
        """
        self.agents_by_type[Market].do("reset_price")

        miners_before = self.count_miners
        self.agents_by_type[BDIMiner].shuffle_do("step")

        # Deaths via population delta — Eq. 19
        self._deaths_this_step = miners_before - self.count_miners


if __name__ == "__main__":
    STEPS = 200

    model = BDIModel(scenario=BDIScenario(seed=42))
    model.run_for(STEPS)

    df = model.recorder.get_table_dataframe("model_data")
    print(df.to_string())