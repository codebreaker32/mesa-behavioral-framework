"""Belief-Desire-Intention (BDI) Gold Miner Agents

Implements Wooldridge's BDI Deliberation Cycle inside step():

    B_{t+1} = brf(B_t, P)                    — Belief Revision     (Eq. 1)
    D_{t+1} = generate_options(B_{t+1}, I_t)  — Option Generation   (Eq. 2)
    I_{t+1} = filter(B_{t+1}, D_{t+1}, I_t)  — Filtering           (Eq. 3)
    execute(plan(I_{t+1}))                     — Plan Execution      (Eq. 4)
"""

from __future__ import annotations

import math
from enum import Enum, auto
from typing import Optional

from mesa.discrete_space import CellAgent, FixedAgent
from mesa.discrete_space.cell import Cell


class Intention(Enum):
    """Active cognitive commitment of the BDI agent.

    Using an Enum (rather than raw string constants) gives IDE support and
    prevents typo bugs. In vanilla Mesa this is still boilerplate — a Phase 3
    framework would replace these with structured Intention objects so the
    TaskManager can manage duration and interruption automatically. [P6]
    """
    IDLE            = auto()
    NAVIGATE_MINE   = auto()
    MINING          = auto()
    NAVIGATE_MARKET = auto()
    SELLING         = auto()

# Environment

class GoldMine(FixedAgent):
    """A finite gold deposit that regenerates after depletion."""

    def __init__(self, model, cell: Cell,
                 capacity: int = 5, regen_time: int = 20) -> None:
        super().__init__(model)
        self.cell = cell
        self.gold = capacity
        self.capacity = capacity
        self.regen_time = regen_time

    def mine_one(self) -> bool:
        """Remove one unit of gold. Returns True if successful."""
        if self.gold > 0:
            self.gold -= 1
            if self.gold == 0:
                self.model.schedule_event(self._regen, after=self.regen_time)
            return True
        return False

    def _regen(self) -> None:
        self.gold = self.capacity


class Market(FixedAgent):
    """A market node where miners sell gold for a fluctuating price.

    Price drops with local supply each step, then recovers toward base.
    Implements Eq. 16 (supply penalty) and Eq. 17 (price recovery).
    """

    def __init__(self, model, cell: Cell, base_price: float = 10.0) -> None:
        super().__init__(model)
        self.cell = cell
        self.base_price = base_price
        self.current_price = base_price
        self.total_sold = 0

    def sell(self, gold: int) -> float:
        """Process gold sale and adjust price by supply (Eq. 16)."""
        revenue = gold * self.current_price
        self.total_sold += gold
        self.current_price = max(1.0, self.base_price - gold * 0.1)
        return revenue

    def reset_price(self) -> None:
        """Recover price toward base each step (Eq. 17)."""
        self.current_price = min(self.base_price, self.current_price + 0.5)


# Agent

