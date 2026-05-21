"""Needs-Based Homeostatic Model
Pain points are documented inline with # [Px] markers that reference the
table in README.md §5.
"""

from __future__ import annotations

import math
from typing import Optional

from mesa.discrete_space import CellAgent, FixedAgent
from mesa.discrete_space.cell import Cell



# Environment: resource patches

class FoodPatch(FixedAgent):
    """A food source that regrows after being eaten."""

    def __init__(self, model, cell: Cell, regrowth_time: int = 8,
                 energy_value: float = 40.0):
        super().__init__(model)
        self.cell = cell
        self.has_food = True
        self.regrowth_time = regrowth_time
        self.energy_value = energy_value

    def consume(self) -> None:
        """Eat this patch and schedule regrowth."""
        if self.has_food:
            self.has_food = False
            self.model.schedule_event(self._regrow, after=self.regrowth_time)

    def _regrow(self) -> None:
        self.has_food = True


class WaterPatch(FixedAgent):
    """A water source that replenishes after being consumed."""

    def __init__(self, model, cell: Cell, regrowth_time: int = 12,
                 hydration_value: float = 50.0):
        super().__init__(model)
        self.cell = cell
        self.has_water = True
        self.regrowth_time = regrowth_time
        self.hydration_value = hydration_value

    def consume(self) -> None:
        """Drink this patch and schedule replenishment."""
        if self.has_water:
            self.has_water = False
            self.model.schedule_event(self._regrow, after=self.regrowth_time)

    def _regrow(self) -> None:
        self.has_water = True



# Agent

