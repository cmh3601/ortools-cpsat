# CP + deep reinforcement learning hybrids

## Architectures

| Pattern | DRL role | CP-SAT role | Template support |
|---|---|---|---|
| Warm start | Policy constructs a full solution | Improves it from a complete hint | `--hint-file` |
| Evaluation / reward | Policy proposes; reward = objective | Checks feasibility and objective exactly | `--fix-hint` |
| Repair | Policy output may violate constraints | Finds the nearest feasible solution (minimise deviation from hint) | add a deviation objective |
| Learned LNS | Policy picks which variables to free | Re-optimises the neighbourhood, others fixed | `--relax` |
| Imitation | Policy learns from expert trajectories | Generates optimal or near-optimal solutions as labels | run CP-SAT offline |
| Decomposition | Policy makes high-level decisions (e.g. zone assignment) | Solves the detailed subproblem | two-stage scripts |

Typical learned-LNS loop:

```text
incumbent ← DRL construction (or dispatching rule)
repeat until budget:
    S ← policy(state, incumbent)            # e.g. k departments to relax
    candidate ← CP-SAT(model | vars ∉ S fixed to incumbent, hint = incumbent, short limit)
    if candidate better: incumbent ← candidate
    reward ← improvement (optionally minus time)
```

## Repair objective (when the policy output is infeasible)

Minimise Σ |x_i − x̂_i| + |y_i − ŷ_i| using `add_abs_equality` on deviation variables,
subject to all hard constraints. Report how often repair was needed and the mean
deviation, because frequent repair means the policy has not learned feasibility.

## Experiment design checklist

- Instances: training, validation and test sets drawn independently; include public
  benchmarks when they exist (e.g. Taillard or ft/la instances for job shops) and larger
  instances than seen in training to test generalisation.
- Baselines: CP-SAT alone with the same total wall-clock budget; a dispatching rule or
  constructive heuristic; a metaheuristic (GA/SA/tabu) if the literature uses one.
- Budgets: count policy inference time and CP time together; give hardware.
- Seeds: at least 5 training seeds for the policy and several solver seeds; report mean ± sd.
- Metrics: objective, gap to best known or to CP-SAT best bound, time to target, anytime
  curve (record with a solution callback), feasibility rate before repair.
- Statistics: paired comparisons per instance (Wilcoxon signed-rank) rather than means only.
- Ablations: hint vs no hint, policy-chosen vs random neighbourhoods, neighbourhood size.

## Common pitfalls

- Comparing a DRL method given minutes of GPU inference with CP-SAT given seconds.
- Reporting CP-SAT "OPTIMAL" from a fixed-hint run as if the policy were optimal.
- Training reward computed by an approximate simulator but evaluation by the exact model
  (or the reverse) without saying so.
- Tuning on the test instances.

## Where to look further

- OR-Tools documentation: https://developers.google.com/optimization/cp/cp_solver
- CP-SAT primer (community guide by D. Krupke): https://d-krupke.github.io/cpsat-primer/
