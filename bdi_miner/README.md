# BDI Gold Miner Model

A spatial **BDI Gold Miner / Market Trader** model. Agents navigate a torus grid to
forage for regenerating gold deposits, manage biological homeostasis, and trade at market
nodes under fluctuating supply-and-demand economics.

## The Cognitive Architecture

Each tick a miner executes four phases:

1. **Belief Revision** — scan Moore neighbourhood for `GoldMine` and
   `Market` agents; update internal map; compute best mine (highest
   gold-per-distance) and best market (highest price-per-distance)
2. **Option Generation** — compute continuous utility scores for
   `survive`, `sell_gold`, `mine_gold`, and `idle`
3. **Intention Filtering** — commit to the highest-utility desire using
   a **Blind Commitment** strategy; stay on current intention unless
   strictly dominated
4. **Plan Execution** — advance the current intention one Mesa tick;
   navigate intentions check arrival per-tick (the tick-amnesia problem)

See **ARCHITECTURE.pdf** for the complete formal specification and pain point table.

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
python bdi_model.py
```

Runs 200 steps and prints the full `DataRecorder` table.

---

## Using From Python

```python
from bdi_model import BDIModel, BDIScenario

model = BDIModel(scenario=BDIScenario(seed=42))
model.run_for(200)

df = model.recorder.get_table_dataframe("model_data")
print(df[["count_miners", "mean_wealth", "mean_gold_held", "gold_in_mines"]].tail(10))
```

---

## References

- Wooldridge, M. (2009). *An Introduction to MultiAgent Systems*. Wiley.
- Rao & Georgeff (1995). BDI agents: From theory to practice. *ICMAS*.
- GAMA BDI Tutorial: <https://gama-platform.org/wiki/BDIAgents>
- Mesa Discussions: [#2526](https://github.com/mesa/mesa/discussions/2526),
  [#2538](https://github.com/mesa/mesa/discussions/2538),
  [#3304](https://github.com/mesa/mesa/discussions/3304)