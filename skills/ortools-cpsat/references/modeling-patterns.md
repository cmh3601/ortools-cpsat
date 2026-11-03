# CP-SAT modelling patterns (snake_case API, ortools >= 9.10)

```python
from ortools.sat.python import cp_model
m = cp_model.CpModel()
```

## Variables

| Need | Call |
|---|---|
| Integer in [lb, ub] | `x = m.new_int_var(lb, ub, "x")` |
| Boolean | `b = m.new_bool_var("b")` |
| Constant | `m.new_constant(5)` |
| Task with start/size/end | `iv = m.new_interval_var(s, size, e, "iv")` (size may be a variable or expression) |
| Fixed-size task | `m.new_fixed_size_interval_var(s, 4, "iv")` |
| Task that may not happen | `m.new_optional_interval_var(s, size, e, presence_bool, "iv")` |

## Scheduling

- Precedence: `m.add(s_next >= e_prev)`; with setup time `m.add(s_next >= e_prev + setup)`.
- Unary machine: `m.add_no_overlap([iv1, iv2, ...])`.
- Renewable resource of capacity C: `m.add_cumulative(intervals, demands, C)`.
- Alternative machines (flexible job shop): one optional interval per eligible machine,
  `m.add_exactly_one(presences)`, and link to a master start/end with
  `m.add(s_alt == s).only_enforce_if(p)`.
- Makespan: `m.add_max_equality(cmax, [last_end_of_each_job])`; `m.minimize(cmax)`.
- Total weighted tardiness: `t_j = m.new_int_var(0, H, ..)`;
  `m.add_max_equality(t_j, [0, e_j - due_j])`; minimise `sum(w_j * t_j)`.
- Sequence-dependent setups: `add_circuit` over a graph of tasks per machine with
  literals for arcs, or explicit pairwise disjunctions for small instances.
- Release dates / deadlines: put them in the start/end domains, not as soft penalties.

## Layout and packing

- Rectangles: x-intervals and y-intervals per item, `m.add_no_overlap_2d(xs, ys)`.
- Rotation: a boolean r, width `w0 + (h0 - w0) * r`, height `h0 + (w0 - h0) * r`.
- Clearance g: inflate each interval size by g and the floor by g.
- Obstacles: fixed intervals added to the same NoOverlap2D.
- Centroid distances without fractions: use doubled centroids `2x + w`.
- Rectilinear distance: `m.add_abs_equality(dx, cx_i - cx_j)` (same for y).
- Euclidean distance is not linear: use rectilinear, a piecewise-linear table via
  `add_element`, or squared distance with `add_multiplication_equality` (slow).
- Grid / slot assignment (QAP-like): booleans `a[i, k]`, `add_exactly_one` per
  department and per slot, distance via products of booleans; only small n.

## Logic and non-linear terms

- If-then: `m.add(x <= 5).only_enforce_if(b)` and `m.add(x > 5).only_enforce_if(~b)`.
- At most / exactly one: `m.add_at_most_one(bools)`, `m.add_exactly_one(bools)`.
- Max/min/abs: `add_max_equality`, `add_min_equality`, `add_abs_equality`.
- Product: `add_multiplication_equality(z, [x, y])`; division `add_division_equality`.
- Table lookup: `add_element(index, values, target)`; allowed tuples `add_allowed_assignments`.
- Automaton constraints over sequences (shift rules): `add_automaton`.

## Search guidance

- Hints: `m.add_hint(var, value)` for every variable you have a value for (complete hints
  help most). Clear with `m.clear_hints()`.
- Decision strategy (only after profiling): `m.add_decision_strategy(vars,
  cp_model.CHOOSE_LOWEST_MIN, cp_model.SELECT_MIN_VALUE)`; with multiple workers most
  workers ignore it.
- Infeasibility explanation: add assumption literals `m.add_assumptions(lits)`, enforce
  constraints with them, then read `solver.sufficient_assumptions_for_infeasibility()`.

## Classic heuristics worth having as baselines or hints

- Dispatching rules for job shops: SPT, LPT, MWKR (most work remaining), FIFO
  (`dispatch_schedule` in `jobshop_cpsat.py`).
- Johnson's rule is optimal for the two-machine flow shop F2||Cmax
  (Johnson, 1954, *Naval Research Logistics Quarterly*, 1(1), 61–68).
- Pairwise-exchange improvement (CRAFT-style) for layouts; a CP-SAT model with
  `--relax` on a few departments is a stronger neighbourhood move.
