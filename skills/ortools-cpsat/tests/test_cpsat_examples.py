"""Tests for the CP-SAT examples: known optimum, brute-force optimum, validators."""

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("ortools")
from ortools.sat.python import cp_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import jobshop_cpsat as js  # noqa: E402
import layout_cpsat as lay  # noqa: E402

FT06 = ROOT / "data" / "ft06.txt"


# --- job shop -------------------------------------------------------------------------------

def test_ft06_reaches_known_optimum_55():
    jobs = js.read_orlib(FT06)
    model, start, _ = js.build_model(jobs)
    solver, status = js.solve(model, time_limit=60, workers=8, seed=0)
    assert status == cp_model.OPTIMAL
    assert solver.objective_value == 55
    starts = [[solver.value(start[j, k]) for k in range(len(job))] for j, job in enumerate(jobs)]
    assert js.validate(jobs, starts) == 55


@pytest.mark.parametrize("rule", ["spt", "lpt", "mwkr", "fifo"])
def test_dispatch_rules_give_feasible_upper_bounds(rule):
    jobs = js.read_orlib(FT06)
    ms = js.validate(jobs, js.dispatch_schedule(jobs, rule))
    assert ms >= 55


def test_fixed_hint_reproduces_hint_makespan():
    jobs = js.read_orlib(FT06)
    hint = js.dispatch_schedule(jobs, "mwkr")
    model, _, _ = js.build_model(jobs, hint)
    solver, status = js.solve(model, time_limit=10, workers=1, fix_hint=True)
    assert status == cp_model.OPTIMAL
    assert solver.objective_value == js.validate(jobs, hint)


def test_validator_rejects_overlap_and_precedence():
    jobs = [[(0, 3), (1, 2)], [(0, 2), (1, 1)]]
    with pytest.raises(AssertionError):
        js.validate(jobs, [[0, 3], [1, 5]])  # both on machine 0 during [1, 3)
    with pytest.raises(AssertionError):
        js.validate(jobs, [[0, 1], [3, 5]])  # job 0 op 1 starts before op 0 ends


def test_deterministic_settings_repeat_exactly():
    jobs = js.read_orlib(FT06)
    runs = []
    for _ in range(2):
        model, start, _ = js.build_model(jobs)
        solver, _ = js.solve(model, time_limit=30, workers=1, seed=3, deterministic_time=5)
        runs.append([[solver.value(start[j, k]) for k in range(6)] for j in range(6)])
    assert runs[0] == runs[1]


# --- facility layout ------------------------------------------------------------------------

def brute_force(spec):
    W, H = spec["floor"]["width"], spec["floor"]["height"]
    options = []
    for f in spec["facilities"]:
        dims = {(f["w"], f["h"])} | ({(f["h"], f["w"])} if f.get("rotatable") else set())
        options.append([(x, y, w, h) for w, h in dims for x in range(W - w + 1) for y in range(H - h + 1)])
    best = None
    names = [f["name"] for f in spec["facilities"]]
    for combo in itertools.product(*options):
        placement = {n: {"x": x, "y": y, "w": w, "h": h, "rotated": False}
                     for n, (x, y, w, h) in zip(names, combo)}
        try:
            val = lay.validate(spec, placement)
        except AssertionError:
            continue
        best = val if best is None else min(best, val)
    return best


def solve_layout(spec, **kw):
    model, v = lay.build_model(spec, **kw)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_workers = 4
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    placement = lay.extract(solver, spec, v)
    val = lay.validate(spec, placement)
    assert solver.objective_value / 2 == pytest.approx(val)
    return val, placement


TINY = {
    "floor": {"width": 4, "height": 3},
    "facilities": [
        {"name": "A", "w": 2, "h": 1, "rotatable": True},
        {"name": "B", "w": 1, "h": 1},
        {"name": "C", "w": 1, "h": 2},
        {"name": "D", "w": 2, "h": 2},
    ],
    "flows": [[0, 1, 3], [1, 2, 2], [0, 2, 1], [2, 3, 4], [0, 3, 2]],
}


def test_tiny_layout_matches_brute_force_optimum():
    val, _ = solve_layout(TINY)
    assert val == pytest.approx(brute_force(TINY))


def test_tiny_layout_with_obstacle_and_separation_matches_brute_force():
    spec = dict(TINY, obstacles=[{"x": 1, "y": 1, "w": 1, "h": 1}], separate=[[0, 3, 2.5]])
    val, _ = solve_layout(spec)
    assert val == pytest.approx(brute_force(spec))


def test_example_layout_runs_and_validates(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "layout_cpsat.py"),
                          str(ROOT / "examples" / "layout_8.json"), "--time-limit", "5",
                          "--workers", "4", "--svg", str(tmp_path / "l.svg")],
                         check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    assert data["status"] in ("OPTIMAL", "FEASIBLE")
    assert data["objective"] == pytest.approx(data["validated_objective"])
    assert data["best_bound"] <= data["objective"] + 1e-9
    assert (tmp_path / "l.svg").read_text().startswith("<svg")


def test_relax_keeps_unfreed_departments_in_place():
    spec = TINY
    _, placement = solve_layout(spec)
    hint = {n: [p["x"], p["y"], int(p["w"] != spec["facilities"][i]["w"])]
            for i, (n, p) in enumerate(placement.items())}
    model, v = lay.build_model(spec, hint=hint, relax={"B"})
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    assert solver.solve(model) == cp_model.OPTIMAL
    new = lay.extract(solver, spec, v)
    for n in ("A", "C", "D"):
        assert (new[n]["x"], new[n]["y"]) == (placement[n]["x"], placement[n]["y"])