class NeedsAgent(CellAgent):
    """Homeostatic agent implementing the prepotency decision matrix (Eq. 14).

    All behavioral logic lives in step(). State decay, survival check,
    and the decision tree are manual — this is the Phase 1 baseline that
    Phase 3 will improve upon.
    """

    def __init__(
        self,
        model,
        cell: Cell,
        energy: float = 80.0,
        hydration: float = 80.0,
        energy_max: float = 100.0,
        hydration_max: float = 100.0,
        decay_energy: float = 1.0,
        decay_hydration: float = 1.5,
        vision: int = 3,
        repro_energy_cost: float = 15.0,
        repro_hydration_cost: float = 10.0,
        repro_cooldown: float = 5.0,
        theta_energy: float = 30.0,
        theta_hydration: float = 30.0,
        phi_energy: float = 70.0,
        phi_hydration: float = 70.0,
    ):
        super().__init__(model)
        self.cell = cell

        # Internal state (floats, managed manually)
        self.energy = float(energy)
        self.hydration = float(hydration)
        self.energy_max = energy_max
        self.hydration_max = hydration_max

        # Biological parameters
        self.decay_energy = decay_energy
        self.decay_hydration = decay_hydration
        self.vision = vision
        self.repro_energy_cost = repro_energy_cost
        self.repro_hydration_cost = repro_hydration_cost
        self.repro_cooldown_reset = repro_cooldown

        # [P4] Cooldown is a raw float counter — no primitive to express
        # "decrement by 1 per step, clamp at 0". Must manage manually.
        self._repro_cooldown = float(repro_cooldown)

        # Decision thresholds
        self.theta_energy = theta_energy
        self.theta_hydration = theta_hydration
        self.phi_energy = phi_energy
        self.phi_hydration = phi_hydration

        # Step-level tracking for DataRecorder metrics
        self.gave_birth_this_step = False 

    # Main step — all logic in one method (Pain Points P1–P5)

    def step(self) -> None:
        """One step: decay → survival check → decide → act.

        Pain points visible here:
          [P1] State decay: 3 explicit lines, one per decaying variable.
               Adding a 4th state (e.g. fatigue) requires a 4th line.
          [P2] Survival check always runs, even when energy is at 99.
               No threshold callback; the condition is polled every tick.
          [P3] Priority is encoded positionally in if/elif order.
               Adding a new high-priority behavior requires finding the
               right insertion point in the chain.
          [P4] Cooldown is a raw float that needs manual decrement and clamp.
          [P5] State evolution, survival, and decision logic are all
               entangled in this one method. Testing any branch in isolation
               requires constructing a full agent.
        """
        self.gave_birth_this_step = False

        # [P1] Manual state decay — Eq. 1, 2, 3
        self.energy          = max(0.0, self.energy    - self.decay_energy)
        self.hydration       = max(0.0, self.hydration - self.decay_hydration)
        self._repro_cooldown = max(0.0, self._repro_cooldown - 1)

        # [P2] Survival check — Eq. 4
        if self.energy <= 0 or self.hydration <= 0:
            self.remove()
            return

        # [P3] Decision matrix — Eq. 14 (priority implicit in elif order)
        if self.hydration < self.theta_hydration:
            # ForageWater: H(t) < θ_H  [highest urgency — dehydrates faster]
            target = self._nearest_resource(WaterPatch, "has_water")
            self._move_toward(target) if target else self._wander()
            self._try_drink()

        elif self.energy < self.theta_energy:
            # ForageFood: E(t) < θ_E
            target = self._nearest_resource(FoodPatch, "has_food")
            self._move_toward(target) if target else self._wander()
            self._try_eat()

        elif (self.energy >= self.phi_energy
              and self.hydration >= self.phi_hydration
              and self._repro_cooldown <= 0):
            # Reproduce: E ≥ φ_E ∧ H ≥ φ_H ∧ C = 0  — Eq. 8–13
            self._reproduce()

        else:
            # Wander: fallback
            self._wander()

    
    # Action implementations
    
    def _reproduce(self) -> None:
        """Spawn one offspring, deduct costs, reset cooldown (Eq. 8–13)."""
        # 50/50 resource split allocation
        child_energy = self.energy / 2.0
        child_hydration = self.hydration / 2.0

        # Parent retains remaining half minus metabolic tax (Eq. 8, 9, 10)
        self.energy          = child_energy - self.repro_energy_cost
        self.hydration       = child_hydration - self.repro_hydration_cost
        self._repro_cooldown  = self.repro_cooldown_reset

        NeedsAgent(
            self.model,
            self.cell,
            energy=child_energy,                # Eq. 11
            hydration=child_hydration,          # Eq. 12
            energy_max=self.energy_max,
            hydration_max=self.hydration_max,
            decay_energy=self.decay_energy,
            decay_hydration=self.decay_hydration,
            vision=self.vision,
            repro_energy_cost=self.repro_energy_cost,
            repro_hydration_cost=self.repro_hydration_cost,
            repro_cooldown=self.repro_cooldown_reset,  # Eq. 13
            theta_energy=self.theta_energy,
            theta_hydration=self.theta_hydration,
            phi_energy=self.phi_energy,
            phi_hydration=self.phi_hydration,
        )
        self.gave_birth_this_step = True  # Flag for DataRecorder

    def _wander(self) -> None:
        """Move to a random immediate Moore neighbour."""
        neighbors = list(self.cell.get_neighborhood(radius=1))
        if neighbors:
            self.cell = self.random.choice(neighbors)

    def _move_toward(self, target_cell: Cell) -> None:
        """Move one step toward target_cell (Eq. 7 — greedy nearest neighbour)."""
        if target_cell is self.cell:
            return
            
        neighbors = list(self.cell.get_neighborhood(radius=1))
        if not neighbors:
            return
            
        # If target is an immediate neighbour, step there directly
        if target_cell in neighbors:
            self.cell = target_cell
            return
            
        # Otherwise pick the neighbour minimising distance to target (Eq. 7)
        self.cell = min(neighbors, key=lambda c: _euclidean(c, target_cell))

    def _nearest_resource(self, patch_type: type, attr: str) -> Optional[Cell]:
        """Return the nearest cell with an active patch of patch_type, or None.

        Scans P_obs (Eq. 5) and returns the cell minimising Eq. 6.
        """
        best_cell = None
        best_dist = float("inf")
        
        for cell in self.cell.get_neighborhood(self.vision, include_center=True):
            # Fast check: ensure the cell has agents before iterating
            if not cell.agents:
                continue
                
            for agent in cell.agents:
                if isinstance(agent, patch_type) and getattr(agent, attr):
                    d = _euclidean(self.cell, cell)
                    if d < best_dist:
                        best_dist = d
                        best_cell = cell
                        
        return best_cell

    def _try_eat(self) -> None:
        """Consume a FoodPatch in the current cell if available."""
        for agent in self.cell.agents:
            if isinstance(agent, FoodPatch) and agent.has_food:
                self.energy = min(self.energy_max, self.energy + agent.energy_value)
                agent.consume()
                return

    def _try_drink(self) -> None:
        """Consume a WaterPatch in the current cell if available."""
        for agent in self.cell.agents:
            if isinstance(agent, WaterPatch) and agent.has_water:
                self.hydration = min(self.hydration_max, self.hydration + agent.hydration_value)
                agent.consume()
                return



# Utility

def _euclidean(cell_a: Cell, cell_b: Cell) -> float:
    """Euclidean distance between two cell positions (used in Eq. 6 and 7)."""
    x1, y1 = cell_a.coordinate
    x2, y2 = cell_b.coordinate
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)