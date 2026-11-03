---
name: ortools-cpsat
description: >-
  Builds, solves, validates and benchmarks combinatorial optimisation models
  with Google OR-Tools CP-SAT: job-shop / flexible scheduling, unequal-area
  facility layout (NoOverlap2D), assignment, packing and timetabling, plus
  CP + deep reinforcement learning hybrids (DRL warm starts, CP repair, LNS
  neighbourhoods chosen by a policy). Use when the task mentions OR-Tools,
  CP-SAT, constraint programming, interval variables, makespan, layout
  optimisation, or comparing a DRL/metaheuristic against an exact solver.
  Triggers: CP-SAT, OR-Tools, 限制式規劃, 排程, 工廠佈局, 設施規劃, 零售佈局,
  makespan, NoOverlap2D, 混合 CP 與強化學習. Not for continuous nonlinear
  optimisation (use scipy/pymoo) or pure LP at large scale (use a MIP solver).
metadata:
  version: "1.0.0"
  author: "張明瀚 (cmh3601)"
  license: MIT
compatibility: Python >= 3.10, ortools >= 9.10 (tested with 9.15). Uses the snake_case CP-SAT API.
---

# OR-Tools CP-SAT

CP-SAT works on integers only, proves optimality through bounds, and is
parallel by default. Results are publishable only if the model is validated
independently and the run is reproducible.

## Workflow

1. **Write the model on paper first**: sets, parameters, decision variables
   with domains, constraints, objective. Decide the integer scale for every
   real-valued quantity (e.g. metres × 10, money in cents) and record it.
2. **Pick the CP-SAT building blocks** (`references/modeling-patterns.md`):
   interval variables for tasks; `add_no_overlap` for unary machines;
   `add_cumulative` for capacities; `add_no_overlap_2d` for rectangles;
   optional intervals for alternative machines; enforcement literals
   (`.only_enforce_if`) for conditional constraints; `add_abs_equality`,
   `add_max_equality`, `add_element` for non-linear terms.
3. **Bound every variable tightly** (horizon = sum of durations, floor size)
   and add valid symmetry breaking only when the instance is truly symmetric.
4. **Start from a bundled template** and adapt it:
   - `scripts/jobshop_cpsat.py` — job shop, dispatching-rule hints, external hints, validator.
   - `scripts/layout_cpsat.py` — unequal-area layout with rotation, obstacles, clearance,
     closeness/separation constraints, hint / fix / relax for CP + DRL, SVG output.
5. **Solve with explicit parameters** (`references/solver-and-reproducibility.md`):
   `max_time_in_seconds` or `max_deterministic_time`, `num_workers`,
   `random_seed`; log with `log_search_progress` while developing.
6. **Interpret the status correctly**: OPTIMAL (proved), FEASIBLE (incumbent,
   report the gap to `best_objective_bound`), INFEASIBLE (proved none exists),
   MODEL_INVALID (bug), UNKNOWN (no solution within limits; not infeasible).
7. **Validate every solution with code that does not reuse the model** (the
   templates include `validate`), recomputing the objective from the solution.
8. **Benchmark fairly** when comparing with DRL or metaheuristics
   (`references/cp-drl-hybrid.md`): same instances, same wall-clock budget
   including policy inference, several seeds, report gaps to the best bound.

## Quick commands

```bash
python scripts/jobshop_cpsat.py data/ft06.txt --time-limit 10 --workers 8 --seed 0
python scripts/jobshop_cpsat.py data/ft06.txt --hint spt
python scripts/layout_cpsat.py examples/layout_8.json --time-limit 30 --svg layout.svg
python scripts/layout_cpsat.py examples/layout_8.json --hint-file policy.json --fix-hint
python scripts/layout_cpsat.py examples/layout_8.json --hint-file policy.json --relax Office,Returns
python -m pytest tests -q
```

ft06 must return makespan 55 (known optimum); the tests also compare layout
optima with brute-force enumeration.

## Rules that prevent common errors

- Coefficients and bounds must be integers. Scale reals and round
  deliberately; for doubled or scaled distances use floor for upper limits
  and ceil for lower limits.
- `--fix-hint` (`fix_variables_to_their_hinted_value`) evaluates a given
  solution; its OPTIMAL status and bound describe the fixed model, not the
  instance. Never report them as optimality of the policy.
- Hints are suggestions. An infeasible or partial hint is silently repaired
  or ignored; check `solver.response_stats()` or the log for hint usage.
- Symmetry-breaking constraints valid for an empty floor become invalid with
  obstacles, fixed departments or partial neighbourhoods; the layout template
  turns them off in those cases.
- Multi-worker runs with a wall-clock limit are not reproducible. For tables
  in a paper use `num_workers=1` or `max_deterministic_time`, fixed seeds, and
  report the OR-Tools version.
- Do not call a solution "optimal" when the status is FEASIBLE; give the gap.

## References in this skill

- `references/modeling-patterns.md` — constraint patterns with snake_case API examples.
- `references/solver-and-reproducibility.md` — parameters, status codes, gaps, determinism, logs.
- `references/cp-drl-hybrid.md` — CP + DRL architectures, experiment design, baselines, reporting.
