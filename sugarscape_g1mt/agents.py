import math
from mesa.discrete_space import CellAgent
from mesa.experimental.behaviorals.behavioral_agent import BehavioralAgent
from mesa.experimental.behaviorals.state import BehavioralState
from mesa.experimental.behaviorals.decision import rule, RulePriority


def get_distance(cell_1, cell_2):
    """Calculate the Euclidean distance between two positions."""
    x1, y1 = cell_1.coordinate
    x2, y2 = cell_2.coordinate
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)


class Trader(BehavioralAgent, CellAgent):
    """
    BehavioralTrader:
    - Metabolism is handled automatically by lazy-evaluating BehavioralStates.
    - Death is event-driven via thresholds.
    - Actions are prioritized using declarative @rules.
    """

    # Declarative Biology: Automatic metabolism decay
    sugar = BehavioralState(
        decay_rate=lambda self: -self.metabolism_sugar, 
        min_value=0.0, 
        thresholds={"starved": 0.0}
    )
    
    spice = BehavioralState(
        decay_rate=lambda self: -self.metabolism_spice, 
        min_value=0.0, 
        thresholds={"starved": 0.0}
    )

    def __init__(
        self, model, cell, sugar=0, spice=0, metabolism_sugar=0, metabolism_spice=0, vision=0
    ):
        super().__init__(model)
        self.cell = cell
        self.vision = vision
        self.metabolism_sugar = metabolism_sugar
        self.metabolism_spice = metabolism_spice
        
        # Initialize states
        self.sugar = sugar
        self.spice = spice
        
        self.prices = []
        self.trade_partners = []

        # Event-Driven Death (Replaces manual `maybe_die` and `is_starved` checks)
        BehavioralState.on_threshold(self, "sugar", "starved", lambda sig: self.remove())
        BehavioralState.on_threshold(self, "spice", "starved", lambda sig: self.remove())

    def step(self):
        """Clean execution loop."""
        self.prices = []
        self.trade_partners = []
        
        # Applies the metabolism decay and triggers death if starved
        self.sync_states() 
        
        # Only evaluate rules if the agent survived metabolism
        if self.cell is not None: 
            super().step()

    # Decision Rules (Combined Macro-Action)

    @rule(condition=lambda self: True, priority=RulePriority.DEFAULT)
    def act(self):
        """
        DEFAULT: In classic Sugarscape, survival and economics are a 
        strictly sequential daily routine to avoid action-eclipsing.
        """
        # 1. Survive
        self.move()
        self.eat()
        
        # 2. Trade
        if self.model.scenario.enable_trade:
            for a in self.cell.get_neighborhood(radius=self.vision).agents:
                if a is not self:
                    self.trade(a)

    # Biological Action Implementations

    def eat(self):
        """
        Modified from Vanilla: We NO LONGER subtract metabolism here! 
        BehavioralState handles continuous decay automatically.
        """
        self.sugar += self.cell.sugar
        self.cell.sugar = 0

        self.spice += self.cell.spice
        self.cell.spice = 0

    def move(self):
        """Identifies optimal move to maximize welfare."""
        neighboring_cells = [
            c for c in self.cell.get_neighborhood(self.vision, include_center=True) if c.is_empty
        ]
        if not neighboring_cells:
            return

        welfares = [
            self.calculate_welfare(self.sugar + c.sugar, self.spice + c.spice)
            for c in neighboring_cells
        ]

        max_welfare = max(welfares)
        candidates = [
            c for c, w in zip(neighboring_cells, welfares) if math.isclose(w, max_welfare)
        ]

        min_dist = min(get_distance(self.cell, c) for c in candidates)
        final_candidates = [
            c for c in candidates if math.isclose(get_distance(self.cell, c), min_dist, rel_tol=1e-02)
        ]

        self.cell = self.random.choice(final_candidates)

    # Economic Math Helpers (Completely Unchanged)
    
    def calculate_welfare(self, sugar, spice):
        m_total = self.metabolism_sugar + self.metabolism_spice
        return (sugar ** (self.metabolism_sugar / m_total)) * (spice ** (self.metabolism_spice / m_total))

    def calculate_MRS(self, sugar, spice):
        return (spice / self.metabolism_spice) / (sugar / self.metabolism_sugar)

    def calculate_sell_spice_amount(self, price):
        if price >= 1: return 1, int(price)
        else: return int(1 / price), 1

    def sell_spice(self, other, sugar, spice):
        self.sugar += sugar
        other.sugar -= sugar
        self.spice -= spice
        other.spice += spice

    def maybe_sell_spice(self, other, price, welfare_self, welfare_other):
        sugar_exchanged, spice_exchanged = self.calculate_sell_spice_amount(price)
        self_sugar, other_sugar = self.sugar + sugar_exchanged, other.sugar - sugar_exchanged
        self_spice, other_spice = self.spice - spice_exchanged, other.spice + spice_exchanged

        if self_sugar <= 0 or other_sugar <= 0 or self_spice <= 0 or other_spice <= 0:
            return False

        both_agents_better_off = (
            welfare_self < self.calculate_welfare(self_sugar, self_spice) and 
            welfare_other < other.calculate_welfare(other_sugar, other_spice)
        )
        mrs_not_crossing = self.calculate_MRS(self_sugar, self_spice) > other.calculate_MRS(other_sugar, other_spice)

        if not (both_agents_better_off and mrs_not_crossing):
            return False

        self.sell_spice(other, sugar_exchanged, spice_exchanged)
        return True

    def trade(self, other):
        if self.sugar <= 0 or self.spice <= 0 or other.sugar <= 0 or other.spice <= 0:
            return

        mrs_self = self.calculate_MRS(self.sugar, self.spice)
        mrs_other = other.calculate_MRS(other.sugar, other.spice)
        welfare_self = self.calculate_welfare(self.sugar, self.spice)
        welfare_other = other.calculate_welfare(other.sugar, other.spice)

        if math.isclose(mrs_self, mrs_other): return

        price = math.sqrt(mrs_self * mrs_other)

        if mrs_self > mrs_other:
            if not self.maybe_sell_spice(other, price, welfare_self, welfare_other): return
        else:
            if not other.maybe_sell_spice(self, price, welfare_other, welfare_self): return

        self.prices.append(price)
        self.trade_partners.append(other.unique_id)
        
        # Recursive call to keep trading until MRS parity is reached
        self.trade(other)