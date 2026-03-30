"""Boltzmann Wealth Distribution with Generosity - Behavioral Framework

Same model as vanilla version, but using behavioral framework:
- BehavioralState for wealth tracking
- @rule decorator for decision logic
- NeedsAgent pattern for generosity behavior

Demonstrates:
- Declarative decision rules
- Automatic priority-based evaluation
- Threshold-driven behavior
"""

from mesa import Model
from mesa.datacollection import DataCollector
from mesa.discrete_space import OrthogonalMooreGrid, CellAgent
from mesa.experimental.data_collection import DataRecorder
from mesa.experimental.behaviorals.behavioral_agent import BehavioralAgent
from mesa.experimental.behaviorals.state import BehavioralState
from mesa.experimental.behaviorals.decision import rule, RulePriority


class WealthAgent(BehavioralAgent, CellAgent):
    """Agent using behavioral framework for wealth trading.
    
    Behavioral Framework: @rule decorator replaces if-else chains.
    Pattern A: Rules execute immediately (step-based).
    """
    
    # Wealth as BehavioralState (no decay, just threshold tracking)
    wealth = BehavioralState(
        decay_rate=0.0,
        min_value=0,
        thresholds={"poverty": 5, "comfort": 15}
    )
    
    def __init__(self, model, pos, initial_wealth=1):
        super().__init__(model)
        self.pos = pos
        self.wealth = initial_wealth
        self.generosity = self.random.random()
        
        # Thresholds
        self.poverty_threshold = 5
        self.comfort_threshold = 15

        

    # BEHAVIORAL RULES (Declarative, Priority-Based)    
    @rule(
        condition=lambda self: self.wealth < self.poverty_threshold,
        priority=RulePriority.CRITICAL
    )
    def seek_help(self):
        """Critical: Seek help when in poverty."""
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=False)
        wealthy = [n for n in neighbors if isinstance(n, WealthAgent) and n.wealth > n.comfort_threshold]
        
        if wealthy:
            donor = self.random.choice(wealthy)
            if self.random.random() < donor.generosity:
                amount = min(3, donor.wealth - donor.poverty_threshold)
                if amount > 0:
                    donor.wealth -= amount
                    self.wealth += amount
    
    @rule(
        condition=lambda self: (
            self.wealth > self.comfort_threshold and
            self.random.random() < self.generosity and
            len(self._find_poor_neighbors()) > 0
        ),
        priority=RulePriority.HIGH
    )
    def donate_to_poor(self):
        """High: Donate to poor neighbors when comfortable."""
        poor = self._find_poor_neighbors()
        if poor:
            recipient = self.random.choice(poor)
            amount = min(2, self.wealth - self.comfort_threshold)
            if amount > 0:
                self.wealth -= amount
                recipient.wealth += amount
    
    @rule(
        condition=lambda self: True,
        priority=RulePriority.DEFAULT
    )
    def trade(self):
        """Default: Trade with random neighbor."""
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=False)
        if neighbors:
            other = self.random.choice(neighbors)
            if isinstance(other, WealthAgent) and self.wealth > 0:
                self.wealth -= 1
                other.wealth += 1
    
    # HELPER
    
    def _find_poor_neighbors(self):
        """Find neighbors in poverty."""
        neighbors = self.model.grid.get_neighbors(self.pos, moore=True, include_center=False)
        return [n for n in neighbors if isinstance(n, WealthAgent) and n.wealth < n.poverty_threshold]




    