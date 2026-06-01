# Needs-Based Homeostatic Agent Model

A formally-specified needs-based agent model implementing Maslow's prepotency
hierarchy written in **Mesa 4.0**

---

## What This Model Does

Agents on a 25×25 torus grid survive by satisfying two biological needs:

- **Energy** — depleted at rate λ_E per step; replenished by eating `FoodPatch`
- **Hydration** — depleted at rate λ_H > λ_E per step; replenished by `WaterPatch`

Each step an agent applies the prepotency decision matrix:

```
H(t) < θ_H  →  ForageWater   [highest urgency — dehydrates faster]
E(t) < θ_E  →  ForageFood
E ≥ φ_E ∧ H ≥ φ_H ∧ C = 0  →  Reproduce
otherwise   →  Wander
```

When either state hits zero the agent dies (`self.remove()`). Food and water
patches regrow after a fixed delay via `model.schedule_event`.

Reproduction uses a **thermodynamically conserved 50/50 resource split**: parent
and child each receive half the pre-reproduction energy and hydration, then the
parent pays the metabolic cost. This matches the formal specification
(Eq. 8–13).

For the full formal specification — equations, variable definitions, and the
measurement plan — see **ARCHITECTURE.pdf**.

---

## Files

```
needs_based_model/
├── agents.py           NeedsAgent, FoodPatch, WaterPatch
├── model.py            NeedsBasedModel, NeedsBasedScenario
├── ARCHITECTURE.pdf    Formal specification (equations, pain point table)
└── README.md 
```

---

## Requirements

Mesa 4.0.0a0.

```bash
pip install git+https://github.com/codebreaker32/mesa.git@behaviorals
# or
cd /path/to/mesa && pip install -e ".[dev]"
```

---

## Quickstart

```bash
python model.py
```

Runs 200 steps via `model.run_for()` and prints the full `DataRecorder` table.

---

## Using From Python

```python
from model import NeedsBasedModel, NeedsBasedScenario

model = NeedsBasedModel(scenario=NeedsBasedScenario(seed=42))
model.run_for(200)

df = model.recorder.get_table_dataframe("model_data")
print(df[["count_agents", "mean_energy", "mean_hydration"]].tail(5))
```

---

## References

- Maslow, A. H. (1943). A theory of human motivation. *Psychological Review*, 50(4).
- Epstein & Axtell (1996). *Growing Artificial Societies*. MIT Press.
- Mesa Discussion [#2529](https://github.com/mesa/mesa/discussions/2529)
- Mesa Discussion [#2538](https://github.com/mesa/mesa/discussions/2538)
- Mesa Discussion [#3304](https://github.com/mesa/mesa/discussions/3304)