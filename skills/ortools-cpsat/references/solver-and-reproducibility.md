# CP-SAT solver parameters, status and reproducibility

```python
solver = cp_model.CpSolver()
p = solver.parameters
p.max_time_in_seconds = 60          # wall clock
p.max_deterministic_time = 30       # machine-independent work budget (preferred for tables)
p.num_workers = 8                   # 0 = all cores; 1 = single thread
p.random_seed = 0
p.relative_gap_limit = 0.0          # stop early at a gap if you set > 0 (report it)
p.log_search_progress = True        # development only
status = solver.solve(model)
```

## Status codes

| Status | Meaning | What to report |
|---|---|---|
| OPTIMAL | Objective proved optimal (within gap limits) | objective, time |
| FEASIBLE | Solution found, optimality not proved | objective, best bound, gap = (obj − bound)/obj |
| INFEASIBLE | Proved that no solution exists | check the model, use assumptions to explain |
| MODEL_INVALID | The model is malformed (e.g. non-integer coefficient, bad domain) | fix the code; `model.validate()` gives details |
| UNKNOWN | Limits reached before any solution or proof | not infeasible; increase the budget or add hints |

Read values with `solver.value(x)`, `solver.boolean_value(b)`,
`solver.objective_value`, `solver.best_objective_bound`, `solver.wall_time`,
`solver.response_stats()`.

## Reproducibility for papers

- Record: OR-Tools version (`import ortools; ortools.__version__`), CPU model, number of
  workers, time or deterministic-time limit, seed(s).
- Single-thread runs with a fixed seed are reproducible. Multi-thread runs with a
  wall-clock limit are not (thread timing differs). Prefer `max_deterministic_time`,
  which stops after the same amount of work regardless of load, and check by rerunning.
- When the solver is a baseline, run several seeds and report mean ± sd of objective and
  gap; when it is part of your method, fix the seed and give the budget.
- Report both the incumbent and the best bound; the bound is what makes a comparison with
  heuristics meaningful.

## Callbacks

Subclass `cp_model.CpSolverSolutionCallback` and override `on_solution_callback` to
record the anytime curve (time, objective) for convergence plots:

```python
class Recorder(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        super().__init__(); self.trace = []
    def on_solution_callback(self):
        self.trace.append((self.wall_time, self.objective_value, self.best_objective_bound))
solver.solve(model, Recorder())
```

## Performance checklist

1. Tight domains and horizons.
2. Prefer global constraints (no_overlap, cumulative, no_overlap_2d, circuit, element)
   to hand-made big-M disjunctions.
3. Avoid products of integer variables where a table or boolean expansion works.
4. Give complete hints from a good heuristic.
5. Try `num_workers` 8–16 for hard instances; more is not always better.
6. Profile with the log: look at which workers find solutions and how the bound moves.