class BDIMiner(CellAgent):
    """BDI Gold Miner implementing Wooldridge's deliberation cycle in step()."""

    def __init__(
        self,
        model,
        cell: Cell,
        vision: int = 5,
        carry_capacity: int = 5,
        energy_max: float = 100.0,
    ) -> None:
        super().__init__(model)
        self.cell = cell
        self.vision = vision
        self.carry_capacity = carry_capacity
        self.energy_max = energy_max

        # [P1] Manual state — energy decays by 1.0 per step (Eq. 5).
        # No primitive to express "this attribute decays at rate λ."
        self.energy: float = energy_max

        # [B] Belief base — raw Python dict (Eq. 1).
        self.beliefs: dict = {
            "known_mines":   {},   # cell.coordinate → GoldMine
            "known_markets": {},   # cell.coordinate → Market
            "best_mine":     None,
            "best_market":   None,
        }

        # [D] Desire base — continuous utility scores (Eq. 11–13).
        # [P3] Values are floats computed inline; changing relative urgency
        # requires editing formulas scattered across _update_desires().
        self.desires: dict[str, float] = {
            "survive":   0.0,
            "mine_gold": 0.0,
            "sell_gold": 0.0,
            "idle":     10.0,
        }

        # [P6] Current intention — no duration encoding.
        # In GAMA, `do goto target: mine.location` navigates in one line.
        # Here each navigating intention is a manual arrival check repeated
        # every tick until self.cell is self.target_cell.
        self.current_intention: Intention = Intention.IDLE
        self.target_cell: Optional[Cell] = None

        self.gold_held: int = 0
        self.wealth: float = 0.0

    # Main step — four-phase BDI deliberation cycle
    def step(self) -> None:
        """Execute the BDI deliberation cycle for one Mesa tick."""

        
        # Pain points visible here:
        #   [P1] Manual energy decay — explicit assignment per variable.
        #   [P2] Survival check polled every tick regardless of energy level.
        #   [P5] All four BDI phases entangled in one method.
        #   [P6] Phase 4 dispatches to duplicated navigation state machines.
        #   [P7] Commitment heuristic in _filter_intentions() is ad-hoc.
        
        # [P1] State decay — Eq. 5
        self.energy = max(0.0, self.energy - 1.0)

        # [P2] Survival check — Eq. 6
        if self.energy <= 0:
            self.remove()
            return

        # Phase 1: Belief Revision — B_{t+1} = brf(B_t, P)  (Eq. 1)
        self._update_beliefs()

        # Phase 2: Option Generation — D_{t+1} = generate_options(...)  (Eq. 2)
        self._update_desires()

        # Phase 3: Filtering — I_{t+1} = filter(...)  (Eq. 3)
        self._filter_intentions()   # [P7]

        # Phase 4: Plan Execution — execute(plan(I_{t+1}))  (Eq. 4)
        # [P6] Each navigation intention is a per-tick arrival check.
        if self.current_intention == Intention.NAVIGATE_MINE:
            self._execute_navigate_mine()
        elif self.current_intention == Intention.MINING:
            self._execute_mining()
        elif self.current_intention == Intention.NAVIGATE_MARKET:
            self._execute_navigate_market()
        elif self.current_intention == Intention.SELLING:
            self._execute_selling()
        else:
            self._wander()

    # Phase 1: Belief Revision

    def _update_beliefs(self) -> None:
        """Perceive neighbourhood and update belief dictionary (Eq. 1).

        [P5] Perception (scanning cells) and belief storage (writing to
        self.beliefs) are fused. A proper BDI framework separates
        perceive() from brf() so each can be overridden independently.
        """
        for cell in self.cell.get_neighborhood(self.vision, include_center=True):
            if not cell.agents:
                continue
            for agent in cell.agents:
                if isinstance(agent, GoldMine) and agent.gold > 0:
                    self.beliefs["known_mines"][cell.coordinate] = agent
                elif isinstance(agent, Market):
                    self.beliefs["known_markets"][cell.coordinate] = agent

        # Prune stale mine beliefs — remove entries for depleted mines.
        self.beliefs["known_mines"] = {
            coord: mine
            for coord, mine in self.beliefs["known_mines"].items()
            if mine.gold > 0
        }

        # Best mine: highest gold-per-distance ratio (Eq. 9)
        mines = self.beliefs["known_mines"]
        self.beliefs["best_mine"] = (
            max(mines.values(),
                key=lambda m: m.gold / (1 + _euclidean(self.cell, m.cell)))
            if mines else None
        )

        # Best market: highest price-per-distance ratio (Eq. 10)
        markets = self.beliefs["known_markets"]
        self.beliefs["best_market"] = (
            max(markets.values(),
                key=lambda m: m.current_price / (1 + _euclidean(self.cell, m.cell)))
            if markets else None
        )

    # Phase 2: Option Generation

    def _update_desires(self) -> None:
        """Compute continuous utility scores for available desires (Eq. 2)."""

        # [P3] The formula constants (200.0, 100.0, 60.0, 30.0) are
        # inline literals. Changing the urgency scale requires editing this
        # method; there is no declarative priority system. 


        # Survival desire — steps up sharply when energy is critical (Eq. 11)
        self.desires["survive"] = 200.0 if self.energy < 30.0 else 0.0

        # Sell desire — rises continuously with inventory fill level (Eq. 12)
        self.desires["sell_gold"] = (
            (self.gold_held / self.carry_capacity) * 100.0
            if self.gold_held > 0 else 0.0
        )

        # Mine desire — active when inventory has room and a mine is known (Eq. 13)
        self.desires["mine_gold"] = (
            60.0 if self.gold_held < self.carry_capacity
                 and self.beliefs["best_mine"] is not None
            else 0.0
        )

    # Phase 3: Filtering / Commitment

    def _filter_intentions(self) -> None:
        """Commit to highest-utility desire unless current plan dominates (Eq. 3)."""

        # [P7] Blind Commitment strategy: stay committed unless a strictly
        # higher-utility desire appears. This is ad-hoc because:
        #   (a) Wooldridge (2009 §2.4) defines bold, cautious, and open-minded
        #       strategies — none can be selected declaratively in Mesa.
        #   (b) Changing the strategy requires rewriting this entire method.
        #   (c) The desire -> intention mapping is a manual lookup with no
        #       type safety.
        top_desire = max(self.desires, key=self.desires.get)
        top_score  = self.desires[top_desire]

        # Stay committed unless dominated (Eq. 14)
        if (top_score <= self._current_intention_priority()
                and self.current_intention != Intention.IDLE):
            return

        if top_desire in ("survive", "sell_gold") and self.beliefs.get("best_market"):
            self._adopt_intention(Intention.NAVIGATE_MARKET)
        elif top_desire == "mine_gold" and self.beliefs.get("best_mine"):
            self._adopt_intention(Intention.NAVIGATE_MINE)
        else:
            self._adopt_intention(Intention.IDLE)

    def _current_intention_priority(self) -> float:
        """Return the utility score backing the current intention."""
        mapping = {
            Intention.IDLE:             self.desires["idle"],
            Intention.NAVIGATE_MINE:    self.desires["mine_gold"],
            Intention.MINING:           self.desires["mine_gold"],
            Intention.NAVIGATE_MARKET:  max(self.desires["sell_gold"],
                                            self.desires["survive"]),
            Intention.SELLING:          max(self.desires["sell_gold"],
                                            self.desires["survive"]),
        }
        return mapping.get(self.current_intention, 0.0)

    def _adopt_intention(self, intention: Intention) -> None:
        """Switch to a new intention and assign the corresponding target cell."""
        
        # [P6] Every intention switch sets self.target_cell manually.
        # The mapping from intention type to target is a hand-written lookup
        # table that must be kept in sync with _resolve_target by hand.

        self.current_intention = intention
        if intention == Intention.NAVIGATE_MINE and self.beliefs.get("best_mine"):
            self.target_cell = self.beliefs["best_mine"].cell
        elif intention in (Intention.NAVIGATE_MARKET, Intention.SELLING) \
                and self.beliefs.get("best_market"):
            self.target_cell = self.beliefs["best_market"].cell
        else:
            self.target_cell = None

    # Phase 4: Plan Execution

    def _execute_navigate_mine(self) -> None:
        """Navigate toward the best known mine, one step per tick."""
        
        # [P6] Tick amnesia. "Go to the mine" requires a per-tick arrival
        # check because Mesa has no duration primitive. This method and
        # _execute_navigate_market are structurally identical — duplicated
        # boilerplate. A Task primitive would express both as one reusable
        # construct.

        if self.beliefs["best_mine"] is None:
            self._adopt_intention(Intention.IDLE)
            return

        if self.cell is self.target_cell:
            self.current_intention = Intention.MINING
            return

        self._move_toward(self.target_cell)

    def _execute_mining(self) -> None:
        """Extract one gold unit per tick until capacity or mine empty."""

        # [P6] Multi-tick action with no native duration. The termination
        # condition is checked manually every tick rather than being encoded
        # once in a Task completion predicate.

        mine = self._mine_at_cell(self.cell)
        if mine is None or mine.gold == 0:
            self._adopt_intention(
                Intention.NAVIGATE_MARKET if self.gold_held > 0 else Intention.IDLE
            )
            return

        if mine.mine_one():
            self.gold_held += 1
            self.energy = max(0.0, self.energy - 0.5)  # mining costs extra energy

        if self.gold_held >= self.carry_capacity:
            self._adopt_intention(Intention.NAVIGATE_MARKET)

    def _execute_navigate_market(self) -> None:
        """Navigate toward best known market, one step per tick."""
        # [P6] Structurally identical to _execute_navigate_mine
        if self.target_cell is None:
            self._adopt_intention(Intention.IDLE)
            return

        if self.cell is self.target_cell:
            self.current_intention = Intention.SELLING
            return

        self._move_toward(self.target_cell)

    def _execute_selling(self) -> None:
        """Sell all held gold at the current market cell (Eq. 15)."""
        market = self._market_at_cell(self.cell)
        if market:
            self.wealth += market.sell(self.gold_held)       # Eq. 15
            self.energy  = min(self.energy_max, self.energy + 20.0)
            self.gold_held = 0

        self._adopt_intention(Intention.IDLE)

    # Movement helpers

    def _move_toward(self, target_cell: Cell) -> None:
        """Movement toward target_cell (Eq. 8)."""
        if target_cell is self.cell:
            return
        neighbors = list(self.cell.get_neighborhood(radius=1))
        if not neighbors:
            return
        if target_cell in neighbors:
            self.cell = target_cell
            return
        self.cell = min(neighbors, key=lambda c: _euclidean(c, target_cell))

    def _wander(self) -> None:
        """Move to a random immediate neighbour."""
        neighbors = list(self.cell.get_neighborhood(radius=1))
        if neighbors:
            self.cell = self.random.choice(neighbors)

    # Cell inspection helpers

    def _mine_at_cell(self, cell: Cell) -> Optional[GoldMine]:
        for agent in cell.agents:
            if isinstance(agent, GoldMine):
                return agent
        return None

    def _market_at_cell(self, cell: Cell) -> Optional[Market]:
        for agent in cell.agents:
            if isinstance(agent, Market):
                return agent
        return None


# Utility

def _euclidean(cell_a: Cell, cell_b: Cell) -> float:
    """Euclidean distance between two cell coordinates."""
    x1, y1 = cell_a.coordinate
    x2, y2 = cell_b.coordinate
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)