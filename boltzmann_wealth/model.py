"""
Boltzmann Wealth Model
======================
Agents exchange currency at random, producing a Boltzmann-Gibbs wealth distribution.
"""

from mesa import Model
from mesa.datacollection import DataCollector
from mesa.discrete_space import OrthogonalMooreGrid
from mesa.examples.basic.boltzmann_wealth_model.agents import MoneyAgent
from mesa.experimental.data_collection import DataRecorder, DatasetConfig
from mesa.experimental.scenarios import Scenario


class BoltzmannScenario(Scenario):
    n: int = 100
    width: int = 10
    height: int = 10


class BoltzmannWealth(Model):
    """Wealth redistribution model.

    All agents start with 1 unit. Each step they move and may give
    1 unit to a random cellmate. Produces a Boltzmann-Gibbs distribution.
    """

    def __init__(self, scenario: BoltzmannScenario = BoltzmannScenario):
        super().__init__(scenario=scenario)

        self.num_agents = scenario.n
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), random=self.random
        )

        self.recorder = DataRecorder(self)

        self.data_registry.track_agents(
            self.agents, "agent_data", "wealth"
        ).record(self.recorder)

        self.data_registry.track_model(
            self, "model_data", "gini"
        ).record(
            self.recorder
        )

        MoneyAgent.create_agents(
            self,
            self.num_agents,
            self.random.choices(self.grid.all_cells.cells, k=self.num_agents),
        )

        self.running = True
        # self.datacollector.collect(self)

    def step(self):
        self.agents.shuffle_do("step")
        # self.datacollector.collect(self)

    @property
    def gini(self) -> float:
        """Gini coefficient of current wealth distribution (0 = equal, 1 = maximal)."""
        wealths = [a.wealth for a in self.agents if isinstance(a, MoneyAgent)]
        if not wealths or sum(wealths) == 0:
            return 0.0
        x = sorted(wealths)
        n = len(x)
        b = sum(xi * (n - i) for i, xi in enumerate(x)) / (n * sum(x))
        return 1 + (1 / n) - 2 * b
    
if __name__ == "__main__":
    model = BoltzmannWealth(scenario=BoltzmannScenario(rng=42))
    model.run_for(100)
    df = model.recorder.get_table_dataframe("model_data")
    print(df.to_string())