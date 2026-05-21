# Needs-Based Homeostatic Agent Model

This model implements a **Needs-Based Homeostatic Agent** grounded in Maslow's prepotency hierarchy, designed to demonstrate architectural friction in Mesa 4.0. Agents inhabit a discrete torus grid, managing continuous biological states for energy (food) and hydration (water) that decay at constant rates per step. Decision logic follows a strict priority matrix where the agent only pursues higher-level activities like reproduction if survival-critical needs are met. Feeding and drinking are achieved through greedy, Moore-neighborhood foraging, with patches acting as idempotent agents that trigger regrowth events. Asexual reproduction occurs when agents exceed thriving thresholds, triggering a thermodynamically conserved 50/50 resource split between parent and offspring, minus a metabolic tax. 

## Documentation & Architecture

Please refer to the [Architecture](https://github.com/user-attachments/files/28110450/NeedsAgent_Design.pdf) for the complete formal specification.